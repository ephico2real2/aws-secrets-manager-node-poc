// The core of a local Amazon SNS: topics, subscriptions, Publish with the same
// validation SNS applies, and one "delivery" per subscription rendered the way
// that protocol would receive it (an email, an SMS, an HTTPS POST body).
// Nothing is sent anywhere: deliveries are kept for the sns-logger screen,
// with recipients masked (the full address never leaves the subscription).
import { randomUUID } from 'node:crypto';
import { maskEndpoint } from '../../../backend/src/alerts/recipients.js';
import { matches } from './event-pattern.js';

export class SnsError extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

// GSM 03.38 basic character set (plus the extension table, which costs 2 septets).
const GSM_BASIC = new Set([..."@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"]);
const GSM_EXT = new Set([...'^{}\\[~]|€\f']);

/** How an SMS is split: encoding, length in units, segments. */
export function smsSegments(text) {
  const chars = [...text];
  const gsm = chars.every((c) => GSM_BASIC.has(c) || GSM_EXT.has(c));
  if (gsm) {
    const units = chars.reduce((n, c) => n + (GSM_EXT.has(c) ? 2 : 1), 0);
    return { encoding: 'GSM-7', units, segments: units <= 160 ? 1 : Math.ceil(units / 153), bytes: Buffer.byteLength(text) };
  }
  const units = chars.reduce((n, c) => n + (c.codePointAt(0) > 0xffff ? 2 : 1), 0);
  return { encoding: 'UCS-2', units, segments: units <= 70 ? 1 : Math.ceil(units / 67), bytes: Buffer.byteLength(text) };
}

const E164 = /^\+[1-9]\d{6,14}$/;

export function createSns({ region = 'us-east-1', account = '000000000000', publicUrl = 'http://localhost:4575', maxDeliveries = 500, log = () => {} } = {}) {
  const topics = new Map(); // arn -> { arn, name, attributes, subs: [] }
  const deliveries = [];
  let seq = 0;

  const topicArn = (name) => `arn:aws:sns:${region}:${account}:${name}`;

  function createTopic(name, attributes = {}) {
    if (!/^[A-Za-z0-9_-]{1,256}(\.fifo)?$/.test(name ?? '')) throw new SnsError('InvalidParameter', 'Invalid parameter: Topic Name');
    const arn = topicArn(name);
    if (!topics.has(arn)) topics.set(arn, { arn, name, attributes: { DisplayName: '', ...attributes }, subs: [] });
    return topics.get(arn);
  }

  function topic(arn) {
    const t = topics.get(arn);
    if (!t) throw new SnsError('NotFound', 'Topic does not exist', 404);
    return t;
  }

  function subscribe(arn, protocol, endpoint, attributes = {}) {
    const t = topic(arn);
    if (!['email', 'email-json', 'sms', 'http', 'https'].includes(protocol)) {
      throw new SnsError('InvalidParameter', `Invalid parameter: Protocol (local sns-logger supports email, email-json, sms, http, https)`);
    }
    if ((protocol === 'email' || protocol === 'email-json') && !/^[^@\s]+@[^@\s]+$/.test(endpoint ?? '')) throw new SnsError('InvalidParameter', 'Invalid parameter: Email address');
    if (protocol === 'sms' && !E164.test(endpoint ?? '')) throw new SnsError('InvalidParameter', 'Invalid parameter: SMS endpoint (use E.164, e.g. +15555550100)');
    if (protocol.startsWith('http') && !/^https?:\/\//.test(endpoint ?? '')) throw new SnsError('InvalidParameter', 'Invalid parameter: Endpoint');
    let filterPolicy;
    if (attributes.FilterPolicy) {
      try {
        filterPolicy = JSON.parse(attributes.FilterPolicy);
        matches(filterPolicy, {}); // reject operators we don't support now, not at publish time
      } catch (err) {
        throw new SnsError('InvalidParameter', `Invalid parameter: FilterPolicy: ${err.message}`);
      }
    }
    const existing = t.subs.find((s) => s.protocol === protocol && s.endpoint === endpoint);
    if (existing) return existing;
    // Locally every subscription is confirmed at once (SNS would email or POST a confirmation link first).
    const sub = { arn: `${arn}:${randomUUID()}`, protocol, endpoint, confirmed: true, filterPolicy };
    t.subs.push(sub);
    log({ event: 'sns.subscription.created', topic: t.name, protocol, endpoint: maskEndpoint(protocol, endpoint), filterPolicy }, `subscribed ${protocol} to ${t.name}`);
    return sub;
  }

  function unsubscribe(subArn) {
    for (const t of topics.values()) {
      const i = t.subs.findIndex((s) => s.arn === subArn);
      if (i >= 0) {
        t.subs.splice(i, 1);
        return true;
      }
    }
    throw new SnsError('NotFound', 'Subscription does not exist', 404);
  }

  function validate({ Message, Subject, MessageStructure }) {
    if (typeof Message !== 'string' || Message === '') throw new SnsError('InvalidParameter', 'Invalid parameter: Message');
    if (Buffer.byteLength(Message) > 262144) throw new SnsError('InvalidParameter', 'Invalid parameter: Message too long');
    if (Subject !== undefined) {
      if (Subject.length === 0 || Subject.length >= 100) throw new SnsError('InvalidParameter', 'Invalid parameter: Subject');
      if (/[\u0000-\u001f\u007f]/.test(Subject)) throw new SnsError('InvalidParameter', 'Invalid parameter: Subject (no line breaks or control characters)');
    }
    if (MessageStructure === undefined) return { default: Message };
    if (MessageStructure !== 'json') throw new SnsError('InvalidParameter', 'Invalid parameter: MessageStructure');
    let parsed;
    try {
      parsed = JSON.parse(Message);
    } catch {
      throw new SnsError('InvalidParameter', 'Invalid parameter: Message Structure - JSON message body failed to parse');
    }
    if (!parsed || typeof parsed.default !== 'string') throw new SnsError('InvalidParameter', 'Invalid parameter: Message Structure - No default entry in JSON message body');
    for (const [k, v] of Object.entries(parsed)) {
      if (typeof v !== 'string') throw new SnsError('InvalidParameter', `Invalid parameter: Message Structure - ${k} must be a string`);
    }
    return parsed;
  }

  function record(d) {
    d.seq = ++seq;
    deliveries.push(d);
    if (deliveries.length > maxDeliveries) deliveries.shift();
    const extra = d.protocol === 'sms' ? { segments: d.sms.segments, encoding: d.sms.encoding } : {};
    log(
      { event: 'sns.delivery.sent', protocol: d.protocol, endpoint: d.toMasked, topic: d.topicName, messageId: d.messageId, publishedBy: d.publishedBy, subject: d.subject, ...extra },
      `delivered ${d.protocol} to ${d.toMasked}${d.topicName ? ` from ${d.topicName}` : ''}`,
    );
  }

  /**
   * Publish. `params` uses the API names: TopicArn | TargetArn | PhoneNumber,
   * Message, Subject, MessageStructure, MessageAttributes {Name: {DataType, StringValue}}.
   */
  function publish(params, { publishedBy = 'unknown' } = {}) {
    const bodies = validate(params);
    const messageId = randomUUID();
    const timestamp = new Date().toISOString();
    const attrs = params.MessageAttributes ?? {};
    const attr = (name) => attrs[name]?.StringValue;

    if (params.PhoneNumber) {
      if (!E164.test(params.PhoneNumber)) throw new SnsError('InvalidParameter', 'Invalid parameter: PhoneNumber Reason: must be E.164');
      const text = bodies.sms ?? bodies.default;
      if (Buffer.byteLength(text) > 1600) throw new SnsError('InvalidParameter', 'Invalid parameter: Message too long for SMS (1600 bytes)');
      record(smsDelivery({ to: params.PhoneNumber, text, messageId, timestamp, attr, publishedBy }));
      return { MessageId: messageId };
    }

    const arn = params.TopicArn ?? params.TargetArn;
    if (!arn) throw new SnsError('InvalidParameter', 'Invalid parameter: TopicArn or TargetArn Reason: no value for required parameter');
    const t = topic(arn);
    const unsubscribeUrl = (sub) => `${publicUrl}/unsubscribe?SubscriptionArn=${encodeURIComponent(sub.arn)}`;
    // Subscription filter policies match message attributes (FilterPolicyScope MessageAttributes).
    const attrValues = Object.fromEntries(Object.entries(attrs).map(([k, v]) => [k, v.DataType === 'Number' ? Number(v.StringValue) : v.StringValue]));
    for (const sub of t.subs.filter((s) => s.confirmed)) {
      if (sub.filterPolicy && !matches(sub.filterPolicy, attrValues)) {
        log({ event: 'sns.delivery.filtered', protocol: sub.protocol, endpoint: maskEndpoint(sub.protocol, sub.endpoint), topic: t.name, messageId }, `not delivered to ${sub.protocol}: the subscription's filter policy doesn't match`);
        continue;
      }
      const base = { messageId, timestamp, topicArn: t.arn, topicName: t.name, publishedBy, subscriptionArn: sub.arn };
      if (sub.protocol === 'email') {
        const from = `${t.attributes.DisplayName || 'AWS Notifications'} <no-reply@sns.amazonaws.com>`;
        const text = bodies.email ?? bodies.default;
        record({
          ...base,
          protocol: 'email',
          toMasked: maskEndpoint('email', sub.endpoint),
          from,
          subject: params.Subject ?? 'AWS Notification Message',
          body:
            `${text}\n\n--\nIf you wish to stop receiving notifications from this topic, please click or visit the link below to unsubscribe:\n` +
            `${unsubscribeUrl(sub)}\n\nPlease do not reply directly to this email. If you have any questions or comments regarding this email, please contact us at https://aws.amazon.com/support`,
        });
      } else if (sub.protocol === 'sms') {
        const text = bodies.sms ?? bodies.default;
        record({ ...smsDelivery({ to: sub.endpoint, text, messageId, timestamp, attr, publishedBy }), ...base, protocol: 'sms' });
      } else {
        const key = sub.protocol === 'email-json' ? 'email-json' : sub.protocol;
        const envelope = {
          Type: 'Notification',
          MessageId: messageId,
          TopicArn: t.arn,
          ...(params.Subject ? { Subject: params.Subject } : {}),
          Message: bodies[key] ?? bodies.default,
          Timestamp: timestamp,
          SignatureVersion: '2',
          Signature: '(local sns-logger: not signed)',
          SigningCertURL: '(local sns-logger)',
          UnsubscribeURL: unsubscribeUrl(sub),
          ...(Object.keys(attrs).length ? { MessageAttributes: Object.fromEntries(Object.entries(attrs).map(([k, v]) => [k, { Type: v.DataType, Value: v.StringValue }])) } : {}),
        };
        record({
          ...base,
          protocol: sub.protocol,
          toMasked: maskEndpoint(sub.protocol, sub.endpoint),
          subject: params.Subject,
          headers: { 'x-amz-sns-message-type': 'Notification', 'x-amz-sns-message-id': messageId, 'x-amz-sns-topic-arn': t.arn, 'x-amz-sns-subscription-arn': sub.arn },
          body: JSON.stringify(envelope, null, 2),
        });
      }
    }
    return { MessageId: messageId };
  }

  function smsDelivery({ to, text, messageId, timestamp, attr, publishedBy }) {
    return {
      protocol: 'sms',
      toMasked: maskEndpoint('sms', to),
      messageId,
      timestamp,
      publishedBy,
      body: text,
      sms: { ...smsSegments(text), senderId: attr('AWS.SNS.SMS.SenderID') ?? null, type: attr('AWS.SNS.SMS.SMSType') ?? 'Promotional' },
    };
  }

  return {
    createTopic,
    topic,
    topicArn,
    listTopics: () => [...topics.values()],
    setTopicAttribute(arn, name, value) {
      topic(arn).attributes[name] = value;
    },
    subscribe,
    unsubscribe,
    publish,
    deliveries: (since = 0) => deliveries.filter((d) => d.seq > since),
  };
}

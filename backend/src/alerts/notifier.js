// Notifications the app sends itself, through Amazon SNS.
//
// Alarms (something is wrong) go logs-first: the log line carries an `event`,
// and a rule on the log store raises the alert (CloudWatch alarm on AWS,
// vmalert locally). This module is for the app's own notifications (it
// switched to a rotated credential) and the "send a test alert" button, so
// nobody is paged twice for the same thing.
//
// One SNS Publish per notification with MessageStructure=json, so each
// subscriber gets a body written for it: email (full context), sms (one short
// line), https (an Amazon Q Developer custom notification for chat). Every
// body is passed through the redactor before it leaves the process.
import { randomUUID } from 'node:crypto';
import os from 'node:os';
import { NOTIFICATIONS, channelsFor, seconds } from './catalogue.js';

const SEVERITY_WORD = { critical: 'CRITICAL', warning: 'WARNING', info: 'INFO' };

/** Cut a UTF-8 string to at most `max` bytes without splitting a character. */
export function truncateBytes(s, max) {
  if (Buffer.byteLength(s) <= max) return s;
  let out = '';
  for (const ch of s) {
    if (Buffer.byteLength(`${out}${ch}…`) > max) break;
    out += ch;
  }
  return `${out}…`;
}

/** The three bodies and the subject for one notification. Exported for tests. */
export function composeMessage({ name, def, details = {}, app, environment, host, alertId, at = new Date(), runbookBase }) {
  const sev = SEVERITY_WORD[def.severity] ?? 'INFO';
  const subject = truncateBytes(`[${sev}] ${app} (${environment}): ${def.title}`.replace(/[\r\n\t]+/g, ' '), 99);
  const detailLines = Object.entries(details).map(([k, v]) => `  ${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`);
  const runbook = `${runbookBase}#${name.replace(/\./g, '')}`;
  const email = [
    `${def.title}.`,
    '',
    `What:     ${name} (${def.severity})`,
    `Where:    ${app} on ${host}, environment ${environment}`,
    `When:     ${at.toISOString()}`,
    ...(detailLines.length ? ['Details:', ...detailLines] : []),
    `Alert ID: ${alertId}`,
    '',
    `Runbook:  ${runbook}`,
  ].join('\n');
  const smsCore = `SecNotes ${environment} ${sev}: ${def.title}`;
  const firstDetail = Object.values(details).find((v) => typeof v === 'string');
  const sms = truncateBytes(`${smsCore}${firstDetail ? ` (${firstDetail})` : ''}. ID ${alertId.slice(0, 8)}`, 140);
  const chat = {
    version: '1.0',
    source: 'custom',
    id: alertId,
    content: {
      textType: 'client-markdown',
      title: `${sev === 'INFO' ? 'ℹ️' : sev === 'WARNING' ? '⚠️' : '🚨'} ${def.title}`,
      description: [`*${app}* · ${environment} · ${host}`, ...Object.entries(details).map(([k, v]) => `• ${k}: \`${typeof v === 'string' ? v : JSON.stringify(v)}\``)].join('\n'),
      nextSteps: [`Runbook: ${runbook}`],
      keywords: [name, def.severity, environment],
    },
    metadata: { threadId: name, summary: def.title, eventType: name, additionalContext: { severity: def.severity, alertId } },
  };
  return {
    subject,
    bodies: { default: email, email, sms, https: JSON.stringify(chat) },
  };
}

export function createNotifier({ config, logger, redactor, client, now = () => Date.now() }) {
  const log = logger.child({ component: 'alerts' });
  const topicArn = config.alerts.topicArn;
  const topicFor = (def) => (def.topic === 'chat' ? config.alerts.chatTopicArn ?? topicArn : topicArn);
  const last = new Map(); // dedup key -> time sent
  const stats = { sent: 0, suppressed: 0, failed: 0 };

  if (!topicArn) {
    log.info('notifications off: SNS_TOPIC_ARN is not set');
    return { enabled: false, notify: async () => undefined, retryAfterMs: () => 0, stats: () => ({ ...stats, enabled: false }) };
  }

  let sns = client;
  async function getClient() {
    if (sns) return sns;
    const { SNSClient } = await import('@aws-sdk/client-sns');
    sns = new SNSClient({ region: config.region, endpoint: config.alerts.endpoint });
    return sns;
  }

  /**
   * Send a catalogued notification. `details` must hold names and IDs only:
   * no field called secret/token (the redactor blanks those), never a value.
   */
  async function notify(name, details = {}, { dedupKey = name } = {}) {
    const def = NOTIFICATIONS[name];
    if (!def) throw new Error(`unknown notification ${name}`);
    const windowMs = (seconds(def.repeat) ?? 0) * 1000;
    const prev = last.get(dedupKey);
    if (windowMs && prev !== undefined && now() - prev < windowMs) {
      stats.suppressed++;
      log.info({ event: 'alerting.notification.suppressed', 'alert.name': name, 'alert.dedup_key': dedupKey, 'alert.repeat': def.repeat }, `notification suppressed: ${name} was sent less than ${def.repeat} ago`);
      return undefined;
    }
    if (windowMs) last.set(dedupKey, now()); // nothing to remember without a window

    const alertId = randomUUID();
    const { subject, bodies } = composeMessage({
      name, def, details, alertId,
      app: 'Secure Notes',
      environment: config.alerts.environment,
      host: os.hostname(),
      runbookBase: config.alerts.runbookBase,
    });
    // Defence in depth: nothing that looks like a loaded secret leaves in a notification.
    const safe = Object.fromEntries(Object.entries(bodies).map(([k, v]) => [k, redactor.scrubString(v)]));
    const smsSegments = Math.max(1, Math.ceil(Buffer.byteLength(safe.sms) / 140));
    const target = topicFor(def);
    const fields = {
      'messaging.system': 'aws.sns',
      'messaging.operation.type': 'send',
      'messaging.destination.name': target.split(':').pop(),
      'aws.sns.topic.arn': target,
      'alert.name': name,
      'alert.severity': def.severity,
      'alert.id': alertId,
      'alert.subject': subject,
      'alert.channels': channelsFor(def),
      'sms.segments': smsSegments,
    };
    try {
      const input = {
          TopicArn: target,
          Subject: subject,
          MessageStructure: 'json',
          Message: JSON.stringify(safe),
          MessageAttributes: {
            'AWS.SNS.SMS.SenderID': { DataType: 'String', StringValue: config.alerts.senderId },
            'AWS.SNS.SMS.SMSType': { DataType: 'String', StringValue: 'Transactional' },
            severity: { DataType: 'String', StringValue: def.severity },
            'alert.name': { DataType: 'String', StringValue: name },
          },
      };
      // A test can pass its own client; otherwise the AWS SDK (loaded on first use).
      const out = client
        ? await client.send({ input })
        : await (await getClient()).send(new (await import('@aws-sdk/client-sns')).PublishCommand(input));
      stats.sent++;
      log.info({ event: 'alerting.notification.sent', ...fields, 'messaging.message.id': out.MessageId }, `notification sent: ${subject}`);
      return out.MessageId;
    } catch (err) {
      stats.failed++;
      last.delete(dedupKey);
      log.warn({ event: 'alerting.notification.failed', ...fields, err }, `notification failed: ${name}`);
      return undefined;
    }
  }

  /** Milliseconds until `name` may be sent again for this key (0: now). */
  function retryAfterMs(name, dedupKey = name) {
    const def = NOTIFICATIONS[name];
    const windowMs = (seconds(def?.repeat) ?? 0) * 1000;
    const prev = last.get(dedupKey);
    return windowMs && prev !== undefined ? Math.max(0, windowMs - (now() - prev)) : 0;
  }

  return { enabled: true, notify, retryAfterMs, stats: () => ({ ...stats, enabled: true, topic: topicArn.split(':').pop() }) };
}

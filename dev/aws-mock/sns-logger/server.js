#!/usr/bin/env node
// DEV-ONLY: sns-logger, a local Amazon SNS with a screen.
//
// The app, Alertmanager and the aws-mock's EventBridge simulation publish to it
// exactly as they would publish to SNS (AWS Query protocol: Action=Publish...).
// Nothing is delivered anywhere: each subscription's delivery is rendered on
// http://localhost:4575 as an email, an SMS or an HTTPS POST body, and logged
// as one JSON line with the recipient masked.
//
// Env:
//   PORT=4575  HOST=0.0.0.0  AWS_REGION=us-east-1
//   SNS_LOGGER_PUBLIC_URL=http://localhost:4575     (links in emails)
//   SNS_LOGGER_TOPICS="name=Display name,..."       (created at start)
//   SNS_LOGGER_SUBSCRIPTIONS="topic|*:protocol:endpoint[ filterPolicyJSON];..."
//   VICTORIALOGS_URL, VMALERT_URL                   (optional: the Pipeline tab)
//   LOG_OTLP_ENDPOINT                               (optional: ship its own log lines)
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createSns, SnsError } from '../lib/sns.js';
import { parseForm, queryMap, queryKeyValues, xmlEscape, xmlUnescape, xmlResponse, xmlError } from '../lib/aws-query.js';
import { principalOf } from '../lib/principals.js';
import { createOtlpShipper } from '../../../backend/src/logship/otlp.js';
import { maskEndpoint } from '../../../backend/src/alerts/recipients.js';

const PORT = Number(process.env.PORT ?? 4575);
const HOST = process.env.HOST ?? '0.0.0.0';
const REGION = process.env.AWS_REGION ?? 'us-east-1';
const PUBLIC_URL = process.env.SNS_LOGGER_PUBLIC_URL ?? `http://localhost:${PORT}`;
const VICTORIALOGS_URL = process.env.VICTORIALOGS_URL;
const VMALERT_URL = process.env.VMALERT_URL;
const here = path.dirname(fileURLToPath(import.meta.url));

// ------------------------------------------------------------------ logs ----
const shipper = process.env.LOG_OTLP_ENDPOINT
  ? createOtlpShipper({ endpoint: process.env.LOG_OTLP_ENDPOINT, resource: { 'service.name': 'sns-logger', 'deployment.environment.name': 'local' } })
  : undefined;
function log(fields, msg, level = 'info') {
  const line = JSON.stringify({ time: new Date().toISOString(), level, app: 'sns-logger', ...fields, msg });
  process.stdout.write(`${line}\n`);
  shipper?.write(line);
}

// ------------------------------------------------------------------- SNS ----
const sns = createSns({ region: REGION, publicUrl: PUBLIC_URL, log });

for (const spec of (process.env.SNS_LOGGER_TOPICS ?? '').split(',').map((s) => s.trim()).filter(Boolean)) {
  const [name, display = ''] = spec.split('=');
  sns.createTopic(name.trim(), { DisplayName: display.trim() });
}
// "topic:protocol:endpoint" or "topic:protocol:endpoint {filter policy JSON}", separated by ";"
for (const spec of (process.env.SNS_LOGGER_SUBSCRIPTIONS ?? '').split(';').map((s) => s.trim()).filter(Boolean)) {
  const space = spec.indexOf(' ');
  const head = space < 0 ? spec : spec.slice(0, space);
  const filter = space < 0 ? undefined : spec.slice(space + 1).trim();
  const [where, protocol, ...rest] = head.split(':');
  const endpoint = rest.join(':');
  for (const t of sns.listTopics()) {
    if (where === '*' || where === t.name) sns.subscribe(t.arn, protocol, endpoint, filter ? { FilterPolicy: filter } : {});
  }
}

// Endpoints are masked here too: recipients never leave this process in full.
const subXml = (s, topicArn) =>
  `<member><SubscriptionArn>${xmlEscape(s.arn)}</SubscriptionArn><Owner>000000000000</Owner><Protocol>${xmlEscape(s.protocol)}</Protocol><Endpoint>${xmlEscape(maskEndpoint(s.protocol, s.endpoint))}</Endpoint><TopicArn>${xmlEscape(topicArn)}</TopicArn></member>`;

/** One SNS action. `p` holds Query-style parameters. Returns the inner XML of <ActionResult>. */
function action(name, p, caller) {
  switch (name) {
    case 'CreateTopic': {
      const t = sns.createTopic(p.Name, queryKeyValues(p, 'Attributes'));
      return `<TopicArn>${xmlEscape(t.arn)}</TopicArn>`;
    }
    case 'ListTopics':
      return `<Topics>${sns.listTopics().map((t) => `<member><TopicArn>${xmlEscape(t.arn)}</TopicArn></member>`).join('')}</Topics>`;
    case 'GetTopicAttributes': {
      const t = sns.topic(p.TopicArn);
      const attrs = { ...t.attributes, TopicArn: t.arn, Owner: '000000000000', SubscriptionsConfirmed: String(t.subs.length), SubscriptionsPending: '0' };
      return `<Attributes>${Object.entries(attrs).map(([k, v]) => `<entry><key>${xmlEscape(k)}</key><value>${xmlEscape(v)}</value></entry>`).join('')}</Attributes>`;
    }
    case 'SetTopicAttributes':
      sns.setTopicAttribute(p.TopicArn, p.AttributeName, p.AttributeValue ?? '');
      return '';
    case 'Subscribe': {
      const s = sns.subscribe(p.TopicArn, p.Protocol, p.Endpoint, queryKeyValues(p, 'Attributes'));
      return `<SubscriptionArn>${xmlEscape(s.arn)}</SubscriptionArn>`;
    }
    case 'ConfirmSubscription':
      return `<SubscriptionArn>${xmlEscape(sns.topic(p.TopicArn).subs[0]?.arn ?? '')}</SubscriptionArn>`;
    case 'Unsubscribe':
      sns.unsubscribe(p.SubscriptionArn);
      return '';
    case 'ListSubscriptions':
      return `<Subscriptions>${sns.listTopics().flatMap((t) => t.subs.map((s) => subXml(s, t.arn))).join('')}</Subscriptions>`;
    case 'ListSubscriptionsByTopic': {
      const t = sns.topic(p.TopicArn);
      return `<Subscriptions>${t.subs.map((s) => subXml(s, t.arn)).join('')}</Subscriptions>`;
    }
    case 'Publish': {
      const { MessageId } = sns.publish(
        {
          TopicArn: p.TopicArn,
          TargetArn: p.TargetArn,
          PhoneNumber: p.PhoneNumber,
          Message: p.Message,
          Subject: p.Subject,
          MessageStructure: p.MessageStructure,
          MessageAttributes: queryMap(p, 'MessageAttributes'),
        },
        { publishedBy: caller.arn ?? caller.invokedBy },
      );
      return `<MessageId>${MessageId}</MessageId>`;
    }
    default:
      throw new SnsError('InvalidAction', `The action ${name} is not valid for this endpoint (local sns-logger).`);
  }
}

// ---------------------------------------------------------------- server ----
const SECURITY_HEADERS = {
  'Content-Security-Policy':
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cross-Origin-Resource-Policy': 'same-origin',
};
const STATIC = {
  '/': ['ui/index.html', 'text/html; charset=utf-8'],
  '/ui.js': ['ui/ui.js', 'text/javascript; charset=utf-8'],
  '/sns.css': ['ui/sns.css', 'text/css; charset=utf-8'],
  // the dashboard's stylesheet, so both screens look alike (copied into the image)
  '/styles.css': [path.resolve(here, '../../../frontend/styles.css'), 'text/css; charset=utf-8'],
};

async function readBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}

async function pipeline() {
  if (!VICTORIALOGS_URL) return { deployed: false };
  const out = { deployed: true, logs: [], alerts: [], errors: [] };
  try {
    const q = encodeURIComponent('_time:15m | sort by (_time desc) | limit 80');
    const res = await fetch(`${VICTORIALOGS_URL}/select/logsql/query?query=${q}`, { signal: AbortSignal.timeout(3000) });
    const text = await res.text();
    out.logs = text.split('\n').filter(Boolean).map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return { _msg: l };
      }
    });
  } catch (err) {
    out.errors.push(`VictoriaLogs: ${err.message}`);
  }
  if (VMALERT_URL) {
    try {
      const res = await fetch(`${VMALERT_URL}/api/v1/alerts`, { signal: AbortSignal.timeout(3000) });
      out.alerts = ((await res.json()).data?.alerts ?? []).map((a) => ({ name: a.name, state: a.state, activeAt: a.activeAt, value: a.value }));
    } catch (err) {
      out.errors.push(`vmalert: ${err.message}`);
    }
  }
  return out;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const requestId = randomUUID();
  // Every response carries the security headers, API answers included.
  const send = (status, body, type) => {
    res.writeHead(status, { 'Content-Type': type, 'x-amzn-RequestId': requestId, ...SECURITY_HEADERS });
    res.end(body);
  };
  const json = (status, obj) => send(status, JSON.stringify(obj), 'application/json');

  try {
    if (req.method === 'GET') {
      if (url.pathname === '/health') return json(200, { status: 'running', topics: sns.listTopics().length });
      if (url.pathname === '/_sns/deliveries') return json(200, { deliveries: sns.deliveries(Number(url.searchParams.get('since') ?? 0)) });
      if (url.pathname === '/_sns/topics') {
        return json(200, {
          topics: sns.listTopics().map((t) => ({ arn: t.arn, name: t.name, displayName: t.attributes.DisplayName, subscriptions: t.subs.map((s) => ({ protocol: s.protocol, endpoint: maskEndpoint(s.protocol, s.endpoint), filterPolicy: s.filterPolicy })) })),
        });
      }
      if (url.pathname === '/_sns/pipeline') return json(200, await pipeline());
      if (url.pathname === '/_sns/export') {
        return send(200, sns.deliveries(0).map((d) => JSON.stringify(d)).join('\n'), 'application/x-ndjson');
      }
      if (url.pathname === '/unsubscribe') {
        const arn = url.searchParams.get('SubscriptionArn') ?? '';
        let ok = true;
        try {
          sns.unsubscribe(arn);
        } catch {
          ok = false;
        }
        return send(200, `<!doctype html><title>Unsubscribe</title><p>${ok ? 'Subscription removed (local sns-logger).' : 'No such subscription.'}</p><p><a href="/">Back</a></p>`, 'text/html; charset=utf-8');
      }
      const file = STATIC[url.pathname];
      if (file) return send(200, readFileSync(path.resolve(here, file[0])), file[1]);
      return json(404, { message: 'not found' });
    }

    if (req.method !== 'POST') return json(405, { message: 'method not allowed' });
    // Only API clients may call the API: SDKs and Alertmanager sign their
    // requests and send no Origin. A web page can't sign, and a browser always
    // sends Origin on a cross-site POST, so a malicious page can't drive this
    // console (create topics, read subscriptions) from the reader's browser.
    if (req.headers.origin || !String(req.headers.authorization ?? '').startsWith('AWS4-HMAC-SHA256 ')) {
      return send(403, xmlError({ code: 'AccessDenied', message: 'Requests must be signed (SigV4) and must not come from a browser page.', requestId }), 'text/xml');
    }
    const caller = principalOf(req.headers);
    const body = await readBody(req);
    const target = req.headers['x-amz-target'] ?? '';
    let name;
    let params;
    const isJson = target.startsWith('AmazonSimpleNotificationService.');
    if (isJson) {
      name = target.split('.')[1];
      params = body ? JSON.parse(body) : {};
      params = { ...params };
      // JSON maps -> the Query protocol's entry.N form, so one code path serves both.
      for (const key of ['Attributes']) {
        if (params[key] && typeof params[key] === 'object') {
          Object.entries(params[key]).forEach(([k, v], i) => {
            params[`${key}.entry.${i + 1}.key`] = k;
            params[`${key}.entry.${i + 1}.value`] = String(v);
          });
          delete params[key];
        }
      }
      if (params.MessageAttributes) {
        const attrs = params.MessageAttributes;
        delete params.MessageAttributes;
        Object.entries(attrs).forEach(([k, v], i) => {
          params[`MessageAttributes.entry.${i + 1}.Name`] = k;
          params[`MessageAttributes.entry.${i + 1}.Value.DataType`] = v.DataType;
          params[`MessageAttributes.entry.${i + 1}.Value.StringValue`] = v.StringValue;
        });
      }
    } else {
      params = parseForm(body);
      name = params.Action;
    }
    try {
      const inner = action(name, params, caller);
      if (isJson) return send(200, JSON.stringify(Object.fromEntries([...inner.matchAll(/<(\w+)>([^<]*)<\/\1>/g)].map((m) => [m[1], xmlUnescape(m[2])]))), 'application/x-amz-json-1.0');
      return send(200, xmlResponse(name, inner, requestId), 'text/xml');
    } catch (err) {
      if (!(err instanceof SnsError)) throw err;
      log({ event: 'sns.request.rejected', action: name, code: err.code, caller: caller.arn ?? caller.invokedBy }, err.message, 'warn');
      if (isJson) return send(err.status, JSON.stringify({ __type: err.code, message: err.message }), 'application/x-amz-json-1.0');
      return send(err.status, xmlError({ code: err.code, message: err.message, requestId }), 'text/xml');
    }
  } catch (err) {
    log({ event: 'sns.request.failed', err: { name: err.name, message: err.message } }, 'request failed', 'error');
    return json(500, { message: 'internal error' });
  }
});

server.listen(PORT, HOST, () =>
  log({ topics: sns.listTopics().map((t) => t.name), pipeline: Boolean(VICTORIALOGS_URL) }, `sns-logger: a local Amazon SNS on http://${HOST}:${PORT} (screen: ${PUBLIC_URL})`),
);

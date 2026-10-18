// Structured logs: the OTLP shipper only ever sees redacted lines, the pretty
// format, recipient masks, and every event name used in the code is catalogued.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Redactor } from '../src/secrets/redactor.js';
import { createLogger } from '../src/log.js';
import { createOtlpShipper, toLogRecord } from '../src/logship/otlp.js';
import { prettyLine } from '../src/logfmt.js';
import { maskEmail, maskPhone, maskEndpoint } from '../src/alerts/recipients.js';
import { ALL_EVENTS, ALERTS, PATTERN_ALERTS, seconds } from '../src/alerts/catalogue.js';

const SECRET_VALUE = 'Xq7RtY2pLm9WvB4nKs8DhF3jGc6ZeA1u';

function captureSink() {
  const lines = [];
  return { lines, write: (l) => lines.push(l) };
}

test('sinks get the redacted line, never a revealed one', () => {
  const redactor = new Redactor();
  redactor.register(SECRET_VALUE);
  const sink = captureSink();
  const out = captureSink();
  const logger = createLogger({ redactor, level: 'debug', revealSecrets: true, out, sinks: [sink] });
  logger.error({ event: 'secrets.fetch.failed' }, `boom with ${SECRET_VALUE} inside`);
  logger.revealUnsafe({ password: SECRET_VALUE }, 'lab line');
  assert.equal(sink.lines.length, 1, 'only the normal line reaches the sink');
  assert.ok(!sink.lines[0].includes(SECRET_VALUE));
  assert.match(sink.lines[0], /\[REDACTED\]/);
  assert.ok(out.lines[1].includes(SECRET_VALUE), 'the revealed line is on stdout only');
});

test('OTLP mapping: severity, event name, flattened attributes, fatal', () => {
  const rec = toLogRecord(JSON.stringify({
    time: '2026-10-18T13:00:00.123Z', level: 'warn', app: 'secure-notes', component: 'secrets',
    secretId: '/rds/dev/notes-db/app', err: { name: 'TimeoutError', code: 'ETIMEDOUT' }, keys: ['a', 'b'],
    event: 'secrets.fetch.stale', msg: 'secret fetch failed, serving last good value',
  }));
  assert.equal(rec.severityNumber, 13);
  assert.equal(rec.severityText, 'WARN');
  assert.equal(rec.timeUnixNano, '1792328400123000000');
  assert.equal(rec.eventName, 'secrets.fetch.stale');
  assert.deepEqual(rec.body, { stringValue: 'secret fetch failed, serving last good value' });
  const attrs = Object.fromEntries(rec.attributes.map((a) => [a.key, a.value]));
  assert.deepEqual(attrs['err.code'], { stringValue: 'ETIMEDOUT' });
  assert.deepEqual(attrs.keys, { stringValue: '["a","b"]' });
  assert.equal(attrs.msg, undefined);
  const fatal = toLogRecord(JSON.stringify({ time: '2026-10-18T13:00:00Z', level: 'error', fatal: true, msg: 'x' }));
  assert.equal(fatal.severityNumber, 21);
});

test('shipper batches, keeps the newest when full, and retries a failed batch', async () => {
  const bodies = [];
  let fail = true;
  const fetchImpl = async (_url, init) => {
    if (fail) return { ok: false, status: 503 };
    bodies.push(JSON.parse(init.body));
    return { ok: true, status: 200 };
  };
  const shipper = createOtlpShipper({ endpoint: 'http://collector:4318/', maxBuffer: 3, intervalMs: 60_000, fetchImpl, resource: { 'service.name': 'secure-notes' } });
  for (let i = 0; i < 5; i++) shipper.write(JSON.stringify({ time: '2026-10-18T13:00:00Z', level: 'info', msg: `line ${i}` }));
  assert.equal(shipper.stats().buffered, 3);
  await shipper.flush();
  assert.equal(shipper.stats().failedBatches, 1);
  assert.equal(shipper.stats().buffered, 3, 'a failed batch goes back');
  fail = false;
  await shipper.drain(1000);
  shipper.close();
  const records = bodies.flatMap((b) => b.resourceLogs[0].scopeLogs[0].logRecords);
  assert.deepEqual(records.map((r) => r.body.stringValue), ['line 2', 'line 3', 'line 4']);
  assert.equal(bodies[0].resourceLogs[0].resource.attributes[0].key, 'service.name');
  assert.equal(shipper.stats().endpoint, 'http://collector:4318/v1/logs');
});

test('pretty format: one readable line', () => {
  const line = prettyLine({
    time: '2026-10-18T08:21:04.123Z', level: 'warn', app: 'secure-notes', component: 'secrets',
    secretId: '/rds/dev/notes-db/app', event: 'secrets.fetch.stale', msg: 'secret fetch failed, serving last good value',
  });
  assert.equal(line, '08:21:04.123 WARN  secrets  secret fetch failed, serving last good value · secretId=/rds/dev/notes-db/app event=secrets.fetch.stale');
});

test('recipients are masked', () => {
  assert.equal(maskEmail('oncall@example.com'), 'on****@example.com');
  assert.equal(maskEmail('a@example.com'), 'a*@example.com');
  assert.equal(maskPhone('+15555550100'), '+1******0100');
  assert.equal(maskEndpoint('https', 'https://chat.example.com/hooks/abc?key=1'), 'https://chat.example.com/…');
  assert.equal(maskEndpoint('sqs', 'arn:aws:sqs:…'), '***');
});

test('every event name used in the code is in the catalogue', () => {
  const src = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
  const files = [];
  const walk = (d) => readdirSync(d).forEach((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : f.endsWith('.js') && files.push(join(d, f))));
  walk(src);
  const used = new Set();
  for (const f of files) {
    if (f.endsWith('catalogue.js')) continue;
    const text = readFileSync(f, 'utf8');
    for (const m of text.matchAll(/event(?:Name)?\s*[:=]\s*(?:[^'"\n]*\?\s*)?'([a-z]+(?:\.[a-z]+)+)'(?:\s*:\s*'([a-z]+(?:\.[a-z]+)+)')?/g)) {
      used.add(m[1]);
      if (m[2]) used.add(m[2]);
    }
  }
  assert.ok(used.size >= 10, `found ${used.size} event names`);
  const unknown = [...used].filter((e) => !ALL_EVENTS.has(e));
  assert.deepEqual(unknown, []);
  for (const a of [...Object.values(ALERTS), ...Object.values(PATTERN_ALERTS)]) {
    assert.ok(seconds(a.when.window), `window ${a.when.window}`);
    assert.ok(a.title.length < 80, a.title);
  }
});

test('notification bodies: subject rules, SMS within 140 bytes, chat card, no secret', async () => {
  const { composeMessage, truncateBytes } = await import('../src/alerts/notifier.js');
  const { NOTIFICATIONS } = await import('../src/alerts/catalogue.js');
  const m = composeMessage({
    name: 'credential.rotated', def: NOTIFICATIONS['credential.rotated'],
    details: { secretName: '/rds/dev/notes-db/app', version: '1a2b3c4d', trigger: 'db-auth-failure' },
    app: 'Secure Notes', environment: 'dev', host: 'ip-10-0-0-5', alertId: '0f8fad5b-d9cb-469f-a165-70867728950e',
    at: new Date('2026-10-18T13:00:00Z'), runbookBase: 'https://example.com/alerts.md',
  });
  assert.equal(m.subject, '[INFO] Secure Notes (dev): The app switched to a rotated credential');
  assert.ok(m.subject.length < 100 && !/[\r\n]/.test(m.subject));
  assert.ok(Buffer.byteLength(m.bodies.sms) <= 140, m.bodies.sms);
  assert.match(m.bodies.email, /Runbook:  https:\/\/example\.com\/alerts\.md#credentialrotated/);
  const chat = JSON.parse(m.bodies.https);
  assert.equal(chat.source, 'custom');
  assert.equal(chat.metadata.additionalContext.severity, 'info');
  assert.equal(typeof m.bodies.default, 'string');
  assert.equal(truncateBytes('ééé', 5), 'é…');
});

test('notifier: dedup within the repeat window, redacted bodies, an alert-sent log line', async () => {
  const { createNotifier } = await import('../src/alerts/notifier.js');
  const redactor = new Redactor();
  redactor.register(SECRET_VALUE);
  const out = captureSink();
  const logger = createLogger({ redactor, level: 'debug', out });
  const sent = [];
  const client = { send: async (cmd) => (sent.push(cmd.input), { MessageId: `m-${sent.length}` }) };
  let t = 0;
  const notifier = createNotifier({
    config: { region: 'us-east-1', alerts: { topicArn: 'arn:aws:sns:us-east-1:000000000000:ops', senderId: 'SECNOTES', environment: 'dev', runbookBase: 'x' } },
    logger, redactor, client, now: () => t,
  });
  assert.equal(await notifier.notify('credential.rotated', { secretName: `oops ${SECRET_VALUE}` }), 'm-1');
  assert.equal(await notifier.notify('credential.rotated', {}), undefined, 'suppressed within 10 minutes');
  t = 11 * 60 * 1000;
  assert.equal(await notifier.notify('credential.rotated', {}), 'm-2');
  assert.ok(!sent[0].Message.includes(SECRET_VALUE), 'a registered value never leaves in a notification');
  assert.equal(sent[0].MessageStructure, 'json');
  assert.equal(sent[0].MessageAttributes.severity.StringValue, 'info');
  const lines = out.lines.map((l) => JSON.parse(l));
  const sentLine = lines.find((l) => l.event === 'alerting.notification.sent');
  assert.equal(sentLine['messaging.message.id'], 'm-1');
  assert.equal(sentLine['messaging.system'], 'aws.sns');
  assert.ok(lines.some((l) => l.event === 'alerting.notification.suppressed'));
});

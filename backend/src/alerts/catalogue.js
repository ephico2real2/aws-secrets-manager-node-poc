// The alert catalogue: every event name the app logs on purpose, and which of
// them raise an alert. It is the single source for:
//   - the `event` field at each call site (a test fails on an unknown name),
//   - the local alert rules (vmalert on VictoriaLogs),
//   - the AWS alarms (CloudWatch Logs metric filters + alarms),
//   - the alert table in docs/reference/alerts.md.
// scripts/sync-alert-rules.js generates the last three; CI checks they're current.
//
// Field names avoid "secret" and "token": the log redactor blanks those keys.

/**
 * @typedef {object} Alert
 * @property {'critical'|'warning'|'info'} severity
 * @property {string} title       one line, used as the email subject (< 100 chars with the prefix)
 * @property {string} source      where it is logged
 * @property {string[]} channels  email | sms | chat
 * @property {{count: number, window: string}} when  fire when at least `count` lines in `window`
 * @property {string} repeat      do not re-notify more often than this
 * @property {string} action      what on-call should do first
 */

/**
 * Events that raise an alert (logs first: a rule on the log store, then SNS).
 * Routing by severity, the same locally and on AWS:
 *   critical -> the alerts topic (email, SMS, chat)
 *   warning  -> the chat topic (chat only)
 */
export const ALERTS = Object.freeze({
  'config.unsafe': {
    severity: 'critical',
    title: 'App refused to start: unsafe configuration',
    source: 'server.js (exit 78)',
    channels: ['email', 'chat'],
    when: { count: 1, window: '5m' },
    repeat: '4h',
    action: 'Read the log line: it lists each problem (a credential in the environment, a missing secret name, a lab flag in production). Fix the unit or ConfigMap and restart.',
  },
  'secrets.load.fatal': {
    severity: 'critical',
    title: 'App could not load its credentials and exited',
    source: 'server.js (exit 1)',
    channels: ['email', 'sms', 'chat'],
    when: { count: 1, window: '5m' },
    repeat: '1h',
    action: 'Check the role can reach Secrets Manager (VPC endpoint, IAM, KMS) and that the secret names resolve. The app is down until it can read them.',
  },
  'secrets.fetch.failed': {
    severity: 'critical',
    title: 'A credential could not be read from Secrets Manager',
    source: 'secrets/provider.js',
    channels: ['email', 'sms', 'chat'],
    when: { count: 1, window: '5m' },
    repeat: '1h',
    action: 'The app has no cached value to fall back on. Check IAM, the VPC endpoint, KMS and the secret name in the log line.',
  },
  'secrets.fetch.stale': {
    severity: 'warning',
    title: 'Serving a cached credential: Secrets Manager unreachable',
    source: 'secrets/provider.js',
    channels: ['chat'],
    when: { count: 3, window: '10m' },
    repeat: '1h',
    action: 'The app keeps working on the last good value for up to SECRET_MAX_STALE_SECONDS. Find out why refreshes fail before that runs out.',
  },
  'agent.forbidden': {
    severity: 'critical',
    title: 'The local credentials agent refused the app',
    source: 'secrets/provider.js (agent mode)',
    channels: ['email', 'chat'],
    when: { count: 1, window: '5m' },
    repeat: '1h',
    action: 'The agent answered 403: the app is not sending its SSRF token, or the token file is unreadable. Check the token file and group membership.',
  },
  'db.auth.rejected': {
    severity: 'warning',
    title: 'Postgres rejected the cached password',
    source: 'clients/db.js',
    channels: ['chat'],
    when: { count: 3, window: '5m' },
    repeat: '30m',
    action: 'Usually a rotation the app recovers from by itself (look for db.auth.recovered). Repeated rejections mean the secret and the database disagree.',
  },
  'cache.auth.rejected': {
    severity: 'warning',
    title: 'Redis rejected the cached password',
    source: 'clients/cache.js',
    channels: ['chat'],
    when: { count: 3, window: '5m' },
    repeat: '30m',
    action: 'Usually a rotation the app recovers from by itself (look for cache.auth.recovered). Repeated rejections mean the secret and the Redis user disagree.',
  },
  'cache.refresh.failed': {
    severity: 'critical',
    title: 'Redis credential refresh failed',
    source: 'clients/cache.js',
    channels: ['email', 'chat'],
    when: { count: 1, window: '5m' },
    repeat: '1h',
    action: 'Redis rejected the password and the app could not read a new one. Check Secrets Manager access and the rotation function.',
  },
  'secrets.reveal.enabled': {
    severity: 'warning',
    title: 'Secret values are being written to the log (lab flag on)',
    source: 'server.js',
    channels: ['chat'],
    when: { count: 1, window: '5m' },
    repeat: '24h',
    action: 'LOG_REVEAL_SECRETS=true is for labs. Turn it off and treat the values in this log as exposed.',
  },
  'rotation.demo.failed': {
    severity: 'warning',
    title: 'A demo rotation failed',
    source: 'demo/rotator.js',
    channels: ['chat'],
    when: { count: 1, window: '5m' },
    repeat: '10m',
    action: 'Demo only. The log line names the step that failed.',
  },
});

/**
 * Alerts that come from a log-level pattern, not from an event name.
 * `match` is a LogsQL filter (local) and a CloudWatch Logs filter pattern (AWS).
 */
export const PATTERN_ALERTS = Object.freeze({
  'app.errors.burst': {
    severity: 'warning',
    title: 'Burst of errors in the app log',
    source: 'any error line (the leak test\'s "simulated:" lines excluded)',
    channels: ['chat'],
    when: { count: 5, window: '5m' },
    repeat: '1h',
    action: 'Look at the error lines in the log store for the same five minutes.',
    logsql: 'level:=error -_msg:"simulated:"*',
    cloudwatch: '{ ($.level = "error") && ($.msg != "simulated:*") }',
  },
});

/** Raised by AWS (CloudTrail -> EventBridge), and locally by the aws-mock. */
export const PLATFORM_ALERTS = Object.freeze({
  'secret.read.unexpected': {
    severity: 'critical',
    title: 'A secret was read by an unexpected identity',
    source: 'CloudTrail -> EventBridge rule SecretReadAlertRule',
    channels: ['email', 'sms', 'chat'],
    when: { count: 1, window: 'each read' },
    repeat: 'never suppressed',
    action: 'Find the identity in the alert. If it was not a planned break-glass read, rotate the secret now and review that identity\'s access.',
  },
});

/** Sent directly by the app (not alarms): they tell, they don't page. */
export const NOTIFICATIONS = Object.freeze({
  'credential.rotated': {
    severity: 'info',
    topic: 'chat', // the chat-only topic: it tells, it doesn't page
    title: 'The app switched to a rotated credential',
    channels: ['chat'],
    repeat: '10m',
  },
  'alerting.test': {
    severity: 'info',
    topic: 'alerts', // the paging topic, so a test reaches email, SMS and chat
    title: 'Test alert from Secure Notes',
    channels: ['email', 'sms', 'chat'],
    repeat: '0',
  },
});

/** Events that are logged for the record but never alert. */
export const RECORD_EVENTS = Object.freeze({
  'db.auth.recovered': 'Postgres accepted the refreshed credential',
  'cache.auth.recovered': 'Redis accepted the refreshed credential',
  'alerting.notification.sent': 'A notification was published to SNS',
  'alerting.notification.suppressed': 'A notification was skipped by dedup or rate limit',
  'alerting.notification.failed': 'Publishing a notification failed',
});

export const ALL_EVENTS = Object.freeze(new Set([
  ...Object.keys(ALERTS),
  ...Object.keys(PLATFORM_ALERTS),
  ...Object.keys(NOTIFICATIONS),
  ...Object.keys(RECORD_EVENTS),
]));

/** "5m" -> 300 */
export function seconds(window) {
  const m = /^(\d+)([smhd])$/.exec(window);
  if (!m) return undefined;
  return Number(m[1]) * { s: 1, m: 60, h: 3600, d: 86400 }[m[2]];
}

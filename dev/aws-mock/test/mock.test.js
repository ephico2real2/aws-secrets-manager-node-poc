// The local AWS stand-ins: EventBridge pattern matching (with the stack's own
// rule), CloudTrail records, SNS validation and delivery, Query parsing.
// Run: node --test dev/aws-mock/test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { matches, deliveredToRule, transformInput } from '../lib/event-pattern.js';
import { cloudTrailEvent } from '../lib/cloudtrail.js';
import { principalOf, callerIdentity, roleArn } from '../lib/principals.js';
import { createSns, smsSegments, SnsError } from '../lib/sns.js';
import { parseForm, queryMap } from '../lib/aws-query.js';

const rule = JSON.parse(readFileSync(new URL('../rules/secret-read-alert.json', import.meta.url), 'utf8'));
const REDIS_ARN = 'arn:aws:secretsmanager:us-east-1:000000000000:secret:/elasticache/dev/notes-cache/app-AbCdEf';
const DB_ARN = 'arn:aws:secretsmanager:us-east-1:000000000000:secret:/rds/dev/notes-db/app-GhIjKl';

// Bind the rule's CloudFormation references the way the mock does.
function bound(node) {
  if (Array.isArray(node)) return node.map(bound);
  if (node && typeof node === 'object') {
    if ('Ref' in node) return { RedisAppSecret: REDIS_ARN, SecretReadAlertTopic: 'arn:aws:sns:us-east-1:000000000000:secure-notes-secret-read-alert' }[node.Ref];
    if ('Fn::GetAtt' in node) {
      return { 'Database.MasterUserSecret.SecretArn': DB_ARN, 'AppRole.Arn': roleArn('secure-notes-app'), 'RedisRotationRole.Arn': roleArn('secure-notes-redis-rotation') }[node['Fn::GetAtt']];
    }
    if ('Fn::Sub' in node) return node['Fn::Sub'].replace('${Environment}', 'dev').replace('${AWS::StackName}', 'notes-cache');
    return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, bound(v)]));
  }
  return node;
}
const pattern = bound(rule.eventPattern);
const read = (key, secretId, op = 'GetSecretValue') =>
  cloudTrailEvent({
    op, input: op === 'BatchGetSecretValue' ? { SecretIdList: [secretId] } : { SecretId: secretId },
    principal: principalOf(key ? { authorization: `AWS4-HMAC-SHA256 Credential=${key}/20261018/us-east-1/secretsmanager/aws4_request` } : {}),
    sourceIp: '10.0.0.5', requestId: 'r-1', region: 'us-east-1',
  });

test('the stack rule: the app and rotation are quiet; users, other roles and batch reads alarm', () => {
  assert.equal(matches(pattern, read('local-app', REDIS_ARN)), false);
  assert.equal(matches(pattern, read('local-rotation', REDIS_ARN)), false);
  assert.equal(matches(pattern, read(undefined, REDIS_ARN)), false, 'unsigned tooling (credential scan, health checks)');
  assert.equal(matches(pattern, read('local-intruder-user', REDIS_ARN)), true);
  assert.equal(matches(pattern, read('local-intruder-role', DB_ARN)), true);
  assert.equal(matches(pattern, read('local-intruder-user', '/elasticache/dev/notes-cache/app')), true, 'Redis secret by name');
  assert.equal(matches(pattern, read('local-intruder-user', '/rds/dev/notes-db/app')), false, 'known gap: the DB secret is matched by ARN only');
  assert.equal(matches(pattern, read('local-intruder-user', REDIS_ARN, 'BatchGetSecretValue')), true);
  assert.equal(matches(pattern, read('local-intruder-user', REDIS_ARN, 'DescribeSecret')), false);
});

test('the stack rule receives read-only events (the S4.2 fix)', () => {
  assert.equal(rule.state, 'ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS');
  assert.equal(deliveredToRule('ENABLED', read('local-intruder-user', REDIS_ARN)), false, 'a plain ENABLED rule never sees GetSecretValue');
  assert.equal(deliveredToRule(rule.state, read('local-intruder-user', REDIS_ARN)), true);
});

test('input transformer builds the alert text from the record', () => {
  const msg = transformInput(rule.target.inputTransformer, read('local-intruder-user', REDIS_ARN));
  assert.match(msg, /^"Secure Notes: secret .*elasticache.* was read by arn:aws:iam::000000000000:user\/mallory from 10\.0\.0\.5 at /);
});

test('pattern operators: exists, prefix, anything-but with prefix, numeric; unknown operators fail', () => {
  assert.ok(matches({ a: [{ exists: false }] }, {}));
  assert.ok(!matches({ a: [{ exists: true }] }, {}));
  assert.ok(matches({ a: [{ prefix: 'arn:' }] }, { a: 'arn:x' }));
  assert.ok(matches({ a: [{ 'anything-but': { prefix: 'arn:aws:iam' } }] }, { a: 'arn:aws:sts' }));
  assert.ok(!matches({ a: [{ 'anything-but': ['x'] }] }, {}), 'anything-but needs the field');
  assert.ok(matches({ n: [{ numeric: ['>', 1, '<=', 5] }] }, { n: 5 }));
  assert.throws(() => matches({ a: [{ cidr: '10.0.0.0/8' }] }, { a: '10.1.1.1' }), /unsupported operator/);
});

test('CloudTrail records never carry a value; STS answers as the caller', () => {
  const e = cloudTrailEvent({ op: 'PutSecretValue', input: { SecretId: 's', SecretString: 'Zq9-very-secret-value' }, principal: principalOf({}), requestId: 'r', region: 'us-east-1' });
  assert.ok(!JSON.stringify(e).includes('Zq9'));
  assert.equal(e.detail.readOnly, false);
  const me = callerIdentity(principalOf({ authorization: 'AWS4-HMAC-SHA256 Credential=local-app/20261018/us-east-1/sts/aws4_request' }));
  assert.match(me.Arn, /:assumed-role\/secure-notes-app\//);
});

test('SNS: per-protocol bodies, masked recipients, filter policies, AWS validation', () => {
  const logged = [];
  const sns = createSns({ log: (f) => logged.push(f) });
  const t = sns.createTopic('ops', { DisplayName: 'Secure Notes' });
  sns.subscribe(t.arn, 'email', 'oncall@example.com', { FilterPolicy: '{"severity":["critical"]}' });
  sns.subscribe(t.arn, 'sms', '+15555550100');
  sns.subscribe(t.arn, 'https', 'https://chat.example.com/hooks/abc');
  const attrs = (sev) => ({ severity: { DataType: 'String', StringValue: sev } });
  sns.publish({ TopicArn: t.arn, Subject: 'hello', MessageStructure: 'json', Message: JSON.stringify({ default: 'd', email: 'e', sms: 's' }), MessageAttributes: attrs('critical') });
  const [email, sms, https] = sns.deliveries();
  assert.equal(email.from, 'Secure Notes <no-reply@sns.amazonaws.com>');
  assert.equal(email.toMasked, 'on****@example.com');
  assert.match(email.body, /^e\n\n--\nIf you wish to stop receiving notifications/);
  assert.equal(sms.body, 's');
  assert.equal(JSON.parse(https.body).Message, 'd', 'https falls back to default');
  assert.ok(!JSON.stringify(sns.deliveries()).includes('oncall@'), 'full addresses are never kept');
  sns.publish({ TopicArn: t.arn, Message: 'info only', MessageAttributes: attrs('info') });
  assert.deepEqual(sns.deliveries(3).map((d) => d.protocol), ['sms', 'https'], 'the email filter policy drops info');
  assert.ok(logged.some((f) => f.event === 'sns.delivery.filtered'));
  assert.throws(() => sns.publish({ TopicArn: t.arn, Message: 'x', Subject: 'two\nlines' }), SnsError);
  assert.throws(() => sns.publish({ TopicArn: t.arn, Message: '{"email":"x"}', MessageStructure: 'json' }), /No default entry/);
  assert.throws(() => sns.publish({ TopicArn: t.arn, Message: 'x', Subject: 'x'.repeat(100) }), /Subject/);
  assert.throws(() => sns.publish({ TopicArn: 'arn:aws:sns:us-east-1:000000000000:nope', Message: 'x' }), /Topic does not exist/);
  assert.throws(() => sns.publish({ PhoneNumber: '+15555550100', Message: 'x'.repeat(1601) }), /1600/);
});

test('SMS segments: GSM-7 160/153, UCS-2 70/67', () => {
  assert.deepEqual([smsSegments('a'.repeat(160)).segments, smsSegments('a'.repeat(161)).segments], [1, 2]);
  assert.equal(smsSegments('🚨 alert').encoding, 'UCS-2');
  assert.equal(smsSegments('é'.repeat(70)).encoding, 'GSM-7');
  assert.equal(smsSegments('ü'.repeat(71)).segments, 1);
  assert.equal(smsSegments('ŵ'.repeat(71)).segments, 2);
});

test('Query parsing of an Alertmanager-style Publish', () => {
  const p = parseForm(
    'Action=Publish&Version=2010-03-31&TopicArn=arn%3Aaws%3Asns%3Aus-east-1%3A000000000000%3Aops&Subject=%5BFIRING%3A1%5D+x&Message=hello' +
      '&MessageAttributes.entry.1.Name=severity&MessageAttributes.entry.1.Value.DataType=String&MessageAttributes.entry.1.Value.StringValue=critical',
  );
  assert.equal(p.Action, 'Publish');
  assert.equal(p.Subject, '[FIRING:1] x');
  assert.deepEqual(queryMap(p, 'MessageAttributes'), { severity: { DataType: 'String', StringValue: 'critical' } });
});

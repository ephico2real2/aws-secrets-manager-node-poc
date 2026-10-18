#!/usr/bin/env node
// DEV-ONLY mock of the slice of AWS this demo uses, so it runs on a laptop
// with no AWS account and no auth tokens:
//
//   * Secrets Manager JSON API (awsJson1.1): CreateSecret, GetSecretValue,
//     DescribeSecret, PutSecretValue, UpdateSecretVersionStage,
//     GetRandomPassword, ListSecrets - including version stage semantics
//     (AWSCURRENT / AWSPENDING / AWSPREVIOUS) used by rotation.
//   * STS GetCallerIdentity, answering as the caller (see lib/principals.js:
//     the dummy access key names the identity).
//   * CloudTrail: a record for every Secrets Manager call, and the stack's
//     unexpected-read EventBridge rule (rules/secret-read-alert.json, generated
//     from infra/cloudformation.yaml) evaluated on each one; a match is
//     published to SNS (MOCK_SNS_ENDPOINT, the sns-logger) as EventBridge would.
//   * Optionally, an emulation of the AWS Workload Credentials Provider
//     (formerly Secrets Manager Agent) HTTP interface on localhost:2773 with
//     SSRF-token checking, so SECRETS_MODE=agent can be tried locally.
//
// It ignores request signatures and stores secrets in plaintext (optionally in
// MOCK_STATE_FILE). Never point anything real at it.
//
// Zero dependencies. Env:
//   PORT=4566  HOST=0.0.0.0  MOCK_STATE_FILE=/data/state.json
//   MOCK_SNS_ENDPOINT=http://sns-logger:4575   where rule matches are published
//   MOCK_RULE_DB_SECRET, MOCK_RULE_REDIS_SECRET, MOCK_RULE_ENVIRONMENT, MOCK_RULE_STACK_NAME
//     local values for the rule's CloudFormation references (defaults match Compose)
//   LOG_OTLP_ENDPOINT   optional: ship CloudTrail records and rule results to a collector
//   MOCK_AGENT_PORT=2773  MOCK_AGENT_TOKEN_FILE=./awssmatoken  MOCK_AGENT_TTL_SECONDS=300
//   MOCK_AGENT_UPSTREAM=http://aws-mock:4566  run ONLY the agent, as a sidecar next
//     to the app, fetching from another mock over HTTP the way the real agent
//     calls Secrets Manager (docker-compose.agent.yml)

import http from 'node:http';
import { randomBytes, randomInt, randomUUID } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync, chmodSync } from 'node:fs';
import { principalOf, callerIdentity, roleArn, ROLE_NAMES } from './lib/principals.js';
import { cloudTrailEvent, createTrail } from './lib/cloudtrail.js';
import { matches, deliveredToRule, transformInput } from './lib/event-pattern.js';
import { createOtlpShipper } from '../../backend/src/logship/otlp.js';

const PORT = Number(process.env.PORT ?? 4566);
const HOST = process.env.HOST ?? '0.0.0.0';
const REGION = process.env.AWS_REGION ?? 'us-east-1';
const ACCOUNT = '000000000000';
const STATE_FILE = process.env.MOCK_STATE_FILE;

// ---------------------------------------------------------------- state ----
/** name -> { arn, name, description, createdDate, lastChangedDate, versions: { id: { secretString, created, stages[] } } } */
let secrets = new Map();

function load() {
  if (STATE_FILE && existsSync(STATE_FILE)) {
    secrets = new Map(Object.entries(JSON.parse(readFileSync(STATE_FILE, 'utf8'))));
    console.log(`[aws-mock] loaded ${secrets.size} secret(s) from ${STATE_FILE}`);
  }
}
function save() {
  if (!STATE_FILE) return;
  try {
    writeFileSync(STATE_FILE, JSON.stringify(Object.fromEntries(secrets)), { mode: 0o600 });
  } catch (err) {
    console.log(`[aws-mock] could not persist state to ${STATE_FILE}: ${err.code ?? err.message}`);
  }
}
load();

class AwsError extends Error {
  constructor(type, message, status = 400) {
    super(message);
    this.type = type;
    this.status = status;
  }
}

const now = () => Date.now() / 1000;

function resolve(secretId) {
  if (!secretId) throw new AwsError('InvalidParameterException', 'SecretId is required');
  for (const s of secrets.values()) if (s.name === secretId || s.arn === secretId) return s;
  throw new AwsError('ResourceNotFoundException', "Secrets Manager can't find the specified secret.");
}

function versionWithStage(s, stage) {
  return Object.entries(s.versions).find(([, v]) => v.stages.includes(stage))?.[0];
}

/** Attach `stage` to versionId, detaching it from wherever it was. AWSCURRENT moves leave AWSPREVIOUS behind. */
function attachStage(s, stage, versionId) {
  const from = versionWithStage(s, stage);
  if (from === versionId) return;
  if (from) s.versions[from].stages = s.versions[from].stages.filter((x) => x !== stage);
  s.versions[versionId].stages.push(stage);
  if (stage === 'AWSCURRENT' && from) {
    const prevHolder = versionWithStage(s, 'AWSPREVIOUS');
    if (prevHolder) s.versions[prevHolder].stages = s.versions[prevHolder].stages.filter((x) => x !== 'AWSPREVIOUS');
    s.versions[from].stages.push('AWSPREVIOUS');
  }
}

function prune(s) {
  // Like AWS, drop versions with no staging label (keep it small).
  for (const [id, v] of Object.entries(s.versions)) if (v.stages.length === 0) delete s.versions[id];
}

// ------------------------------------------------------- secretsmanager ----
const ops = {
  CreateSecret(b) {
    if (!b.Name) throw new AwsError('InvalidParameterException', 'Name is required');
    if (secrets.has(b.Name)) throw new AwsError('ResourceExistsException', `The operation failed because the secret ${b.Name} already exists.`);
    const suffix = randomBytes(3).toString('hex');
    const versionId = b.ClientRequestToken ?? randomUUID();
    const s = {
      arn: `arn:aws:secretsmanager:${REGION}:${ACCOUNT}:secret:${b.Name}-${suffix}`,
      name: b.Name,
      description: b.Description,
      createdDate: now(),
      lastChangedDate: now(),
      versions: {},
    };
    if (b.SecretString !== undefined) s.versions[versionId] = { secretString: b.SecretString, created: now(), stages: ['AWSCURRENT'] };
    secrets.set(b.Name, s);
    save();
    return { ARN: s.arn, Name: s.name, VersionId: b.SecretString !== undefined ? versionId : undefined };
  },

  GetSecretValue(b) {
    const s = resolve(b.SecretId);
    const versionId = b.VersionId ?? versionWithStage(s, b.VersionStage ?? 'AWSCURRENT');
    const v = versionId && s.versions[versionId];
    if (!v || (b.VersionStage && !v.stages.includes(b.VersionStage))) {
      throw new AwsError('ResourceNotFoundException', "Secrets Manager can't find the specified secret value for staging label: " + (b.VersionStage ?? 'AWSCURRENT'));
    }
    return { ARN: s.arn, Name: s.name, VersionId: versionId, SecretString: v.secretString, VersionStages: v.stages, CreatedDate: v.created };
  },

  DescribeSecret(b) {
    const s = resolve(b.SecretId);
    return {
      ARN: s.arn,
      Name: s.name,
      Description: s.description,
      RotationEnabled: false,
      CreatedDate: s.createdDate,
      LastChangedDate: s.lastChangedDate,
      VersionIdsToStages: Object.fromEntries(Object.entries(s.versions).map(([id, v]) => [id, v.stages])),
    };
  },

  ListSecrets() {
    return { SecretList: [...secrets.values()].map((s) => ({ ARN: s.arn, Name: s.name, CreatedDate: s.createdDate })) };
  },

  PutSecretValue(b) {
    const s = resolve(b.SecretId);
    const versionId = b.ClientRequestToken ?? randomUUID();
    if (s.versions[versionId]) {
      if (s.versions[versionId].secretString !== b.SecretString) {
        throw new AwsError('ResourceExistsException', 'A version with this ClientRequestToken already exists with different content.');
      }
      return { ARN: s.arn, Name: s.name, VersionId: versionId, VersionStages: s.versions[versionId].stages };
    }
    s.versions[versionId] = { secretString: b.SecretString, created: now(), stages: [] };
    for (const stage of b.VersionStages ?? ['AWSCURRENT']) attachStage(s, stage, versionId);
    s.lastChangedDate = now();
    prune(s);
    save();
    return { ARN: s.arn, Name: s.name, VersionId: versionId, VersionStages: s.versions[versionId].stages };
  },

  UpdateSecretVersionStage(b) {
    const s = resolve(b.SecretId);
    const { VersionStage: stage, MoveToVersionId: to, RemoveFromVersionId: from } = b;
    if (!stage) throw new AwsError('InvalidParameterException', 'VersionStage is required');
    const holder = versionWithStage(s, stage);
    if (to) {
      if (!s.versions[to]) throw new AwsError('ResourceNotFoundException', 'MoveToVersionId not found');
      if (holder && holder !== to && holder !== from) {
        throw new AwsError('InvalidParameterException', `The staging label ${stage} is currently attached to version ${holder}. You must specify it in RemoveFromVersionId.`);
      }
      attachStage(s, stage, to);
    } else if (from) {
      if (holder !== from) throw new AwsError('InvalidParameterException', `${stage} is not attached to ${from}`);
      s.versions[from].stages = s.versions[from].stages.filter((x) => x !== stage);
    }
    s.lastChangedDate = now();
    prune(s);
    save();
    return { ARN: s.arn, Name: s.name };
  },

  GetRandomPassword(b) {
    const len = b.PasswordLength ?? 32;
    let chars = '';
    if (!b.ExcludeUppercase) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    if (!b.ExcludeLowercase) chars += 'abcdefghijklmnopqrstuvwxyz';
    if (!b.ExcludeNumbers) chars += '0123456789';
    if (!b.ExcludePunctuation) chars += '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~';
    if (b.IncludeSpace) chars += ' ';
    if (b.ExcludeCharacters) chars = [...chars].filter((c) => !b.ExcludeCharacters.includes(c)).join('');
    let out = '';
    for (let i = 0; i < len; i++) out += chars[randomInt(chars.length)];
    return { RandomPassword: out };
  },
};

// --------------------------------------------------------------- STS ------
function stsXml(identity) {
  return `<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><GetCallerIdentityResult><Arn>${identity.Arn}</Arn><UserId>${identity.UserId}</UserId><Account>${identity.Account}</Account></GetCallerIdentityResult><ResponseMetadata><RequestId>${randomUUID()}</RequestId></ResponseMetadata></GetCallerIdentityResponse>`;
}

// ------------------------------------------- CloudTrail and EventBridge ----
const shipper = process.env.LOG_OTLP_ENDPOINT
  ? createOtlpShipper({ endpoint: process.env.LOG_OTLP_ENDPOINT, resource: { 'service.name': 'aws-mock', 'deployment.environment.name': 'local' } })
  : undefined;
function shipJson(level, fields, msg) {
  shipper?.write(JSON.stringify({ time: new Date().toISOString(), level, app: 'aws-mock', ...fields, msg }));
}

const trail = createTrail();
const evaluations = [];
const SNS_ENDPOINT = process.env.MOCK_SNS_ENDPOINT;

const RULE_FILE = new URL('./rules/secret-read-alert.json', import.meta.url);
const rule = existsSync(RULE_FILE) ? JSON.parse(readFileSync(RULE_FILE, 'utf8')) : undefined;

// The rule's CloudFormation references, bound to local values. Secret ARNs are
// looked up when the rule runs, because the seed job creates the secrets later.
const arnOfSecret = (name) => () => secrets.get(name)?.arn ?? `unknown-secret:${name}`;
const SUBS = {
  Environment: process.env.MOCK_RULE_ENVIRONMENT ?? 'dev',
  'AWS::StackName': process.env.MOCK_RULE_STACK_NAME ?? 'notes-cache',
  'AWS::Region': REGION,
  'AWS::AccountId': ACCOUNT,
  'AWS::Partition': 'aws',
};
const BINDINGS = {
  'Fn::GetAtt:Database.MasterUserSecret.SecretArn': arnOfSecret(process.env.MOCK_RULE_DB_SECRET ?? '/rds/dev/notes-db/app'),
  'Ref:RedisAppSecret': arnOfSecret(process.env.MOCK_RULE_REDIS_SECRET ?? '/elasticache/dev/notes-cache/app'),
  'Fn::GetAtt:AppRole.Arn': () => roleArn(ROLE_NAMES.app),
  'Fn::GetAtt:RedisRotationRole.Arn': () => roleArn(ROLE_NAMES.rotation),
  'Ref:SecretReadAlertTopic': () => `arn:aws:sns:${REGION}:${ACCOUNT}:secure-notes-secret-read-alert`,
};

/** Replace {"Ref"...}/{"Fn::GetAtt"...}/{"Fn::Sub"...} with local values. Unknown ones throw. */
function bind(node) {
  if (Array.isArray(node)) return node.map(bind);
  if (node && typeof node === 'object') {
    const keys = Object.keys(node);
    if (keys.length === 1 && (keys[0] === 'Ref' || keys[0] === 'Fn::GetAtt')) {
      const ref = `${keys[0]}:${Array.isArray(node[keys[0]]) ? node[keys[0]].join('.') : node[keys[0]]}`;
      if (!BINDINGS[ref]) throw new Error(`rules/secret-read-alert.json: no local binding for ${ref}`);
      return BINDINGS[ref]();
    }
    if (keys.length === 1 && keys[0] === 'Fn::Sub') {
      return String(node['Fn::Sub']).replace(/\$\{([^}]+)\}/g, (_, name) => {
        if (!(name in SUBS)) throw new Error(`rules/secret-read-alert.json: no local value for \${${name}}`);
        return SUBS[name];
      });
    }
    return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, bind(v)]));
  }
  return node;
}
if (rule) {
  bind(rule.eventPattern); // fail at startup, not at the first read, if a reference is unknown
  bind(rule.target.arn);
  console.log(`[aws-mock] EventBridge rule SecretReadAlertRule loaded (State=${rule.state}, sha256 ${rule.sha256.slice(0, 12)})`);
}

async function publishToSns(topicArn, message) {
  const body = new URLSearchParams({ Action: 'Publish', Version: '2010-03-31', TopicArn: topicArn, Message: message });
  const res = await fetch(SNS_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
      Authorization: `AWS4-HMAC-SHA256 Credential=local-events/${new Date().toISOString().slice(0, 10).replace(/-/g, '')}/${REGION}/sns/aws4_request, SignedHeaders=host, Signature=local`,
    },
    body,
    signal: AbortSignal.timeout(5000),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`SNS answered ${res.status}: ${text.slice(0, 200)}`);
  return /<MessageId>([^<]+)<\/MessageId>/.exec(text)?.[1];
}

/** Record one call and run the rule on it, as CloudTrail + EventBridge would. */
async function audit(req, op, input, requestId, errorCode) {
  const principal = principalOf(req.headers);
  const event = cloudTrailEvent({
    op, input, principal, requestId, errorCode, region: REGION,
    sourceIp: req.socket.remoteAddress?.replace(/^::ffff:/, ''), userAgent: req.headers['user-agent'],
  });
  trail.add(event);
  const who = principal.arn ?? principal.invokedBy;
  const target = input.SecretId ?? (input.SecretIdList ?? []).join(',') ?? '';
  shipJson('info', { event: 'cloudtrail.record', 'cloudtrail.event_name': op, 'cloudtrail.read_only': event.detail.readOnly, 'aws.principal': who, 'aws.secret_name': target, 'aws.request_id': requestId, errorCode }, `CloudTrail: ${op} ${target} by ${who}`);
  if (!rule) return;
  const pattern = bind(rule.eventPattern);
  const delivered = deliveredToRule(rule.state, event);
  const matched = matches(pattern, event);
  const evaluation = { time: event.time, op, secret: target, who, matched, delivered, state: rule.state };
  if (matched && !delivered) evaluation.note = `EventBridge does not deliver read-only management events to a rule in state ${rule.state}`;
  if (matched && delivered) {
    const message = transformInput(rule.target.inputTransformer ?? {}, event);
    try {
      evaluation.messageId = SNS_ENDPOINT ? await publishToSns(bind(rule.target.arn), message) : undefined;
      evaluation.note = SNS_ENDPOINT ? 'published to SNS' : 'matched, but MOCK_SNS_ENDPOINT is not set';
    } catch (err) {
      evaluation.note = `publish failed: ${err.message}`;
    }
  }
  if (matched) {
    console.log(`[aws-mock] eventbridge SecretReadAlertRule matched ${op} ${target} by ${who}: ${evaluation.note}`);
    shipJson(evaluation.messageId ? 'warn' : 'info', { event: 'eventbridge.rule.matched', 'eventbridge.rule': 'SecretReadAlertRule', 'eventbridge.delivered': delivered, 'aws.principal': who, 'aws.secret_name': target, 'messaging.message.id': evaluation.messageId }, `EventBridge rule SecretReadAlertRule: ${evaluation.note}`);
  }
  evaluations.push(evaluation);
  if (evaluations.length > 100) evaluations.shift();
}

// -------------------------------------------------------------- server ----
async function readBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}

const api = http.createServer(async (req, res) => {
  const target = req.headers['x-amz-target'] ?? '';
  const body = await readBody(req);
  const reply = (status, payload, type = 'application/x-amz-json-1.1', extra = {}) => {
    res.writeHead(status, { 'Content-Type': type, 'x-amzn-RequestId': randomUUID(), ...extra });
    res.end(typeof payload === 'string' ? payload : JSON.stringify(payload));
  };

  if (req.method === 'GET' && (req.url === '/health' || req.url === '/_localstack/health')) {
    return reply(200, { status: 'running', services: { secretsmanager: 'running', sts: 'running' } }, 'application/json');
  }
  // Local-only views for the dashboard's detection lab: names and identities, never values.
  if (req.method === 'GET' && req.url.startsWith('/_mock/cloudtrail')) {
    return reply(200, { records: trail.since(Number(new URL(req.url, 'http://x').searchParams.get('since') ?? 0)) }, 'application/json');
  }
  if (req.method === 'GET' && req.url === '/_mock/eventbridge') {
    return reply(200, { rule: rule ? { name: 'SecretReadAlertRule', state: rule.state, sha256: rule.sha256 } : null, evaluations }, 'application/json');
  }

  // STS (query protocol, or JSON for newer SDKs)
  if (target.startsWith('AWSSecurityTokenServiceV20110615.') || /(^|&)Action=GetCallerIdentity(&|$)/.test(body)) {
    const identity = callerIdentity(principalOf(req.headers));
    console.log(`[aws-mock] sts:GetCallerIdentity -> ${identity.Arn}`);
    return target ? reply(200, identity, 'application/x-amz-json-1.0') : reply(200, stsXml(identity), 'text/xml');
  }

  if (!target.startsWith('secretsmanager.')) {
    return reply(400, { __type: 'UnknownOperationException', message: `unsupported target '${target}'` });
  }
  const op = target.slice('secretsmanager.'.length);
  const requestId = randomUUID();
  let input = {};
  try {
    if (!ops[op]) throw new AwsError('UnknownOperationException', `mock does not implement ${op}`);
    input = body ? JSON.parse(body) : {};
    const out = ops[op](input);
    console.log(`[aws-mock] secretsmanager:${op} ${input.SecretId ?? input.Name ?? ''}`.trim()); // never log values
    reply(200, out, undefined, { 'x-amzn-RequestId': requestId });
    await audit(req, op, input, requestId);
  } catch (err) {
    const type = err.type ?? 'InternalServiceError';
    console.log(`[aws-mock] secretsmanager:${op} -> ${type}`);
    if (!res.headersSent) reply(err.status ?? 500, { __type: type, message: err.message }, 'application/x-amz-json-1.1', { 'x-amzn-ErrorType': type });
    await audit(req, op, input, requestId, type).catch(() => {});
  }
});

const UPSTREAM = process.env.MOCK_AGENT_UPSTREAM;
if (!UPSTREAM) api.listen(PORT, HOST, () => console.log(`[aws-mock] Secrets Manager + STS mock on http://${HOST}:${PORT}`));

/** GetSecretValue, from this process's store or, as a sidecar, from the upstream mock. */
async function getSecretValue(input) {
  if (!UPSTREAM) return ops.GetSecretValue(input);
  const res = await fetch(UPSTREAM, {
    method: 'POST',
    // The real agent signs with the host's role: the app's identity here.
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'secretsmanager.GetSecretValue',
      Authorization: 'AWS4-HMAC-SHA256 Credential=local-app/20260101/us-east-1/secretsmanager/aws4_request, SignedHeaders=host, Signature=local',
    },
    body: JSON.stringify(input),
  });
  const out = await res.json();
  if (!res.ok) throw new AwsError(out.__type ?? 'InternalServiceError', out.message ?? `upstream ${res.status}`, res.status);
  return out;
}

// ------------------------------- Workload Credentials Provider emulation ----
if (process.env.MOCK_AGENT_PORT) {
  const tokenFile = process.env.MOCK_AGENT_TOKEN_FILE ?? './awssmatoken';
  const token = randomBytes(32).toString('base64url');
  writeFileSync(tokenFile, token, { mode: 0o640 });
  chmodSync(tokenFile, 0o640);
  const ttlMs = Number(process.env.MOCK_AGENT_TTL_SECONDS ?? 300) * 1000;
  const cache = new Map();

  const agent = http.createServer(async (req, res) => {
    const json = (status, obj) => {
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(obj));
    };
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/ping') return json(200, { status: 'healthy' });
    // Like the real agent: refuse proxied requests and requests without the SSRF token.
    if (req.headers['x-forwarded-for']) return json(400, { message: 'X-Forwarded-For not allowed' });
    if (req.headers['x-aws-parameters-secrets-token'] !== token) return json(403, { message: 'Bad Token' });
    if (url.pathname !== '/secretsmanager/get') return json(404, { message: 'not found' });

    const secretId = url.searchParams.get('secretId');
    const versionStage = url.searchParams.get('versionStage') ?? undefined;
    const key = `${secretId}|${versionStage ?? ''}`;
    const hit = cache.get(key);
    const refreshNow = url.searchParams.get('refreshNow') === 'true';
    try {
      if (!hit || refreshNow || Date.now() - hit.at > ttlMs) {
        cache.set(key, { at: Date.now(), value: await getSecretValue({ SecretId: secretId, VersionStage: versionStage }) });
        console.log(`[aws-mock agent] fetched ${secretId}${refreshNow ? ' (refreshNow)' : ''}`);
      }
      json(200, cache.get(key).value);
    } catch (err) {
      json(err.status ?? 500, { __type: err.type, message: err.message });
    }
  });
  agent.listen(Number(process.env.MOCK_AGENT_PORT), '127.0.0.1', () =>
    console.log(`[aws-mock] Workload Credentials Provider emulation on http://127.0.0.1:${process.env.MOCK_AGENT_PORT} (token file ${tokenFile})`),
  );
}

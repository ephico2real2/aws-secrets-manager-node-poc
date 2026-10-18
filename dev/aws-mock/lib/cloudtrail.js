// CloudTrail-shaped records for each Secrets Manager call, wrapped the way
// EventBridge delivers them ("AWS API Call via CloudTrail"). Request
// parameters only: a record never contains SecretString or SecretBinary.
import { randomUUID } from 'node:crypto';
import { ACCOUNT } from './principals.js';

const READ_ONLY = new Set(['GetSecretValue', 'BatchGetSecretValue', 'DescribeSecret', 'ListSecrets', 'GetRandomPassword', 'ListSecretVersionIds', 'GetResourcePolicy']);
const SAFE_PARAMS = ['SecretId', 'VersionId', 'VersionStage', 'Name', 'SecretIdList', 'Filters', 'MoveToVersionId', 'RemoveFromVersionId'];

const lower = (k) => k[0].toLowerCase() + k.slice(1);

export function cloudTrailEvent({ op, input = {}, principal, sourceIp, userAgent, requestId, region, errorCode }) {
  const requestParameters = {};
  for (const k of SAFE_PARAMS) if (input[k] !== undefined) requestParameters[lower(k)] = input[k];
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const detail = {
    eventVersion: '1.11',
    userIdentity: principal,
    eventTime: now,
    eventSource: 'secretsmanager.amazonaws.com',
    eventName: op,
    awsRegion: region,
    sourceIPAddress: principal.type === 'AWSService' ? principal.invokedBy : sourceIp,
    userAgent: userAgent ?? 'unknown',
    requestParameters,
    responseElements: null,
    requestID: requestId,
    eventID: randomUUID(),
    readOnly: READ_ONLY.has(op),
    eventType: 'AwsApiCall',
    managementEvent: true,
    recipientAccountId: ACCOUNT,
    eventCategory: 'Management',
  };
  if (errorCode) {
    detail.errorCode = errorCode;
    detail.errorMessage = `${errorCode} (local mock)`;
  }
  return {
    version: '0',
    id: randomUUID(),
    'detail-type': 'AWS API Call via CloudTrail',
    source: 'aws.secretsmanager',
    account: ACCOUNT,
    time: now,
    region,
    resources: [],
    detail,
  };
}

/** A bounded in-memory trail. */
export function createTrail(size = 300) {
  const events = [];
  let seq = 0;
  return {
    add(e) {
      events.push({ seq: ++seq, event: e });
      if (events.length > size) events.shift();
    },
    since(n = 0) {
      return events.filter((x) => x.seq > n);
    },
  };
}

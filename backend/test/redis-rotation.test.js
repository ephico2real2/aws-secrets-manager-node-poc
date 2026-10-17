// The Redis (ElastiCache user) rotation function from infra/rotation, driven
// through Secrets Manager's four steps against in-memory fakes of Secrets
// Manager and ElastiCache. Run: npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
process.env.USER_ID = 'stack-app';
process.env.WAIT_MS = '1';
const { handler } = require('../../infra/rotation/elasticache-user-rotation.js');

function notFound() {
  return Object.assign(new Error('not found'), { name: 'ResourceNotFoundException' });
}

/** Secrets Manager with version stages, as rotation sees it. */
function fakeSecretsManager(initial) {
  const versions = new Map([['v1', { value: JSON.stringify(initial), stages: ['AWSCURRENT'] }]]);
  return {
    versions,
    rotationEnabled: true,
    start(token) { versions.set(token, { value: undefined, stages: ['AWSPENDING'] }); },
    async describeSecret() {
      return { RotationEnabled: this.rotationEnabled, VersionIdsToStages: Object.fromEntries([...versions].map(([k, v]) => [k, [...v.stages]])) };
    },
    async getSecretValue({ VersionStage, VersionId }) {
      const hit = [...versions].find(([k, v]) => v.stages.includes(VersionStage) && (!VersionId || k === VersionId) && v.value !== undefined);
      if (!hit) throw notFound();
      return { SecretString: hit[1].value };
    },
    async getRandomPassword() { return { RandomPassword: 'n'.repeat(40) }; },
    async putSecretValue({ ClientRequestToken, SecretString, VersionStages }) {
      versions.set(ClientRequestToken, { value: SecretString, stages: VersionStages });
    },
    async updateSecretVersionStage({ VersionStage, MoveToVersionId, RemoveFromVersionId }) {
      const from = versions.get(RemoveFromVersionId);
      from.stages = from.stages.filter((s) => s !== VersionStage).concat('AWSPREVIOUS');
      const to = versions.get(MoveToVersionId);
      to.stages = to.stages.filter((s) => s !== 'AWSPENDING').concat(VersionStage);
    },
  };
}

/** ElastiCache: a user that is "modifying" for a moment after each change. */
function fakeElastiCache(passwords) {
  return {
    passwords: [...passwords],
    history: [],
    busy: 0,
    async describeUsers({ UserId }) {
      assert.equal(UserId, 'stack-app');
      const status = this.busy > 0 ? (this.busy--, 'modifying') : 'active';
      return { Users: [{ Status: status, Authentication: { Type: 'password', PasswordCount: this.passwords.length } }] };
    },
    async modifyUser({ UserId, AuthenticationMode }) {
      assert.equal(UserId, 'stack-app');
      assert.equal(this.busy, 0, 'must wait for the user to be active before modifying it');
      this.passwords = [...AuthenticationMode.Passwords];
      this.history.push([...this.passwords]);
      this.busy = 2;
    },
  };
}

async function rotate(sm, ec, token) {
  globalThis.__rotationClients = { sm, ec };
  sm.start(token);
  for (const Step of ['createSecret', 'setSecret', 'testSecret', 'finishSecret']) {
    await handler({ SecretId: 'stack/redis', ClientRequestToken: token, Step });
  }
}

test('a rotation adds the new password alongside the old, then retires the old one', async () => {
  const sm = fakeSecretsManager({ username: 'notes-app', password: 'o'.repeat(40) });
  const ec = fakeElastiCache(['o'.repeat(40)]);
  await rotate(sm, ec, 't1');

  assert.deepEqual(ec.history, [['o'.repeat(40), 'n'.repeat(40)], ['n'.repeat(40)]]);
  assert.deepEqual(sm.versions.get('t1').stages, ['AWSCURRENT']);
  assert.deepEqual(sm.versions.get('v1').stages, ['AWSPREVIOUS']);
  assert.deepEqual(JSON.parse(sm.versions.get('t1').value), { username: 'notes-app', password: 'n'.repeat(40) });
});

test('each step can be retried safely', async () => {
  const sm = fakeSecretsManager({ username: 'notes-app', password: 'o'.repeat(40) });
  const ec = fakeElastiCache(['o'.repeat(40)]);
  globalThis.__rotationClients = { sm, ec };
  sm.start('t2');
  const step = (Step) => handler({ SecretId: 'stack/redis', ClientRequestToken: 't2', Step });
  await step('createSecret');
  const first = sm.versions.get('t2').value;
  await step('createSecret'); // a retry keeps the password it already generated
  assert.equal(sm.versions.get('t2').value, first);
  await step('setSecret');
  await step('setSecret');
  await step('testSecret');
  await step('finishSecret');
  await step('finishSecret'); // already AWSCURRENT: nothing to do
  assert.deepEqual(ec.passwords, ['n'.repeat(40)]);
});

test('refuses a token that is not AWSPENDING, and a secret without rotation', async () => {
  const sm = fakeSecretsManager({ username: 'notes-app', password: 'o'.repeat(40) });
  globalThis.__rotationClients = { sm, ec: fakeElastiCache(['o'.repeat(40)]) };
  await assert.rejects(handler({ SecretId: 's', ClientRequestToken: 'nope', Step: 'createSecret' }), /unknown version/);
  sm.start('t3');
  sm.rotationEnabled = false;
  await assert.rejects(handler({ SecretId: 's', ClientRequestToken: 't3', Step: 'createSecret' }), /not enabled/);
});

test('testSecret fails when the new password did not reach ElastiCache', async () => {
  const sm = fakeSecretsManager({ username: 'notes-app', password: 'o'.repeat(40) });
  const ec = fakeElastiCache(['o'.repeat(40)]);
  globalThis.__rotationClients = { sm, ec };
  sm.start('t4');
  await handler({ SecretId: 's', ClientRequestToken: 't4', Step: 'createSecret' });
  await assert.rejects(handler({ SecretId: 's', ClientRequestToken: 't4', Step: 'testSecret' }), /new password not set/);
});

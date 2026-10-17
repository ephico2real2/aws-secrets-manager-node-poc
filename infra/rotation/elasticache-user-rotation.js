// Secrets Manager rotation for an ElastiCache RBAC user (inlined into
// infra/cloudformation.yaml by scripts/sync-rotation-lambda.js; edit HERE).
// ElastiCache users accept two passwords, so there is no moment when the app's
// password stops working before it can fetch the new one.
'use strict';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const clients = () => {
  if (globalThis.__rotationClients) return globalThis.__rotationClients; // tests
  const { SecretsManager } = require('@aws-sdk/client-secrets-manager');
  const { ElastiCache } = require('@aws-sdk/client-elasticache');
  return { sm: new SecretsManager({}), ec: new ElastiCache({}) };
};
const read = async (sm, id, stage, token) =>
  JSON.parse((await sm.getSecretValue({ SecretId: id, VersionStage: stage, VersionId: token })).SecretString);

async function settle(ec, userId) {
  const wait = Number(process.env.WAIT_MS || 10000);
  for (let i = 0; i < 60; i++) {
    const u = (await ec.describeUsers({ UserId: userId })).Users[0];
    if (u.Status === 'active') return u;
    await sleep(wait);
  }
  throw new Error(`user ${userId} still modifying`);
}
const setPasswords = async (ec, userId, passwords) => {
  await settle(ec, userId);
  await ec.modifyUser({ UserId: userId, AuthenticationMode: { Type: 'password', Passwords: passwords } });
  return settle(ec, userId);
};

exports.handler = async ({ SecretId: id, ClientRequestToken: token, Step: step }) => {
  const { sm, ec } = clients();
  const userId = process.env.USER_ID;
  const meta = await sm.describeSecret({ SecretId: id });
  if (!meta.RotationEnabled) throw new Error('rotation is not enabled');
  const stages = (meta.VersionIdsToStages || {})[token];
  if (!stages) throw new Error('unknown version');
  if (stages.includes('AWSCURRENT')) return; // already done
  if (!stages.includes('AWSPENDING')) throw new Error('version is not AWSPENDING');
  const current = await read(sm, id, 'AWSCURRENT');

  if (step === 'createSecret') {
    try {
      await read(sm, id, 'AWSPENDING', token);
    } catch (e) {
      if (e.name !== 'ResourceNotFoundException') throw e;
      const { RandomPassword } = await sm.getRandomPassword({ PasswordLength: 40, ExcludePunctuation: true });
      await sm.putSecretValue({ SecretId: id, ClientRequestToken: token,
        SecretString: JSON.stringify({ ...current, password: RandomPassword }), VersionStages: ['AWSPENDING'] });
    }
  } else if (step === 'setSecret') {
    // Both passwords valid while the app catches up.
    const pending = await read(sm, id, 'AWSPENDING', token);
    await setPasswords(ec, userId, [current.password, pending.password]);
  } else if (step === 'testSecret') {
    const u = await settle(ec, userId);
    if (u.Authentication.Type !== 'password' || u.Authentication.PasswordCount < 2) throw new Error('new password not set');
  } else if (step === 'finishSecret') {
    const pending = await read(sm, id, 'AWSPENDING', token);
    const old = Object.keys(meta.VersionIdsToStages).find((v) => meta.VersionIdsToStages[v].includes('AWSCURRENT'));
    await sm.updateSecretVersionStage({ SecretId: id, VersionStage: 'AWSCURRENT', MoveToVersionId: token, RemoveFromVersionId: old });
    // Then retire the old password. A client still using it gets WRONGPASS on
    // its next login and re-reads the secret; open connections are unaffected.
    await setPasswords(ec, userId, [pending.password]);
  } else {
    throw new Error(`unknown step ${step}`);
  }
};

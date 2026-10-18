import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { config, assertSafeEnvironment } from './config.js';
import { createLogger } from './log.js';
import { createEventLog } from './events.js';
import { Redactor, createSecretsProvider } from './secrets/index.js';
import { createDb } from './clients/db.js';
import { createCache } from './clients/cache.js';
import { createHttpServer, createRouter } from './http.js';
import { registerRoutes } from './routes.js';
import { NOTES_SCHEMA } from './schema.js';

const redactor = new Redactor();
const logger = createLogger({
  redactor,
  level: config.logging.level,
  revealSecrets: config.logging.revealSecrets && config.nodeEnv !== 'production',
  base: { app: 'secure-notes' },
});

process.on('unhandledRejection', (err) => logger.error({ err }, 'unhandled rejection'));
process.on('uncaughtException', (err) => {
  logger.error({ err }, 'uncaught exception; exiting');
  process.exit(1);
});

try {
  assertSafeEnvironment();
} catch (err) {
  logger.error(err.message);
  process.exit(78); // EX_CONFIG: systemd will not hot-loop on a config error with RestartPreventExitStatus=78
}

logger.debug(
  {
    secretsMode: config.secretsMode,
    secretIds: config.secretIds,
    endpoint: config.awsEndpoint ?? (config.secretsMode === 'agent' ? config.agent.url : `secretsmanager.${config.region} (SDK default)`),
    logLevel: config.logging.level,
  },
  'credential sources: which secrets this process will consume',
);
if (config.logging.revealSecrets) {
  logger.warn(
    { logLevel: config.logging.level },
    config.logging.level === 'debug'
      ? 'LOG_REVEAL_SECRETS=true: secret values will be written to this log. Lab use only; never in production.'
      : 'LOG_REVEAL_SECRETS=true has no effect unless LOG_LEVEL=debug',
  );
}

const events = createEventLog();
const provider = createSecretsProvider({ config, redactor, logger });
provider.on('loaded', ({ secretId, reason, changed, versionId }) => {
  const alias = Object.entries(config.secretIds).find(([, id]) => id === secretId)?.[0] ?? secretId;
  events.record(
    'secrets',
    changed ? 'new-version' : 'loaded',
    changed
      ? `Picked up new version ${versionId.slice(0, 8)} of the ${alias} secret (${reason})`
      : `Loaded the ${alias} secret, version ${versionId.slice(0, 8)} (${reason})`,
  );
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Fail fast if we cannot read our secrets, but tolerate a few seconds of
// startup ordering (e.g. the network or a local mock coming up).
async function warmUp() {
  for (let attempt = 1; ; attempt++) {
    try {
      await Promise.all([provider.get(config.secretIds.db), provider.get(config.secretIds.redis)]);
      return;
    } catch (err) {
      if (attempt >= 8) throw err;
      logger.warn({ attempt, err }, 'could not load secrets yet; retrying');
      await sleep(Math.min(500 * 2 ** attempt, 8_000));
    }
  }
}

try {
  await warmUp();
} catch (err) {
  logger.error({ err }, 'unable to load secrets from Secrets Manager; exiting');
  process.exit(1);
}

const db = createDb({ provider, secretId: config.secretIds.db, config, logger, events });
const cache = await createCache({ provider, secretId: config.secretIds.redis, config, logger, events });
await db.ping();
if (config.db.autoMigrate) {
  // Check first: a least-privilege login may read the table but not CREATE in the schema.
  const { rows } = await db.query(`SELECT to_regclass('public.notes') IS NOT NULL AS present`);
  if (!rows[0].present) await db.query(NOTES_SCHEMA);
  logger.info('database schema ensured');
}

const rotator = config.demo.enabled
  ? (await import('./demo/rotator.js')).createRotator({ config, redactor, logger, events })
  : undefined;

const router = createRouter();
registerRoutes(router, { config, provider, db, cache, events, logger, redactor, rotator });

const here = path.dirname(fileURLToPath(import.meta.url));
const server = createHttpServer({
  router,
  staticDir: process.env.STATIC_DIR ?? path.resolve(here, '../../frontend'),
  logger,
  redactor,
  isProduction: config.nodeEnv === 'production',
});

server.listen(config.port, config.host, () => {
  logger.info(
    { host: config.host, port: config.port, secretsMode: provider.mode, demoMode: config.demo.enabled },
    'secure-notes listening',
  );
});

async function shutdown(signal) {
  logger.info({ signal }, 'shutting down');
  server.close();
  await Promise.allSettled([db.close(), cache.close()]);
  process.exit(0);
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

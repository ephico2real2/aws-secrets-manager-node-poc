# Backlog — epics, features and stories

[← Initiative](README.md) · [Source review](01-source-review.md) · [ADR-001](02-adr-001-secrets-manager-selection.md)

**How to read a story:** ID · title · *As a … I want … so that …* · acceptance criteria
(each one testable) · size (S ≤ 1 day, M ≤ 3 days, L ≤ 1 week) · status, with the
evidence that proves it. ✅ Done · 🔜 To do · 🔎 Needs verification on AWS.

Epics run in the order of the [epic map](README.md#how-the-work-is-organized):
discover → decide → change the app and the platform → harden → automate → prove → teach.

## E0 — Discovery: review the initial source code

**S0.1 · Inventory every credential** · S · ✅
*As a security engineer, I want a list of every credential and every place it lives, so
that the redesign covers all of them.*
- [x] Each credential, its locations, who can read it, rotation and audit status are tabulated.

Evidence: [source review §2](01-source-review.md#2-where-each-credential-lives-and-who-can-read-it)

**S0.2 · Threat-model the `.env` approach** · S · ✅
*As a security engineer, I want the findings ranked by severity, so that we fix the worst first.*
- [x] Findings F1–F7 with severity; requirements R1–R6 derived from them.

Evidence: [source review §3–4](01-source-review.md#3-findings)

**S0.3 · Prove F1 with a live demo** · S · ✅
*As an engineer, I want to see a `.env` password read out of a running container, so that
the risk is concrete, not theoretical.*
- [x] Given a container started with `--env-file --rm -d`, when I run `exec env`,
  `/proc/1/environ`, `inspect` or read `/proc/PID/environ` on the host, then the password appears.
- [x] The same lookups on Secure Notes show secret IDs only.
- [x] CI runs it on every push and fails if the generic password is *not* readable.

Evidence: `scripts/env-file-demo.sh`, CI job `env-file-demo`, [chapter 2](../learn/02-the-env-file-problem.md)

## E1 — Select a secrets management tool for AWS

**S1.1 · Compare the options against our requirements** · S · ✅
*As an architect, I want options scored against R1–R6, cost and operating burden, so that
the choice is explainable.*
- [x] At least four options; criteria tied to requirements; scores and reasons.

**S1.2 · Decide and record the consequences** · S · ✅
- [x] Decision, consequences (good and bad), and the conditions that would reverse it.

Evidence (both): [ADR-001](02-adr-001-secrets-manager-selection.md)

**S1.3 · Learning brief for the team** · M · ✅
*As a junior engineer, I want the retrieval pattern explained across products, and how
JWT workload identity works, so that I can apply it on any stack.*
- [x] The seven-step pattern, mapped to AWS, Vault, Azure Key Vault and Google Secret Manager.
- [x] JWT claims and the token exchange, with the places this repo uses it.

Evidence: [chapter 1](../learn/01-secrets-managers.md), [chapter 3](../learn/03-why-a-secrets-manager.md)

## E2 — Application changes: consume secrets at runtime

**Feature F2.1 · Configuration holds no secrets** · S · ✅
*As an operator, I want the app to refuse to start if a credential is in its environment,
so that nobody "fixes" an outage by pasting a password in.*
- [x] `DB_PASSWORD`, `PGPASSWORD`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
  `REDIS_URL`, `REDISCLI_AUTH` set → exit 78. In production also static AWS keys, demo
  mode, a mock endpoint, or the reveal flag.

Evidence: `backend/src/config.js`, `backend/test/secrets.test.js`, [test case 8](../../demo/test-case-08-reveal-refused-in-production.md)

**F2.2 · Fetch with the platform identity** · M · ✅
- [x] SDK mode (`GetSecretValue`, default credential chain) and agent mode (`localhost:2773`
  with the SSRF token) behind one interface.

Evidence: `backend/src/secrets/fetchers.js`, [test case 9](../../demo/test-case-09-agent-mode.md)

**F2.3 · Cache safely** · M · ✅
- [x] TTL with ±10% jitter; concurrent misses share one call; the last good value is served
  if a refresh fails.

Evidence: `backend/src/secrets/provider.js`, `backend/test/secrets.test.js`

**F2.4 · Rotation without restart** · M · ✅
*As an SRE, I want the app to recover by itself when a password rotates, so that rotation
can run on a schedule.*
- [x] Given the password rotated, when a new connection fails with `28P01` or `WRONGPASS`,
  then the app refreshes once, retries, and the request succeeds.

Evidence: `backend/src/clients/`, `backend/test/redis-rotation.test.js`, [test cases 2](../../demo/test-case-02-rotate-postgres.md) and [3](../../demo/test-case-03-rotate-redis.md)

**F2.5 · No secret in logs or API responses** · M · ✅
- [x] `SecretValue` prints `[REDACTED]`; key- and value-based redaction of every line.
- [x] The leak test finds no value in logs or responses.

Evidence: `backend/src/secrets/SecretValue.js`, `redactor.js`, [test case 4](../../demo/test-case-04-leak-test.md)

**F2.6 · Masked debug logging; lab-only reveal flag** · S · ✅
- [x] Debug lines show secret ID, version and keys, with passwords fully masked.
- [x] `LOG_REVEAL_SECRETS=true` prints values to stdout only, is flagged on the dashboard,
  and is refused in production.

Evidence: `backend/src/secrets/mask.js`, `backend/test/mask.test.js`, [test cases 5](../../demo/test-case-05-debug-log.md) and [7](../../demo/test-case-07-reveal-flag.md)

**F2.7 · Agent mode** · S · ✅
- [x] Reads through the AWS Workload Credentials Provider with its SSRF token; forces a
  refresh after an auth failure, because the agent's cache doesn't see rotation.

Evidence: `docker-compose.agent.yml`, CI job `compose (agent)`, [test case 9](../../demo/test-case-09-agent-mode.md)

**F2.8 · Secret naming convention** · M · ✅
*As a platform engineer, I want secret names built from one pattern
(`/{service}/{env}/{resource}/{name}`), so that environments differ by one setting and
IAM can grant by path.*
- [x] Given `SECRETS_ENV=prod` and `REDIS_SECRET_RESOURCE=secure-notes`, the app reads
  `/elasticache/prod/secure-notes/app`; presets and custom patterns supported.
- [x] An explicit `*_SECRET_ID` wins (needed for the `rds!…` secret RDS names itself).
- [x] Settings from env vars, `config.yaml`, `config.json` or `config.env`; a config file
  with a credential in it is refused; an unknown environment or token stops startup.
- [x] Compose, kind and the CloudFormation stack use the convention; the seed job and the
  app build names with the same function.

Evidence: `backend/src/secrets/naming.js`, `backend/test/naming.test.js`, [secret naming reference](../reference/secret-naming.md), `deploy/config/`

## E3 — Platform and infrastructure on AWS

**F3.1 · Identity without keys** · S · ✅ — EC2 instance role; IMDSv2 required, hop limit 1; IRSA on EKS/ROSA.
**F3.2 · Private network path** · S · ✅ — Secrets Manager VPC endpoint with an account-only policy; the role may read only via that endpoint.
**F3.3 · Encryption** · S · ✅ — customer-managed KMS key, decrypt only via Secrets Manager; RDS and ElastiCache encrypted at rest and in transit.
**F3.4 · Managed credentials** · M · ✅ — RDS `ManageMasterUserPassword`; a generated ElastiCache user secret; a rotation function for it.
**F3.5 · Kubernetes and OpenShift** · M · ✅ — Kustomize overlays; no Kubernetes Secret holds an app credential.

Evidence: `infra/cloudformation.yaml`, `deploy/k8s/`, [GUIDE](../GUIDE.md), [test case 10](../../demo/test-case-10-kubernetes.md)

## E4 — Security hardening

From the [system design review](../learn/05-system-design.md).

**S4.1 · Resource policy on the Redis secret** · S · ✅ (🔎 first AWS run)
*As a security engineer, I want only the app, its rotation function and a named
break-glass role to read the secret, so that a broadly privileged admin or a
misconfigured role can't.*
- [x] Deny `GetSecretValue` to every other principal; deny the app outside the VPC endpoint.
- [x] `BlockPublicPolicy` on; created after the cache user so the stack's own read succeeds.
- [ ] 🔎 On AWS: a stack update that touches the cache user still succeeds; a read by
  another admin role is denied.

Evidence: `RedisSecretPolicy` in `infra/cloudformation.yaml` (parameter `SecretAdminRoleArn`)

**S4.1b · Resource policy on the RDS-managed secret** · S · 🔜 🔎
- [ ] Prove on AWS that a resource policy on the `rds!` secret leaves RDS managed rotation
  working; then add the same deny.

**S4.2 · Alarm on unexpected secret reads** · M · ✅ (🔎 first AWS run)
*As an on-call engineer, I want an alert when anyone other than the app or rotation reads
a secret, so that misuse is noticed in minutes, not in an audit.*
- [x] EventBridge rule on CloudTrail `GetSecretValue` / `BatchGetSecretValue` for both
  secrets, excluding the app and rotation roles → SNS (encrypted), optional email.
- [x] Optional trail (`CreateTrail=true`) for accounts without one.
- [ ] 🔎 On AWS: a read from the console raises an email within minutes; the app's reads don't.

Evidence: `SecretReadAlertRule`, `SecretReadAlertTopic`, output `SecretReadAlertTopicArn`

**S4.3 · AWS Config rules** · S · ✅ (opt-in)
- [x] `EnableConfigRules=true` adds: rotation enabled, scheduled rotation succeeded, EC2 IMDSv2.

Evidence: `RotationEnabledRule`, `RotationSucceededRule`, `ImdsV2Rule`

**S4.4 · Least-privilege database user** · M · 🔜
*As a DBA, I want the app to log in as a role that owns only its tables, so that a stolen
app credential can't administer the database.*
- [ ] A `notes_app` role and its own secret, rotated with the alternating-users template.
- [ ] The master user is used only by RDS rotation and administrators.

**S4.5 · IAM authentication for RDS and ElastiCache** · L · 🔜
- [ ] Spike: token per new connection; measure connection rate against RDS limits;
  ElastiCache needs Valkey 7.2+/Redis 7+ and reconnects after 12 hours.

**S4.6 · Regional resilience and tighter egress** · M · 🔜
- [ ] Replica secrets in a second region; 443 egress limited to VPC endpoints; KMS key
  administrators named explicitly.

## E5 — Delivery and automation

**F5.1 · One build, every platform** · M · ✅ — the same images on Compose, kind, OpenShift and EC2.
**F5.2 · Supply chain** · M · ✅ — SBOM, vulnerability scan, cosign keyless signing and attestation; [test case 11](../../demo/test-case-11-supply-chain.md).
**F5.3 · Air-gapped installs** · S · ✅ — `scripts/mirror-images.sh`; [test case 12](../../demo/test-case-12-image-mirror.md).
**F5.4 · Keyless deploys** · M · ✅ — GitHub OIDC to an IAM role scoped to one environment; no stored AWS keys (`.github/workflows/aws.yaml`).
**S5.5 · Automation examples for other teams** · S · ✅ — Terraform, Ansible, External Secrets and CSI in [chapter 3](../learn/03-why-a-secrets-manager.md#automation-terraform-ansible-and-kubernetes).

## E6 — Verification and evidence

**F6.1 · Unit tests** · ✅ — real `pg`, `ioredis` and AWS SDK clients against fakes; run in CI job `checks`.
**F6.2 · End-to-end** · ✅ — dashboard walk with screenshots, smoke test, leak test, on Compose (both modes) and kind.
**F6.3 · Credential scan** · ✅ — searches every container, file, log and Kubernetes object for the real values; self-tests with the reveal flag on ([test case 6](../../demo/test-case-06-credential-scan.md)).

Evidence: [TEST-CASES](../TEST-CASES.md), [CI reference](../reference/ci.md)

## E7 — Documentation and enablement

**S7.1 · Learning path** · M · ✅ — [chapters 1–6](../learn/README.md), each with what you'll learn, diagrams and sources.
**S7.2 · README as the landing page** · S · ✅ — the story first; reference material in [`docs/reference/`](../reference/).
**S7.3 · Request-flow diagrams matched to the code** · S · ✅ — [chapter 6](../learn/06-request-flows.md).
**S7.4 · Docs stay correct** · S · ✅ — CI checks every relative link and renders every Mermaid diagram.

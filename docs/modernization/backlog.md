# Backlog — epics, features and stories

[← Initiative](README.md) · [Source review](01-source-review.md) · [ADR-001](02-adr-001-secrets-manager-selection.md) · [GitHub issues](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atype%3Aepic)

**How to read it:** an **epic** is an outcome; a **feature** is a capability; a **story** is
one deliverable with acceptance criteria (each one testable). Size: S ≤ 1 day, M ≤ 3
days, L ≤ 1 week. Status: ✅ done, with evidence · 🔎 built, to verify on AWS · 🔜 to do.

Every item is also a GitHub issue (linked as #N), with sub-issues for the hierarchy and
labels `type:epic|feature|story`, `epic:E0…E7`, `size:S|M|L` and `needs-aws-verification`.
Done items are closed with their evidence. This page and the issues are generated from
the same list, so they say the same thing.

Order: see the [epic map](README.md#how-the-work-is-organized). E0 then E1; E2 and E3 after
E1; E4, E5 and E6 in parallel once E3 is in place; E7 throughout. A small feature with
one deliverable is written as its own story (persona and acceptance criteria) rather
than split into stories.

## E0 — Discovery: review the initial source code

[#1](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/1) · ✅ · **Outcome:** The initial `.env`-based design is reviewed, its risks ranked, and requirements R1–R6 written. Docs: [Source review](01-source-review.md)

### F0.1 · Source review of the initial design · ✅ · [#2](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/2)

**S0.1 · Inventory every credential and where it lives** · S · ✅ · [#3](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/3)
*As a security engineer, I want a list of every credential and every place it lives, so that the redesign covers all of them.*
- [x] Each credential, its locations, who can read it, rotation and audit status are tabulated.

Evidence: [Source review §2](01-source-review.md)

**S0.2 · Threat-model the .env approach** · S · ✅ · [#4](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/4)
*As a security engineer, I want the findings ranked by severity, so that we fix the worst first.*
- [x] Findings F1–F7 with severity.
- [x] Requirements R1–R6 derived from them.

Evidence: [Source review §3–4](01-source-review.md)

### F0.2 · Live proof of the .env problem · ✅ · [#5](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/5)

**S0.3 · Prove F1 with a live Podman demo** · S · ✅ · [#6](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/6)
*As an engineer, I want to see a `.env` password read out of a running container, so that the risk is concrete, not theoretical.*
- [x] Given a container started with `--env-file --rm -d`, when I run `exec env`, `/proc/1/environ`, `inspect` or read `/proc/PID/environ` on the host, then the password appears.
- [x] The same lookups on Secure Notes show secret IDs only.
- [x] CI runs it on every push and fails if the generic password is *not* readable.

Evidence: [scripts/env-file-demo.sh](../../scripts/env-file-demo.sh), CI job `env-file-demo`, [chapter 2: The .env file problem](../learn/02-the-env-file-problem.md)

## E1 — Select a secrets management tool for AWS

[#7](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/7) · ✅ · **Outcome:** A recorded decision, with criteria, scores, consequences and the conditions that would reverse it. Docs: [ADR-001](02-adr-001-secrets-manager-selection.md)

### F1.1 · ADR-001: choose the secrets manager · ✅ · [#8](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/8)

**S1.1 · Compare the options against our requirements** · S · ✅ · [#9](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/9)
*As an architect, I want options scored against R1–R6, cost and operating burden, so that the choice is explainable.*
- [x] At least four options: Secrets Manager, Parameter Store, Vault, Kubernetes Secrets.
- [x] Criteria tied to requirements; scores with reasons.

Evidence: [ADR-001](02-adr-001-secrets-manager-selection.md)

**S1.2 · Decide and record the consequences** · S · ✅ · [#10](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/10)
*As a tech lead, I want the decision and its trade-offs written down, so that future teams know when to revisit it.*
- [x] Decision and consequences, good and bad.
- [x] Conditions under which Vault would win.

Evidence: [ADR-001](02-adr-001-secrets-manager-selection.md)

### F1.2 · Team enablement on the pattern · ✅ · [#11](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/11)

**S1.3 · Learning brief: retrieval pattern and JWT workload identity** · M · ✅ · [#12](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/12)
*As a junior engineer, I want the retrieval pattern explained across products, and how JWT workload identity works, so that I can apply it on any stack.*
- [x] The seven-step pattern mapped to AWS, Vault, Azure Key Vault and Google Secret Manager.
- [x] JWT claims and the token exchange, with the places this repo uses it.

Evidence: [chapter 1: Secrets managers](../learn/01-secrets-managers.md), [chapter 3: Why a secrets manager](../learn/03-why-a-secrets-manager.md)

## E2 — Application changes: consume secrets at runtime

[#13](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/13) · ✅ · **Outcome:** The app fetches, caches, refreshes and redacts its secrets; config holds names only. Docs: [chapter 4: Secure Notes, before and after](../learn/04-secure-notes-app.md), [chapter 6: Request flows](../learn/06-request-flows.md)

**F2.1 · Configuration holds no secrets** · S · ✅ · [#14](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/14)
*As an operator, I want the app to refuse to start if a credential is in its environment, so that nobody "fixes" an outage by pasting a password in.*
- [x] `DB_PASSWORD`, `PGPASSWORD`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `REDIS_URL`, `REDISCLI_AUTH` set → exit 78.
- [x] In production also static AWS keys, demo mode, a mock endpoint, or the reveal flag.

Evidence: [backend/src/config.js](../../backend/src/config.js), [test case 8](../../demo/test-case-08-reveal-refused-in-production.md)

**F2.2 · Fetch with the platform identity (SDK or agent)** · M · ✅ · [#15](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/15)
*As a developer, I want one fetch interface over the AWS SDK and the local agent, so that the deployment can choose without code changes.*
- [x] SDK mode: `GetSecretValue` with the default credential chain.
- [x] Agent mode: `localhost:2773` with the agent's SSRF token.

Evidence: [backend/src/secrets/fetchers.js](../../backend/src/secrets/fetchers.js)

**F2.3 · Cache secrets safely** · M · ✅ · [#16](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/16)
*As an SRE, I want few API calls and resilience to a brief outage, so that Secrets Manager is not on every request's path.*
- [x] TTL with ±10% jitter.
- [x] Concurrent misses share one call (single-flight).
- [x] The last good value is served if a refresh fails.

Evidence: [backend/src/secrets/provider.js](../../backend/src/secrets/provider.js), [backend/test/secrets.test.js](../../backend/test/secrets.test.js)

**F2.4 · Rotation without restart** · M · ✅ · [#17](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/17)
*As an SRE, I want the app to recover by itself when a password rotates, so that rotation can run on a schedule.*
- [x] Given the password rotated, when a new connection fails with `28P01` or `WRONGPASS`, then the app refreshes once, retries, and the request succeeds.

Evidence: [backend/src/clients/](../../backend/src/clients/), [backend/test/redis-rotation.test.js](../../backend/test/redis-rotation.test.js), [test case 2](../../demo/test-case-02-rotate-postgres.md), [test case 3](../../demo/test-case-03-rotate-redis.md)

**F2.5 · No secret in logs or API responses** · M · ✅ · [#18](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/18)
*As a security engineer, I want every log line and response scrubbed, so that a secret can't leak through an error message.*
- [x] `SecretValue` prints `[REDACTED]`; key- and value-based redaction of every line.
- [x] The leak test finds no value in logs or responses.

Evidence: [backend/src/secrets/redactor.js](../../backend/src/secrets/redactor.js), [test case 4](../../demo/test-case-04-leak-test.md)

**F2.6 · Masked debug logging and a lab-only reveal flag** · S · ✅ · [#19](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/19)
*As an operator, I want to see which secret and keys were used without seeing values, so that I can debug safely.*
- [x] Debug lines show secret ID, version and keys, passwords fully masked.
- [x] `LOG_REVEAL_SECRETS=true` prints values to stdout only, is flagged on the dashboard, and is refused in production.

Evidence: [backend/src/secrets/mask.js](../../backend/src/secrets/mask.js), [test case 5](../../demo/test-case-05-debug-log.md), [test case 7](../../demo/test-case-07-reveal-flag.md)

**F2.7 · Agent mode** · S · ✅ · [#20](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/20)
*As a platform engineer, I want the app to read through the AWS Workload Credentials Provider, so that the app needs no AWS SDK credentials of its own where the agent runs.*
- [x] Reads with the agent's SSRF token (a local file that proves the caller is on the host, so a forged request can't reach the agent); forces a refresh after an auth failure, because the agent's cache doesn't see rotation.

Evidence: [docker-compose.agent.yml](../../docker-compose.agent.yml), [test case 9](../../demo/test-case-09-agent-mode.md)

**F2.8 · Secret naming convention /{service}/{env}/{resource}/{name}** · M · ✅ · [#21](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/21)
*As a platform engineer, I want secret names built from one pattern, so that environments differ by one setting and IAM can grant by path.*
- [x] Given `SECRETS_ENV=prod` and `REDIS_SECRET_RESOURCE=secure-notes`, the app reads `/elasticache/prod/secure-notes/app`; presets and custom patterns.
- [x] An explicit `*_SECRET_ID` wins (the `rds!…` secret RDS names itself).
- [x] Settings from env vars, `config.yaml`, `config.json` or `config.env`; a config file holding a credential is refused; an unknown environment or token stops startup.
- [x] Compose, kind and the CloudFormation stack use it; the seed job and the app share one resolver.

Evidence: [backend/src/secrets/naming.js](../../backend/src/secrets/naming.js), [backend/test/naming.test.js](../../backend/test/naming.test.js), [secret naming reference](../reference/secret-naming.md)

## E3 — Platform and infrastructure on AWS

[#22](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/22) · ✅ · **Outcome:** Identity without keys, a private network path, customer-managed encryption and managed rotation. Docs: [infra/cloudformation.yaml](../../infra/cloudformation.yaml), [GUIDE](../GUIDE.md)

**F3.1 · Identity without keys** · S · ✅ · [#23](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/23)
*As a security engineer, I want workloads to use platform identity, so that there is no key to steal.*
- [x] EC2 instance role; IMDSv2 required, hop limit 1.
- [x] IRSA on EKS/ROSA; GitHub OIDC for CI.

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml), [infra/irsa-trust-policy.example.json](../../infra/irsa-trust-policy.example.json)

**F3.2 · Private network path to Secrets Manager** · S · ✅ · [#24](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/24)
*As a network engineer, I want secret requests to stay inside AWS, so that they can't be intercepted or exfiltrated over the internet.*
- [x] VPC endpoint with an account-only endpoint policy.
- [x] The app role may read only via that endpoint (`aws:SourceVpce`).

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml)

**F3.3 · Encryption at rest and in transit** · S · ✅ · [#25](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/25)
*As a security engineer, I want our own KMS key and TLS everywhere, so that a stolen disk or packet reveals nothing.*
- [x] Customer-managed KMS key; the app and rotation roles may decrypt only via Secrets Manager.
- [x] RDS and ElastiCache encrypted at rest and in transit; RDS certificate verified.

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml), [backend/src/clients/db.js](../../backend/src/clients/db.js)

**F3.4 · Managed credentials and rotation** · M · ✅ · [#26](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/26)
*As a DBA, I want the database and cache passwords created and rotated by AWS, so that no one ever types one.*
- [x] RDS `ManageMasterUserPassword`.
- [x] A generated ElastiCache user secret and a rotation function using the user's two password slots.

Evidence: [infra/rotation/elasticache-user-rotation.js](../../infra/rotation/elasticache-user-rotation.js)

**F3.5 · Kubernetes and OpenShift** · M · ✅ · [#27](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/27)
*As a platform engineer, I want the same images on kind, OpenShift and EKS/ROSA, so that the pattern isn't EC2-specific.*
- [x] Kustomize overlays; Pod Security restricted.
- [x] No Kubernetes Secret holds an app credential.

Evidence: [deploy/k8s/](../../deploy/k8s/), [test case 10](../../demo/test-case-10-kubernetes.md)

## E4 — Security hardening

[#28](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/28) · 🔜 · **Outcome:** Gaps found in the system design review are closed: who may read, detection, compliance, least privilege, resilience. Docs: [chapter 5: System design review](../learn/05-system-design.md)

### F4.1 · Restrict who can read each secret · 🔜 · [#29](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/29)

**S4.1 · Resource policy on the Redis secret** · S · ✅ built · 🔎 verify on AWS · [#30](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/30)
*As a security engineer, I want only the app, its rotation function and a named break-glass role to read the secret, so that a broadly privileged admin or a misconfigured role can't.*
- [x] Deny `GetSecretValue` to every other principal; deny the app outside the VPC endpoint.
- [x] `BlockPublicPolicy` on; created after the cache user so the stack's own read succeeds.
- [ ] On AWS: a stack update that touches the cache user still succeeds; a read by another admin role is denied.

Evidence: `RedisSecretPolicy` in [infra/cloudformation.yaml](../../infra/cloudformation.yaml), parameter `SecretAdminRoleArn`

**S4.1b · Resource policy on the RDS-managed secret** · S · 🔜 · [#31](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/31)
*As a security engineer, I want the same deny on the `rds!` secret, so that both credentials have the same protection.*
- [ ] Prove on AWS that a resource policy on the `rds!` secret leaves RDS managed rotation working.
- [ ] Then add the same deny.

### F4.2 · Detect misuse and drift · ✅ built · 🔎 verify on AWS · [#33](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/33)

**S4.2 · Alarm on unexpected secret reads** · M · ✅ built · 🔎 verify on AWS · [#34](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/34)
*As an on-call engineer, I want an alert when anyone other than the app or rotation reads a secret, so that misuse is noticed in minutes, not in an audit.*
- [x] EventBridge rule on CloudTrail `GetSecretValue` / `BatchGetSecretValue` for both secrets by any role, user or root other than the app and rotation roles → encrypted SNS, optional email.
- [x] Known gap, documented: the RDS secret is matched by ARN, so a read by name alone is in CloudTrail but not alarmed.
- [x] Optional trail (`CreateTrail=true`) for accounts without one.
- [ ] On AWS: a read from the console raises an email within minutes; the app's reads don't.

Evidence: `SecretReadAlertRule`, `SecretReadAlertTopic` in [infra/cloudformation.yaml](../../infra/cloudformation.yaml)

**S4.3 · AWS Config rules for rotation and IMDSv2** · S · ✅ · [#35](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/35)
*As a compliance owner, I want drift flagged automatically, so that a secret without rotation or an IMDSv1 instance doesn't go unnoticed.*
- [x] `EnableConfigRules=true` adds: rotation enabled, scheduled rotation succeeded, EC2 IMDSv2.

Evidence: `RotationEnabledRule`, `RotationSucceededRule`, `ImdsV2Rule` in [infra/cloudformation.yaml](../../infra/cloudformation.yaml)

### F4.3 · Least privilege, fewer passwords and regional resilience · 🔜 · [#36](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/36)

**S4.4 · Least-privilege database user** · M · 🔜 · [#32](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/32)
*As a DBA, I want the app to log in as a role that owns only its tables, so that a stolen app credential can't administer the database.*
- [ ] A `notes_app` role and its own secret, named by the convention (`/rds/<env>/<db>/app`), rotated with the alternating-users template.
- [ ] The master user is used only by RDS rotation and administrators.

**S4.5 · Spike: IAM authentication for RDS and ElastiCache** · L · 🔜 · [#37](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/37)
*As an architect, I want to know whether we can drop passwords entirely, so that there is nothing left to steal.*
- [ ] Token per new connection; measure the connection rate against RDS limits.
- [ ] ElastiCache: Valkey 7.2+/Redis 7+, reconnect before 12 hours.
- [ ] A recommendation with trade-offs.

**S4.6 · Replica secrets in a second region; tighter egress and KMS policy** · M · 🔜 · [#38](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/38)
*As an SRE, I want secrets available after a regional outage and less room for exfiltration, so that we recover and stay contained.*
- [ ] Replica secrets in a second region.
- [ ] 443 egress limited to VPC endpoints.
- [ ] KMS key administrators named explicitly.

## E5 — Delivery and automation

[#39](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/39) · ✅ · **Outcome:** One build for every platform, a verifiable supply chain and keyless deploys. Docs: [CI reference](../reference/ci.md)

**F5.1 · One build, every platform** · M · ✅ · [#40](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/40)
*As a release engineer, I want the exact tested images published, so that nothing is rebuilt between test and release.*
- [x] The same images on Compose, kind, OpenShift and EC2.

Evidence: [.github/workflows/ci.yaml](../../.github/workflows/ci.yaml)

**F5.2 · Supply chain: SBOM, scan, signing** · M · ✅ · [#41](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/41)
*As a security engineer, I want every image scanned, described and signed, so that a cluster can admit only what CI built.*
- [x] CycloneDX SBOM, grype scan failing on fixable criticals.
- [x] cosign keyless signature and SBOM attestation, verified anonymously.

Evidence: [test case 11](../../demo/test-case-11-supply-chain.md)

**F5.3 · Air-gapped installs** · S · ✅ · [#42](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/42)
*As a platform engineer, I want to copy the images into our own registry, so that clusters without internet can run the app.*
- [x] `scripts/mirror-images.sh` mirrors and verifies layers; generated overlay pulls only from the mirror.

Evidence: [test case 12](../../demo/test-case-12-image-mirror.md)

**F5.4 · Keyless deploys from GitHub Actions** · M · ✅ · [#43](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/43)
*As a release engineer, I want CI to deploy with a short-lived role, so that no AWS key is stored in GitHub.*
- [x] GitHub OIDC to an IAM role scoped to one environment.
- [x] The deploy role can rotate but never read secrets.

Evidence: [.github/workflows/aws.yaml](../../.github/workflows/aws.yaml), [infra/github-actions-bootstrap.yaml](../../infra/github-actions-bootstrap.yaml)

**F5.5 · Automation examples for other teams** · S · ✅ · [#44](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/44)
*As a platform engineer, I want Terraform, Ansible and Kubernetes examples, so that other teams can adopt the pattern with their tools.*
- [x] Terraform (managed RDS password, rotation, write-only values), Ansible lookup, External Secrets and CSI.

Evidence: [chapter 3: Why a secrets manager](../learn/03-why-a-secrets-manager.md)

## E6 — Verification and evidence

[#45](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/45) · ✅ · **Outcome:** Every claim has an automated test that fails if it stops being true. Docs: [TEST-CASES](../TEST-CASES.md), [demo pages](../../demo/README.md)

**F6.1 · Unit tests** · M · ✅ · [#46](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/46)
*As a developer, I want fast tests of the secrets layer, so that regressions show up before deploy.*
- [x] Real `pg`, `ioredis` and AWS SDK clients against fakes; run in CI job `checks`.

Evidence: [backend/test/](../../backend/test/)

**F6.2 · End-to-end walks with screenshots** · M · ✅ · [#47](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/47)
*As a reviewer, I want each run to photograph the dashboard and assert what it must show, so that evidence is automatic.*
- [x] Dashboard walk, smoke test and leak test on Compose (both modes) and kind.

Evidence: [demo pages](../../demo/README.md)

**F6.3 · Credential scan** · M · ✅ · [#48](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/48)
*As a security engineer, I want the running stack searched for the real values, so that "no credential anywhere" is proven, not assumed.*
- [x] Searches every container, file, log and Kubernetes object; self-tests with the reveal flag on.

Evidence: [test case 6](../../demo/test-case-06-credential-scan.md)

## E7 — Documentation and enablement

[#49](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/49) · ✅ · **Outcome:** A learning path a junior engineer can follow, and docs that CI keeps correct. Docs: [Learning path](../learn/README.md), [README.md](../../README.md)

### F7.1 · Learning path · ✅ · [#50](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/50)

**S7.1 · Chapters 1–6** · M · ✅ · [#51](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/51)
*As a junior engineer, I want a short, ordered set of chapters, so that I understand the design from first principles to the code.*
- [x] Each chapter: what you'll learn, diagrams, sources, next link.

Evidence: [Learning path](../learn/README.md)

**S7.3 · Request-flow diagrams matched to the code** · S · ✅ · [#52](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/52)
*As a developer, I want sequence diagrams that name the file for each step, so that I can read the code next to them.*
- [x] Startup, rotation recovery and log masking flows.

Evidence: [chapter 6: Request flows](../learn/06-request-flows.md)

### F7.2 · Navigation and docs quality · ✅ · [#53](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/53)

**S7.2 · README as the landing page** · S · ✅ · [#54](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/54)
*As a newcomer, I want the README to tell the story and point to the right document, so that I don't read 300 lines to find my path.*
- [x] Problem, story, run, see it work, reference.
- [x] Reference material moved to `docs/reference/` without loss.

Evidence: [README.md](../../README.md), [security controls](../reference/security-controls.md)

**S7.4 · CI keeps the docs correct** · S · ✅ · [#55](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/55)
*As a maintainer, I want broken links and diagrams to fail the build, so that the docs can't rot silently.*
- [x] Every relative link and anchor resolves.
- [x] Every Mermaid diagram renders.

Evidence: [scripts/docs-check.js](../../scripts/docs-check.js), CI job `docs`

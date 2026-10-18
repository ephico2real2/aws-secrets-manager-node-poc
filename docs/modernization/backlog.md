# Backlog — epics, features and stories

[← Initiative](README.md) · [Source review](01-source-review.md) · [ADR-001](02-adr-001-secrets-manager-selection.md) · [GitHub issues](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atype%3Aepic)

**How to read it:** an **epic** is an outcome; a **feature** is a capability; a **story** is
one deliverable with acceptance criteria (each one testable). Size: S ≤ 1 day, M ≤ 3
days, L ≤ 1 week. Status: ✅ done, with evidence · 🔎 built, to verify on AWS · 🔜 to do.

Every item is also a GitHub issue (linked as #N), with sub-issues for the hierarchy and
labels `app|tutorial`, `type:epic|feature|story`, `epic:E0…E7`, `size:S|M|L` and
`needs-aws-verification`.

**Two tracks.** Issue titles start with the track, so the two kinds of work never mix:

| Track | Prefix and label | What it is | Epics |
| --- | --- | --- | --- |
| **APP** | `APP:` · [`app`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Aapp) | The modernization itself: what a team does to move an app from `.env` passwords to a secrets manager | E0–E6, E8–E12 (E15 parked) |
| **TUTORIAL** | `TUTORIAL:` · [`tutorial`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atutorial) | Building this tutorial about it: learning path, guide, demos, version folders | E7, E13–E14 |

Done items are closed with their evidence. This page and the issues are generated from
the same list, so they say the same thing.

Order: see the [epic map](README.md#how-the-work-is-organized). E0 then E1; E2 and E3 after
E1; E4, E5 and E6 in parallel once E3 is in place; E7 throughout. A small feature with
one deliverable is written as its own story (persona and acceptance criteria) rather
than split into stories.

## Track APP — modernizing the app

### E0 — Discovery: review the initial source code

[#1](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/1) · ✅ · **Outcome:** The initial `.env`-based design is reviewed, its risks ranked, and requirements R1–R6 written. Docs: [Source review](01-source-review.md)

#### F0.1 · Source review of the initial design · ✅ · [#2](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/2)

**S0.1 · Inventory every credential and where it lives** · S · ✅ · [#3](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/3)
*As a security engineer, I want a list of every credential and every place it lives, so that the redesign covers all of them.*
- [x] Each credential, its locations, who can read it, rotation and audit status are tabulated.

Evidence: [Source review §2](01-source-review.md)

**S0.2 · Threat-model the .env approach** · S · ✅ · [#4](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/4)
*As a security engineer, I want the findings ranked by severity, so that we fix the worst first.*
- [x] Findings F1–F7 with severity.
- [x] Requirements R1–R6 derived from them.

Evidence: [Source review §3–4](01-source-review.md)

### E1 — Select a secrets management tool for AWS

[#7](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/7) · ✅ · **Outcome:** A recorded decision, with criteria, scores, consequences and the conditions that would reverse it. Docs: [ADR-001](02-adr-001-secrets-manager-selection.md)

#### F1.1 · ADR-001: choose the secrets manager · ✅ · [#8](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/8)

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

### E2 — Application changes: consume secrets at runtime

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

### E3 — Platform and infrastructure on AWS

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

### E4 — Security hardening

[#28](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/28) · 🔜 · **Outcome:** Gaps found in the system design review are closed: who may read, detection, compliance, least privilege, resilience. Docs: [chapter 5: System design review](../learn/05-system-design.md)

#### F4.1 · Restrict who can read each secret · 🔜 · [#29](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/29)

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

#### F4.2 · Detect misuse and drift · ✅ built · 🔎 verify on AWS · [#33](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/33)

**S4.2 · Alarm on unexpected secret reads** · M · ✅ built · 🔎 verify on AWS · [#34](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/34)
*As an on-call engineer, I want an alert when anyone other than the app or rotation reads a secret, so that misuse is noticed in minutes, not in an audit.*
- [x] EventBridge rule on CloudTrail `GetSecretValue` / `BatchGetSecretValue` for both secrets by any role, user or root other than the app and rotation roles → encrypted SNS, optional email.
- [x] Known gap, documented: the RDS secret is matched by ARN, so a read by name alone is in CloudTrail but not alarmed.
- [x] Optional trail (`CreateTrail=true`) for accounts without one.
- [ ] On AWS: a read from the console raises an email within minutes; the app's reads don't.
- [x] The topic uses a customer-managed KMS key: EventBridge and CloudWatch alarms can't publish to a topic encrypted with `alias/aws/sns` (fixed by S12.1).
- [x] The rule has `State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`; without it EventBridge never delivers read-only events such as `GetSecretValue` (fixed by S11.4).

Evidence: `SecretReadAlertRule`, `SecretReadAlertTopic` in [infra/cloudformation.yaml](../../infra/cloudformation.yaml)

**S4.3 · AWS Config rules for rotation and IMDSv2** · S · ✅ · [#35](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/35)
*As a compliance owner, I want drift flagged automatically, so that a secret without rotation or an IMDSv1 instance doesn't go unnoticed.*
- [x] `EnableConfigRules=true` adds: rotation enabled, scheduled rotation succeeded, EC2 IMDSv2.

Evidence: `RotationEnabledRule`, `RotationSucceededRule`, `ImdsV2Rule` in [infra/cloudformation.yaml](../../infra/cloudformation.yaml)

#### F4.3 · Least privilege, fewer passwords and regional resilience · 🔜 · [#36](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/36)

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

### E5 — Delivery and automation

[#39](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/39) · 🔜 · **Outcome:** One build for every platform, a verifiable supply chain and keyless deploys. Docs: [CI reference](../reference/ci.md)

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

#### F5.6 · Local labs on any laptop: kind and OpenShift Local · 🔜 · [#116](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/116)

**S5.1 · kind cluster: pinned, port-mapped, checked first** · S · ✅ · [#117](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/117)
*As a developer, I want `scripts/kind-up.sh` to build the same cluster on my Mac and in CI, and to open the app without a port-forward, so that the lab just works.*
- [x] `deploy/kind/cluster.yaml` pins the node image by digest (amd64 and arm64) and maps the app and the console to 127.0.0.1:3000 and :4575 through NodePorts.
- [x] `scripts/preflight.sh` checks bash, Docker and its memory, kind and the node image, kubectl's skew, Node.js and free ports; `kind-up.sh` runs it strictly.
- [x] CI's kind job runs the same scripts, reaches both ports with no port-forward, and exports kind's logs on failure.

Evidence: [deploy/kind/cluster.yaml](../../deploy/kind/cluster.yaml), [scripts/preflight.sh](../../scripts/preflight.sh), [scripts/kind-up.sh](../../scripts/kind-up.sh), CI job `kind`

**S5.2 · Bootstrap a MacBook and a Linux machine** · S · ✅ · [#118](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/118)
*As a new contributor, I want one command to install what the lab needs, so that I don't assemble the toolchain by hand.*
- [x] `scripts/bootstrap/linux.sh`: kind at its pin, checked against the release's SHA-256; kubectl if missing; used by CI.
- [x] `scripts/bootstrap/macos.sh`: Homebrew formulae and Docker Desktop, then the preflight; changes no settings.
- [x] Run end to end on a real MacBook: Compose and kind. Done on Podman (Apple silicon, Podman 6.1.2, rootless, 4 CPUs, 4 GiB): `compose-check.sh` and `k8s-check.sh` passed; the machine used 1582 MiB of 3887 with kind.
- [x] `macos.sh --podman`: Podman Desktop and a 4 GiB machine instead of Docker Desktop; the preflight names the engine, points the docker CLI at Podman's socket (`DOCKER_HOST`) and kind at Podman (`KIND_EXPERIMENTAL_PROVIDER`).
- [x] PyYAML for `sync-event-pattern.py` in `.tmp/venv` at the CI pin (Homebrew's Python refuses `pip install --user`).

Evidence: [scripts/bootstrap/macos.sh](../../scripts/bootstrap/macos.sh), [scripts/bootstrap/linux.sh](../../scripts/bootstrap/linux.sh), [test case 10: the lab on Podman](../../demo/test-case-10-kubernetes.md), [GUIDE B1: Podman instead of Docker](../GUIDE.md)

**S5.3 · OpenShift: Routes for the app and the console; images built on the cluster** · M · 🔜 · [#119](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/119)
*As an OpenShift user, I want to open the app and the notification console through Routes, and to build the images on the cluster, so that the lab runs on OpenShift Local on any Mac.*
- [x] Routes `secure-notes` and `sns-logger` (edge TLS); a NetworkPolicy lets the router reach the console; `k8s-deploy.sh` points the console link at its Route.
- [x] `overlays/openshift-local` with `scripts/openshift-build.sh`: BuildConfigs build both images from HEAD for the cluster's CPU; image lookup resolves the short names.
- [ ] Run on OpenShift Local (CRC) end to end, including `k8s-check.sh` (the owner: CI has no OpenShift).

Evidence: [deploy/k8s/overlays/openshift/console-route.yaml](../../deploy/k8s/overlays/openshift/console-route.yaml), [scripts/openshift-build.sh](../../scripts/openshift-build.sh)

### E6 — Verification and evidence

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

### E8 — Structured logs with alert events

[#58](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/58) · ✅ · **Outcome:** Every security-relevant log line carries a catalogued event name; logs ship in the OpenTelemetry format without ever carrying a secret; humans get a readable format. Docs: [plan E8–E15](plan-e8-e15.md)

#### F8.1 · Alert events and the catalogue · ✅ · [#59](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/59)

**S8.1 · Event fields at every alert-worthy call site, from one catalogue** · M · ✅ · [#60](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/60)
*As an on-call engineer, I want every alert-worthy log line to carry a stable event name, so that alert rules match names, not message text.*
- [x] `backend/src/alerts/catalogue.js` lists each event: severity, source, channels, dedup, runbook.
- [x] Call sites add an `event` field only; messages unchanged; the leak test's simulated lines carry no event.
- [x] A test fails if code uses an event that isn't in the catalogue.

Evidence: [backend/src/alerts/catalogue.js](../../backend/src/alerts/catalogue.js), [backend/test/logging.test.js](../../backend/test/logging.test.js)

#### F8.2 · Ship logs in the OpenTelemetry format · ✅ · [#61](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/61)

**S8.2 · OTLP shipper after redaction** · M · ✅ · [#62](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/62)
*As a platform engineer, I want logs pushed to a collector in the OpenTelemetry format, so that any log store (VictoriaLogs locally, CloudWatch Logs on AWS) can receive them.*
- [x] Hooked inside `emit()` after redaction: a registered value ships as `[REDACTED]`; `revealUnsafe` lines are never shipped.
- [x] Bounded buffer, oldest dropped first; the shipper never logs through itself.
- [x] OTLP mapping: Timestamp, SeverityNumber, Body, EventName, Attributes, Resource `service.name`.

Evidence: [backend/src/logship/otlp.js](../../backend/src/logship/otlp.js), [backend/src/log.js](../../backend/src/log.js)

**S8.3 · Readable log format for humans** · S · ✅ · [#63](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/63)
*As a developer, I want `LOG_FORMAT=pretty`, so that I can read logs in a terminal.*
- [x] One line per record: time, level, component, message, key=value fields.
- [x] Refused in production; the JSON format stays the default and the ring buffer stays JSON.

Evidence: [backend/src/logfmt.js](../../backend/src/logfmt.js)

**S8.4 · An alarm can't be lost or misfire because of its log line** · S · ✅ · [#112](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/112)
*As an on-call engineer, I want every line an alarm depends on to reach the log store, and no line to page for nothing, so that I can trust the pages I get.*
- [x] The file sink writes synchronously: the `config.unsafe` line is on disk before the process exits; write errors are counted and shown by a posture check.
- [x] Startup retries log no alert event; only `secrets.load.fatal` pages. An agent 403 is reported at once, even while a cached value is served.
- [x] `secrets.reveal.enabled` alerts only when the flag has an effect (debug); a forced refresh that fails says whether a cached value is still served.
- [x] A unit test scans every dotted string literal: each event the code uses is catalogued, and each catalogued alert is emitted.

Evidence: [backend/src/logship/file.js](../../backend/src/logship/file.js), [backend/src/secrets/provider.js](../../backend/src/secrets/provider.js), [backend/test/logging.test.js](../../backend/test/logging.test.js)

### E9 — Notifications through SNS, and a local SNS console

[#64](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/64) · ✅ · **Outcome:** The app can notify through Amazon SNS; locally an SNS-compatible sns-logger shows each email, SMS and webhook delivery on a screen like the dashboard. Docs: [plan E8–E15](plan-e8-e15.md)

#### F9.1 · sns-logger: a local Amazon SNS · ✅ · [#65](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/65)

**S9.1 · SNS API subset (Query protocol)** · L · ✅ · [#66](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/66)
*As a developer, I want an SNS endpoint on my laptop, so that the app, Alertmanager and the alarm simulation publish exactly as they would to AWS.*
- [x] CreateTopic, ListTopics, Get/SetTopicAttributes, Subscribe, ConfirmSubscription, Unsubscribe, ListSubscriptions(ByTopic), Publish.
- [x] Validation like SNS: subject < 100 chars without line breaks, `default` key with MessageStructure=json, 256 KiB, SMS 1600 bytes.
- [x] Deliveries per subscription protocol (email, sms, https), logged with masked endpoints.

Evidence: [dev/aws-mock/lib/sns.js](../../dev/aws-mock/lib/sns.js), [dev/aws-mock/sns-logger/server.js](../../dev/aws-mock/sns-logger/server.js), [dev/aws-mock/test/mock.test.js](../../dev/aws-mock/test/mock.test.js)

**S9.2 · sns-logger screen** · M · ✅ · [#67](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/67)
*As a presenter, I want the deliveries shown as an inbox, a phone and a chat feed, so that the audience sees what on-call would receive.*
- [x] Email like 'AWS Notifications <no-reply@sns.amazonaws.com>' with the unsubscribe footer; SMS bubbles with segments; webhook JSON and chat card; topics.
- [x] Strict CSP, same look as the dashboard; works on Compose and kind.

Evidence: [sns-logger screen](../../dev/aws-mock/sns-logger/ui/index.html)

#### F9.2 · App notifier · ✅ · [#68](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/68)

**S9.3 · Publish notifications from the app** · M · ✅ · [#69](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/69)
*As an operator, I want the app to send a notification when it recovers from a rotation, and a test alert on demand, so that I know the alert path works.*
- [x] `@aws-sdk/client-sns`, topic from `SNS_TOPIC_ARN`; a mock endpoint is refused in production.
- [x] MessageStructure=json with email, sms and https bodies; dedup and rate limit.
- [x] An 'alert sent' log line with OpenTelemetry messaging fields and the SNS MessageId.

Evidence: [backend/src/alerts/notifier.js](../../backend/src/alerts/notifier.js), [scripts/alerts-check.sh](../../scripts/alerts-check.sh)

**S9.4 · Mask recipients everywhere** · S · ✅ · [#70](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/70)
*As a privacy officer, I want email addresses and phone numbers masked in logs and screens, so that alerting doesn't spread personal data.*
- [x] `maskEmail` → `on***@example.com`, `maskPhone` → `+1******0100`, shared by the app and the mock.

Evidence: [backend/src/alerts/recipients.js](../../backend/src/alerts/recipients.js)

**S9.5 · Harden the local SNS console** · S · ✅ · [#113](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/113)
*As a security engineer, I want the dev-only console unusable from a web page and free of full recipients, so that running it on a laptop is safe.*
- [x] `ListSubscriptions(ByTopic)` return masked endpoints; `alerts-check.sh` checks them.
- [x] Every response carries the security headers; attribute keys are escaped.
- [x] POSTs must be SigV4-signed and carry no `Origin`, so a cross-site form can't drive the API.
- [x] The test alert is limited to one a minute (it pages by SMS).

Evidence: [dev/aws-mock/sns-logger/server.js](../../dev/aws-mock/sns-logger/server.js), [scripts/alerts-check.sh](../../scripts/alerts-check.sh)

### E10 — Local log pipeline: OpenTelemetry, VictoriaLogs, vmalert, Alertmanager

[#71](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/71) · 🔜 · **Outcome:** Logs first, then alerts, locally: the same shape as CloudWatch Logs, metric filters, alarms and SNS on AWS. Docs: [plan E8–E15](plan-e8-e15.md)

#### F10.1 · Log store and rules · 🔜 · [#72](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/72)

**S10.1 · OpenTelemetry Collector and VictoriaLogs overlay** · M · ✅ · [#73](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/73)
*As a developer, I want `docker-compose.observability.yml` to run a collector and VictoriaLogs, so that I can search every service's logs.*
- [x] App, aws-mock and sns-logger records arrive in VictoriaLogs (OTLP), browsable in vmui.
- [x] Works with Docker and Podman (no logging-driver dependency).

Evidence: [docker-compose.observability.yml](../../docker-compose.observability.yml), [deploy/observability/otel-collector.yaml](../../deploy/observability/otel-collector.yaml)

**S10.2 · Alert rules generated from the catalogue** · M · ✅ · [#74](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/74)
*As an on-call engineer, I want the local rules and the AWS metric filters generated from one list, so that they can't disagree.*
- [x] `scripts/sync-alert-rules.js --check` writes the vmalert rules, the CloudFormation block and the docs table.
- [x] CI fails if any of them is stale.

Evidence: [scripts/sync-alert-rules.js](../../scripts/sync-alert-rules.js), [deploy/observability/vmalert-rules.yaml](../../deploy/observability/vmalert-rules.yaml)

**S10.3 · Alertmanager publishes to SNS** · S · ✅ · [#75](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/75)
*As an on-call engineer, I want alerts routed to SNS, so that the same subscriptions receive them.*
- [x] `sns_configs` with `api_url` → sns-logger, dummy SigV4 keys; an email template like a CloudWatch alarm email.

Evidence: [deploy/observability/alertmanager.yml](../../deploy/observability/alertmanager.yml)

**S10.5 · Pipeline check covers the chat route and a pattern rule** · S · 🔜 · [#114](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/114)
*As an on-call engineer, I want CI to prove a warning reaches chat only, so that the second route is as tested as the first.*
- [ ] Trigger `app.errors.burst` (or `secrets.fetch.stale`) in CI; assert one chat delivery and no page.

Evidence: [plan E8–E15](plan-e8-e15.md)

**S10.4 · Pipeline pane in sns-logger** · S · ✅ · [#76](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/76)
*As a presenter, I want to see log lines arrive and turn into alerts, so that the whole path is visible.*
- [x] A live tail from VictoriaLogs, correlated with deliveries by MessageId; says 'not deployed' without the overlay.

Evidence: [scripts/pipeline-check.sh](../../scripts/pipeline-check.sh)

### E11 — Detection lab: the unexpected-read alarm, end to end on a laptop

[#77](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/77) · ✅ · **Outcome:** A button reads a secret as an intruder; the local CloudTrail, EventBridge rule and SNS deliver the alert, using the same rule as the AWS stack. Docs: [plan E8–E15](plan-e8-e15.md)

#### F11.1 · Local CloudTrail and EventBridge · ✅ · [#78](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/78)

**S11.1 · Callers have identities; reads are audited** · M · ✅ · [#79](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/79)
*As a security engineer, I want each local caller to have its own identity and every read recorded like CloudTrail, so that detection can be tested without AWS.*
- [x] Access keys map to the app role, the seed/deployer, an intruder user and an intruder role; unsigned tooling matches no alarm branch.
- [x] CloudTrail-shaped records for GetSecretValue and BatchGetSecretValue, never containing a value.

Evidence: [dev/aws-mock/lib/principals.js](../../dev/aws-mock/lib/principals.js), [dev/aws-mock/lib/cloudtrail.js](../../dev/aws-mock/lib/cloudtrail.js)

**S11.2 · EventBridge pattern evaluator fed by the stack's own rule** · M · ✅ · [#80](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/80)
*As a security engineer, I want the local alarm to use the exact rule from `infra/cloudformation.yaml`, so that a rule that can't fire on AWS can't fire locally either.*
- [x] `scripts/sync-event-pattern.py --check` extracts EventPattern, State and InputTransformer.
- [x] Operators: exact, arrays, nesting, $or, anything-but, prefix, exists; arrays of objects are flattened; unknown operators and malformed arguments fail.
- [x] The rule matches the Redis secret by name, full ARN and partial ARN (a prefix), and names the secret of a batch read.

Evidence: [dev/aws-mock/lib/event-pattern.js](../../dev/aws-mock/lib/event-pattern.js), [scripts/sync-event-pattern.py](../../scripts/sync-event-pattern.py), [dev/aws-mock/rules/secret-read-alert.json](../../dev/aws-mock/rules/secret-read-alert.json)

**S11.3 · Simulate an unexpected read from the dashboard** · S · ✅ · [#81](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/81)
*As a presenter, I want a button that reads a secret as an intruder, so that the audience sees the alert arrive.*
- [x] Demo-only route with its own intruder client; returns IDs only.
- [x] A read of the RDS secret by name shows the documented gap: audited, not alarmed.

Evidence: [backend/src/routes.js](../../backend/src/routes.js), [dashboard: Detection lab](../../frontend/index.html)

**S11.4 · Fix the rule state so read-only events are delivered** · S · ✅ · [#82](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/82)
*As a security engineer, I want the AWS rule to receive read-only management events, so that S4.2 can actually fire.*
- [x] `State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` on `SecretReadAlertRule`; the local evaluator enforces it.

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml), [chapter 7: Alerts and audit](../learn/07-alerts-and-audit.md)

**S11.5 · Detection lab on kind** · S · ✅ · [#83](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/83)
*As a platform engineer, I want sns-logger and the simulated alarm on Kubernetes too, so that the demo works on every path.*
- [x] sns-logger Deployment and Service, NetworkPolicies, k8s-check assertions.

Evidence: [deploy/k8s/components/local-backing-services/sns-logger.yaml](../../deploy/k8s/components/local-backing-services/sns-logger.yaml), [scripts/k8s-check.sh](../../scripts/k8s-check.sh)

### E12 — Logging and alerting on AWS

[#84](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/84) · 🔜 · **Outcome:** On AWS: journald → CloudWatch Logs → metric filters → alarms → SNS, and CloudTrail → EventBridge → SNS, on topics that can actually receive them. Docs: [plan E8–E15](plan-e8-e15.md)

#### F12.1 · Topics, keys and subscriptions · ✅ built · 🔎 verify on AWS · [#85](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/85)

**S12.1 · Customer-managed key for the alert topics** · S · ✅ built · 🔎 verify on AWS · [#86](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/86)
*As a security engineer, I want the alert topics encrypted with our own key that EventBridge and CloudWatch may use, so that alarms are delivered.*
- [x] `AlertsKey`; `SecretReadAlertTopic` and a new `OpsAlertsTopic` use it.
- [x] Subscriptions from `AlertEmail`, `AlertPhone`, `AlertWebhookUrl`.
- [ ] Verified on a real AWS account (S12.5).

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml), [chapter 7: Alerts and audit](../learn/07-alerts-and-audit.md)

**S12.4 · IAM, endpoints and app settings** · S · ✅ built · 🔎 verify on AWS · [#87](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/87)
*As a platform engineer, I want the app allowed to publish and to ship logs, privately, so that alerting doesn't widen access.*
- [x] AppRole: `sns:Publish` on the ops topic only; optional SNS and Logs endpoints; `SNS_TOPIC_ARN` in app.env.
- [x] Bootstrap role can read the evidence (metrics, log events, TestEventPattern).
- [ ] Verified on a real AWS account (S12.5).

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml)

#### F12.2 · Logs to CloudWatch, alarms from logs · 🔜 · [#88](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/88)

**S12.2 · CloudWatch agent ships the app's log file** · M · ✅ built · 🔎 verify on AWS · [#89](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/89)
*As an operator, I want the app's logs in CloudWatch Logs, so that they survive the instance and can raise alarms.*
- [x] The app writes its redacted JSON lines to `LOG_FILE` synchronously, so the line explaining an exit is never lost.
- [x] Set up before the app starts, only with `EnableCloudWatchLogs=true`; 30-day log group; logrotate timer enabled.
- [ ] Verified on a real AWS account (S12.5).

Evidence: [infra/cloudformation.yaml](../../infra/cloudformation.yaml), [backend/src/logship/file.js](../../backend/src/logship/file.js), [infra/systemd/secure-notes.service](../../infra/systemd/secure-notes.service)

**S12.3 · Metric filters and alarms generated from the catalogue** · M · ✅ built · 🔎 verify on AWS · [#90](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/90)
*As an on-call engineer, I want each catalogued event to raise a CloudWatch alarm, so that AWS alerts match the local ones.*
- [x] One filter and alarm per catalogued alert; ALARM pages (critical) or posts to chat (warning); OK goes to chat; missing data is not breaching.
- [ ] Verified on a real AWS account (S12.5).

Evidence: [scripts/sync-alert-rules.js](../../scripts/sync-alert-rules.js), [alert catalogue](../reference/alerts.md)

**S12.5 · Prove it on AWS** · M · 🔜 · [#91](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/91)
*As a reviewer, I want the manual AWS workflow to prove both alert paths, so that 'built' becomes 'verified'.*
- [ ] A denied read by the deploy role publishes to the secret-read topic.
- [ ] A test log event trips an alarm.
- [ ] TestEventPattern fixtures match the mock.
- [ ] A batch read's alert text names the secret (`secretIdList[0]` in the InputTransformer).

Evidence: [plan E8–E15](plan-e8-e15.md)

**S12.6 · Close the by-name gap for the RDS-managed secret** · S · 🔜 · [#115](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/115)
*As a security engineer, I want a read of the RDS secret by name or partial ARN to alarm too, so that the documented gap goes away.*
- [ ] Check on AWS whether Secrets Manager's CloudTrail records carry `resources[].ARN`; if so, match on it.
- [ ] The mock records `resources` the same way; the detection lab's gap button then alarms.

Evidence: [plan E8–E15](plan-e8-e15.md)

## Track TUTORIAL — building the tutorial

### E7 — Tutorial: learning path, guides and demos

[#49](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/49) · ✅ · **Outcome:** Everything that teaches the design rather than changes the app: the learning path, the live .env demo, the deployment guide, the tutorial and the demo pages, kept correct by CI. Docs: [Learning path](../learn/README.md), [README.md](../../README.md)

#### F7.1 · Learning path · ✅ · [#50](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/50)

**S7.1 · Chapters 1–6** · M · ✅ · [#51](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/51)
*As a junior engineer, I want a short, ordered set of chapters, so that I understand the design from first principles to the code.*
- [x] Each chapter: what you'll learn, diagrams, sources, next link.

Evidence: [Learning path](../learn/README.md)

**S7.3 · Request-flow diagrams matched to the code** · S · ✅ · [#52](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/52)
*As a developer, I want sequence diagrams that name the file for each step, so that I can read the code next to them.*
- [x] Startup, rotation recovery and log masking flows.

Evidence: [chapter 6: Request flows](../learn/06-request-flows.md)

#### F7.2 · Navigation and docs quality · ✅ · [#53](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/53)

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

#### F7.3 · Live proof of the .env problem · ✅ · [#5](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/5)

**S7.5 · Prove F1 with a live Podman demo** · S · ✅ · [#6](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/6)
*As an engineer, I want to see a `.env` password read out of a running container, so that the risk is concrete, not theoretical.*
- [x] Given a container started with `--env-file --rm -d`, when I run `exec env`, `/proc/1/environ`, `inspect` or read `/proc/PID/environ` on the host, then the password appears.
- [x] The same lookups on Secure Notes show secret IDs only.
- [x] CI runs it on every push and fails if the generic password is *not* readable.

Evidence: [scripts/env-file-demo.sh](../../scripts/env-file-demo.sh), CI job `env-file-demo`, [chapter 2: The .env file problem](../learn/02-the-env-file-problem.md)

#### F7.4 · Team enablement on the pattern · ✅ · [#11](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/11)

**S7.6 · Learning brief: retrieval pattern and JWT workload identity** · M · ✅ · [#12](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/12)
*As a junior engineer, I want the retrieval pattern explained across products, and how JWT workload identity works, so that I can apply it on any stack.*
- [x] The seven-step pattern mapped to AWS, Vault, Azure Key Vault and Google Secret Manager.
- [x] JWT claims and the token exchange, with the places this repo uses it.

Evidence: [chapter 1: Secrets managers](../learn/01-secrets-managers.md), [chapter 3: Why a secrets manager](../learn/03-why-a-secrets-manager.md)

**F7.5 · Automation examples for other teams** · S · ✅ · [#44](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/44)
*As a platform engineer, I want Terraform, Ansible and Kubernetes examples, so that other teams can adopt the pattern with their tools.*
- [x] Terraform (managed RDS password, rotation, write-only values), Ansible lookup, External Secrets and CSI.

Evidence: [chapter 3: Why a secrets manager](../learn/03-why-a-secrets-manager.md)

**F7.6 · Step-by-step deployment guide** · M · ✅ · [#56](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/56)
*As someone deploying for the first time, I want every command with what I should see after it, so that I can run paths A, B and C without help.*
- [x] Paths A (Compose), B (kind, OpenShift, EKS/ROSA) and C (EC2), each command followed by a check.
- [x] Troubleshooting and clean-up sections; the manual GitHub Actions run for path C.

Evidence: [GUIDE](../GUIDE.md), [quick reference](../reference/deploy-quickref.md)

**F7.7 · Tutorial, demo pages and test-case catalogue** · M · ✅ · [#57](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/57)
*As a presenter, I want one page per feature with the CI screenshot and output, so that I can demo or study one thing at a time.*
- [x] The tutorial walks every feature on a laptop, with screenshots.
- [x] One demo page per test case, with the CI screenshot and output, indexed in demo/README.md.
- [x] TEST-CASES lists every automated test and what it proves.
- [x] Screenshots come from the CI walk (`scripts/capture/`), so they show the current app.

Evidence: [TUTORIAL](../TUTORIAL.md), [demo pages](../../demo/README.md), [TEST-CASES](../TEST-CASES.md)

#### F7.8 · Folder READMEs and a handover · ✅ · [#120](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/120)

**S7.7 · A README in every folder, and a docs index** · S · ✅ · [#121](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/121)
*As a reader, I want each folder to say what it holds, so that I can find my way without reading the code.*
- [x] `docs/README.md` (where to start, by goal) and `docs/reference/README.md`; READMEs in backend, frontend, deploy, dev, infra, scripts and versions; a repository map in the root README.

Evidence: [docs index](../README.md), [repository map](../../README.md)

**S7.8 · Handover for the next contributor or AI agent** · S · ✅ · [#122](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/122)
*As the owner, I want a handover in the repo, so that a new session can continue the work or rebuild the lab on my Mac.*
- [x] `HANDOVER.md`: state, working rules, map, generated files, open work, CI, lessons, and recreating the lab on a MacBook; `CLAUDE.md` points to it.

Evidence: [HANDOVER.md](../../HANDOVER.md), [CLAUDE.md](../../CLAUDE.md)

### E13 — Version folders and milestone tags

[#92](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/92) · 🔜 · **Outcome:** The app's history is runnable: v0 with the .env leak, then tagged milestones. Docs: [plan E8–E15](plan-e8-e15.md)

#### F13.1 · versions/ and tags · 🔜 · [#93](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/93)

**S13.1 · versions/v0-env-file: the original app, runnable** · M · ✅ · [#94](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/94)
*As a learner, I want to run the original `.env` app and see the leak myself, so that the redesign has a clear 'before'.*
- [x] Own Compose project on port 3001, fake values, `leak.sh`.
- [x] CI asserts the leak is found; v0 is never published.

Evidence: [versions/v0-env-file](../../versions/v0-env-file/README.md), CI job `v0-leak`

**S13.2 · Milestone tags with releases** · S · 🔜 · [#95](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/95)
*As a reader, I want tags for each milestone, so that I can check out the app at each step of the story.*
- [ ] `v1-secrets-manager` and `v2-alerts`, each with a release linking the CI evidence: run the `milestone` workflow (this session can't push tags).
- [x] Release notes in `docs/releases/`; the `milestone` workflow creates the tag and the release.

Evidence: [.github/workflows/milestone.yaml](../../.github/workflows/milestone.yaml), [docs/releases/v1-secrets-manager.md](../releases/v1-secrets-manager.md)

### E14 — Tutorial: alerts and audit

[#96](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/96) · ✅ · **Outcome:** Learners see the logs-first alerting design, locally and on AWS, one demo at a time. Docs: [plan E8–E15](plan-e8-e15.md)

#### F14.1 · Chapter, demos and reference · ✅ · [#97](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/97)

**S14.1 · Chapter 7: alerts and audit** · M · ✅ · [#98](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/98)
*As a junior engineer, I want a chapter on logs-first alerting, so that I understand the path from a log line to an SMS.*
- [x] Diagrams: local pipeline, AWS pipeline, unexpected-read sequence, rotation-alert sequence.
- [x] Glossary entries.

Evidence: [chapter 7: Alerts and audit](../learn/07-alerts-and-audit.md)

**S14.2 · Demo test cases 13–18 with captures** · M · ✅ · [#99](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/99)
*As a presenter, I want one page per alert demo with the CI screenshot, so that I can show each one.*
- [x] sns-logger email, SMS and chat; pipeline pane; detection lab; vmui.

Evidence: [demo test cases 13–18](../../demo/README.md), [scripts/capture/alerts.yaml](../../scripts/capture/alerts.yaml)

**S14.3 · Reference and navigation updates** · S · ✅ · [#100](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/100)
*As a reader, I want the alert catalogue and the docs kept in step with the code, so that nothing is stale.*
- [x] `docs/reference/alerts.md` generated; GUIDE, TUTORIAL, TEST-CASES, security controls, README, backlog updated.

Evidence: [alert catalogue](../reference/alerts.md), [README.md](../../README.md)

**S14.4 · Backlog and issues generated from the repo** · S · ✅ · [#101](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/101)
*As a maintainer, I want the backlog page and the GitHub issues generated from data in the repo, so that anyone can regenerate them.*
- [x] `scripts/backlog/` holds the data, the page renderer and the issue writer.

Evidence: [scripts/backlog](../../scripts/backlog/README.md)

## Parked — planned, not scheduled

### E15 — MOVED: Secure Notes on OpenBao and HashiCorp Vault → openbao-node-poc

[#102](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/102) · ✅ · **Outcome:** A sibling repo shows the same app on OpenBao (primary) and Vault, on Compose and Kubernetes, with SDK/HTTP retrieval and External Secrets Operator, no env vars, auto-refresh and the reveal flag. Docs: [parked plan](parked-openbao-vault.md)

#### F15.1 · Decide and set up · ✅ · [#103](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/103)

**S15.1 · ADR-002: OpenBao first, Vault second** · S · ✅ · [#104](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/104)
*As an architect, I want the choice recorded with accurate licensing and feature facts, so that the team doesn't rely on myths.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#7](https://github.com/ephico2real2/openbao-node-poc/issues/7) (B1 · ADR-002).

Evidence: [openbao-node-poc#7](https://github.com/ephico2real2/openbao-node-poc/issues/7), [plan (moved)](parked-openbao-vault.md)

**S15.2 · New repo with version folders v0–v4** · S · ✅ · [#105](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/105)
*As a learner, I want each step in its own folder, so that I can follow the app as it changes.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#3](https://github.com/ephico2real2/openbao-node-poc/issues/3) (B0 · the repo, seeded with the AWS path kept; steps/ folders and tags).

Evidence: [openbao-node-poc#3](https://github.com/ephico2real2/openbao-node-poc/issues/3), [plan (moved)](parked-openbao-vault.md)

#### F15.2 · Retrieval and refresh · ✅ · [#106](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/106)

**S15.0 · One switch: SECRETS_PROVIDER=aws|vault|openbao** · M · ✅ · [#111](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/111)
*As an operator, I want to choose the secrets manager with one setting, so that the same app runs on AWS Secrets Manager, HashiCorp Vault or OpenBao.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#8](https://github.com/ephico2real2/openbao-node-poc/issues/8) (B2 · SECRETS_PROVIDER=aws|openbao|vault).

Evidence: [openbao-node-poc#8](https://github.com/ephico2real2/openbao-node-poc/issues/8), [plan (moved)](parked-openbao-vault.md)

**S15.3 · OpenBao in Compose with KV v2 and AppRole; HTTP client with token renewal** · M · ✅ · [#107](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/107)
*As a developer, I want the app to read from OpenBao over its HTTP API, so that no client library or env var is needed.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#12](https://github.com/ephico2real2/openbao-node-poc/issues/12) (B3 · OpenBao KV on Compose).

Evidence: [openbao-node-poc#12](https://github.com/ephico2real2/openbao-node-poc/issues/12), [plan (moved)](parked-openbao-vault.md)

**S15.4 · Dynamic PostgreSQL credentials with lease renewal** · M · ✅ · [#108](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/108)
*As a DBA, I want per-instance database users that expire, so that a leaked credential is short-lived.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#15](https://github.com/ephico2real2/openbao-node-poc/issues/15) (B4 · dynamic credentials and leases).

Evidence: [openbao-node-poc#15](https://github.com/ephico2real2/openbao-node-poc/issues/15), [plan (moved)](parked-openbao-vault.md)

**S15.5 · Kubernetes: Helm and External Secrets Operator, no env vars** · L · ✅ · [#109](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/109)
*As a platform engineer, I want secrets delivered by ESO as a mounted volume the app watches, so that rotation needs no restart and nothing is in the environment.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#18](https://github.com/ephico2real2/openbao-node-poc/issues/18) (B5 · Kubernetes, ESO, OpenShift).

Evidence: [openbao-node-poc#18](https://github.com/ephico2real2/openbao-node-poc/issues/18), [plan (moved)](parked-openbao-vault.md)

**S15.6 · HashiCorp Vault variant** · M · ✅ · [#110](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/110)
*As a Vault user, I want the same app on Vault, so that both products are covered.*
- [x] Moved to ephico2real2/openbao-node-poc, where it continues as [#21](https://github.com/ephico2real2/openbao-node-poc/issues/21) (B6 · the Vault variant).

Evidence: [openbao-node-poc#21](https://github.com/ephico2real2/openbao-node-poc/issues/21), [plan (moved)](parked-openbao-vault.md)

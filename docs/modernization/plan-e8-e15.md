# Plan E8–E15: logs-first alerting, a local SNS console, a detection lab, version folders

[← Initiative](README.md) · [Backlog](backlog.md) · [Parked: OpenBao and Vault](parked-openbao-vault.md)

The approved plan for the next epics. Status lives in the [backlog](backlog.md) and the GitHub issues; this page records the design.

## As built: where the build differs from this plan

The plan below is kept as approved. These are the places where the build went another way, and why:

| Plan | As built | Why |
| --- | --- | --- |
| journald → CloudWatch agent → `AWS::Logs::Transformer` (ParseJSON) | The app also writes its redacted JSON lines to `/var/log/secure-notes/app.jsonl` (`LOG_FILE`, written synchronously); the CloudWatch agent collects that file; logrotate with `copytruncate` | Plain JSON with no journald wrapper, and no Transformer to prove on AWS first. The agent comes from the Amazon Linux repository, not a pinned RPM |
| `scripts/sync-event-pattern.js` (js-yaml) and `AWSEvents.TestEventPattern` parity fixtures | `scripts/sync-event-pattern.py` (PyYAML); the parity fixtures are unit tests in `dev/aws-mock/test` | PyYAML was already on the runner; TestEventPattern needs AWS, and moves to S12.5 |
| `/api/demo/alerts` | `/api/demo/detections` (rule matches and deliveries) | The name says what it returns |
| `secrets.load.fatal` inhibits `fetch.failed`; `*.auth.rejected` only if no `*.recovered` within 2 min | Startup retries don't log an alert event at all, so only `load.fatal` pages; `*.auth.rejected` fires at 3 in 5 minutes | Simpler, and the same on AWS (CloudWatch has no inhibition) |
| One `OpsAlertsTopic` with filter policies | Three topics (secret-read, ops-alerts, ops-chat), routed by severity | CloudWatch alarms carry no message attributes, so a filter policy would drop them |
| The catalogue's `channels` per alert | Channels follow the severity (critical pages; warnings go to chat); `repeat` drives generated Alertmanager routes | Each topic's subscribers decide the channels; per-alert channels would need a topic per combination |
| A recorded Alertmanager 0.34.1 request body as a fixture | A hand-written Query-protocol body in the same shape; the real Alertmanager runs in CI's pipeline check | The pipeline check exercises the real one end to end |
| Alarm `OKActions` on the same topic | `OKActions` go to the chat topic; locally `send_resolved: false` | A recovery is news, not a page |

The unexpected-read rule also matches the Redis secret by ARN prefix, which closes a partial-ARN gap that the review found. The RDS-named DB secret keeps its documented gap.

## Context

The goal of this round of work:

- Proper structured logging, with well-formatted lines that show emails, SMS and alerts being sent, with their context.
- Alerts through **Amazon SNS** on AWS, and locally through an **sns-logger**: a container on the app's network (`http://sns-logger:4575`, `http://localhost:4575`) that shows each delivered message on a screen like the notes dashboard.
- **Logs first, then alerts**: logs go to AWS logging and alerts come from there. Locally this uses a CNCF-style log stack (OpenTelemetry format into VictoriaLogs), and sns-logger shows the messages arriving.
- A local, end-to-end version of the **unexpected secret read** alarm we built for AWS.
- Version folders that tell the app's story. A **separate OpenBao/Vault repo** is parked as a plan and issues only.

All work goes on the backlog and on GitHub issues, as **APP** or **TUTORIAL**.

Decisions taken when planning:
- the full CNCF log stack;
- `versions/v0-env-file` plus git tags, with the current app staying at the repo root;
- email, SMS and webhook/chat channels.

The research also found **two bugs in the AWS alarm shipped as S4.2**, so it can never fire today:
1. **Wrong topic key.** The topic uses the AWS-managed key `alias/aws/sns`. EventBridge can't publish to a topic encrypted with that key, and neither can CloudWatch alarms. Fix: a customer managed key.
2. **Missing rule state.** The rule has no `State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`. Without it, EventBridge doesn't deliver read-only events such as `GetSecretValue`.

Both are fixed in E11/E12. Issue #34 (S4.2) is reopened until both are fixed.

## Target architecture

**Local (Docker Compose)**

The base stack adds `sns-logger` (port 4575, loopback). It is the same image as `aws-mock`, with a second entrypoint, so the image count stays 2 and the CI digest checks keep working.

`docker-compose.observability.yml` is an opt-in overlay (about 600 MB) that the CI SDK leg always uses. It adds:

| Service | Image | Address |
| --- | --- | --- |
| OpenTelemetry Collector | `otel/opentelemetry-collector-contrib:0.163.1` | internal :4318 |
| VictoriaLogs | `victoriametrics/victoria-logs:v1.53.0` | 127.0.0.1:9428, with its vmui UI |
| vmalert | `victoriametrics/vmalert:v1.154.0` | 127.0.0.1:8880 |
| Alertmanager | `prom/alertmanager:v0.34.1` | 127.0.0.1:9093 |

```
app / aws-mock / sns-logger ──stdout (unchanged JSON)──► docker / podman logs
        └──OTLP/HTTP JSON──► otel-collector ──OTLP protobuf──► VictoriaLogs ◄── sns-logger "Pipeline" pane (tail)
                                                                   │ LogsQL rules
                                                         vmalert ──► Alertmanager ──SNS Publish──► sns-logger ──► email / SMS / webhook cards
SDK read ─► aws-mock: CloudTrail-shaped record ─► EventBridge-pattern evaluator (same rule as the stack) ─SNS Publish──┘
```

- The app pushes OTLP itself, because Podman has no fluentd log driver.
- No new runtime dependency: the shipper builds the OTLP JSON by hand.
- stdout stays the main log and keeps its current format, so every existing check, capture and filter keeps working.

**AWS**

```
journald ─► CloudWatch agent ─► Logs group /secure-notes/<stack>/app ─► Transformer (ParseJSON) ─► metric filters ─► alarms ─► OpsAlertsTopic
CloudTrail ─► EventBridge rule (State=ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS) ─► SecretReadAlertTopic
both topics: customer-managed AlertsKey; subscriptions: email, SMS, https
```

## One alert catalogue, three generated outputs

`backend/src/alerts/catalogue.js` is the only source. `scripts/sync-alert-rules.js --check` runs in CI and generates:

1. the vmalert rules;
2. the CloudFormation metric filters and alarms (a marked block, the same way `sync-rotation-lambda` works);
3. the alert table in the docs.

| Event | Severity | Source | Channels | Dedup / rule |
| --- | --- | --- | --- | --- |
| `secret.read.unexpected` | critical | CloudTrail → EventBridge | email, SMS, chat | every read |
| `secrets.load.fatal` | critical | server.js (exit 1) | email, SMS, chat | inhibits `fetch.failed` |
| `secrets.fetch.failed` | critical | provider.js | email, SMS, chat | per secret, 1 h |
| `config.unsafe` | critical | server.js (exit 78) | email, chat | 4 h |
| `cache.refresh.failed` / `agent.forbidden` | critical | cache.js / fetchers.js | email, chat | 1 h |
| `secrets.fetch.stale` | warning | provider.js | chat | ≥3 in 10 min |
| `db.auth.rejected` / `cache.auth.rejected` | warning | db.js / cache.js | chat | only if no `*.recovered` within 2 min |
| `secrets.reveal.enabled` | warning | server.js | chat | 24 h |
| `app.errors.burst` | warning | `level=error`, excluding the leak test's `simulated:` lines | chat | ≥5 in 5 min |
| `credential.rotated` (notification) | info | provider `loaded`, changed | chat, published directly | 10 min |

- At each call site the change is one `event` field; messages stay as they are.
- Alarms flow **logs-first only**, so nobody is paged twice. The app publishes directly only for notifications and for the "Send test alert" button.
- No alert field is named like `secret` or `token`, because the redactor blanks those.
- Recipients never enter the app: they are SNS subscriptions.

## Message formats

- **Log line for a sent alert:**
  `{"level":"info","component":"alerts","event":"alerting.notification.sent","msg":"notification sent: …","messaging.system":"aws.sns","messaging.destination.name":"…","aws.sns.topic.arn":"…","messaging.message.id":"…","alert.name":"…","alert.severity":"…","sms.segments":1}`
  The field names follow the OpenTelemetry semantic conventions.
- **sns-logger, one line per delivery:**
  `{"event":"sns.delivery.sent","protocol":"sms","endpoint":"+1******0100","segments":2,"publishedBy":"events.amazonaws.com"}`
- **`LOG_FORMAT=pretty`:** human-readable lines, e.g. `08:21:04.123 WARN secrets secret fetch failed, serving last good value · secretId=/rds/dev/notes-db/app event=secrets.fetch.stale`. stdout only; refused in production.
- **OTLP mapping:**
  - `time` → Timestamp
  - level → SeverityNumber: debug 5, info 9, warn 13, error 17; 21 for the two exit events
  - `msg` → Body
  - `event` → EventName
  - the other fields → Attributes
  - Resource: `service.name`, `service.version`, `deployment.environment.name`
- **SNS `MessageStructure=json`** (keys must be strings):
  - `default`
  - `email`: what happened, where, when, runbook, alert ID
  - `sms`: ≤140 bytes, GSM-7
  - `https`: an Amazon Q Developer custom-notification body for chat
  - Subject under 100 characters, no line breaks.
- **Masking:** `maskEmail` (`on***@example.com`) and `maskPhone` (`+1******0100`) go in a new, dependency-free `backend/src/alerts/recipients.js`. The mock image reuses it.

## Components and file-level changes

### E8 · APP · Structured logs (`backend/src/log.js`, `backend/src/alerts/`)
- **S8.1** Add `event` fields at the call sites; add `catalogue.js`; add a test that every event used in the code is in the catalogue.
- **S8.2** OTLP shipper, hooked after redaction inside `emit()` (never on `out`):
  - `revealUnsafe` lines are never shipped;
  - bounded buffer that drops the oldest lines first;
  - never logs through itself;
  - `LOG_OTLP_ENDPOINT` setting.
- **S8.3** `LOG_FORMAT=pretty`.

### E9 · APP · Notifications and the sns-logger
- **S9.1** sns-logger API in `dev/aws-mock/sns-logger/`, using the AWS Query protocol (form-encoded in, XML out); it also accepts the JSON form.
  - Supports: CreateTopic, ListTopics, Get/SetTopicAttributes, Subscribe, ConfirmSubscription, Unsubscribe, ListSubscriptions(ByTopic), and Publish (Subject, MessageStructure, `MessageAttributes.entry.N`, PhoneNumber).
  - Validates like AWS: subject length, a `default` key, 256 KiB maximum, SMS 1600 bytes.
  - Subscriptions come from `SNS_LOGGER_SUBSCRIPTIONS`, with example.com and 555-01xx values only.
- **S9.2** sns-logger UI. Same origin, strict CSP, and the dashboard's `styles.css` copied in at build time. Tabs:
  - **Email:** "AWS Notifications <no-reply@sns.amazonaws.com>", masked To, and the unsubscribe footer.
  - **SMS:** phone-style bubbles showing sender ID, bytes and 140-byte segments.
  - **Webhook/chat:** the SNS envelope JSON plus a chat card.
  - **Topics.**
  - **Pipeline:** a live tail of VictoriaLogs, correlated by MessageId. It says "not deployed" when the overlay is off.
- **S9.3** `backend/src/alerts/notifier.js`, using `@aws-sdk/client-sns` pinned to the lockfile's SDK version:
  - rate limit and dedup;
  - writes the "alert sent" log line;
  - "Send test alert" button;
  - setting `SNS_TOPIC_ARN`, plus a mock SNS endpoint that is refused in production.
- **S9.4** Recipient masking.

### E10 · APP · Local log pipeline (`docker-compose.observability.yml`, `deploy/observability/`)
- **S10.1** Collector config: OTLP receiver, then otlphttp out to VictoriaLogs `/insert/opentelemetry/v1/logs` with the header `VL-Stream-Fields: service.name`.
- **S10.2** vmalert rules generated from the catalogue (`type: vlogs`, `… | stats count() as n | filter n:>0`). Short evaluation intervals in CI.
- **S10.3** Alertmanager `sns_configs`:
  - `api_url: http://sns-logger:4575`;
  - dummy sigv4 keys and a region;
  - a template laid out like a CloudWatch alarm email.
- **S10.4** sns-logger Pipeline pane.

### E11 · APP · Detection lab: simulate the unexpected-read alarm (`dev/aws-mock/`)
- **S11.1** `principals.js` maps access keys to identities:

  | Access key | Identity | Who uses it |
  | --- | --- | --- |
  | `local-app` | assumed role `secure-notes-app` | the app |
  | `local-seed` | deployer | the seed job |
  | `local-intruder-user` | IAMUser `mallory` | the demo button |
  | `local-intruder-role` | assumed role `ops-admin` | the demo button |
  | unsigned | `local-tooling` service | credential scan, healthchecks; matches no alarm branch, so CI never false-alarms |

  - STS returns the caller's identity.
  - Compose and the kind ConfigMap split the shared key into `local-app` and `local-seed`.
  - `cloudtrail.js` writes CloudTrail-shaped records for `GetSecretValue` and `BatchGetSecretValue`. They never contain `SecretString`.
- **S11.2** `event-pattern.js`, a small evaluator for the operators we use: exact values, arrays, nesting, `$or`, `anything-but`, `prefix`, `exists`.
  - An unknown operator stops startup.
  - It honours the rule's `State`, so it would have caught bug 2.

  `scripts/sync-event-pattern.js --check` reads **the same rule from `infra/cloudformation.yaml`**:
  - it uses js-yaml with a schema for the short CloudFormation tags;
  - it turns Ref/GetAtt/Sub into placeholders and writes `dev/aws-mock/rules/secret-read-alert.json` with a sha256, so local and AWS can't drift;
  - the mock also implements `AWSEvents.TestEventPattern`, so the same fixtures run against the mock and against real AWS.
- **S11.3** A demo "Detection lab" card, backed by `POST /api/demo/unexpected-read {as: user|role, target: redis|db-by-name}`.
  - It is demo-only, uses its own client with the intruder key, and returns IDs only.
  - `db-by-name` shows the documented gap: the read is audited but not alarmed.
  - The card links to the inbox and shows recent deliveries through `/api/demo/alerts`. The dashboard's CSP blocks cross-origin fetches, so this has to go through the backend.
- **S11.4** Add `State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` to the rule, and reopen #34.
- **S11.5** kind: sns-logger Deployment and Service, NetworkPolicies, and `k8s-check.sh`. The observability overlay stays Compose-only for now.

### E12 · APP · Logging and alerting on AWS (`infra/cloudformation.yaml`, bootstrap, `aws.yaml`)
- **S12.1** `AlertsKey` customer-managed key, allowing events, cloudwatch and logs to use `GenerateDataKey*` and `Decrypt`. `SecretReadAlertTopic` moves to it. New `OpsAlertsTopic`. Conditional subscriptions from the parameters `AlertEmail`, `AlertPhone` (E.164) and `AlertWebhookUrl` (https only).
- **S12.2** CloudWatch agent: a pinned RPM with checksum, collecting journald for unit `secure-notes`. `AppLogGroup` keeps 30 days. An `AWS::Logs::Transformer` with ParseJSON unwraps journald's `body.MESSAGE`. Labelled `needs-aws-verification`; the fallback is a file collector.
- **S12.3** Generated metric filters (`ApplyOnTransformedLogs: true`) and alarms. Each alarm notifies on both ALARM and OK, and treats missing data as not breaching.
- **S12.4** IAM:
  - `AppRole`: `sns:Publish` on the ops topic, plus KMS through SNS.
  - Optional SNS and Logs interface endpoints.
  - Add `SNS_TOPIC_ARN` to `app.env`.
  - Bootstrap role: `cloudwatch:GetMetricStatistics`, `logs:FilterLogEvents`, `events:TestEventPattern`.
- **S12.5** Checks in `aws.yaml`:
  - The deploy role's read attempt is denied but still recorded, so the alarm should fire. Check `NumberOfMessagesPublished`.
  - A test log event trips an alarm.
  - The TestEventPattern fixtures pass, proving the mock matches AWS.

### E13 · TUTORIAL · Version folders and tags
- **S13.1** `versions/v0-env-file/`:
  - the original `.env` app (pg and ioredis; reads `DB_PASSWORD` and `REDIS_URL`; logs the URL on an error);
  - `v0.env` with the source review's fake values;
  - its own Compose project on port 3001;
  - `leak.sh` (`exec env`, `/proc/1/environ`, `inspect`, `compose config`, logs).

  A CI job asserts the leak **is** found. v0 is never published.
- **S13.2** Annotated tags with GitHub Releases that link to the CI evidence: `v1-secrets-manager` on today's HEAD, and `v2-alerts` when E8–E12 are green.

### E14 · TUTORIAL · Docs and demos
- **S14.1** `docs/learn/07-alerts-and-audit.md`, with four Mermaid diagrams (local pipeline, AWS pipeline, unexpected-read sequence, rotation-alert sequence) and new glossary entries.
- **S14.2** Demo test cases 13–18, with captures from a new `scripts/capture/alerts.yaml`: sns-logger email, SMS and chat; the pipeline pane; the detection lab; vmui.
- **S14.3** `docs/reference/alerts.md` (generated); updates to TUTORIAL, GUIDE, TEST-CASES, security-controls (posture counts change now that STS returns a role), README and backlog.
- **S14.4** Commit the issue/backlog generator from the session scratchpad as `scripts/backlog/` (data plus a generator), so the backlog page and the issues can be reproduced.

### E15 · PARKED (APP and TUTORIAL) · Sibling repo `openbao-node-poc`
Issues and a plan document only (`docs/modernization/parked-openbao-vault.md`); no code. Recommended as a new repo, which can take its own direction. Version folders from the start:

| Folder | What it adds |
| --- | --- |
| `v0-env-file` | A copy of this repo's v0 |
| `v1-openbao-kv` | OpenBao 2.7.1 in Compose (static seal and self-init, KV v2, AppRole), plain `fetch` against the HTTP API, token renew |
| `v2-openbao-dynamic` | PostgreSQL dynamic credentials with lease renewal and auto-refresh. Redis becomes **Valkey**, because OpenBao has no Redis plugin |
| `v3-k8s` | Helm (raft); External Secrets Operator 2.13 with the Vault provider, which is stable and works with OpenBao; a mounted Secret watched through the `..data` swap, so no env vars; VaultDynamicSecret |
| `v4-vault` | HashiCorp Vault 2.2.0 (about 10% of the tutorial), with its Redis plugin |

The reveal flag is kept throughout.

Plan ADR-002 records the licensing facts accurately:
- OpenBao is MPL-2.0 and an OpenSSF sandbox project.
- Vault is BSL 1.1 under IBM.
- "IBM removed Enterprise features" is inaccurate: those features were always Enterprise-only.
- OpenBao now has namespaces, standby reads and control groups for free, but **not** replication, Sentinel or Transform.

## Issues and sequencing

- **Issues:** created through the REST API with sub-issues, the same way as before. Titles start with `APP:` or `TUTORIAL:`. Labels: `app`/`tutorial`, `type:*`, `epic:E8…E15`, `size:*`, `needs-aws-verification`, and `parked` for E15.
- **Backlog:** `backlog.md` is regenerated, and the initiative page gains E8–E15.
- **Order:** issues and the `v1-secrets-manager` tag → E8 → E9 and E11 in parallel → E10 → E12. E14 runs alongside. E13 is independent. The `v2-alerts` tag goes last.
- **Pushes:** one commit series per epic, each pushed only after the previous CI run has finished.

## Verification

- **Unit tests (backend):**
  - A registered value is shipped as `[REDACTED]`, and revealed lines are never shipped.
  - Buffering, pretty format, masks.
  - Notifier: dedup, subject rules, and the payload is unchanged by `redactor.scrub`.
  - Catalogue coverage.
- **Unit tests (mock):**
  - evaluator fixtures;
  - a real Alertmanager 0.34.1 request body;
  - SMS segment math;
  - CloudTrail records free of `SecretString`.
- **CI checks job:** `sync-alert-rules --check` and `sync-event-pattern --check`.
- **CI compose job**, SDK leg with the overlay:
  - app records are in VictoriaLogs;
  - no secret-read alert is delivered before the button is pressed;
  - the button produces email, SMS and https deliveries within 10 s;
  - a forced fetch failure produces an Alertmanager alert, delivered within 120 s.
- **Credential scan:** extended to VictoriaLogs, Alertmanager and the sns-logger export. With the reveal flag on, VictoriaLogs must still be clean.
- **Captures:** new walk pages 10–14, with text assertions.
- **kind:** the simulated read raises a delivery in sns-logger.
- **Docs job:** links and all new diagrams.
- **AWS (manual `aws.yaml`):** an alarm email and SMS publish (checked by metric), and the TestEventPattern parity checks.

## Risks

- **New places for values to land** (VictoriaLogs, Alertmanager, sns-logger): all scanned, and no alert field has a sensitive name.
- **Alert loops:** the shipper and sns-logger never alert on themselves.
- **CI timing:** polling with deadlines.
- **SMS:** the sandbox applies, and US numbers don't show a sender ID.
- **Chat:** an SNS https endpoint must be confirmed, and Slack can't read SNS messages directly. The route is Amazon Q Developer custom notifications.
- **Journald transformer:** not yet proven on AWS; the fallback is a file collector.
- **Memory:** the overlay is opt-in for laptops.

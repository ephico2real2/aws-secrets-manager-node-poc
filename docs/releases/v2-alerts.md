**Milestone 2 of the Secure Notes story: alerts from logs and from the audit trail, end to end on a laptop.**

- **Structured logs built for alerting.** Every alertable line carries a stable `event` name from one catalogue (`backend/src/alerts/catalogue.js`). Lines are redacted before any copy leaves the process, and are shipped in the OpenTelemetry log format. `LOG_FORMAT=pretty` makes them readable in a terminal.
- **Logs first, then alerts.** Locally: OpenTelemetry Collector → VictoriaLogs → vmalert → Alertmanager → SNS. On AWS: CloudWatch agent → CloudWatch Logs → metric filters → alarms → SNS. One script generates the vmalert rules, the CloudWatch alarms and the alert reference table, so they can't drift apart.
- **sns-logger, a local SNS.** It speaks the SNS Query API and shows every delivery on http://localhost:4575: email, SMS (with 140-byte segments) and chat cards, plus a Pipeline tab that reads the log store. Recipients are masked everywhere.
- **Detection lab.** Reading a secret as the IAM user `mallory` raises the stack's own EventBridge rule, evaluated locally from the same CloudFormation template. Reading the DB secret by name shows the known gap: the read is recorded but not alarmed.
- **The app's own notifications** (`credential.rotated` and the test alert) tell the chat topic without paging anyone.
- **The "before" picture:** `versions/v0-env-file` is the original `.env` app. Its `leak.sh` finds the passwords in 8 of 9 places.

**Fixed:** the unexpected-read alarm (S4.2, issue #34) could never fire on AWS, for two reasons:
1. The topic used the AWS-managed `aws/sns` key. It now uses the customer-managed `AlertsKey`.
2. The rule lacked `State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`.

Proving it on AWS is S12.5, still open.

**Evidence:** [CI run RUN_ID](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/runs/RUN_ID), with all jobs green, and the [ci-captures](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures) branch. Start with chapter 7 of the learning path, [Alerts and audit](https://github.com/ephico2real2/aws-secrets-manager-node-poc/blob/v2-alerts/docs/learn/07-alerts-and-audit.md), and demo test cases 13–18.

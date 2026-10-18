# dev/

[← Project README](../README.md)

**Development and CI only. Never deploy anything from here to production.** These are
stand-ins for the AWS services, so the whole lab runs on a laptop or a CI runner with no
AWS account and no real keys. `config.js` refuses a mock endpoint when
`NODE_ENV=production`.

| Path | What it is |
| --- | --- |
| [`aws-mock/server.js`](aws-mock/server.js) | The AWS stand-in on port 4566. It plays: **Secrets Manager** (CreateSecret, GetSecretValue, DescribeSecret, PutSecretValue, UpdateSecretVersionStage, GetRandomPassword: what the seed job, the app and rotation use); **STS** (GetCallerIdentity answers as the caller); **CloudTrail** (a record for every secret read, without the value, at `/_mock/cloudtrail`); **EventBridge** (it evaluates the CloudFormation stack's own unexpected-read rule and publishes matches to SNS, see `/_mock/eventbridge`); and, in agent mode (`docker-compose.agent.yml`), the local credentials agent |
| [`aws-mock/lib/`](aws-mock/lib) | `principals.js` maps an access key ID to an identity (below); `cloudtrail.js` writes the audit records; `event-pattern.js` is a small EventBridge pattern matcher (unknown operators fail); `sns.js` is the SNS model (topics, subscriptions, deliveries, SMS segments); `aws-query.js` parses the AWS Query protocol |
| [`aws-mock/rules/secret-read-alert.json`](aws-mock/rules/secret-read-alert.json) | **Generated.** A copy of `SecretReadAlertRule` from `infra/cloudformation.yaml`, made by `scripts/sync-event-pattern.py`. CI fails if it is stale, so the laptop runs the same rule AWS does |
| [`aws-mock/sns-logger/`](aws-mock/sns-logger) | A local Amazon SNS with a screen, on port 4575 (the same image, a second entrypoint). The app, Alertmanager and the EventBridge stand-in publish to it as they would to SNS. It delivers nothing: each delivery is shown as an email, a text message or a chat post, with recipients masked |
| [`aws-mock/test/`](aws-mock/test) | Unit tests: the stack's rule, the matcher, CloudTrail records, SNS validation and delivery. Run `node --test dev/aws-mock/test/*.test.js` |
| [`aws-mock/Dockerfile`](aws-mock/Dockerfile) | One image for both services. Build it from the repository root (`docker compose build aws-mock`) |
| [`redis-entrypoint.sh`](redis-entrypoint.sh) | Starts Redis with an ACL file, so the users the seed job creates survive a restart |

## Who is calling: the access key decides

Local runs sign their requests with dummy keys. The stand-in ignores the signature and reads
the key ID as the caller's identity. That is how the lab can show an intruder:

| Key ID | Identity | Used by |
| --- | --- | --- |
| `local-app` | assumed role `secure-notes-app` | the app |
| `local-seed` | the deployer | the seed job |
| `local-intruder-user` | IAM user `mallory` | the Detection lab |
| `local-intruder-role` | assumed role `ops-admin` | the Detection lab |
| `local-events` | `events.amazonaws.com` | the EventBridge stand-in publishing to SNS |
| `local-alertmanager` | Alertmanager's role | the log pipeline |
| *(unsigned)* | `local-tooling` | the credential scan and health checks; matches no alarm |

sns-logger accepts only signed requests that carry no `Origin` header. A web page can't
sign a request, and browsers always send `Origin` on a cross-site POST, so another page
can't drive the console from your browser.

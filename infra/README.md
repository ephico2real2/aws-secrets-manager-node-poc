# infra/

[← Project README](../README.md) · [GUIDE Part C](../docs/GUIDE.md#part-c--deploy-to-aws-on-ec2)

Everything for running Secure Notes on AWS itself. Kubernetes manifests are in
[`../deploy`](../deploy/README.md).

| Path | What it is |
| --- | --- |
| [`cloudformation.yaml`](cloudformation.yaml) | The EC2 stack. GUIDE Part C deploys it step by step. It contains: <ul><li>a Secrets Manager VPC endpoint, and a KMS key for the secrets;</li><li>RDS Postgres with `ManageMasterUserPassword` (RDS creates and rotates that secret);</li><li>ElastiCache Redis with TLS, an RBAC user, its secret, and a rotation function;</li><li>a least-privilege instance role, and an EC2 instance that requires IMDSv2 and has no inbound ports, running the app under systemd;</li><li>for alerting: a customer-managed key, three SNS topics, the CloudWatch agent and log group, the generated metric filters and alarms, and `SecretReadAlertRule` (CloudTrail → EventBridge → SNS)</li></ul> |
| [`github-actions-bootstrap.yaml`](github-actions-bootstrap.yaml) | A one-time stack: the GitHub OIDC role that the manual `aws.yaml` workflow assumes. No stored AWS keys. Deploy it with `scripts/aws-bootstrap.py`, which also writes its outputs to GitHub |
| [`rotation/elasticache-user-rotation.js`](rotation/elasticache-user-rotation.js) | The Redis rotation function, as testable source. `scripts/sync-rotation-lambda.js` copies it into the template (inline, 4 KB limit); CI checks that the copy matches |
| [`systemd/secure-notes.service`](systemd/secure-notes.service) | The hardened unit on EC2: a dedicated user (`securenotes`), `ProtectSystem=strict`, `NoNewPrivileges`, a private `/tmp`, and a `LogsDirectory` for the file the CloudWatch agent reads |
| [`iam-policy.example.json`](iam-policy.example.json), [`irsa-trust-policy.example.json`](irsa-trust-policy.example.json) | The app's least-privilege policy and the IRSA trust policy, for EKS or ROSA (GUIDE B3) |

**Generated blocks:** two parts of `cloudformation.yaml` are written by scripts. The alarms
between `# ---- BEGIN generated alarms` and `# ---- END` come from
`scripts/sync-alert-rules.js`, and the inline rotation code comes from
`scripts/sync-rotation-lambda.js`. Edit their sources, not the template.

**Status:** CI lints both templates with `cfn-lint` on every push. The alerting pieces
(the key, the topics, the CloudWatch agent, the alarms and the rule state) are built and
proven locally, but not yet on a real account. That is story S12.5 (issue #91), run
through `.github/workflows/aws.yaml`.

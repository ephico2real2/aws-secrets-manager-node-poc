**Milestone 1 of the Secure Notes story: credentials come from AWS Secrets Manager at runtime.**

- No credential in environment variables, files, images, logs or Kubernetes objects, proven by the credential scan in CI.
- Rotation without restart for Postgres and Redis; masked debug logging; a lab-only reveal flag that production refuses.
- Secret naming convention `/{service}/{env}/{resource}/{name}`.
- On AWS: instance role, IMDSv2, VPC endpoint, customer-managed KMS key, RDS-managed rotation, a Redis rotation function, a resource policy on the Redis secret, optional Config rules.

Known issue: the unexpected-read alarm (S4.2) can't fire yet, because of the topic's key and the rule's state (issue #34). Fixed in v2.

Evidence: [CI run 39131534692](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/runs/39131534692), all jobs green, and the [ci-captures](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures) branch.

Start with the [README](https://github.com/ephico2real2/aws-secrets-manager-node-poc/blob/v1-secrets-manager/README.md); the version before it is [`versions/v0-env-file`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/main/versions/v0-env-file).

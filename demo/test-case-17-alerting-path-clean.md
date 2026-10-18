# Test case 17 — No credential in the alerting path

[← all test cases](README.md)

**What it proves:** alerting adds new places a value could land: the log store, Alertmanager, the SNS deliveries and the audit records. The credential scan searches each of them for every real password (every version) and finds none, including when the lab-only reveal flag is on.

**Catalogue IDs:** N6, N11, N12, C1–C16 ([TEST-CASES.md](../docs/TEST-CASES.md)) · **Proven in CI by:** `compose (sdk)`, `kind`, unit tests · **Evidence from:** [CI run 39140499800](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/runs/39140499800), published on [`ci-captures`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures)

## Steps

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.observability.yml scripts/credential-scan.sh compose
```

## What you should see

Every line `clean`. Four sources are new with alerting:

```
-- alerting (deliveries, audit records, the log store)
  ok    sns-logger: every delivery (email, SMS and chat bodies)        clean
  ok    aws-mock: CloudTrail records                                   clean
  ok    VictoriaLogs: every stored record                              clean
  ok    Alertmanager: alerts                                           clean
```

Why they stay clean:
- every copy of a log line (stdout, the file on EC2, the OpenTelemetry shipper) receives the same already-redacted string;
- lines printed by the reveal flag go to stdout only, never to a log store ([test case 7](test-case-07-reveal-flag.md));
- notification bodies pass through the redactor;
- CloudTrail records never include `SecretString`;
- no alert field is named like `secret` or `token`.

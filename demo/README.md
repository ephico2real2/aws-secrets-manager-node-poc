# Demo — one test case at a time

Each file below is one thing this project claims about credentials, shown the
way you would demo it: **what it proves, the steps (click or command), what you
should see, the screenshot and the real output from a CI run.** The pictures and
outputs come from the CI captures on the
[`ci-captures`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures)
branch, so they show the app as it actually ran.

Start with test case 1; the rest can be done in any order. Each one needs only
Docker (test case 10 also needs kind, test case 12 also needs `skopeo`).

| # | Test case | What you'll see | Catalogue IDs |
| --- | --- | --- | --- |
| 1 | [Start the app and load the secrets](test-case-01-start-and-load-secrets.md) | Both credentials in memory: name, version, fingerprint — never the value | S1–S8 |
| 2 | [Rotate the Postgres password from the dashboard](test-case-02-rotate-postgres.md) | Click **Rotate Postgres secret**, then **Drop connections**: `auth-failed → new-version → recovered` | R1, R2 |
| 3 | [Rotate the Redis password from the dashboard](test-case-03-rotate-redis.md) | Click **Rotate Redis secret**: both passwords valid for a moment, then the old one is revoked | R1, R2 |
| 4 | [Try to leak a password](test-case-04-leak-test.md) | Click **Run leak attempts**: `0 of 6 leaked` | L1–L7 |
| 5 | [Read the debug log, values masked](test-case-05-debug-log.md) | Tick **Credential lines only**: which secret, which keys, `password=******** (32 chars, fp=…)` | D1–D7 |
| 6 | [No credential in any container or pod](test-case-06-credential-scan.md) | The real passwords searched for everywhere: every place `clean` | C1–C16 |
| 7 | [Reveal the real values in a lab](test-case-07-reveal-flag.md) | `LOG_REVEAL_SECRETS=true`: red banner, posture fails, the scan finds the values in the app log only | C11, F1–F6 |
| 8 | [Production refuses the reveal flag](test-case-08-reveal-refused-in-production.md) | The app will not start: exit code 78 | F4 |
| 9 | [Agent mode](test-case-09-agent-mode.md) | `mode: agent`; the agent rejects a request without its token (403) | A1–A4 |
| 10 | [The same on Kubernetes (kind)](test-case-10-kubernetes.md) | Pod specs, ConfigMaps, decoded Secrets, events, pod files and logs: all `clean` | C2–C5, C12–C15, P1, P2 |
| 11 | [Scanned, listed and signed images](test-case-11-supply-chain.md) | 0 fixable critical vulnerabilities; an SBOM per image; signatures verified without logging in | K1–K3, K5 |
| 12 | [Mirror the images to your own registry](test-case-12-image-mirror.md) | All four images copied; the overlay pulls only from your registry; layers identical | K4 |

The catalogue IDs refer to [`docs/TEST-CASES.md`](../docs/TEST-CASES.md), which lists
every automated test. For the same features as one continuous walk-through, see
[`docs/TUTORIAL.md`](../docs/TUTORIAL.md).

## Before you start

```bash
git clone https://github.com/ephico2real2/aws-secrets-manager-node-poc.git
cd aws-secrets-manager-node-poc
docker compose up --build        # then open http://localhost:3000
```

When you're done: `docker compose down -v`.

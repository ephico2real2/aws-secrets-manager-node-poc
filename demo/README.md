# Demo — one test case at a time

Each file below is one thing this project claims about credentials, shown the
way you would demo it: **what it proves, the steps (click or command), what you
should see, the screenshot and the real output from a CI run.** The pictures and
outputs come from the CI captures on the
[`ci-captures`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures)
branch, so they show the app as it actually ran.

Do them **in order**: test case 6 searches for the passwords that test cases 2–4
created and leaked into the logs, and test cases 9 and 10 change which stack is
running. Test cases 13–17 are about alerts. They run on the base stack; test cases 16
and 17 add the log pipeline overlay (`docker-compose.observability.yml`). Test case 18
is the "before" picture and runs on its own. Counts such as versions, file numbers and fingerprints will differ on
your machine; the shape of the output is what matters.

**You need:** Docker with Compose v2, `jq`, and for the check scripts Node.js 22
and `curl` on your machine. Test case 10 also needs [kind](https://kind.sigs.k8s.io)
and `kubectl`; test case 11 `cosign` (and Linux on x86-64 for the scan script);
test case 12 `skopeo` (or `oc`) and a registry you can push to. Test case 16 needs about
600 MB more of images for the log pipeline.

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
| 13 | [An intruder reads a secret: the alarm fires](test-case-13-detection-lab.md) | Click **Read Redis secret as IAM user mallory**: the stack's own EventBridge rule matches, and email, SMS and chat are delivered | N1–N3, N7 |
| 14 | [What on-call receives: email and SMS](test-case-14-sns-email-and-sms.md) | The notification console: the email with its footer, the SMS split into parts, recipients masked | N2, N5, N6, N12, N13 |
| 15 | [Chat: a rotation tells, it doesn't page](test-case-15-chat-and-rotation.md) | **The app switched to a rotated credential** on the chat-only topic | N4 |
| 16 | [Logs first, then alerts](test-case-16-logs-first.md) | Secrets Manager stopped: the log line → VictoriaLogs → vmalert → Alertmanager → a critical page | N8–N10 |
| 17 | [No credential in the alerting path](test-case-17-alerting-path-clean.md) | The scan adds the deliveries, CloudTrail records, the log store and Alertmanager: all `clean` | N6, N11, N12 |
| 18 | [Before: the original `.env` app leaks everywhere](test-case-18-v0-before.md) | `versions/v0-env-file/leak.sh`: the passwords in 8 of 9 places | N14 |

The catalogue IDs refer to [`docs/TEST-CASES.md`](../docs/TEST-CASES.md), which lists
every automated test. For the same features as one continuous walk-through, see
[`docs/TUTORIAL.md`](../docs/TUTORIAL.md).

## Before you start

```bash
git clone https://github.com/ephico2real2/aws-secrets-manager-node-poc.git
cd aws-secrets-manager-node-poc
docker compose up --build -d     # then open http://localhost:3000
docker compose logs -f app       # optional: follow the log in a second terminal
```

When you're done: `docker compose down -v`.

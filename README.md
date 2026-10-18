# Secure Notes — from `.env` passwords to AWS Secrets Manager

[![ci](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/workflows/ci.yaml/badge.svg)](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/workflows/ci.yaml)

**The problem.** Most apps start with their database and cache passwords in a `.env`
file. Anyone who can reach the host, the container runtime, the orchestrator, CI logs or
a backup can read them; they are never rotated, and nobody knows who read them.
[See it for yourself](docs/learn/02-the-env-file-problem.md): `podman exec … env` prints
every password. The original app is kept, runnable, in
[`versions/v0-env-file`](versions/v0-env-file/README.md).

**The solution shown here.** Secure Notes (frontend, Node.js backend, Postgres, Redis)
gets its credentials at runtime from AWS Secrets Manager, using the platform's identity
instead of a stored key. Credentials stay out of disk, environment variables, logs, API
responses and Kubernetes objects; they rotate without a restart; every read is audited
and an unexpected one raises an alarm by email, SMS and chat. A dashboard lets you watch
the secrets load, rotate them, see the app recover by itself, try to leak them, and read
a secret as an intruder to see the alarm arrive.

| Version | What changes | Where |
| --- | --- | --- |
| **v0** | Passwords in a `.env` file: works, and leaks | [`versions/v0-env-file`](versions/v0-env-file/README.md) |
| **v1** | Credentials from AWS Secrets Manager at runtime; rotation without restart; nothing in env, files, images or logs | tag `v1-secrets-manager` (created by the [milestone workflow](.github/workflows/milestone.yaml)) |
| **v2** | Logs first, then alerts: structured logs, SNS notifications, the unexpected-read alarm simulated end to end | this branch; tag `v2-alerts` when released |
| **next** | The same app on OpenBao and HashiCorp Vault, AWS kept: `SECRETS_PROVIDER=aws\|openbao\|vault` | the sibling repo [`openbao-node-poc`](https://github.com/ephico2real2/openbao-node-poc) |

## Read the story

| | Start here | What it is |
| --- | --- | --- |
| 1 | **[Learning path](docs/learn/README.md)** | Seven short chapters, from "what is a secrets manager" to alerts and audit. Any language; Secure Notes is the worked example |
| 2 | **[Modernization initiative](docs/modernization/README.md)** | The same work run as an agile project: [source review](docs/modernization/01-source-review.md) → [tool selection (ADR-001)](docs/modernization/02-adr-001-secrets-manager-selection.md) → [epics, features and stories](docs/modernization/backlog.md), tracked as [GitHub issues](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues) |

The chapters:

1. [Secrets managers and how a workload fetches a secret](docs/learn/01-secrets-managers.md): AWS, Vault, Azure Key Vault, Google
2. [The `.env` file problem, shown live](docs/learn/02-the-env-file-problem.md)
3. [Why a secrets manager](docs/learn/03-why-a-secrets-manager.md): encryption, audit, rotation, Terraform/Ansible, JWT workload identity
4. [Secure Notes, before and after](docs/learn/04-secure-notes-app.md): the architecture and the code an app must add
5. [System design review](docs/learn/05-system-design.md): what's right, what to improve, the target architecture
6. [Inside the app: request flows](docs/learn/06-request-flows.md): startup, rotation, log masking
7. [Alerts and audit](docs/learn/07-alerts-and-audit.md): from a log line or a CloudTrail record to an email, an SMS and a chat post

## Run it

The same images run three ways.

| Path | Where | Secrets come from | AWS account? |
| --- | --- | --- | --- |
| **A. Docker Compose** | Your laptop | A bundled Secrets Manager mock | No |
| **B. Kubernetes / OpenShift** | kind, OpenShift, or EKS/ROSA | The mock in the cluster, or real Secrets Manager via IRSA | Only for EKS/ROSA |
| **C. AWS on EC2** | An EC2 instance built by CloudFormation | Real Secrets Manager via the instance role | Yes |

Quickest start (needs only a container engine: Docker, or Podman after `. scripts/podman.env`):

```bash
docker compose up --build        # dashboard http://localhost:3000, notification console http://localhost:4575
docker compose down -v           # stop and wipe

# with the log pipeline (OpenTelemetry Collector, VictoriaLogs, vmalert, Alertmanager):
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build
```

**On a MacBook:** `scripts/bootstrap/macos.sh` installs what's missing (Homebrew formulae,
Docker Desktop, or Podman Desktop with `--podman`; then `. scripts/podman.env` in each terminal), then `scripts/preflight.sh kind` checks the machine. kind maps the app to
`localhost:3000` (`scripts/kind-up.sh`); OpenShift Local works too, building the images on
the cluster for Apple silicon (`scripts/openshift-build.sh`).

- **First time:** the [step-by-step guide](docs/GUIDE.md): every command, what you should see, troubleshooting.
- **Done it before:** the [quick reference](docs/reference/deploy-quickref.md): the commands for A, B and C.

## See it work

- [Tutorial](docs/TUTORIAL.md): every feature on your laptop, with screenshots.
- [Demo pages](demo/README.md): one page per test case, with the CI screenshot and output.
- [Test cases](docs/TEST-CASES.md): every automated test and what it proves.

Every push runs paths A and B on a GitHub runner and publishes the screenshots and logs to
the [`ci-captures`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures)
branch ([what CI proves](docs/reference/ci.md)).

## Reference

| Page | For |
| --- | --- |
| [Alerts and notifications](docs/reference/alerts.md) | Every alert: what it means, who gets it, what to do first; how alerts travel locally and on AWS |
| [Security controls](docs/reference/security-controls.md) | Every control and where it lives; debug logging and the reveal flag; SDK vs agent mode; the production checklist |
| [Secret naming convention](docs/reference/secret-naming.md) | `/{service}/{env}/{resource}/{name}`, set from env vars, `config.yaml`, `config.env`, Kustomize, or Helm (example) |
| [CI](docs/reference/ci.md) | What each job proves |
| [Quick reference](docs/reference/deploy-quickref.md) | Commands for paths A–C, and the project layout |

## Repository map

Each folder has a README that explains what's in it.

| Folder | What it holds |
| --- | --- |
| [`backend/`](backend/README.md) | The app (Node.js): secrets cache, rotation-aware clients, logging and alerts |
| [`frontend/`](frontend/README.md) | The dashboard: static files, no build step |
| [`deploy/`](deploy/README.md) | kind cluster config, Kubernetes overlays (kind, OpenShift, AWS), the log pipeline config |
| [`infra/`](infra/README.md) | AWS: the CloudFormation stacks, the Redis rotation function, the systemd unit |
| [`dev/`](dev/README.md) | Dev/CI only: the AWS stand-in and the local SNS with a screen |
| [`scripts/`](scripts/README.md) | Set up, run, prove and generate: the same scripts on a laptop and in CI |
| [`docs/`](docs/README.md) | The learning path, tutorial, guide, test catalogue, reference and the modernization case study |
| [`demo/`](demo/README.md) | One page per test case, with CI screenshots |
| [`versions/`](versions/README.md) | Earlier versions you can run (v0: the `.env` app) |
| [`HANDOVER.md`](HANDOVER.md) | For a new contributor or AI agent: the state, the rules, the open work, and how to rebuild the lab on a Mac |

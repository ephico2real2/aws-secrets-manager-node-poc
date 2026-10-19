# Handover: continue this project in a new session

**Read this file first, then follow it.** It holds everything a new AI agent (Claude Code or
any other) needs to pick the work up where it stopped. The last session ended on
2026-10-18; the last code change is commit `4cf522a`, with every CI job green (run
39175989647, including `compose (podman)` and the chat-route check). That session ran the lab
on the owner's MacBook on Podman (section 11), closed #114, #118 and #123, and parked #119.

Paste this into a new session to start:

> You are continuing work on `ephico2real2/aws-secrets-manager-node-poc`. Read `HANDOVER.md`
> at the repo root and follow its working rules exactly, especially the commit rules. Then
> run the "Get your bearings" commands, tell me in five lines what state the repo is in,
> and ask me which open item to take next. Don't change anything until I answer.

To rebuild the lab on a MacBook instead, paste:

> Read `HANDOVER.md` in this repo and follow section 11, "Recreate the lab on a MacBook".
> Use Podman (`scripts/bootstrap/macos.sh --podman`, then `. scripts/podman.env`); don't
> start Docker Desktop. Show me the preflight table first. Then bring up the target I name
> (Docker Compose, kind, or Compose with the log pipeline), run its check script, and give
> me the URLs. Stop and ask before resizing the Podman machine or installing anything that
> needs my password.

---

## 1. What this project is

**Secure Notes** is a small Node.js notes app (Postgres and Redis behind a dashboard). It
teaches one thing: an app that reads its database and cache credentials from **AWS Secrets
Manager at runtime**, so no password is ever in an env var, a file, an image, a log or a
Kubernetes object. CI proves that claim on every push by searching the running stack for
the real password values.

It is three things at once:

1. **An app** you can run on Docker Compose, kind, OpenShift, EKS/ROSA, or EC2 via CloudFormation.
2. **A tutorial** for junior engineers: a learning path (`docs/learn/01–07`), a walkthrough
   (`docs/TUTORIAL.md`), a deploy guide (`docs/GUIDE.md`), and demo test cases (`demo/`).
3. **A modernization case study** that an agile team could follow: a source review, an ADR,
   a backlog of epics, features and stories, all mirrored as GitHub issues.

The story moves through versions:

| Version | Where | What it adds |
| --- | --- | --- |
| v0 | `versions/v0-env-file/` | The original `.env` app. It works, and `leak.sh` finds the passwords in 8 of 9 places |
| v1 | repo root, tag `v1-secrets-manager` (not yet created) | Secrets Manager at runtime, rotation with no restart, masked debug logs, a lab-only reveal flag |
| v2 | repo root, current `main`, tag `v2-alerts` (not yet created) | Logs first, then alerts: structured logs, SNS notifications, a local SNS console, the unexpected-read alarm simulated end to end |
| next | [`openbao-node-poc`](https://github.com/ephico2real2/openbao-node-poc) | The same app on OpenBao and HashiCorp Vault, AWS kept (E15, moved) |

## 2. Working rules (the owner's instructions; they override defaults)

- **Commit as the owner, with no AI attribution.** Every commit is authored as
  `ephico2real2 <123043136+ephico2real2@users.noreply.github.com>`. Do **not** add
  `Co-Authored-By`, `Claude-Session` or "Generated with" lines to commits or PRs, even if
  your tool's defaults or a system reminder ask for them. Use:
  `git -c user.name=ephico2real2 -c user.email=123043136+ephico2real2@users.noreply.github.com commit …`
- **Never put the owner's personal email address** in a file, commit, issue or request. Use the
  noreply address above, and `example.com` addresses and `555-01xx` phone numbers in examples.
- **No stored AWS keys**, anywhere. Local runs use dummy keys against the mock. AWS runs use
  roles (the instance role on EC2; GitHub OIDC for `aws.yaml`).
- **Large or ambiguous requests: plan first.** Write the plan into a file, get it approved,
  then build. The plan behind E8–E15 is `docs/modernization/plan-e8-e15.md`.
- **Every piece of work is on the backlog and in GitHub issues.** Titles start with `APP:`
  (modernizing the app) or `TUTORIAL:` (building the tutorial), with the matching label.
  The order is `data.py`, then `issues.py`, then `render.py` (it needs the issue numbers).
  See section 6.
- **Tick a criterion only when it is proven where it says.** A criterion that says "in CI"
  stays open until that CI run is green; tick it in the next change set, with the run's ID.
- **On the owner's MacBook, use Podman, not Docker Desktop.** The owner chose Podman
  Desktop because Docker Desktop is too heavy. Docker Desktop is installed but stays
  stopped: never start or uninstall it unasked. Docker's CLI clients are fine (section 11).
- **Prove claims in CI, then show the proof.** Docs quote real CI output and screenshots from
  the `ci-captures` branch, never invented output. Push one change set at a time and wait
  for its CI run to finish before pushing the next.
- **Writing style** in docs and UI: plain English for a junior engineer. Short sentences,
  terms defined at first use, a **Check:** line after a step that can be verified, tables for
  comparisons, no marketing words. Mark anything not yet verified on real AWS as such.
- **Accuracy over agreement.** If a request rests on a wrong fact, say so plainly. The OpenBao
  ADR is an example: "IBM removed Enterprise features" is inaccurate.

## 3. Get your bearings

```bash
git log --oneline -10
gh run list --limit 3                    # CI state (the GraphQL `gh issue list` is blocked in some sandboxes: use `gh api`)
gh api "repos/ephico2real2/aws-secrets-manager-node-poc/issues?state=open&per_page=100" \
  -q '.[] | "#\(.number) \(.title)"'
(cd backend && npm ci && npm test)       # unit tests
node --test dev/aws-mock/test/*.test.js  # mock tests (EventBridge matcher, SNS, CloudTrail)
node scripts/sync-alert-rules.js --check && python3 scripts/sync-event-pattern.py --check   # on a Mac: .tmp/venv/bin/python3 (section 9)
node scripts/docs-check.js               # links (and Mermaid if Playwright is set up)
. scripts/podman.env                     # on the owner's Mac: the docker CLI and kind at Podman (section 11)
docker compose up --build -d             # http://localhost:3000 (app) and :4575 (notification console)
scripts/compose-check.sh                 # end-to-end, alert paths and the credential scan
```

## 4. Map of the repo

| Path | What it is |
| --- | --- |
| `backend/src/` | The app. `secrets/` (provider, fetchers for SDK and agent mode, naming convention, redactor, `SecretValue`), `clients/` (rotation-aware pg and ioredis), `alerts/` (**catalogue.js**, notifier, recipient masks), `logship/` (OTLP shipper, file sink), `log.js`, `config.js` (refuses unsafe settings), `routes.js`, `security/checks.js` (posture) |
| `frontend/` | The dashboard (no build step; strict CSP). Includes the Rotation lab, leak test and Detection lab |
| `dev/aws-mock/` | **Dev only.** Stands in for Secrets Manager, STS, CloudTrail and EventBridge (`lib/event-pattern.js`, with the stack's own rule in `rules/secret-read-alert.json`). `sns-logger/` is a local SNS with a screen on :4575 (same image, second entrypoint) |
| `docker-compose.yml` | Base stack: app, aws-mock, sns-logger, seed, postgres, redis |
| `docker-compose.agent.yml` | Agent mode (AWS Workload Credentials Provider stand-in) |
| `docker-compose.observability.yml` | Optional log pipeline: OpenTelemetry Collector → VictoriaLogs → vmalert → Alertmanager → sns-logger |
| `deploy/kind/cluster.yaml` | The kind cluster: node image pinned by digest (amd64 + arm64), the app and the console mapped to `127.0.0.1:3000` and `:4575` through NodePorts |
| `deploy/observability/` | Collector, Alertmanager config (routes generated), vmalert rules (generated) |
| `deploy/k8s/` | Kustomize: base, components, overlays `kind`, `openshift` (two Routes), `openshift-local` (images built on the cluster), `aws`, and `mirror` (generated) |
| `infra/cloudformation.yaml` | The EC2 stack: VPC endpoint, KMS keys, RDS with a managed secret, ElastiCache with an RBAC user and a rotation function, alert topics, CloudWatch agent, **generated** metric filters and alarms, and `SecretReadAlertRule` |
| `infra/github-actions-bootstrap.yaml` | OIDC role for the manual `aws.yaml` workflow |
| `infra/tags.json` | The tags every AWS resource carries (`Project`, `Owner`, `Repository`, `ManagedBy`, plus `Stack`, `Environment`, `DeployedBy`) and the reviewed lists of taggable and untaggable resource types; `scripts/tags-check.py` holds both templates and the workflow to it |
| `versions/v0-env-file/` | The "before" app and `leak.sh` |
| `scripts/` | `bootstrap/macos.sh` and `bootstrap/linux.sh` (set up a machine), `preflight.sh` (check it), `podman.env` (source it: the docker CLI and kind at Podman), `kind-up.sh` / `kind-down.sh`, `openshift-build.sh`, `compose-check.sh`, `k8s-check.sh`, `alerts-check.sh`, `pipeline-check.sh` (the log pipeline, and a warning that goes to chat only), `credential-scan.sh` (searches for the real values), `capture-local.sh` (CI's checked walk, on your machine), `k8s-deploy.sh`, `images-build.sh`, `mirror-images.sh`, `scan-images.sh`, `package.sh`, the `sync-*` generators, `capture/` (Playwright walks with text assertions), `backlog/` (issues and backlog generator), `versions.env` (all pins) |
| `docs/learn/` | Learning path, chapters 1–7 (chapter 7 is alerts and audit) |
| `docs/TUTORIAL.md`, `docs/GUIDE.md`, `docs/TEST-CASES.md` | The walkthrough, the deploy guide (Parts A, B, C; C7b checks alerts on AWS), and the catalogue of automated tests (IDs S, R, L, D, C, F, A, P, K, N…) |
| `docs/reference/` | `alerts.md` (generated table), `secret-naming.md`, `security-controls.md`, `deploy-quickref.md`, `ci.md` |
| `docs/modernization/` | Source review, ADR-001, `backlog.md` (generated), `plan-e8-e15.md` (with an "as built" note), `parked-openbao-vault.md` |
| `docs/releases/` | Release notes used by the milestone workflow |
| `demo/` | Test cases 1–18, one page each, with CI screenshots and output (10 and 14 also show the MacBook run on Podman, labelled) |
| `.github/workflows/` | `ci.yaml` (every push), `aws.yaml` (manual, real AWS), `milestone.yaml` (manual: tag and release) |

## 5. Generated files: edit the source, then regenerate

CI fails if any generated file is stale.

| Source | Command | Writes |
| --- | --- | --- |
| `backend/src/alerts/catalogue.js` | `node scripts/sync-alert-rules.js` | `deploy/observability/vmalert-rules.yaml`, the routes block in `alertmanager.yml`, the alarms block in `infra/cloudformation.yaml`, the table in `docs/reference/alerts.md` |
| `SecretReadAlertRule` in `infra/cloudformation.yaml` | `python3 scripts/sync-event-pattern.py` | `dev/aws-mock/rules/secret-read-alert.json` |
| `infra/rotation/elasticache-user-rotation.js` | `node scripts/sync-rotation-lambda.js` | the inline function in the template |
| `scripts/backlog/data.py` | `python3 scripts/backlog/issues.py` and then `python3 scripts/backlog/render.py` | GitHub issues (idempotent; numbers in `issue-numbers.json`), then `docs/modernization/backlog.md` |

Event names are a contract. Every `event` the code logs must be in the catalogue, and every
catalogued alert must be logged somewhere; a unit test checks both directions. Field names
must not contain `secret` or `token`, because the redactor blanks those keys.

## 6. Backlog and issues

Tracks: **APP** (E0–E6, E8–E12; E15 parked) and **TUTORIAL** (E7, E13, E14). Labels are
`app|tutorial`, `type:epic|feature|story`, `epic:E…`, `size:S|M|L`,
`needs-aws-verification`, and `parked`. Done items are closed with their evidence.

Open stories at handover:

| Issue | Story | Needs |
| --- | --- | --- |
| #91 | **S12.5 Prove it on AWS**: a denied read raises the secret-read alert; a test log event trips an alarm; TestEventPattern fixtures match the mock; a batch read's text names the secret | an AWS account; run `aws.yaml`. This also closes #34, #86, #87, #89, #90 |
| #126 | S5.6 **On AWS: tags checked after deploy, nothing tagged left after teardown**: built (`scripts/aws-tags.py`, 12 unit tests); tests P7, P8 | an `aws.yaml` run, after the bootstrap is deployed again (section 8) |
| #115 | S12.6 Close the by-name gap for the RDS-managed secret (match `detail.resources.ARN` if CloudTrail carries it) | AWS first, to confirm the record shape |
| #30, #31 | S4.1, S4.1b Resource policies on the secrets | AWS verification |
| #32, #37, #38 | S4.4 least-privilege DB user; S4.5 IAM auth spike; S4.6 replica secrets and egress | design and AWS |
| #95 | S13.2 Milestone tags: **the owner runs** `milestone.yaml` (this sandbox can't push tags) | see section 8 |
| #119 | S5.3 Run OpenShift Local end to end: Routes, `openshift-build.sh`, `k8s-check.sh` | **Parked** (label `parked`): CRC was deleted on the owner's Mac on 2026-10-13, and the owner restores it later. Don't recreate it unasked (section 11.4) |
| #102–#111 | E15 **moved** to [`openbao-node-poc`](https://github.com/ephico2real2/openbao-node-poc) (epics B0–B8 there); closed here | — |

Closed on 2026-10-18, with their evidence: #118 (S5.2, the MacBook lab on Podman), #114
(S10.5, a warning goes to chat only: CI run 39174954533) and #123 (S5.4, `capture-local.sh`).
#86, #87, #89, #90 and #34 close with #91.

## 7. How CI works (pattern from the owner's cilium-implementation-poc)

`ci.yaml` jobs:
- `checks`: unit tests, sync checks, shellcheck, kubeconform, cfn-lint.
- `build`: images built once, SBOM and grype gate.
- `compose (sdk)`: runs with the observability overlay, the alerts walk and `pipeline-check` (a critical alert pages; the `app.errors.burst` warning goes to chat only).
- `compose (agent)`.
- `compose (podman)`: the base stack on rootless Podman through the docker CLI (`scripts/podman.env`), then `compose-check.sh`. Not a gate for `images`.
- `kind`: runs `scripts/bootstrap/linux.sh` and `kind-up.sh` (strict preflight), deploys under Pod Security restricted, reaches the app and the console on the mapped host ports (no port-forward), and exports kind's own logs on failure.
- `mirror`.
- `env-file-demo`, `v0-leak`.
- `docs`: links and Mermaid rendering.
- `images`: on `main` only, push to GHCR, cosign sign, SBOM attestation.

Playwright walks (`scripts/capture/*.yaml`) assert the visible text on each page, and push
screenshots and logs to the **`ci-captures`** branch, one folder per run and job.
`demo/images/` are copies of those. When a walk fails, read `walk.log` and the PNG in that
branch.

## 8. Waiting on the owner

**Before the next AWS run,** deploy the bootstrap stack again (GUIDE C11, step 1): since
2026-10-18 the workflow tags the stack, which needs `cloudformation:TagResource` on the deploy
role. Without it the run stops at "Deploy the stack" with access denied.

Create the two milestone releases. Go to Actions → **milestone** → Run workflow:

| tag | ref | notes_file |
| --- | --- | --- |
| `v1-secrets-manager` | `8b9974c` | `docs/releases/v1-secrets-manager.md` |
| `v2-alerts` | `b5404d6` (or a later green commit) | `docs/releases/v2-alerts.md` |

Then close #95.

## 9. Lessons that cost time (don't repeat them)

- **CSS changes text.** `.timeline .tag` is upper-case, so a capture that expects "alarm sent"
  must match text that isn't transformed ("published to SNS").
- **VictoriaLogs' image has no shell or wget,** so it gets no healthcheck; dependents use `service_started` and retry.
- **VictoriaLogs ingests OTLP protobuf only.** The app sends OTLP/HTTP JSON to the collector, which converts.
- **Alertmanager rejects unknown top-level keys.** Keep YAML anchors inside a receiver.
- **CloudWatch alarms carry no SNS message attributes,** so filter policies drop them. That is why there are three topics routed by severity, not one filtered topic.
- **EventBridge and read-only events.** It only delivers `GetSecretValue` to a rule in state `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`.
- **The `aws/sns` key.** EventBridge and CloudWatch alarms can't publish to a topic encrypted with it. These two facts are why S4.2 could never fire before v2.
- **Exit paths lose async writes.** The file sink writes synchronously so `config.unsafe` survives `process.exit`.
- **`pkill -f` can match your own shell.** Use PIDs.
- **Homebrew's Python refuses `pip install --user`** (PEP 668), and Homebrew has no PyYAML formula. `scripts/bootstrap/macos.sh` puts PyYAML in `.tmp/venv` at `PYYAML_VERSION`; the preflight checks it.
- **A VM's memory reads low inside it.** A 4 GiB Podman machine reports 3887 MiB, so a whole-GiB floor said "3 GiB". The preflight compares MiB, allowing 10%.
- **The docker CLI does not find Podman by itself.** `DOCKER_HOST` must point at the machine's API socket, and kind needs `KIND_EXPERIMENTAL_PROVIDER=podman`; the preflight says so when either is missing, and `. scripts/podman.env` sets both.
- **The refresh route allows one manual refresh per secret every 2 s** (`routes.js`); faster calls get a 429 and log nothing. `pipeline-check.sh` paces its forced refreshes for that.
- **A check must be seen to fail.** The chat-route check was run once with the burst routed to the paging receiver: both lines said `FAIL`. Do the same for any new check.
- **The sandbox's network is limited.** If `npm install` can't reach the registry locally, CI resolves the lockfile (the `checks` job uploads it as an artifact). Tag pushes and some GitHub APIs (GraphQL, releases) are blocked in the cloud sandbox; use REST through `gh api`.
- **sns-logger only accepts signed requests that carry no `Origin`.** A hand-made `curl` POST needs an `Authorization: AWS4-HMAC-SHA256 Credential=<key>/…` header. The access key ID is the caller's identity in the mock (`local-app`, `local-seed`, `local-intruder-user`, `local-intruder-role`, `local-events`, `local-alertmanager`; unsigned is `local-tooling`).
- **kind's NodePort traffic is subject to NetworkPolicy.** kindnet enforces policies, and traffic from a host port arrives from the node, not from a pod. So the console needs its own allow rule (`overlays/kind/console-networkpolicy.yaml`). OpenShift's router needs one too (`router-networkpolicy.yaml`, using the `policy-group.network.openshift.io/ingress` namespace label).
- **The published images are amd64 only.** OpenShift Local on an Apple-silicon Mac runs arm64, so it builds the images on the cluster (`scripts/openshift-build.sh`). kind on a Mac is fine: `images-build.sh` builds locally for the Mac's CPU, and the node image is multi-arch.
- **Buildah enforces short-name rules,** so the Dockerfiles name `docker.io/library/node:22-alpine` in full.
- **The cloud sandbox can't pull from Docker Hub** or reach dl.k8s.io, so kind and OpenShift changes are proven in CI (kind) or by the owner (OpenShift), not locally.

## 10. Where to read more

- Decisions: `docs/modernization/02-adr-001-secrets-manager-selection.md`, and `plan-e8-e15.md` (the "As built" table lists where the build differs from the plan, and why).
- Alerts: `docs/learn/07-alerts-and-audit.md` and `docs/reference/alerts.md`.
- Every automated test, by ID: `docs/TEST-CASES.md`.
- The parked Vault/OpenBao work: `docs/modernization/parked-openbao-vault.md`.
- Every folder has a README; `docs/README.md` is the index of the documentation.

## 11. Recreate the lab on a MacBook

Use this when the owner asks to run the lab on their Mac (Apple silicon or Intel). Every
command runs from the repo root. Ask before anything that needs their password.

**The owner's Mac runs the lab on Podman Desktop** (machine `podman-machine-default`: 4 CPUs,
4 GiB, rootless), not Docker Desktop. Docker Desktop is installed but stays stopped; don't start
it. Every command below works unchanged once `. scripts/podman.env` has run in that terminal.
Resizing the machine is fine when a lab needs it, but 4 GiB was enough for every lab. When the
work is done, stop the lab, and `podman machine stop` frees the memory.

### 11.1 Get the code and the tools

```bash
git clone https://github.com/ephico2real2/aws-secrets-manager-node-poc.git
cd aws-secrets-manager-node-poc
scripts/bootstrap/macos.sh --podman       # the owner's Mac: Podman Desktop
. scripts/podman.env                      # in every new terminal
# scripts/bootstrap/macos.sh              # another Mac with Docker Desktop; add --openshift for the oc CLI
```

`macos.sh` needs Homebrew (<https://brew.sh>; its installer asks for the password, so the
owner runs it). It installs what's missing:
- the formulae `bash`, `jq`, `node`, `kind` and `kubernetes-cli` (plus `openshift-cli` with `--openshift`);
- with `--podman`: the `podman` formula and the Podman Desktop cask, a 4 GiB machine if none
  exists, and Homebrew's `docker` and `docker-compose` clients only if no `docker` CLI is on the `PATH`;
- without it: the Docker Desktop cask;
- PyYAML in `.tmp/venv`, for `scripts/sync-event-pattern.py`.

Then it starts the engine and prints the preflight tables. It changes no settings.

Fix every `REQUIRED-FAIL` row before going on. The common ones on a new Mac:

| Row | Fix |
| --- | --- |
| `bash (env bash)` 3.2 | `brew install bash`, then open a new Terminal, so `/opt/homebrew/bin` comes before `/bin` |
| `docker` not answering | Podman: `podman machine start`, then `. scripts/podman.env` (the row prints the socket). Docker Desktop: `open -a Docker` |
| `kind provider` (warn) | `. scripts/podman.env` (it sets `KIND_EXPERIMENTAL_PROVIDER=podman`) |
| `memory for the lab` (warn) | 4 GiB for every lab (measured: 1.5 GiB used with kind, 1.0 GiB with the log pipeline). Podman: `podman machine stop && podman machine set --memory 4096 && podman machine start`; Docker Desktop: Settings → Resources → Memory |
| `port 3000` / `4575` in use | Another lab is running: `docker compose down` or `scripts/kind-down.sh` |

### 11.2 Docker Compose (the quickest lab)

```bash
scripts/preflight.sh compose
docker compose up --build -d
scripts/compose-check.sh                  # ends with "All checks passed" and the alert checks
# http://localhost:3000 (dashboard) · http://localhost:4575 (notification console)
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build -d   # optional log pipeline
docker compose down -v                    # stop and wipe
scripts/capture-local.sh compose          # optional: screenshots, each page checked like CI's (.tmp/captures/)
```

### 11.3 kind

```bash
docker compose down -v                    # kind uses the same two ports
scripts/kind-up.sh                        # preflight (strict), then deploy/kind/cluster.yaml
scripts/images-build.sh                   # builds for the Mac's CPU and loads into kind
scripts/k8s-deploy.sh deploy/k8s/overlays/kind
scripts/k8s-check.sh                      # ends with "k8s-check: all checks passed"
# http://localhost:3000 · http://localhost:4575  (no port-forward)
scripts/kind-down.sh
```

To run kind beside Compose, use `KIND_APP_PORT=3100 KIND_CONSOLE_PORT=4675 scripts/kind-up.sh`.
**On Podman,** `. scripts/podman.env` sets `DOCKER_HOST` to the machine's API socket and
`KIND_EXPERIMENTAL_PROVIDER=podman`; the commands above and those of 11.2 are then unchanged.

Proven on 2026-10-18 on the owner's MacBook (Apple silicon, Podman 6.1.2, rootless, 4 CPUs,
4 GiB, Docker Desktop stopped): `compose-check.sh` and `k8s-check.sh` both passed. The machine
used 1074 MiB of 3887 with Compose, 1582 MiB with kind, and 980 MiB with Compose and the log
pipeline (`pipeline-check.sh` passed), so 4 GiB is enough for every lab. Screenshots: demo test cases 10 and 14. Colima is not tried.

Without Docker Desktop, the bootstrap installs Homebrew's `docker` and `docker-compose`; add
`"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]` to `~/.docker/config.json` (GUIDE B1,
"Without Docker Desktop"). Proven with docker 29.9.1 and docker-compose 5.6.0 (bottles unpacked, Docker
Desktop's CLI off the `PATH`): `compose-check.sh` passed.

### 11.4 OpenShift Local (CRC)

**Parked (#119).** CRC was deleted on the owner's Mac on 2026-10-13; the owner restores it
later. Don't run `crc setup` or `crc start`, or download a bundle, unless the owner asks.

The owner downloads CRC with their Red Hat account (console.redhat.com/openshift/create/local),
then:

```bash
crc setup
crc config set memory 10240 && crc config set cpus 4
crc start                                  # asks for the pull secret the first time
eval $(crc oc-env)
oc login -u developer https://api.crc.testing:6443   # password: developer
scripts/preflight.sh openshift
oc new-project secure-notes
scripts/openshift-build.sh                 # builds both images ON the cluster from HEAD (arm64 on Apple silicon)
# it prints https://secure-notes-secure-notes.apps-crc.testing and https://sns-logger-secure-notes.apps-crc.testing
oc -n secure-notes port-forward svc/secure-notes 3000:80 &
KUBECTL=oc scripts/k8s-check.sh
```

On an Intel Mac, or any amd64 cluster that can pull from ghcr.io, `KUBECTL=oc
scripts/k8s-deploy.sh deploy/k8s/overlays/openshift` deploys the published images instead.

`openshift-build.sh` uploads committed code only (`git archive` of HEAD), so commit before
building. CRC's certificates are self-signed, so the browser asks to accept each address
once.

**Not yet proven:** CI has no OpenShift cluster. The Routes, the router policy and
`openshift-build.sh` were written from Red Hat's documentation and validated by kustomize
and kubeconform, but have not run on CRC yet. If a step fails:
1. Fix it.
2. Record what changed in section 9 of this file.
3. Update GUIDE B2.

### 11.5 The AWS path from a Mac

Part C of `docs/GUIDE.md` works from a Mac as written. It needs the AWS CLI
(`brew install awscli`) and the Session Manager plugin
(`brew install --cask session-manager-plugin`). Sign in with SSO or a role; never with
stored keys.

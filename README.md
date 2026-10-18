# Secure Notes — Node.js consuming AWS Secrets Manager without exposing credentials

[![ci](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/workflows/ci.yaml/badge.svg)](https://github.com/ephico2real2/aws-secrets-manager-node-poc/actions/workflows/ci.yaml)

A small but complete app (frontend, Node.js backend, Postgres, Redis) that shows how a
Node service should get its database and cache credentials from AWS Secrets Manager
and keep them out of disk, environment variables, logs and API responses. A dashboard
lets you watch the secrets load, rotate them, see the app recover by itself, and try
to leak them.

The same app, built into the same images, runs three ways:

| Path | Where it runs | Secrets come from | AWS account? | Start here |
| --- | --- | --- | --- | --- |
| **A. Docker Compose** | Your laptop | Bundled Secrets Manager mock | No | [A](#a-run-locally-with-docker-compose) |
| **B. Kubernetes / OpenShift** | kind, OpenShift Local, a dev cluster — or EKS/ROSA with real AWS | Mock in the cluster, or real Secrets Manager via IRSA | Only for EKS/ROSA | [B](#b-run-on-kubernetes-or-openshift) |
| **C. AWS on EC2** | An EC2 instance built by CloudFormation | Real Secrets Manager via the instance role | Yes | [C](#c-deploy-to-aws-on-ec2) |

**New to this?** Follow the step-by-step guide in [`docs/GUIDE.md`](docs/GUIDE.md): every
command, what you should see after it, and troubleshooting, written for a first deployment.

**See it work:** the [tutorial](docs/TUTORIAL.md) walks through every feature on your laptop;
the [demo folder](demo/README.md) has one page per test case, with the CI screenshot and
output for each; and [`docs/TEST-CASES.md`](docs/TEST-CASES.md) lists every automated test and
what it proves.

Every push runs path A and path B on kind on a GitHub runner and publishes screenshots of the
dashboard to the [`ci-captures`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/tree/ci-captures)
branch — see [CI](#ci-what-every-push-proves).

## One build, one set of images

`docker compose build` is the only place images are built. It produces
`secure-notes-app:dev` and `secure-notes-aws-mock:dev`; Docker Compose runs them,
`scripts/images-build.sh` loads the exact same images into kind, and CI pushes the
images that passed every job to GHCR (`ghcr.io/ephico2real2/aws-secrets-manager-node-poc/app`)
for OpenShift and EKS to pull. Nothing is rebuilt between the test and the publish.

## A. Run locally with Docker Compose

Needs only Docker.

```bash
docker compose up --build        # then open http://localhost:3000
docker compose down -v           # stop and wipe (new random credentials next time)
```

Five containers start: Postgres 16, Redis 7, the Secrets Manager mock (`dev/aws-mock`),
a one-shot `seed` job and the app. The seed job generates random passwords, stores them
in Secrets Manager, applies them to Postgres and Redis, then replaces the bootstrap
passwords. After startup, the only copy of every credential is in Secrets Manager.

**Agent mode:** the same stack with the app reading its secrets through a local agent
on its own `localhost:2773`, as `SECRETS_MODE=agent` does on EC2:

```bash
docker compose -f docker-compose.yml -f docker-compose.agent.yml up --build
```

> LocalStack's image now requires an account and auth token, so the project ships its
> own zero-dependency mock. Point `AWS_MOCK_ENDPOINT` at LocalStack if you prefer it.

## B. Run on Kubernetes or OpenShift

Kustomize, in `deploy/k8s/`:

| Directory | What it is |
| --- | --- |
| `base/` | The app alone: hardened Deployment (non-root, read-only root, no capabilities, seccomp), Service, ServiceAccount with no token, default-deny NetworkPolicies. Production mode, no credentials. |
| `components/local-backing-services/` | Postgres, Redis, the mock and the seed Job inside the cluster, each reachable only from the app and the seed. |
| `overlays/kind/` | base + backing services, Pod Security `restricted` enforced on the namespace. |
| `overlays/openshift/` | base + backing services + a TLS Route, published images, no fixed UIDs so the restricted-v2 SCC assigns them. |
| `overlays/aws/` | base only, against real RDS, ElastiCache and Secrets Manager; the ServiceAccount carries an IAM role (IRSA) on EKS or ROSA. |

**kind** (needs Docker, kind and kubectl):

```bash
scripts/kind-up.sh                                # the cluster
scripts/images-build.sh                           # docker compose build, then load into kind
scripts/k8s-deploy.sh deploy/k8s/overlays/kind    # apply and wait
kubectl -n secure-notes port-forward svc/secure-notes 3000:80   # open http://localhost:3000
scripts/k8s-check.sh                              # evidence + smoke test (in another terminal)
```

**OpenShift** (OpenShift Local / CRC or a dev cluster; images pulled from GHCR):

```bash
oc new-project secure-notes
KUBECTL=oc scripts/k8s-deploy.sh deploy/k8s/overlays/openshift
oc -n secure-notes get route secure-notes        # open https://<that host>
```

**A cluster that can't reach ghcr.io or Docker Hub:** copy the four images into a
registry it can reach, then deploy the overlay the script generates (it checks that
every image comes from your registry):

```bash
skopeo login registry.example.com             # or podman/oc registry login
scripts/mirror-images.sh registry.example.com/team/secure-notes
KUBECTL=oc scripts/k8s-deploy.sh deploy/k8s/overlays/mirror
```

It uses `skopeo` (or `oc image mirror` with `MIRROR_TOOL=oc`); `BASE_OVERLAY=kind`
mirrors for the kind overlay instead. A private registry also needs a pull secret
linked to the `secure-notes` and `default` service accounts.

**EKS or ROSA, real AWS:** fill in the placeholders in `deploy/k8s/overlays/aws/`,
create the IAM role for IRSA (`infra/irsa-trust-policy.example.json`) and the `rds-ca`
ConfigMap, then `kubectl apply -k deploy/k8s/overlays/aws`. The IRSA role gets the same
read-only, two-secret policy as the EC2 role.

## C. Deploy to AWS on EC2

```bash
./scripts/package.sh my-artifacts-bucket            # zip the app and upload it
aws cloudformation deploy \
  --stack-name secure-notes \
  --template-file infra/cloudformation.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      VpcId=vpc-xxxx AppSubnetId=subnet-app \
      DataSubnetIds=subnet-a,subnet-b \
      AppArtifactBucket=my-artifacts-bucket
# then run the stack's "OpenTheApp" output and browse to http://localhost:3000
```

The stack creates a KMS key, a Secrets Manager VPC endpoint, RDS Postgres with
`ManageMasterUserPassword` (RDS creates and rotates the secret), ElastiCache for Redis
with TLS and an RBAC user, the least-privilege instance role, and an IMDSv2-only
instance with no inbound ports, running the app under a hardened systemd unit.
Pass `SecretsMode=agent` to use the AWS Workload Credentials Provider instead of the SDK.

The Redis password rotates too: a small function in the stack
([`infra/rotation/elasticache-user-rotation.js`](infra/rotation/elasticache-user-rotation.js),
unit-tested and copied into the template by `scripts/sync-rotation-lambda.js`) adds a
new password next to the old one (ElastiCache users accept two), moves `AWSCURRENT`,
then retires the old password, every `RedisRotationDays` (30 by default). The app
re-reads the secret when Redis rejects the old password, so nothing restarts.

### Part C from GitHub Actions (manual)

[`.github/workflows/aws.yaml`](.github/workflows/aws.yaml) runs Part C end to end on demand:
deploy the stack, check the instance through SSM Run Command (no secrets in the
config or the process environment, IMDSv1 rejected), rotate the RDS-managed and Redis secrets,
photograph the real dashboard through an SSM port forward, list who read the secrets
from CloudTrail, then tear everything down (snapshot, leftover secret and artifacts
included) unless you ask to keep it.

It never runs on push and stores no AWS keys: the job runs in the GitHub environment
`aws` and assumes a role through GitHub's OIDC token. That role can deploy and rotate,
but cannot read any secret. One-time setup:

1. As an admin, deploy the bootstrap stack:
   `aws cloudformation deploy --stack-name secure-notes-github --template-file infra/github-actions-bootstrap.yaml --capabilities CAPABILITY_NAMED_IAM`
2. In the repository settings, create the environment `aws` and add yourself as a required reviewer.
3. On that environment, set `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `AWS_CFN_EXEC_ROLE_ARN`,
   `AWS_ARTIFACT_BUCKET` (the bootstrap stack's outputs), `AWS_VPC_ID`, `AWS_APP_SUBNET_ID`
   and `AWS_DATA_SUBNET_IDS` (comma-separated, two or more AZs).
4. Actions → **aws (Part C)** → Run workflow.

## CI: what every push proves

[`.github/workflows/ci.yaml`](.github/workflows/ci.yaml):

```
checks ─► build ─┬─► compose (sdk, agent) ─┐
         (scan,  ├─► kind ─────────────────┼─► images (main only: push, sign, attest)
          SBOM)  └─► mirror ───────────────┘
```

| Job | What it proves |
| --- | --- |
| `checks` | Unit tests with the real `pg`, `ioredis` and AWS SDK; every JS file parses; shellcheck; every Kustomize overlay renders and matches its schemas (the OpenShift Route is skipped: it has no public schema); `cfn-lint` on both CloudFormation templates; actionlint on every workflow; the Redis rotation function's tests, and that the copy in the template matches it. |
| `build` | `docker compose build`, once; a CycloneDX SBOM per image (syft) and a vulnerability scan (grype) that fails on any CRITICAL vulnerability with a fix; the images are saved and handed to every later job. |
| `compose (sdk)`, `compose (agent)` | Path A on the runner, once per secrets mode: the dashboard walk, the bootstrap passwords burned, the end-to-end smoke test. In agent mode also: the agent served the app's fetches, its SSRF token is visible only to the agent and the app, and it rejects a request without the token. |
| `kind` | Path B under Pod Security `restricted`: who each container runs as, that Kubernetes holds no copy of the app's credentials, the bootstrap burned, SCRAM-only password changes in the Postgres log, and the smoke test. |
| `mirror` | `scripts/mirror-images.sh` copies all four images into a throwaway registry; the generated overlay pulls only from it and the copies match the originals. |
| `images` | On `main`, pushes the exact images that passed to GHCR, signs each digest with cosign (keyless, this workflow's GitHub identity) and attaches its SBOM as a signed attestation, then verifies both without logging in. |
| `aws (Part C)` | Separate, manual workflow (above): Part C on real AWS, then teardown. Linted on every push. |

The dashboard walk (`scripts/capture/`, adapted from
[cilium-implementation-poc](https://github.com/ephico2real2/cilium-implementation-poc))
drives Chromium through `scripts/capture/dashboard.yaml`: first load, a Postgres
rotation and recovery, a Redis rotation, the leak test and a phone-width view. Each
page states the text it must show, so a screenshot of a broken page fails the job.
The PNGs go to the `ci-captures` branch, one folder per run and job, and appear on the
run's summary page.

## How the app keeps credentials from being exposed

| Control | Where | Why |
|---|---|---|
| **No keys anywhere** | EC2 instance role; IRSA on EKS/ROSA | The SDK gets short-lived credentials from the platform. Nothing to steal from disk or env. |
| **IMDSv2 required, hop limit 1** | `infra/cloudformation.yaml` | Blocks the SSRF attack that reads role credentials from `169.254.169.254`. |
| **Least-privilege IAM, bound to the VPC endpoint** | `AppRole`, `infra/iam-policy.example.json` | Read-only, two secret ARNs, only via `aws:SourceVpce`; `kms:Decrypt` only through Secrets Manager. |
| **Secrets only in memory** | `backend/src/secrets/provider.js` | Never in files, env vars, CLI args, Kubernetes Secrets or ConfigMaps. |
| **Refuse unsafe config** | `backend/src/config.js` | Startup fails if `DB_PASSWORD`, `PGPASSWORD`, `DATABASE_URL`, `REDIS_URL` etc. are set; in production also on static AWS keys, demo mode or a mock endpoint. The image defaults to production. |
| **Cache: TTL, single-flight, stale-on-error** | `provider.js` | Few API calls, no thundering herd, survives a brief Secrets Manager outage. |
| **Rotation-aware clients** | `backend/src/clients/` | `pg.Pool` reads the password per new connection; on `28P01`/`WRONGPASS` the app force-refreshes and retries, so rotation needs no restart. |
| **`SecretValue` wrapper** | `backend/src/secrets/SecretValue.js` | `JSON.stringify`, `console.log` and template strings print `[REDACTED]`; values only through a greppable `.reveal()`. |
| **Two-layer redaction** | `redactor.js`, `log.js` | Key-based plus value-based scrubbing of every log line and API response; library error objects reduced to safe fields. |
| **Passwords sent as hashes** | `backend/src/demo/crypto.js` | SCRAM verifiers for Postgres, `#sha256` for Redis ACLs: never in server logs. |
| **Hardened runtime** | systemd unit; Kubernetes `securityContext` | Non-root, no core dumps (systemd), read-only root, no capabilities, seccomp, no service-account token. |
| **Network** | Security groups; NetworkPolicies | No inbound to the server; in Kubernetes, default-deny with the backing services reachable only from the app. |
| **Small supply chain** | `backend/package.json` | Four runtime dependencies; HTTP, logging and headers use Node built-ins. |

**Check an image yourself** before you run it:

```bash
cosign verify ghcr.io/ephico2real2/aws-secrets-manager-node-poc/app:latest \
  --certificate-identity https://github.com/ephico2real2/aws-secrets-manager-node-poc/.github/workflows/ci.yaml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
cosign verify-attestation --type cyclonedx <same arguments>      # the signed SBOM
```

A cluster can enforce the same rule at admission (OpenShift's sigstore image policies,
or Kyverno / policy-controller on other clusters). The SBOMs and scan reports of every
build are also in the run's `…build-supply-chain` folder on `ci-captures`.

## Debug logging, the reveal flag, and the credential scan

| Setting | Default | What it does |
| --- | --- | --- |
| `LOG_LEVEL=debug` | `debug` in Compose and kind, `info` on AWS (`LogLevel` parameter) | Each secret load and each login is logged with the secret ID, version and every key: passwords as `******** (32 chars, fp=…)`, usernames partly masked, hosts and ports in full. The dashboard's log panel has a **Credential lines only** filter. |
| `LOG_REVEAL_SECRETS=true` | off | Lab troubleshooting only: those debug lines also print the real values. Red banner on the dashboard, a failing posture check, never served by `/api/logs`, and **refused in production** (the app exits 78). |

`scripts/credential-scan.sh compose|k8s` reads every password from the Secrets Manager
stand-in and searches the running stack for the **values**: container configuration,
pod specs, ConfigMaps, decoded Kubernetes Secrets, events, the app's process environment,
every file in the app container, the Postgres and Redis data, and every container's log.
It never prints a value. `compose-check.sh` and `k8s-check.sh` run it after the end-to-end
test; CI also runs it with the reveal flag on and requires it to find the values in the
app's log and nowhere else.

## SDK mode vs Workload Credentials Provider mode

`SECRETS_MODE=sdk` (default): the app calls `GetSecretValue` with the AWS SDK v3 and
caches in-process. `SECRETS_MODE=agent`: the app calls the AWS Workload Credentials
Provider (formerly the Secrets Manager Agent) on `http://localhost:2773` with the SSRF
token from `/var/run/awssmatoken`, and forces `refreshNow=true` after an auth failure,
because the agent does not invalidate its cache on rotation. AWS notes that anyone on
the host with the token can read the agent's cache, so `sdk` is the default.
CI runs Path A in both modes (`docker-compose.agent.yml`).

## Project layout

```
backend/        Node.js app: src/secrets (provider, fetchers, SecretValue, redactor),
                src/clients (Postgres, Redis), src/security (posture checks),
                src/demo (rotation lab), scripts (seed, smoke test), test (unit)
frontend/       dashboard (vanilla JS, strict CSP, textContent only)
dev/            Secrets Manager + STS + agent mock (dev/CI only), Redis entrypoint
deploy/k8s/     Kustomize base, component and overlays (kind, OpenShift, AWS)
docs/           GUIDE.md (deploy, all three paths), TUTORIAL.md, TEST-CASES.md
demo/           one page per test case, with CI screenshots and output
infra/          CloudFormation (app stack + GitHub OIDC bootstrap), rotation/ (Redis rotation function),
                systemd unit, example IAM and IRSA policies
scripts/        the same scripts on a laptop and in CI; capture/ = the dashboard walk
.github/        ci.yaml and the browser-walk action
```

## Production checklist

- [ ] `NODE_ENV=production` (the image default): enforces the startup guards; demo routes are not registered.
- [x] Rotation on: RDS managed rotation for the DB secret; the stack's rotation function for the Redis user.
- [ ] A dedicated least-privilege DB role for the app instead of the RDS master user.
- [ ] CloudTrail plus an alarm on `GetSecretValue` from any principal other than the app role.
- [ ] Resource policies on the secrets allowing only the app role and admins.
- [ ] No `--inspect`, no shell for the service user, Session Manager logging on.
- [ ] The committed `package-lock.json`, installed with `npm ci`.
- [ ] Only signed images admitted: verify the cosign signature at the cluster (see CI above).

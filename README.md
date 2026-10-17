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

Every push runs paths A and B on a GitHub runner and publishes screenshots of the
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
| `ci/openshift-sim/` | CI only: the openshift overlay on kind, every pod forced to an arbitrary UID with GID 0, the way OpenShift runs it. |

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

### Part C from GitHub Actions (manual)

[`.github/workflows/aws.yaml`](.github/workflows/aws.yaml) runs Part C end to end on demand:
deploy the stack, check the instance through SSM Run Command (no secrets in the
config or the process environment, IMDSv1 rejected), rotate the RDS-managed secret,
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
checks ─► build ─┬─► compose ─────────────────────┐
                 └─► kind (kind, openshift-sim) ───┴─► images (main only)
```

| Job | What it proves |
| --- | --- |
| `checks` | Unit tests with the real `pg`, `ioredis` and AWS SDK; every JS file parses; shellcheck; every Kustomize overlay renders and matches its schemas (Route included); `cfn-lint` on the CloudFormation template. |
| `build` | `docker compose build`, once; the images are saved and handed to every later job. |
| `compose` | Path A on the runner: the dashboard walk, the bootstrap passwords burned, the end-to-end smoke test. |
| `kind (kind)` | Path B under Pod Security `restricted`: who each container runs as, that Kubernetes holds no copy of the app's credentials, the bootstrap burned, SCRAM-only password changes in the Postgres log, and the smoke test. |
| `kind (openshift-sim)` | The OpenShift overlay with every pod as UID 1000680000 / GID 0, so an image that only works as its built-in user fails here, not on your cluster. |
| `images` | On `main`, pushes the exact images that passed to GHCR. |
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

## SDK mode vs Workload Credentials Provider mode

`SECRETS_MODE=sdk` (default): the app calls `GetSecretValue` with the AWS SDK v3 and
caches in-process. `SECRETS_MODE=agent`: the app calls the AWS Workload Credentials
Provider (formerly the Secrets Manager Agent) on `http://localhost:2773` with the SSRF
token from `/var/run/awssmatoken`, and forces `refreshNow=true` after an auth failure,
because the agent does not invalidate its cache on rotation. AWS notes that anyone on
the host with the token can read the agent's cache, so `sdk` is the default.

## Project layout

```
backend/        Node.js app: src/secrets (provider, fetchers, SecretValue, redactor),
                src/clients (Postgres, Redis), src/security (posture checks),
                src/demo (rotation lab), scripts (seed, smoke test), test (unit)
frontend/       dashboard (vanilla JS, strict CSP, textContent only)
dev/            Secrets Manager + STS + agent mock (dev/CI only), Redis entrypoint
deploy/k8s/     Kustomize base, component and overlays (kind, OpenShift, AWS)
infra/          CloudFormation (app stack + GitHub OIDC bootstrap), systemd unit, example IAM and IRSA policies
scripts/        the same scripts on a laptop and in CI; capture/ = the dashboard walk
.github/        ci.yaml and the browser-walk action
```

## Production checklist

- [ ] `NODE_ENV=production` (the image default): enforces the startup guards; demo routes are not registered.
- [ ] Rotation on: RDS managed rotation for the DB secret; Secrets Manager's ElastiCache rotation function for the Redis user.
- [ ] A dedicated least-privilege DB role for the app instead of the RDS master user.
- [ ] CloudTrail plus an alarm on `GetSecretValue` from any principal other than the app role.
- [ ] Resource policies on the secrets allowing only the app role and admins.
- [ ] No `--inspect`, no shell for the service user, Session Manager logging on.
- [ ] The committed `package-lock.json`, installed with `npm ci`.

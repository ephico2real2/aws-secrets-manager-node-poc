# Run and deploy: quick reference

[← README](../../README.md) · Step by step: [GUIDE](../GUIDE.md)

The commands for each path, for when you've done it once. The [guide](../GUIDE.md) explains every step.

## One build, one set of images

`docker compose build` is the only place images are built. It produces
`secure-notes-app:dev` and `secure-notes-aws-mock:dev`; Docker Compose runs them,
`scripts/images-build.sh` loads the exact same images into kind, and CI pushes the
images that passed every job to GHCR (`ghcr.io/ephico2real2/aws-secrets-manager-node-poc/app`)
for OpenShift and EKS to pull. Nothing is rebuilt between the test and the publish.

## A. Run locally with Docker Compose

Needs only Docker to run. The check scripts (`scripts/*-check.sh`) also need Node.js 22, `curl` and `jq`.

```bash
docker compose up --build        # then open http://localhost:3000
docker compose down -v           # stop and wipe (new random credentials next time)
```

Six containers start: Postgres 16, Redis 7, the AWS mock (`dev/aws-mock`: Secrets
Manager, STS, CloudTrail records and the stack's unexpected-read rule), sns-logger (a
local SNS with a screen on http://localhost:4575), a one-shot `seed` job and the app. The seed job generates random passwords, stores them
in Secrets Manager, applies them to Postgres and Redis, then replaces the bootstrap
passwords. After startup, the only copy of every credential is in Secrets Manager.

**Agent mode:** the same stack with the app reading its secrets through a local agent
on its own `localhost:2773`, as `SECRETS_MODE=agent` does on EC2:

```bash
docker compose -f docker-compose.yml -f docker-compose.agent.yml up --build
```

**The log pipeline** (logs first, then alerts; about 600 MB more memory):

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build
# VictoriaLogs http://localhost:9428/select/vmui · vmalert http://localhost:8880 · Alertmanager http://localhost:9093
scripts/pipeline-check.sh        # a real failure becomes a delivered alert
```

**The original app (v0)**, with its passwords in a `.env` file:
`cd versions/v0-env-file && docker compose up --build -d && ./leak.sh` (port 3001).

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
([`infra/rotation/elasticache-user-rotation.js`](../../infra/rotation/elasticache-user-rotation.js),
unit-tested and copied into the template by `scripts/sync-rotation-lambda.js`) adds a
new password next to the old one (ElastiCache users accept two), moves `AWSCURRENT`,
then retires the old password, every `RedisRotationDays` (30 by default). The app
re-reads the secret when Redis rejects the old password, so nothing restarts.

### Part C from GitHub Actions (manual)

[`.github/workflows/aws.yaml`](../../.github/workflows/aws.yaml) runs Part C end to end on demand:
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

## Project layout

```
backend/        Node.js app: src/secrets (provider, fetchers, SecretValue, redactor),
                src/clients (Postgres, Redis), src/security (posture checks),
                src/demo (rotation lab), scripts (seed, smoke test), test (unit)
frontend/       dashboard (vanilla JS, strict CSP, textContent only)
dev/            Secrets Manager + STS + agent mock (dev/CI only), Redis entrypoint
deploy/k8s/     Kustomize base, component and overlays (kind, OpenShift, AWS)
docs/           GUIDE.md (deploy, all three paths), TUTORIAL.md, TEST-CASES.md;
                learn/ (the learning path), modernization/ (initiative, ADR, backlog),
                reference/ (controls, CI, secret naming, this page)
deploy/config/  example config.yaml and config.env (secret naming settings)
demo/           one page per test case, with CI screenshots and output
infra/          CloudFormation (app stack + GitHub OIDC bootstrap), rotation/ (Redis rotation function),
                systemd unit, example IAM and IRSA policies
scripts/        the same scripts on a laptop and in CI; capture/ = the dashboard walk
.github/        ci.yaml and the browser-walk action
```

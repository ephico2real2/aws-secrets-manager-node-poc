# deploy/

[← Project README](../README.md) · [GUIDE.md](../docs/GUIDE.md) · [Quick reference](../docs/reference/deploy-quickref.md)

The manifests and configuration for running Secure Notes on a cluster, plus the
optional log pipeline. Docker Compose files live at the repository root. The AWS
CloudFormation stack lives in [`../infra`](../infra/README.md).

| Path | What it is |
| --- | --- |
| [`kind/cluster.yaml`](kind/cluster.yaml) | The kind cluster: one node, the Kubernetes image pinned by digest (amd64 and arm64), and the app and the notification console mapped to `127.0.0.1:3000` and `:4575`. Used by `scripts/kind-up.sh` |
| [`k8s/base/`](k8s/base) | The app alone: Deployment, Service, ServiceAccount (no token), default-deny NetworkPolicies. Hardened: non-root, read-only root filesystem, no capabilities, seccomp |
| [`k8s/components/local-backing-services/`](k8s/components/local-backing-services) | **Dev only.** Everything AWS would provide, inside the cluster: Postgres, Redis, the AWS stand-in, the local SNS (sns-logger) and the one-shot seed job, with their NetworkPolicies |
| [`k8s/overlays/`](k8s/overlays) | One overlay per target. See the table below |
| [`config/`](config) | Example settings files for the secret naming convention (`config.example.yaml`, `config.example.env`) |
| [`observability/`](observability) | The log pipeline for `docker-compose.observability.yml`: the OpenTelemetry Collector's config, the Alertmanager config, and the vmalert rules. The rules and Alertmanager's routes are **generated** from `backend/src/alerts/catalogue.js` (run `node scripts/sync-alert-rules.js`) |

## Overlays

| Overlay | Use it for | Deploy with |
| --- | --- | --- |
| `kind` | kind on a laptop or in CI; any local Kubernetes | `scripts/kind-up.sh && scripts/images-build.sh && scripts/k8s-deploy.sh deploy/k8s/overlays/kind` |
| `openshift` | OpenShift Local (CRC) or a dev cluster, with the published images from GHCR (amd64) | `oc new-project secure-notes && KUBECTL=oc scripts/k8s-deploy.sh deploy/k8s/overlays/openshift` |
| `openshift-local` | OpenShift with images built on the cluster from your checkout (Apple-silicon CRC, or no access to GHCR) | `oc new-project secure-notes && scripts/openshift-build.sh` |
| `aws` | EKS, or ROSA with STS: only the app, against real RDS, ElastiCache and Secrets Manager, through IRSA | See [GUIDE B3](../docs/GUIDE.md#b3--eks-or-rosa-against-real-aws) |
| `mirror` | Not committed: `scripts/mirror-images.sh` writes it, for clusters that can only pull from your own registry | `KUBECTL=oc scripts/k8s-deploy.sh deploy/k8s/overlays/mirror` |

How the app is reached on each target:

| Target | The app | The notification console |
| --- | --- | --- |
| kind | <http://localhost:3000> (NodePort 30080, mapped by `kind/cluster.yaml`) | <http://localhost:4575> (NodePort 30575) |
| OpenShift | `https://` Route `secure-notes` (edge TLS) | `https://` Route `sns-logger`; the deploy script points the dashboard's link at it |
| Anything else | `kubectl -n secure-notes port-forward svc/secure-notes 3000:80` | `kubectl -n secure-notes port-forward svc/sns-logger 4575:4575` |

The app's credentials never become a Kubernetes object. The only Secret in the namespace
is `local-bootstrap`: the one-time startup passwords, which the seed job replaces
straight away and which stop working after that.

CI checks that every overlay renders and matches its schema (the Route has no public
schema, so it is skipped). It deploys the `kind` overlay on every push. The OpenShift
overlays are validated but not deployed in CI, because CI has no OpenShift cluster.

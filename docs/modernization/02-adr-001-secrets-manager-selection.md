# ADR-001 — Which secrets manager Secure Notes uses on AWS

**Epic E1 · Select the tool.** [← Source review](01-source-review.md) · [Initiative](README.md) · Next: [Backlog →](backlog.md)

| | |
| --- | --- |
| Status | Accepted |
| Context | Requirements R1–R6 from the [source review](01-source-review.md) |
| Decision | **AWS Secrets Manager**, read by the app at runtime with its platform identity |

## Context

Secure Notes runs on AWS (EC2 today; EKS or ROSA next) and uses RDS Postgres and
ElastiCache Redis. It needs a store that keeps its two credentials encrypted, lets only
the app read them, records every read, and rotates them with nobody typing a password.

## Options

| Option | In one line |
| --- | --- |
| A. **AWS Secrets Manager** | Managed secret store with built-in rotation, KMS encryption and IAM access |
| B. **SSM Parameter Store** (`SecureString`) | Managed key/value config store; values can be KMS-encrypted |
| C. **HashiCorp Vault** (self-managed or HCP) | A secrets platform: KV store, dynamic short-lived credentials, many identity methods |
| D. **Kubernetes Secrets** (+ Sealed Secrets or SOPS in git) | Secrets stored as cluster objects; base64, encrypted at rest only if the cluster is set up for it |

## Criteria and scores

3 = meets it well, 2 = with extra work, 1 = poorly or not at all.

| Criterion (requirement) | A. Secrets Manager | B. Parameter Store | C. Vault | D. K8s Secrets |
| --- | --- | --- | --- | --- |
| Rotation without people (R2, R4) | 3 — managed for RDS; Lambda templates for others, incl. ElastiCache users | 1 — none built in | 3 — dynamic DB credentials, leases | 1 — none |
| Platform identity, no stored key (R3) | 3 — IAM roles, IRSA, Pod Identity | 3 — same | 2 — AWS IAM, Kubernetes and JWT auth, but Vault itself must be run and trusted | 2 — the cluster's own RBAC; outside the cluster nothing |
| Encryption and network path (R1) | 3 — KMS envelope encryption, TLS, VPC endpoint, resource policies | 2 — KMS, VPC endpoint; no resource policies | 3 — AES-256-GCM barrier, TLS; network is yours to build | 1 — etcd encryption must be enabled; any pod with access reads it |
| Audit and alerting (R3, R5) | 3 — every read in CloudTrail; EventBridge rules | 3 — CloudTrail | 2 — audit devices; shipping and alerting are yours | 1 — API audit log, if enabled |
| Works on EC2, Kubernetes and a laptop (R6) | 3 — SDK, local agent, External Secrets, CSI driver; a mock for laptops | 2 — SDK; fewer integrations | 3 — Vault Agent, Secrets Operator | 1 — Kubernetes only |
| Operating burden | 3 — none to run | 3 — none | 1 — HA cluster, unseal, upgrades, backups (less with HCP) | 2 — part of the cluster |
| Cost at our size (2 secrets) | 2 — $0.40 per secret per month + $0.05 per 10,000 calls | 3 — standard tier is free | 1 — servers or an HCP subscription, plus people | 3 — free |
| Portability to other clouds | 1 — AWS only | 1 — AWS only | 3 — any cloud, on-premises | 2 — any cluster |
| **Total** | **21** | 18 | 18 | 13 |

## Decision

Use **AWS Secrets Manager**. It is the only option that rotates both of our credentials
with nothing to run: RDS rotates its own master password, and a stack-owned Lambda
rotates the ElastiCache user. Access is an IAM decision bound to the VPC endpoint, and
every read is in CloudTrail, which is what the unexpected-read alarm (S4.2) is built on.

The app reads secrets **at runtime**, not through environment variables: config holds
only secret IDs (R1). It uses the AWS SDK, or the local agent where a sidecar or host
process is preferred.

## Consequences

- ✅ No servers to run; rotation, encryption and audit come from managed services.
- ✅ The app's code depends on a small interface (`fetch(secretId)`), so a different store
  is a new fetcher, not a rewrite (`backend/src/secrets/fetchers.js`).
- ⚠️ AWS lock-in for the store itself. Accepted: the app already runs on AWS.
- ⚠️ A small monthly cost per secret and per call; the app's cache (one call per secret
  per ~5 minutes) keeps call volume negligible.
- ⚠️ Secrets Manager is a runtime dependency. Mitigated by the cache serving the last good
  value during an outage, and by fetching at startup with retries.
- 🔁 Revisit if any of these becomes true (Vault wins then): workloads span several clouds
  or on-premises; we want **dynamic per-instance database credentials** with leases rather
  than rotated shared ones; or an existing Vault platform team already runs it.

## Sources

- [AWS Secrets Manager: rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html) · [encryption](https://docs.aws.amazon.com/secretsmanager/latest/userguide/security-encryption.html) · [pricing](https://aws.amazon.com/secrets-manager/pricing/)
- [Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Vault database secrets engine](https://developer.hashicorp.com/vault/docs/secrets/databases) · [seal and barrier](https://developer.hashicorp.com/vault/docs/concepts/seal)
- [Kubernetes: good practices for Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

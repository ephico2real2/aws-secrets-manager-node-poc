# Parked: Secure Notes on OpenBao and HashiCorp Vault

[← Initiative](README.md) · [Backlog: E15](backlog.md#e15--moved-secure-notes-on-openbao-and-hashicorp-vault--openbao-node-poc) · [Plan E8–E15](plan-e8-e15.md)

**Status: moved.** Since 2026-10-18 this work lives in its own repository,
[`ephico2real2/openbao-node-poc`](https://github.com/ephico2real2/openbao-node-poc). It was
seeded from this repo with the AWS path kept, and continues there as epics B0–B8
([initiative](https://github.com/ephico2real2/openbao-node-poc/blob/main/docs/modernization/README.md)).
The plan below is kept as it was written; the new repo's plan supersedes it.

**Goal:** show that the Secure Notes design is not tied to AWS. The same app runs on
**OpenBao** (about 90% of the tutorial) and **HashiCorp Vault**, on Docker Compose and
Kubernetes. It keeps the same rules:

- credentials are fetched at runtime;
- no credential sits in an environment variable;
- credentials refresh automatically on rotation or lease expiry;
- the lab-only flag that reveals values still works, end to end.

## One switch: `SECRETS_PROVIDER`

The app chooses its secrets manager with a single setting:

| `SECRETS_PROVIDER` | Talks to | How it authenticates | Notes |
| --- | --- | --- | --- |
| `aws` (default) | AWS Secrets Manager | IAM role (instance profile, IRSA) | `SECRETS_MODE` (`sdk` or `agent`) still chooses the SDK or the local agent |
| `vault` | HashiCorp Vault | AppRole, Kubernetes or JWT auth → a Vault token | HTTP API with `fetch`; Redis database plugin available |
| `openbao` | OpenBao | the same auth methods | the same HTTP API and fetcher as `vault`; Valkey plugin instead of Redis; namespaces available |

`vault` and `openbao` share one fetcher, because OpenBao keeps Vault's API. The value
switches only what really differs: token prefixes, which plugins exist, and feature
checks such as namespaces.

Everything else stays the same whichever provider is chosen:
- config holds only the provider, an address and secret names;
- the app refuses to start if a credential is in the environment;
- the cache, rotation recovery, log masking and the lab-only reveal flag work as they do now.

The app already reads secrets through one interface (`fetch(secretId)` in
`backend/src/secrets/fetchers.js`), so adding a provider means a new fetcher plus its
auth, not a redesign.

## Why a new repository

The secrets manager changes most of the stack: the server itself, unsealing, auth methods,
dynamic credentials, and the Kubernetes operators. A separate repo (proposed name
`openbao-node-poc`) can take its own direction without making this one harder to follow.
It starts with **version folders**, so the app's evolution is readable from the
directory listing.

| Folder | What it adds |
| --- | --- |
| `v0-env-file` | The original `.env` app, copied from this repo's `versions/v0-env-file` |
| `v1-openbao-kv` | OpenBao in Compose (static seal and self-init, so it needs no manual steps); KV v2; AppRole; the app reads over the HTTP API with `fetch` and renews its token |
| `v2-openbao-dynamic` | PostgreSQL dynamic credentials with lease renewal and re-issue. **Valkey** replaces Redis, because OpenBao ships a Valkey plugin and no Redis plugin |
| `v3-k8s` | Helm (raft storage); External Secrets Operator writes a Secret that is mounted as a volume; the app watches the mount; VaultDynamicSecret generator |
| `v4-vault` | The same on HashiCorp Vault, including its Redis database plugin |

## Facts the ADR must get right (checked October 2026)

| | OpenBao | HashiCorp Vault |
| --- | --- | --- |
| License | MPL-2.0 | BSL 1.1 since Vault 1.15 (Aug 2023); each release converts to MPL 2.0 after 4 years |
| Steward | OpenSSF (Linux Foundation) sandbox project, since June 2025 | IBM (acquisition of HashiCorp closed 27 Feb 2025) |
| Latest | 2.7.1 (Oct 2026) | 2.2.0 (Oct 2026) |
| Namespaces | Yes, since 2.3 | Enterprise only |
| Read scaling | Standby reads since 2.5 | Performance replication (Enterprise) |
| Control groups | Since 2.7 | Enterprise only |
| Replication, Sentinel, Transform | No | Enterprise only |
| Storage | Raft, PostgreSQL, PebbleDB; `file` removed in 2.7 | Raft, file, others |
| Built-in database plugins | PostgreSQL, MySQL/MariaDB, Cassandra, InfluxDB, Valkey | Many, including Redis and Redis ElastiCache |

Two common claims need care:
- **"IBM removed Enterprise features from Vault."** Inaccurate. Namespaces, replication,
  Sentinel and HSM support have always been Enterprise-only. What did change is that
  HCP Vault Secrets reached end of life (July 2026).
- **"OpenBao provides all the Enterprise features."** Overstated. OpenBao now offers
  namespaces, standby reads, control groups and PKCS#11/KMIP auto-unseal for free.
  It has no performance or DR replication, no Sentinel, and no Transform engine.

## Design notes for the Kubernetes version

- **External Secrets Operator** (2.x, `external-secrets.io/v1`). Its Vault provider is
  stable and documented for OpenBao; the dedicated OpenBao provider is still alpha.
- **No environment variables.** Mount the Secret as a volume, with no `envFrom` and no
  `subPath`. Kubernetes updates a mounted Secret by swapping a `..data` symlink
  atomically. The app watches the directory for that swap and also re-reads it on a
  timer.
- **Dynamic credentials through ESO** create a new database user on each refresh. Set
  the lease TTL well above the refresh interval plus the time the kubelet takes to
  update the volume.
- **Vault Secrets Operator** is Vault-only (BSL). OpenBao has a CSI provider instead.
- **There is no official Node.js client.** Plain `fetch` against the HTTP API works on
  both servers. The app needs these calls: token `renew-self`, `lookup-self`, and
  `sys/leases/renew`.

## Sources

- OpenBao: [release notes](https://openbao.org/community/release-notes/2-7-0/) · [deprecations](https://openbao.org/community/deprecation/) · [database secrets engines](https://openbao.org/docs/secrets/databases/) · [self-init](https://openbao.org/docs/configuration/self-init/) · [static seal](https://openbao.org/docs/configuration/seal/static/) · [Helm](https://openbao.org/docs/platform/k8s/helm/)
- Vault: [release notes](https://developer.hashicorp.com/vault/docs/updates/release-notes) · [license](https://github.com/hashicorp/vault/blob/main/LICENSE) · [IBM completes acquisition](https://newsroom.ibm.com/2025-02-27-ibm-completes-acquisition-of-hashicorp,-creates-comprehensive,-end-to-end-hybrid-cloud-platform) · [Redis database plugin](https://developer.hashicorp.com/vault/docs/secrets/databases/redis)
- External Secrets Operator: [Vault provider](https://external-secrets.io/latest/provider/hashicorp-vault/) · [OpenBao](https://external-secrets.io/latest/provider/openbao/) · [Vault dynamic secret generator](https://external-secrets.io/latest/api/generator/vault/)
- Kubernetes: [Secrets mounted as volumes](https://kubernetes.io/docs/concepts/configuration/secret/)

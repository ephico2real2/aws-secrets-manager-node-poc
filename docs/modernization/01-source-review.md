# Source review — the initial design

**Epic E0 · Discovery.** [← Initiative](README.md) · [Backlog](backlog.md) · Next: [ADR-001 →](02-adr-001-secrets-manager-selection.md)

**What you'll learn:** how the first version of Secure Notes handled its credentials,
what is wrong with that, and the requirements the rest of this initiative must meet.

## 1. The initial code

Like most apps, Secure Notes started by reading credentials from environment
variables, loaded from a `.env` file:

```bash
# .env
DB_HOST=db.internal
DB_USER=notes_app
DB_PASSWORD=Example-Only-Pa55w0rd
REDIS_URL=redis://:Example-Only-R3dis@cache.internal:6379
```

```js
// db.js — initial version
const pool = new pg.Pool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,   // a long-lived password, in the environment
});

// cache.js — initial version
const redis = new Redis(process.env.REDIS_URL);   // password inside the URL
```

The same pattern exists in every language: `os.environ["DB_PASSWORD"]` (Python),
`System.getenv("DB_PASSWORD")` (Java), `os.Getenv("DB_PASSWORD")` (Go),
`Environment.GetEnvironmentVariable("DB_PASSWORD")` (.NET).

## 2. Where each credential lives, and who can read it

| Credential | Lives in | Who can read it | Rotated? | Audited? |
| --- | --- | --- | --- | --- |
| Postgres password | `.env` on disk, the container's environment, the compose file or deployment spec, CI variables, developers' laptops, backups | Anyone with shell or runtime access to the host or container, the orchestrator API, CI logs, the backup system | Manually, rarely: every copy must change together | No |
| Redis password (in `REDIS_URL`) | Same places, plus any log or error message that prints the URL | Same, plus anyone who reads logs | Same | No |

## 3. Findings

| ID | Finding | Severity | Proof |
| --- | --- | --- | --- |
| F1 | Credentials are plaintext in the process environment: readable with `exec env`, `/proc/1/environ`, `inspect` (no shell needed), and inherited by every child process | Critical | [The `.env` demo](../learn/02-the-env-file-problem.md), run in CI with Podman |
| F2 | No rotation: changing a password means editing every copy and restarting every instance, so it rarely happens | High | — |
| F3 | No audit: nothing records who or what read a credential | High | — |
| F4 | One static credential shared across instances, environments and people; leaving staff keep it | High | — |
| F5 | Leaks through logs and errors: a connection string in an error message carries the password | Medium | The [leak test](../../demo/test-case-04-leak-test.md) reproduces this |
| F6 | Copies spread to CI variables, compose files, wikis and laptops: "secret sprawl" | Medium | — |
| F7 | A `.env` committed by mistake ends up in git history for good | Medium | — |

## 4. Requirements for the new design

| ID | Requirement | Addressed by |
| --- | --- | --- |
| R1 | No credential in any environment variable, file, image, log or Kubernetes object | E2, E3, verified by E6 |
| R2 | Rotate any credential without restarting the app | E2, E3 |
| R3 | The workload proves who it is with a platform identity, not a stored key; every read is authorized and audited | E1, E3, E4 |
| R4 | No human handles a production credential: created, stored and rotated by automation | E3, E5 |
| R5 | Misuse is detected: an unexpected read raises an alert | E4 |
| R6 | Works the same on EC2, Kubernetes/OpenShift and a laptop | E2, E3 |

These requirements drive the tool selection in [ADR-001](02-adr-001-secrets-manager-selection.md).

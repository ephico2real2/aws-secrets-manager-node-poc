# Initiative: modernize how Secure Notes handles credentials

**Goal:** no human ever handles, and no environment ever exposes, a production credential.
Secure Notes reads its database and cache credentials at runtime from a central secrets
manager, proves who it is with a platform identity, and keeps working through rotation.

**Problem:** the initial version read long-lived passwords from a `.env` file. Anyone with
access to the host, the container runtime, the orchestrator, CI logs or backups could read
them; they were never rotated, and nobody could tell who had read them
([source review](01-source-review.md)).

## Success measures

| Measure | Target | How it is checked |
| --- | --- | --- |
| Credentials in environment, files, images, logs or Kubernetes objects | 0 | The credential scan searches for the real values on every CI run |
| Restarts needed to rotate a credential | 0 | Rotation tests on Compose, kind and (manually) AWS |
| Secret reads not authenticated by a platform identity | 0 | No access keys anywhere; IAM role or JWT-based identity only |
| Secret reads not audited | 0 | CloudTrail records every `GetSecretValue`; an alarm fires on unexpected readers |
| Credentials created, typed or copied by a person | 0 | Created by RDS, CloudFormation and rotation functions only |

## How the work is organized

Epics hold features; features hold user stories with acceptance criteria. The full list,
with status and evidence, is in the [backlog](backlog.md), and every item is a GitHub
issue with its features and stories as sub-issues.

The work runs in **two tracks**, so the modernization never mixes with the effort of
explaining it:

| Track | Issue prefix and label | What it is | Epics | Issues |
| --- | --- | --- | --- | --- |
| **APP** | `APP:` · `app` | Modernizing the app: what a team does when asked to move an application from `.env` passwords to a secrets manager | E0–E6, E8–E12 | [all](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Aapp) · [open](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Aapp+is%3Aopen) |
| **TUTORIAL** | `TUTORIAL:` · `tutorial` | Building this tutorial about it: the learning path, the live `.env` demo, the guide, the demo pages, the version folders | E7, E13–E14 | [all](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atutorial) · [open](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atutorial+is%3Aopen) |

```mermaid
flowchart LR
  subgraph app["Track APP: modernize the app"]
    E0["E0 Discovery<br/>source review"] --> E1["E1 Select the tool<br/>ADR-001"]
    E1 --> E2["E2 App changes"]
    E1 --> E3["E3 Platform on AWS"]
    E2 --> E6["E6 Verification"]
    E3 --> E6
    E3 --> E4["E4 Hardening"]
    E3 --> E5["E5 Delivery and automation"]
    E4 --> E8["E8 Structured logs"]
    E8 --> E9["E9 Notifications, sns-logger"]
    E8 --> E11["E11 Detection lab"]
    E9 --> E10["E10 Local log pipeline"]
    E10 --> E12["E12 Logging and alerting on AWS"]
    E11 --> E12
  end
  subgraph tut["Track TUTORIAL: explain it"]
    E7["E7 Learning path,<br/>guide and demos"]
    E13["E13 Version folders, tags"]
    E14["E14 Alerts and audit docs"]
  end
  E15["E15 OpenBao and Vault<br/>(parked, new repo)"]
  app -. "documents the outcome of" .-> tut
```

E0 then E1; E2 and E3 after E1; E4, E5 and E6 in parallel once E3 is in place. Then
logs-first alerting: E8, then E9 and E11 in parallel, E10, and E12 on AWS
([plan](plan-e8-e15.md)). The TUTORIAL epics follow the APP work and document it. E15 is
[parked](parked-openbao-vault.md).

| Track | Epic | Outcome | Status |
| --- | --- | --- | --- |
| APP | E0 Discovery | The initial design reviewed; requirements R1–R6 | ✅ [Source review](01-source-review.md) |
| APP | E1 Select a secrets manager for AWS | Decision with criteria and consequences | ✅ [ADR-001](02-adr-001-secrets-manager-selection.md) |
| APP | E2 Application changes | The app fetches, caches, refreshes and redacts secrets; names follow a convention | ✅ |
| APP | E3 Platform on AWS | Identity, network path, encryption, managed rotation | ✅ |
| APP | E4 Security hardening | Resource policy, unexpected-read alarm, Config rules; least-privilege DB user, IAM auth, multi-region next | 🔎 S4.1 built, verify on AWS · ⚠️ S4.2 reopened (fixed by S11.4, S12.1) · ✅ S4.3 (opt-in) · 🔜 S4.1b, S4.4–S4.6 |
| APP | E5 Delivery and automation | One build, CI, supply chain, keyless deploys | ✅ |
| APP | E6 Verification and evidence | Every claim has a test that fails if it stops being true | ✅ |
| APP | E8 Structured logs | Catalogued alert events; logs shipped in the OpenTelemetry format, never with a secret | 🔜 |
| APP | E9 Notifications | The app notifies through SNS; a local sns-logger shows email, SMS and chat deliveries | 🔜 |
| APP | E10 Local log pipeline | Collector, VictoriaLogs, vmalert, Alertmanager: logs first, then alerts | 🔜 |
| APP | E11 Detection lab | The unexpected-read alarm simulated end to end with the stack's own rule | 🔜 |
| APP | E12 Logging and alerting on AWS | CloudWatch Logs, metric filters, alarms; topics that can actually receive alarms | 🔜 |
| TUTORIAL | E7 Learning path, guides and demos | A path a junior engineer can follow; the `.env` demo; guide, tutorial and demo pages | ✅ |
| TUTORIAL | E13 Version folders and tags | `versions/v0-env-file` runnable; milestone tags | 🔜 |
| TUTORIAL | E14 Alerts and audit docs | Chapter 7, demo test cases 13–18, alert reference | 🔜 |
| Parked | E15 OpenBao and Vault | A sibling repo: the same app on OpenBao and Vault, with External Secrets Operator | ⏸ [parked](parked-openbao-vault.md) |

## Read in this order

1. [Source review](01-source-review.md): what was wrong with the initial design
2. [ADR-001](02-adr-001-secrets-manager-selection.md): which tool, and why
3. [Backlog](backlog.md): the epics, features and stories
4. [Plan E8–E15](plan-e8-e15.md): logs-first alerting, the detection lab, version folders
5. [Parked: OpenBao and Vault](parked-openbao-vault.md)
6. The [learning path](../learn/README.md): the story for the whole team

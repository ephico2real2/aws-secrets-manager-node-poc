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
with status and evidence, is in the [backlog](backlog.md), and every item is a
[GitHub issue](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atype%3Aepic)
with its features and stories as sub-issues. Open work:
[`is:open`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+is%3Aopen).

```mermaid
flowchart LR
  E0["E0 Discovery<br/>source review"] --> E1["E1 Select the tool<br/>ADR-001"]
  E1 --> E2["E2 App changes"]
  E1 --> E3["E3 Platform on AWS"]
  E2 --> E6["E6 Verification"]
  E3 --> E6
  E3 --> E4["E4 Hardening"]
  E3 --> E5["E5 Delivery and automation"]
  E6 --> E7["E7 Docs and enablement"]
  E4 --> E7
```

| Epic | Outcome | Status |
| --- | --- | --- |
| E0 Discovery | The initial design reviewed; requirements R1–R6 | ✅ [Source review](01-source-review.md) |
| E1 Select a secrets manager for AWS | Decision with criteria and consequences | ✅ [ADR-001](02-adr-001-secrets-manager-selection.md) |
| E2 Application changes | The app fetches, caches, refreshes and redacts secrets; names follow a convention | ✅ |
| E3 Platform on AWS | Identity, network path, encryption, managed rotation | ✅ |
| E4 Security hardening | Resource policy, unexpected-read alarm, Config rules; least-privilege DB user, IAM auth, multi-region next | ✅ top three (🔎 verify on AWS) · 🔜 rest |
| E5 Delivery and automation | One build, CI, supply chain, keyless deploys | ✅ |
| E6 Verification and evidence | Every claim has a test that fails if it stops being true | ✅ |
| E7 Documentation and enablement | A learning path a junior engineer can follow | ✅ |

## Read in this order

1. [Source review](01-source-review.md): what was wrong with the initial design
2. [ADR-001](02-adr-001-secrets-manager-selection.md): which tool, and why
3. [Backlog](backlog.md): the epics, features and stories
4. The [learning path](../learn/README.md): the story for the whole team

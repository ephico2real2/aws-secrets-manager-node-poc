# Plan: every AWS resource tagged, and a teardown that proves it removed them

Status: **approved** by the owner on 2026-10-18, with the decisions at the end. Steps 1–3 are
built (backlog S5.5); steps 4–5 are next (S5.6) and can only be proven on the owner's AWS account.

## Why

Part C runs on real AWS through the manual `aws (Part C)` workflow: GitHub's OIDC token
assumes the deploy role (no AWS keys stored), CloudFormation builds the stack, the app runs
on EC2 against the real Secrets Manager, and the run deletes the stack unless `keep_stack`
is set. The owner's requirement: **every piece of infrastructure carries tags**, so it can
be found, costed and proven gone.

## What is true today (read from the templates and the workflow)

| Fact | Where |
| --- | --- |
| `aws cloudformation deploy` runs with no `--tags`, so the stack has no tags of its own to pass on | `.github/workflows/aws.yaml`, "Deploy the stack" |
| Of the stack's 72 resources, one is tagged: the instance, with `Name` only | `infra/cloudformation.yaml` |
| The root disk comes from the launch template's block device mapping; AWS does not pass stack tags to such volumes | [AWS: resource tagging](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-resource-tags.html) |
| The database keeps a final snapshot on delete (`DeletionPolicy: Snapshot`), without `CopyTagsToSnapshot`; the workflow then deletes the snapshot | template, `Database`; workflow, "Tear down" |
| The bootstrap template (OIDC provider, artifact bucket, two roles) has no tags | `infra/github-actions-bootstrap.yaml` |
| The deploy role cannot read tags (`tag:GetResources` is not in its policy) | bootstrap template, `GitHubDeployRole` |
| Teardown deletes the stack, the final snapshot, the Redis secret and the artifacts; it does not check that nothing is left | workflow, "Tear down" |
| Kept on purpose: the optional trail's bucket (`DeletionPolicy: Retain`, only when `CreateTrail=true`, default `false`). The KMS keys wait 30 days (the default) before AWS deletes them | template |

## The tags

One set, defined once in `infra/tags.json` and read by the workflow, the checks and the docs:

| Key | Value |
| --- | --- |
| `Project` | `secure-notes` |
| `Stack` | the stack name (`secure-notes-ci` by default) |
| `Environment` | `dev` (the secret naming convention's `{env}`) |
| `ManagedBy` | `cloudformation` |
| `Repository` | `ephico2real2/aws-secrets-manager-node-poc` |
| `DeployedBy` | `github-actions` (the bootstrap: `console`) |
| `Owner`, `CostCenter` | the owner's choice (a team name, never a personal email: the repository is public) |

## The changes

1. **Stack tags on every deploy.** `aws cloudformation deploy --tags` from `infra/tags.json`.
   CloudFormation applies them to every resource type that takes tags.
2. **Where stack tags don't reach:**
   - the launch template gets `TagSpecifications` for `instance`, `volume` and `network-interface`;
   - the database gets `CopyTagsToSnapshot: true`, so its final snapshot is tagged too;
   - the bootstrap template tags its own resources from parameters, so a console deploy cannot forget them.
3. **A check on every push (no AWS needed),** in the `checks` job: a script reads both
   templates and fails if a resource type that takes tags has a way around them (the three
   cases above), or if a resource type is on neither reviewed list in `infra/tags.json`. The
   lists come from the CloudFormation resource schemas (cfn-lint 1.57.2's copy): of the 32
   types, 20 take tags and 12 do not (aliases, policies, subscriptions, permissions, metric
   filters, egress rules, the rotation schedule, the instance profile, Config rules, and the
   launch template, which tags itself through `TagSpecifications`).
4. **Proof on AWS, after deploy.** The workflow lists the stack's resources, reads their tags
   through the Resource Groups Tagging API, and fails if any taggable resource lacks a required
   tag, including the ones AWS makes for the stack (the root volume, the instance's network
   interface, the RDS-managed secret). The deploy role gets read-only `tag:GetResources`.
5. **Proof of teardown.** After `delete-stack`, the workflow searches for anything still
   tagged `Stack=<name>` and fails if something other than the expected leftovers remains
   (KMS keys pending deletion; the trail bucket only with `CreateTrail=true`). The run's
   summary lists what was deleted and what is left.
6. **Docs:** GUIDE C10 and C11, `docs/reference/security-controls.md`, the backlog (a new
   story under E12), and the handover.

## How it is proven

| Step | Where |
| --- | --- |
| 1–3 | every push: `checks` (the static check, run once with a resource left untagged to see it fail) |
| 4–5 | the `aws (Part C)` workflow on the owner's AWS account; until then the story is labelled `needs-aws-verification` |

## Decisions (the owner, 2026-10-18)

1. `Owner=ephico2real2`, no `CostCenter`.
2. The trail bucket is kept on delete, tagged, and reported as an expected leftover.
3. The KMS keys are deleted 7 days after the stack (the minimum).

## Found while building

- A deploy with stack tags needs `cloudformation:TagResource` and `UntagResource`:
  `CreateChangeSet` and `ExecuteChangeSet` depend on them (AWS Service Authorization
  Reference). The deploy role lacked them, so the bootstrap stack must be deployed again
  before the next run (GUIDE C11).
- AWS does not document whether the secret RDS makes for the database copies the database's
  tags. Step 4 checks it on the first run, and the deploy role may tag that secret
  (`secretsmanager:TagResource` on `rds!*`, our tag keys only).

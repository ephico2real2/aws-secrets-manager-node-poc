# versions/

[← Project README](../README.md)

The app's history, in versions you can run. Each version solves a problem the one before
it had. The current app is the repository root. Earlier versions that differ enough to
need their own code live here as folders. The milestones are git tags.

| Version | Where | Credentials come from | What it adds |
| --- | --- | --- | --- |
| **v0** | [`v0-env-file/`](v0-env-file/README.md) | a `.env` file, as environment variables | Nothing: this is the "before" picture. `leak.sh` finds the passwords in 8 of 9 places |
| **v1** | tag `v1-secrets-manager` | AWS Secrets Manager at runtime | No credential in env, files, images, logs or Kubernetes objects; rotation without restart; masked debug logs; a lab-only reveal flag |
| **v2** | tag `v2-alerts`, and `main` today | the same | Logs first, then alerts: structured logs, SNS notifications, the local SNS console, the unexpected-read alarm simulated end to end |

The tags are created by the `milestone` workflow (Actions → milestone → Run workflow),
with release notes from [`docs/releases/`](../docs/releases). If a tag isn't there yet, it
hasn't been released.

The next step in the story continues in a sibling repository,
[`openbao-node-poc`](https://github.com/ephico2real2/openbao-node-poc): the same app on OpenBao
and HashiCorp Vault, with this repo's AWS path kept.

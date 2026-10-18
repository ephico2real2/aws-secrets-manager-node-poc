# Learning path: from `.env` files to a centralized secrets manager

Six short chapters, each building on the last. The principles apply to any language and
any secrets manager; **Secure Notes** (Node.js, Postgres, Redis, AWS) is the worked
example throughout. About 30 minutes in total.

| # | Chapter | You'll learn |
| --- | --- | --- |
| 1 | [Secrets managers and how workloads fetch secrets](01-secrets-managers.md) | The retrieval pattern common to AWS Secrets Manager, HashiCorp Vault, Azure Key Vault and Google Secret Manager |
| 2 | [The `.env` file problem](02-the-env-file-problem.md) | A live Podman demo: anyone with access to a container can read its `.env` credentials |
| 3 | [Why a secrets manager](03-why-a-secrets-manager.md) | Encryption, audit, rotation, automation with Terraform and Ansible, and workload identity with JWTs |
| 4 | [Secure Notes, before and after](04-secure-notes-app.md) | The app's architecture with `.env` and with Secrets Manager, and the code an app must add |
| 5 | [System design review](05-system-design.md) | What the AWS design gets right, what to improve, and the target architecture |
| 6 | [Inside the app: request flows](06-request-flows.md) | Startup retrieval, rotation recovery and log masking, step by step |

**Then:** run it yourself with the [tutorial](../TUTORIAL.md), demo one feature at a time
with the [demo pages](../../demo/README.md), or deploy it with the [guide](../GUIDE.md).
The work behind all of this is organized as an agile initiative in
[`docs/modernization/`](../modernization/README.md).

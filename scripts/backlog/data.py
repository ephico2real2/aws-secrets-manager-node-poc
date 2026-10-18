# The backlog (docs/modernization/backlog.md) as data, for GitHub issues.
B = "https://github.com/ephico2real2/aws-secrets-manager-node-poc/blob/main/"
def d(path, text=None):
    return f"[{text or path}]({B}{path})"

LEARN = lambda n, f, t: d(f"docs/learn/{f}", f"chapter {n}: {t}")
BACKLOG = d("docs/modernization/backlog.md", "backlog")

# Each item: id, type, title, (story text), criteria [(done, text)], size, status, evidence [markdown], children [...]
EPICS = [
 dict(id="E0", title="Discovery: review the initial source code",
  outcome="The initial `.env`-based design is reviewed, its risks ranked, and requirements R1–R6 written.",
  docs=[d("docs/modernization/01-source-review.md", "Source review")],
  children=[
   dict(id="F0.1", type="feature", title="Source review of the initial design", status="done", docs=[d("docs/modernization/01-source-review.md","Source review")], children=[
     dict(id="S0.1", type="story", title="Inventory every credential and where it lives", size="S", status="done",
      story="As a security engineer, I want a list of every credential and every place it lives, so that the redesign covers all of them.",
      criteria=[(1,"Each credential, its locations, who can read it, rotation and audit status are tabulated.")],
      evidence=[d("docs/modernization/01-source-review.md","Source review §2")]),
     dict(id="S0.2", type="story", title="Threat-model the .env approach", size="S", status="done",
      story="As a security engineer, I want the findings ranked by severity, so that we fix the worst first.",
      criteria=[(1,"Findings F1–F7 with severity."),(1,"Requirements R1–R6 derived from them.")],
      evidence=[d("docs/modernization/01-source-review.md","Source review §3–4")]),
   ]),
   dict(id="F0.2", type="feature", title="Live proof of the .env problem", status="done", docs=[LEARN(2,"02-the-env-file-problem.md","The .env file problem")], children=[
     dict(id="S0.3", type="story", title="Prove F1 with a live Podman demo", size="S", status="done",
      story="As an engineer, I want to see a `.env` password read out of a running container, so that the risk is concrete, not theoretical.",
      criteria=[(1,"Given a container started with `--env-file --rm -d`, when I run `exec env`, `/proc/1/environ`, `inspect` or read `/proc/PID/environ` on the host, then the password appears."),
                (1,"The same lookups on Secure Notes show secret IDs only."),
                (1,"CI runs it on every push and fails if the generic password is *not* readable.")],
      evidence=[d("scripts/env-file-demo.sh"), "CI job `env-file-demo`", LEARN(2,"02-the-env-file-problem.md","The .env file problem")]),
   ]),
  ]),
 dict(id="E1", title="Select a secrets management tool for AWS",
  outcome="A recorded decision, with criteria, scores, consequences and the conditions that would reverse it.",
  docs=[d("docs/modernization/02-adr-001-secrets-manager-selection.md","ADR-001")],
  children=[
   dict(id="F1.1", type="feature", title="ADR-001: choose the secrets manager", status="done", docs=[d("docs/modernization/02-adr-001-secrets-manager-selection.md","ADR-001")], children=[
     dict(id="S1.1", type="story", title="Compare the options against our requirements", size="S", status="done",
      story="As an architect, I want options scored against R1–R6, cost and operating burden, so that the choice is explainable.",
      criteria=[(1,"At least four options: Secrets Manager, Parameter Store, Vault, Kubernetes Secrets."),(1,"Criteria tied to requirements; scores with reasons.")],
      evidence=[d("docs/modernization/02-adr-001-secrets-manager-selection.md","ADR-001")]),
     dict(id="S1.2", type="story", title="Decide and record the consequences", size="S", status="done",
      story="As a tech lead, I want the decision and its trade-offs written down, so that future teams know when to revisit it.",
      criteria=[(1,"Decision and consequences, good and bad."),(1,"Conditions under which Vault would win.")],
      evidence=[d("docs/modernization/02-adr-001-secrets-manager-selection.md","ADR-001")]),
   ]),
   dict(id="F1.2", type="feature", title="Team enablement on the pattern", status="done", docs=[LEARN(1,"01-secrets-managers.md","Secrets managers"), LEARN(3,"03-why-a-secrets-manager.md","Why a secrets manager")], children=[
     dict(id="S1.3", type="story", title="Learning brief: retrieval pattern and JWT workload identity", size="M", status="done",
      story="As a junior engineer, I want the retrieval pattern explained across products, and how JWT workload identity works, so that I can apply it on any stack.",
      criteria=[(1,"The seven-step pattern mapped to AWS, Vault, Azure Key Vault and Google Secret Manager."),(1,"JWT claims and the token exchange, with the places this repo uses it.")],
      evidence=[LEARN(1,"01-secrets-managers.md","Secrets managers"), LEARN(3,"03-why-a-secrets-manager.md","Why a secrets manager")]),
   ]),
  ]),
 dict(id="E2", title="Application changes: consume secrets at runtime",
  outcome="The app fetches, caches, refreshes and redacts its secrets; config holds names only.",
  docs=[LEARN(4,"04-secure-notes-app.md","Secure Notes, before and after"), LEARN(6,"06-request-flows.md","Request flows")],
  children=[
   dict(id="F2.1", type="feature", title="Configuration holds no secrets", size="S", status="done",
    story="As an operator, I want the app to refuse to start if a credential is in its environment, so that nobody \"fixes\" an outage by pasting a password in.",
    criteria=[(1,"`DB_PASSWORD`, `PGPASSWORD`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `REDIS_URL`, `REDISCLI_AUTH` set → exit 78."),(1,"In production also static AWS keys, demo mode, a mock endpoint, or the reveal flag.")],
    evidence=[d("backend/src/config.js"), d("demo/test-case-08-reveal-refused-in-production.md","test case 8")]),
   dict(id="F2.2", type="feature", title="Fetch with the platform identity (SDK or agent)", size="M", status="done",
    story="As a developer, I want one fetch interface over the AWS SDK and the local agent, so that the deployment can choose without code changes.",
    criteria=[(1,"SDK mode: `GetSecretValue` with the default credential chain."),(1,"Agent mode: `localhost:2773` with the agent's SSRF token.")],
    evidence=[d("backend/src/secrets/fetchers.js")]),
   dict(id="F2.3", type="feature", title="Cache secrets safely", size="M", status="done",
    story="As an SRE, I want few API calls and resilience to a brief outage, so that Secrets Manager is not on every request's path.",
    criteria=[(1,"TTL with ±10% jitter."),(1,"Concurrent misses share one call (single-flight)."),(1,"The last good value is served if a refresh fails.")],
    evidence=[d("backend/src/secrets/provider.js"), d("backend/test/secrets.test.js")]),
   dict(id="F2.4", type="feature", title="Rotation without restart", size="M", status="done",
    story="As an SRE, I want the app to recover by itself when a password rotates, so that rotation can run on a schedule.",
    criteria=[(1,"Given the password rotated, when a new connection fails with `28P01` or `WRONGPASS`, then the app refreshes once, retries, and the request succeeds.")],
    evidence=[d("backend/src/clients/"), d("backend/test/redis-rotation.test.js"), d("demo/test-case-02-rotate-postgres.md","test case 2"), d("demo/test-case-03-rotate-redis.md","test case 3")]),
   dict(id="F2.5", type="feature", title="No secret in logs or API responses", size="M", status="done",
    story="As a security engineer, I want every log line and response scrubbed, so that a secret can't leak through an error message.",
    criteria=[(1,"`SecretValue` prints `[REDACTED]`; key- and value-based redaction of every line."),(1,"The leak test finds no value in logs or responses.")],
    evidence=[d("backend/src/secrets/redactor.js"), d("demo/test-case-04-leak-test.md","test case 4")]),
   dict(id="F2.6", type="feature", title="Masked debug logging and a lab-only reveal flag", size="S", status="done",
    story="As an operator, I want to see which secret and keys were used without seeing values, so that I can debug safely.",
    criteria=[(1,"Debug lines show secret ID, version and keys, passwords fully masked."),(1,"`LOG_REVEAL_SECRETS=true` prints values to stdout only, is flagged on the dashboard, and is refused in production.")],
    evidence=[d("backend/src/secrets/mask.js"), d("demo/test-case-05-debug-log.md","test case 5"), d("demo/test-case-07-reveal-flag.md","test case 7")]),
   dict(id="F2.7", type="feature", title="Agent mode", size="S", status="done",
    story="As a platform engineer, I want the app to read through the AWS Workload Credentials Provider, so that the app needs no AWS SDK credentials of its own where the agent runs.",
    criteria=[(1,"Reads with the agent's SSRF token (a local file that proves the caller is on the host, so a forged request can't reach the agent); forces a refresh after an auth failure, because the agent's cache doesn't see rotation.")],
    evidence=[d("docker-compose.agent.yml"), d("demo/test-case-09-agent-mode.md","test case 9")]),
   dict(id="F2.8", type="feature", title="Secret naming convention /{service}/{env}/{resource}/{name}", size="M", status="done",
    story="As a platform engineer, I want secret names built from one pattern, so that environments differ by one setting and IAM can grant by path.",
    criteria=[(1,"Given `SECRETS_ENV=prod` and `REDIS_SECRET_RESOURCE=secure-notes`, the app reads `/elasticache/prod/secure-notes/app`; presets and custom patterns."),
              (1,"An explicit `*_SECRET_ID` wins (the `rds!…` secret RDS names itself)."),
              (1,"Settings from env vars, `config.yaml`, `config.json` or `config.env`; a config file holding a credential is refused; an unknown environment or token stops startup."),
              (1,"Compose, kind and the CloudFormation stack use it; the seed job and the app share one resolver.")],
    evidence=[d("backend/src/secrets/naming.js"), d("backend/test/naming.test.js"), d("docs/reference/secret-naming.md","secret naming reference")]),
  ]),
 dict(id="E3", title="Platform and infrastructure on AWS",
  outcome="Identity without keys, a private network path, customer-managed encryption and managed rotation.",
  docs=[d("infra/cloudformation.yaml"), d("docs/GUIDE.md","GUIDE")],
  children=[
   dict(id="F3.1", type="feature", title="Identity without keys", size="S", status="done", story="As a security engineer, I want workloads to use platform identity, so that there is no key to steal.",
    criteria=[(1,"EC2 instance role; IMDSv2 required, hop limit 1."),(1,"IRSA on EKS/ROSA; GitHub OIDC for CI.")], evidence=[d("infra/cloudformation.yaml"), d("infra/irsa-trust-policy.example.json")]),
   dict(id="F3.2", type="feature", title="Private network path to Secrets Manager", size="S", status="done", story="As a network engineer, I want secret requests to stay inside AWS, so that they can't be intercepted or exfiltrated over the internet.",
    criteria=[(1,"VPC endpoint with an account-only endpoint policy."),(1,"The app role may read only via that endpoint (`aws:SourceVpce`).")], evidence=[d("infra/cloudformation.yaml")]),
   dict(id="F3.3", type="feature", title="Encryption at rest and in transit", size="S", status="done", story="As a security engineer, I want our own KMS key and TLS everywhere, so that a stolen disk or packet reveals nothing.",
    criteria=[(1,"Customer-managed KMS key; the app and rotation roles may decrypt only via Secrets Manager."),(1,"RDS and ElastiCache encrypted at rest and in transit; RDS certificate verified.")], evidence=[d("infra/cloudformation.yaml"), d("backend/src/clients/db.js")]),
   dict(id="F3.4", type="feature", title="Managed credentials and rotation", size="M", status="done", story="As a DBA, I want the database and cache passwords created and rotated by AWS, so that no one ever types one.",
    criteria=[(1,"RDS `ManageMasterUserPassword`."),(1,"A generated ElastiCache user secret and a rotation function using the user's two password slots.")], evidence=[d("infra/rotation/elasticache-user-rotation.js")]),
   dict(id="F3.5", type="feature", title="Kubernetes and OpenShift", size="M", status="done", story="As a platform engineer, I want the same images on kind, OpenShift and EKS/ROSA, so that the pattern isn't EC2-specific.",
    criteria=[(1,"Kustomize overlays; Pod Security restricted."),(1,"No Kubernetes Secret holds an app credential.")], evidence=[d("deploy/k8s/"), d("demo/test-case-10-kubernetes.md","test case 10")]),
  ]),
 dict(id="E4", title="Security hardening",
  outcome="Gaps found in the system design review are closed: who may read, detection, compliance, least privilege, resilience.",
  docs=[LEARN(5,"05-system-design.md","System design review")],
  children=[
   dict(id="F4.1", type="feature", title="Restrict who can read each secret", status="open", docs=[LEARN(5,"05-system-design.md","System design review")], children=[
     dict(id="S4.1", type="story", title="Resource policy on the Redis secret", size="S", status="done", aws=True,
      story="As a security engineer, I want only the app, its rotation function and a named break-glass role to read the secret, so that a broadly privileged admin or a misconfigured role can't.",
      criteria=[(1,"Deny `GetSecretValue` to every other principal; deny the app outside the VPC endpoint."),(1,"`BlockPublicPolicy` on; created after the cache user so the stack's own read succeeds."),
                (0,"On AWS: a stack update that touches the cache user still succeeds; a read by another admin role is denied.")],
      evidence=["`RedisSecretPolicy` in " + d("infra/cloudformation.yaml"), "parameter `SecretAdminRoleArn`"]),
     dict(id="S4.1b", type="story", title="Resource policy on the RDS-managed secret", size="S", status="open", aws=True,
      story="As a security engineer, I want the same deny on the `rds!` secret, so that both credentials have the same protection.",
      criteria=[(0,"Prove on AWS that a resource policy on the `rds!` secret leaves RDS managed rotation working."),(0,"Then add the same deny.")], evidence=[]),
   ]),
   dict(id="F4.2", type="feature", title="Detect misuse and drift", status="done", docs=[LEARN(5,"05-system-design.md","System design review")], children=[
     dict(id="S4.2", type="story", title="Alarm on unexpected secret reads", size="M", status="done", aws=True,
      story="As an on-call engineer, I want an alert when anyone other than the app or rotation reads a secret, so that misuse is noticed in minutes, not in an audit.",
      criteria=[(1,"EventBridge rule on CloudTrail `GetSecretValue` / `BatchGetSecretValue` for both secrets by any role, user or root other than the app and rotation roles → encrypted SNS, optional email."),(1,"Known gap, documented: the RDS secret is matched by ARN, so a read by name alone is in CloudTrail but not alarmed."),(1,"Optional trail (`CreateTrail=true`) for accounts without one."),
                (0,"On AWS: a read from the console raises an email within minutes; the app's reads don't.")],
      evidence=["`SecretReadAlertRule`, `SecretReadAlertTopic` in " + d("infra/cloudformation.yaml")]),
     dict(id="S4.3", type="story", title="AWS Config rules for rotation and IMDSv2", size="S", status="done",
      story="As a compliance owner, I want drift flagged automatically, so that a secret without rotation or an IMDSv1 instance doesn't go unnoticed.",
      criteria=[(1,"`EnableConfigRules=true` adds: rotation enabled, scheduled rotation succeeded, EC2 IMDSv2.")],
      evidence=["`RotationEnabledRule`, `RotationSucceededRule`, `ImdsV2Rule` in " + d("infra/cloudformation.yaml")]),
   ]),
   dict(id="F4.3", type="feature", title="Least privilege, fewer passwords and regional resilience", status="open", docs=[LEARN(5,"05-system-design.md","System design review")], children=[
     dict(id="S4.4", type="story", title="Least-privilege database user", size="M", status="open",
      story="As a DBA, I want the app to log in as a role that owns only its tables, so that a stolen app credential can't administer the database.",
      criteria=[(0,"A `notes_app` role and its own secret, named by the convention (`/rds/<env>/<db>/app`), rotated with the alternating-users template."),(0,"The master user is used only by RDS rotation and administrators.")], evidence=[]),
     dict(id="S4.5", type="story", title="Spike: IAM authentication for RDS and ElastiCache", size="L", status="open",
      story="As an architect, I want to know whether we can drop passwords entirely, so that there is nothing left to steal.",
      criteria=[(0,"Token per new connection; measure the connection rate against RDS limits."),(0,"ElastiCache: Valkey 7.2+/Redis 7+, reconnect before 12 hours."),(0,"A recommendation with trade-offs.")], evidence=[]),
     dict(id="S4.6", type="story", title="Replica secrets in a second region; tighter egress and KMS policy", size="M", status="open",
      story="As an SRE, I want secrets available after a regional outage and less room for exfiltration, so that we recover and stay contained.",
      criteria=[(0,"Replica secrets in a second region."),(0,"443 egress limited to VPC endpoints."),(0,"KMS key administrators named explicitly.")], evidence=[]),
   ]),
  ]),
 dict(id="E5", title="Delivery and automation",
  outcome="One build for every platform, a verifiable supply chain and keyless deploys.",
  docs=[d("docs/reference/ci.md","CI reference")],
  children=[
   dict(id="F5.1", type="feature", title="One build, every platform", size="M", status="done", story="As a release engineer, I want the exact tested images published, so that nothing is rebuilt between test and release.",
    criteria=[(1,"The same images on Compose, kind, OpenShift and EC2.")], evidence=[d(".github/workflows/ci.yaml")]),
   dict(id="F5.2", type="feature", title="Supply chain: SBOM, scan, signing", size="M", status="done", story="As a security engineer, I want every image scanned, described and signed, so that a cluster can admit only what CI built.",
    criteria=[(1,"CycloneDX SBOM, grype scan failing on fixable criticals."),(1,"cosign keyless signature and SBOM attestation, verified anonymously.")], evidence=[d("demo/test-case-11-supply-chain.md","test case 11")]),
   dict(id="F5.3", type="feature", title="Air-gapped installs", size="S", status="done", story="As a platform engineer, I want to copy the images into our own registry, so that clusters without internet can run the app.",
    criteria=[(1,"`scripts/mirror-images.sh` mirrors and verifies layers; generated overlay pulls only from the mirror.")], evidence=[d("demo/test-case-12-image-mirror.md","test case 12")]),
   dict(id="F5.4", type="feature", title="Keyless deploys from GitHub Actions", size="M", status="done", story="As a release engineer, I want CI to deploy with a short-lived role, so that no AWS key is stored in GitHub.",
    criteria=[(1,"GitHub OIDC to an IAM role scoped to one environment."),(1,"The deploy role can rotate but never read secrets.")], evidence=[d(".github/workflows/aws.yaml"), d("infra/github-actions-bootstrap.yaml")]),
   dict(id="F5.5", type="feature", title="Automation examples for other teams", size="S", status="done", story="As a platform engineer, I want Terraform, Ansible and Kubernetes examples, so that other teams can adopt the pattern with their tools.",
    criteria=[(1,"Terraform (managed RDS password, rotation, write-only values), Ansible lookup, External Secrets and CSI.")], evidence=[LEARN(3,"03-why-a-secrets-manager.md","Why a secrets manager")]),
  ]),
 dict(id="E6", title="Verification and evidence",
  outcome="Every claim has an automated test that fails if it stops being true.",
  docs=[d("docs/TEST-CASES.md","TEST-CASES"), d("demo/README.md","demo pages")],
  children=[
   dict(id="F6.1", type="feature", title="Unit tests", size="M", status="done", story="As a developer, I want fast tests of the secrets layer, so that regressions show up before deploy.",
    criteria=[(1,"Real `pg`, `ioredis` and AWS SDK clients against fakes; run in CI job `checks`.")], evidence=[d("backend/test/")]),
   dict(id="F6.2", type="feature", title="End-to-end walks with screenshots", size="M", status="done", story="As a reviewer, I want each run to photograph the dashboard and assert what it must show, so that evidence is automatic.",
    criteria=[(1,"Dashboard walk, smoke test and leak test on Compose (both modes) and kind.")], evidence=[d("demo/README.md","demo pages")]),
   dict(id="F6.3", type="feature", title="Credential scan", size="M", status="done", story="As a security engineer, I want the running stack searched for the real values, so that \"no credential anywhere\" is proven, not assumed.",
    criteria=[(1,"Searches every container, file, log and Kubernetes object; self-tests with the reveal flag on.")], evidence=[d("demo/test-case-06-credential-scan.md","test case 6")]),
  ]),
 dict(id="E7", title="Documentation and enablement",
  outcome="A learning path a junior engineer can follow, and docs that CI keeps correct.",
  docs=[d("docs/learn/README.md","Learning path"), d("README.md")],
  children=[
   dict(id="F7.1", type="feature", title="Learning path", status="done", docs=[d("docs/learn/README.md","Learning path")], children=[
     dict(id="S7.1", type="story", title="Chapters 1–6", size="M", status="done",
      story="As a junior engineer, I want a short, ordered set of chapters, so that I understand the design from first principles to the code.",
      criteria=[(1,"Each chapter: what you'll learn, diagrams, sources, next link.")], evidence=[d("docs/learn/README.md","Learning path")]),
     dict(id="S7.3", type="story", title="Request-flow diagrams matched to the code", size="S", status="done",
      story="As a developer, I want sequence diagrams that name the file for each step, so that I can read the code next to them.",
      criteria=[(1,"Startup, rotation recovery and log masking flows.")], evidence=[LEARN(6,"06-request-flows.md","Request flows")]),
   ]),
   dict(id="F7.2", type="feature", title="Navigation and docs quality", status="done", docs=[d("README.md")], children=[
     dict(id="S7.2", type="story", title="README as the landing page", size="S", status="done",
      story="As a newcomer, I want the README to tell the story and point to the right document, so that I don't read 300 lines to find my path.",
      criteria=[(1,"Problem, story, run, see it work, reference."),(1,"Reference material moved to `docs/reference/` without loss.")], evidence=[d("README.md"), d("docs/reference/security-controls.md","security controls")]),
     dict(id="S7.4", type="story", title="CI keeps the docs correct", size="S", status="done",
      story="As a maintainer, I want broken links and diagrams to fail the build, so that the docs can't rot silently.",
      criteria=[(1,"Every relative link and anchor resolves."),(1,"Every Mermaid diagram renders.")], evidence=[d("scripts/docs-check.js"), "CI job `docs`"]),
   ]),
  ]),
]

# ---- two tracks: APP (modernizing the app) and TUTORIAL (building this tutorial) ----
# Work that exists only to teach moves from the app epics into E7.
def _take(epic_id, feat_id):
    e = next(x for x in EPICS if x["id"] == epic_id)
    f = next(x for x in e["children"] if x["id"] == feat_id)
    e["children"].remove(f)
    return f

_E = {e["id"]: e for e in EPICS}
for _e in EPICS:
    _e["track"] = "tutorial" if _e["id"] == "E7" else "app"
_E["E7"]["title"] = "Tutorial: learning path, guides and demos"
_E["E7"]["outcome"] = ("Everything that teaches the design rather than changes the app: the learning path, "
                       "the live .env demo, the deployment guide, the tutorial and the demo pages, kept correct by CI.")

_f = _take("E0", "F0.2"); _f["id"] = "F7.3"; _f["children"][0]["id"] = "S7.5"
_g = _take("E1", "F1.2"); _g["id"] = "F7.4"; _g["children"][0]["id"] = "S7.6"
_h = _take("E5", "F5.5"); _h["id"] = "F7.5"
_E["E7"]["children"] += [_f, _g, _h,
 dict(id="F7.6", type="feature", title="Step-by-step deployment guide", size="M", status="done",
  story="As someone deploying for the first time, I want every command with what I should see after it, so that I can run paths A, B and C without help.",
  criteria=[(1,"Paths A (Compose), B (kind, OpenShift, EKS/ROSA) and C (EC2), each command followed by a check."),(1,"Troubleshooting and clean-up sections; the manual GitHub Actions run for path C.")],
  evidence=[d("docs/GUIDE.md","GUIDE"), d("docs/reference/deploy-quickref.md","quick reference")]),
 dict(id="F7.7", type="feature", title="Tutorial, demo pages and test-case catalogue", size="M", status="done",
  story="As a presenter, I want one page per feature with the CI screenshot and output, so that I can demo or study one thing at a time.",
  criteria=[(1,"The tutorial walks every feature on a laptop, with screenshots."),(1,"One demo page per test case, with the CI screenshot and output, indexed in demo/README.md."),
            (1,"TEST-CASES lists every automated test and what it proves."),(1,"Screenshots come from the CI walk (`scripts/capture/`), so they show the current app.")],
  evidence=[d("docs/TUTORIAL.md","TUTORIAL"), d("demo/README.md","demo pages"), d("docs/TEST-CASES.md","TEST-CASES")]),
]

# ---- S4.2 reopened: two defects found while planning E11/E12 ----
_s42 = next(s for f in _E["E4"]["children"] for s in f.get("children", []) if s["id"] == "S4.2")
_s42["criteria"] += [
    (0, "The topic uses a customer-managed KMS key: EventBridge and CloudWatch alarms can't publish to a topic encrypted with `alias/aws/sns` (fixed by S12.1)."),
    (0, "The rule has `State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`; without it EventBridge never delivers read-only events such as `GetSecretValue` (fixed by S11.4)."),
]

PLAN = d("docs/modernization/plan-e8-e15.md", "plan E8–E15")
CH7 = LEARN(7, "07-alerts-and-audit.md", "Alerts and audit")
def S(id, title, size, story, criteria, evidence=(), aws=False, status="open"):
    return dict(id=id, type="story", title=title, size=size, status=status, story=story,
                criteria=[(0, c) for c in criteria], evidence=list(evidence) or [PLAN], **({"aws": True} if aws else {}))
def F(id, title, children, docs=()):
    return dict(id=id, type="feature", title=title, status="open", docs=list(docs) or [PLAN], children=children)

EPICS += [
 dict(id="E8", track="app", title="Structured logs with alert events",
  outcome="Every security-relevant log line carries a catalogued event name; logs ship in the OpenTelemetry format without ever carrying a secret; humans get a readable format.",
  docs=[PLAN], children=[
   F("F8.1", "Alert events and the catalogue", [
     S("S8.1", "Event fields at every alert-worthy call site, from one catalogue", "M",
       "As an on-call engineer, I want every alert-worthy log line to carry a stable event name, so that alert rules match names, not message text.",
       ["`backend/src/alerts/catalogue.js` lists each event: severity, source, channels, dedup, runbook.",
        "Call sites add an `event` field only; messages unchanged; the leak test's simulated lines carry no event.",
        "A test fails if code uses an event that isn't in the catalogue."]),
   ]),
   F("F8.2", "Ship logs in the OpenTelemetry format", [
     S("S8.2", "OTLP shipper after redaction", "M",
       "As a platform engineer, I want logs pushed to a collector in the OpenTelemetry format, so that any log store (VictoriaLogs locally, CloudWatch Logs on AWS) can receive them.",
       ["Hooked inside `emit()` after redaction: a registered value ships as `[REDACTED]`; `revealUnsafe` lines are never shipped.",
        "Bounded buffer, oldest dropped first; the shipper never logs through itself.",
        "OTLP mapping: Timestamp, SeverityNumber, Body, EventName, Attributes, Resource `service.name`."]),
     S("S8.3", "Readable log format for humans", "S",
       "As a developer, I want `LOG_FORMAT=pretty`, so that I can read logs in a terminal.",
       ["One line per record: time, level, component, message, key=value fields.", "Refused in production; the JSON format stays the default and the ring buffer stays JSON."]),
     S("S8.4", "An alarm can't be lost or misfire because of its log line", "S",
       "As an on-call engineer, I want every line an alarm depends on to reach the log store, and no line to page for nothing, so that I can trust the pages I get.",
       ["The file sink writes synchronously: the `config.unsafe` line is on disk before the process exits; write errors are counted and shown by a posture check.",
        "Startup retries log no alert event; only `secrets.load.fatal` pages. An agent 403 is reported at once, even while a cached value is served.",
        "`secrets.reveal.enabled` alerts only when the flag has an effect (debug); a forced refresh that fails says whether a cached value is still served.",
        "A unit test scans every dotted string literal: each event the code uses is catalogued, and each catalogued alert is emitted."]),
   ]),
  ]),
 dict(id="E9", track="app", title="Notifications through SNS, and a local SNS console",
  outcome="The app can notify through Amazon SNS; locally an SNS-compatible sns-logger shows each email, SMS and webhook delivery on a screen like the dashboard.",
  docs=[PLAN], children=[
   F("F9.1", "sns-logger: a local Amazon SNS", [
     S("S9.1", "SNS API subset (Query protocol)", "L",
       "As a developer, I want an SNS endpoint on my laptop, so that the app, Alertmanager and the alarm simulation publish exactly as they would to AWS.",
       ["CreateTopic, ListTopics, Get/SetTopicAttributes, Subscribe, ConfirmSubscription, Unsubscribe, ListSubscriptions(ByTopic), Publish.",
        "Validation like SNS: subject < 100 chars without line breaks, `default` key with MessageStructure=json, 256 KiB, SMS 1600 bytes.",
        "Deliveries per subscription protocol (email, sms, https), logged with masked endpoints."]),
     S("S9.2", "sns-logger screen", "M",
       "As a presenter, I want the deliveries shown as an inbox, a phone and a chat feed, so that the audience sees what on-call would receive.",
       ["Email like 'AWS Notifications <no-reply@sns.amazonaws.com>' with the unsubscribe footer; SMS bubbles with segments; webhook JSON and chat card; topics.",
        "Strict CSP, same look as the dashboard; works on Compose and kind."]),
   ]),
   F("F9.2", "App notifier", [
     S("S9.3", "Publish notifications from the app", "M",
       "As an operator, I want the app to send a notification when it recovers from a rotation, and a test alert on demand, so that I know the alert path works.",
       ["`@aws-sdk/client-sns`, topic from `SNS_TOPIC_ARN`; a mock endpoint is refused in production.",
        "MessageStructure=json with email, sms and https bodies; dedup and rate limit.",
        "An 'alert sent' log line with OpenTelemetry messaging fields and the SNS MessageId."]),
     S("S9.4", "Mask recipients everywhere", "S",
       "As a privacy officer, I want email addresses and phone numbers masked in logs and screens, so that alerting doesn't spread personal data.",
       ["`maskEmail` → `on***@example.com`, `maskPhone` → `+1******0100`, shared by the app and the mock."]),
     S("S9.5", "Harden the local SNS console", "S",
       "As a security engineer, I want the dev-only console unusable from a web page and free of full recipients, so that running it on a laptop is safe.",
       ["`ListSubscriptions(ByTopic)` return masked endpoints; `alerts-check.sh` checks them.",
        "Every response carries the security headers; attribute keys are escaped.",
        "POSTs must be SigV4-signed and carry no `Origin`, so a cross-site form can't drive the API.",
        "The test alert is limited to one a minute (it pages by SMS)."]),
   ]),
  ]),
 dict(id="E10", track="app", title="Local log pipeline: OpenTelemetry, VictoriaLogs, vmalert, Alertmanager",
  outcome="Logs first, then alerts, locally: the same shape as CloudWatch Logs, metric filters, alarms and SNS on AWS.",
  docs=[PLAN], children=[
   F("F10.1", "Log store and rules", [
     S("S10.1", "OpenTelemetry Collector and VictoriaLogs overlay", "M",
       "As a developer, I want `docker-compose.observability.yml` to run a collector and VictoriaLogs, so that I can search every service's logs.",
       ["App, aws-mock and sns-logger records arrive in VictoriaLogs (OTLP), browsable in vmui.", "Works with Docker and Podman (no logging-driver dependency)."]),
     S("S10.2", "Alert rules generated from the catalogue", "M",
       "As an on-call engineer, I want the local rules and the AWS metric filters generated from one list, so that they can't disagree.",
       ["`scripts/sync-alert-rules.js --check` writes the vmalert rules, the CloudFormation block and the docs table.", "CI fails if any of them is stale."]),
     S("S10.3", "Alertmanager publishes to SNS", "S",
       "As an on-call engineer, I want alerts routed to SNS, so that the same subscriptions receive them.",
       ["`sns_configs` with `api_url` → sns-logger, dummy SigV4 keys; an email template like a CloudWatch alarm email."]),
     S("S10.5", "Pipeline check covers the chat route and a pattern rule", "S",
       "As an on-call engineer, I want CI to prove a warning reaches chat only, so that the second route is as tested as the first.",
       ["Trigger `app.errors.burst` (or `secrets.fetch.stale`) in CI; assert one chat delivery and no page."]),
     S("S10.4", "Pipeline pane in sns-logger", "S",
       "As a presenter, I want to see log lines arrive and turn into alerts, so that the whole path is visible.",
       ["A live tail from VictoriaLogs, correlated with deliveries by MessageId; says 'not deployed' without the overlay."]),
   ]),
  ]),
 dict(id="E11", track="app", title="Detection lab: the unexpected-read alarm, end to end on a laptop",
  outcome="A button reads a secret as an intruder; the local CloudTrail, EventBridge rule and SNS deliver the alert, using the same rule as the AWS stack.",
  docs=[PLAN], children=[
   F("F11.1", "Local CloudTrail and EventBridge", [
     S("S11.1", "Callers have identities; reads are audited", "M",
       "As a security engineer, I want each local caller to have its own identity and every read recorded like CloudTrail, so that detection can be tested without AWS.",
       ["Access keys map to the app role, the seed/deployer, an intruder user and an intruder role; unsigned tooling matches no alarm branch.",
        "CloudTrail-shaped records for GetSecretValue and BatchGetSecretValue, never containing a value."]),
     S("S11.2", "EventBridge pattern evaluator fed by the stack's own rule", "M",
       "As a security engineer, I want the local alarm to use the exact rule from `infra/cloudformation.yaml`, so that a rule that can't fire on AWS can't fire locally either.",
       ["`scripts/sync-event-pattern.py --check` extracts EventPattern, State and InputTransformer.",
        "Operators: exact, arrays, nesting, $or, anything-but, prefix, exists; arrays of objects are flattened; unknown operators and malformed arguments fail.",
        "The rule matches the Redis secret by name, full ARN and partial ARN (a prefix), and names the secret of a batch read."]),
     S("S11.3", "Simulate an unexpected read from the dashboard", "S",
       "As a presenter, I want a button that reads a secret as an intruder, so that the audience sees the alert arrive.",
       ["Demo-only route with its own intruder client; returns IDs only.", "A read of the RDS secret by name shows the documented gap: audited, not alarmed."]),
     S("S11.4", "Fix the rule state so read-only events are delivered", "S",
       "As a security engineer, I want the AWS rule to receive read-only management events, so that S4.2 can actually fire.",
       ["`State: ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` on `SecretReadAlertRule`; the local evaluator enforces it."], aws=True),
     S("S11.5", "Detection lab on kind", "S",
       "As a platform engineer, I want sns-logger and the simulated alarm on Kubernetes too, so that the demo works on every path.",
       ["sns-logger Deployment and Service, NetworkPolicies, k8s-check assertions."]),
   ]),
  ]),
 dict(id="E12", track="app", title="Logging and alerting on AWS",
  outcome="On AWS: journald → CloudWatch Logs → metric filters → alarms → SNS, and CloudTrail → EventBridge → SNS, on topics that can actually receive them.",
  docs=[PLAN], children=[
   F("F12.1", "Topics, keys and subscriptions", [
     S("S12.1", "Customer-managed key for the alert topics", "S",
       "As a security engineer, I want the alert topics encrypted with our own key that EventBridge and CloudWatch may use, so that alarms are delivered.",
       ["`AlertsKey`; `SecretReadAlertTopic` and a new `OpsAlertsTopic` use it.", "Subscriptions from `AlertEmail`, `AlertPhone`, `AlertWebhookUrl`."], aws=True),
     S("S12.4", "IAM, endpoints and app settings", "S",
       "As a platform engineer, I want the app allowed to publish and to ship logs, privately, so that alerting doesn't widen access.",
       ["AppRole: `sns:Publish` on the ops topic only; optional SNS and Logs endpoints; `SNS_TOPIC_ARN` in app.env.", "Bootstrap role can read the evidence (metrics, log events, TestEventPattern)."], aws=True),
   ]),
   F("F12.2", "Logs to CloudWatch, alarms from logs", [
     S("S12.2", "CloudWatch agent ships the app's log file", "M",
       "As an operator, I want the app's logs in CloudWatch Logs, so that they survive the instance and can raise alarms.",
       ["The app writes its redacted JSON lines to `LOG_FILE` synchronously, so the line explaining an exit is never lost.",
        "Set up before the app starts, only with `EnableCloudWatchLogs=true`; 30-day log group; logrotate timer enabled."], aws=True),
     S("S12.3", "Metric filters and alarms generated from the catalogue", "M",
       "As an on-call engineer, I want each catalogued event to raise a CloudWatch alarm, so that AWS alerts match the local ones.",
       ["One filter and alarm per catalogued alert; ALARM pages (critical) or posts to chat (warning); OK goes to chat; missing data is not breaching."], aws=True),
     S("S12.5", "Prove it on AWS", "M",
       "As a reviewer, I want the manual AWS workflow to prove both alert paths, so that 'built' becomes 'verified'.",
       ["A denied read by the deploy role publishes to the secret-read topic.", "A test log event trips an alarm.", "TestEventPattern fixtures match the mock.",
        "A batch read's alert text names the secret (`secretIdList[0]` in the InputTransformer)."], aws=True),
     S("S12.6", "Close the by-name gap for the RDS-managed secret", "S",
       "As a security engineer, I want a read of the RDS secret by name or partial ARN to alarm too, so that the documented gap goes away.",
       ["Check on AWS whether Secrets Manager's CloudTrail records carry `resources[].ARN`; if so, match on it.", "The mock records `resources` the same way; the detection lab's gap button then alarms."], aws=True),
   ]),
  ]),
 dict(id="E13", track="tutorial", title="Version folders and milestone tags",
  outcome="The app's history is runnable: v0 with the .env leak, then tagged milestones.",
  docs=[PLAN], children=[
   F("F13.1", "versions/ and tags", [
     S("S13.1", "versions/v0-env-file: the original app, runnable", "M",
       "As a learner, I want to run the original `.env` app and see the leak myself, so that the redesign has a clear 'before'.",
       ["Own Compose project on port 3001, fake values, `leak.sh`.", "CI asserts the leak is found; v0 is never published."]),
     S("S13.2", "Milestone tags with releases", "S",
       "As a reader, I want tags for each milestone, so that I can check out the app at each step of the story.",
       ["`v1-secrets-manager` and `v2-alerts`, each with a release linking the CI evidence."]),
   ]),
  ]),
 dict(id="E14", track="tutorial", title="Tutorial: alerts and audit",
  outcome="Learners see the logs-first alerting design, locally and on AWS, one demo at a time.",
  docs=[PLAN], children=[
   F("F14.1", "Chapter, demos and reference", [
     S("S14.1", "Chapter 7: alerts and audit", "M",
       "As a junior engineer, I want a chapter on logs-first alerting, so that I understand the path from a log line to an SMS.",
       ["Diagrams: local pipeline, AWS pipeline, unexpected-read sequence, rotation-alert sequence.", "Glossary entries."]),
     S("S14.2", "Demo test cases 13–18 with captures", "M",
       "As a presenter, I want one page per alert demo with the CI screenshot, so that I can show each one.",
       ["sns-logger email, SMS and chat; pipeline pane; detection lab; vmui."]),
     S("S14.3", "Reference and navigation updates", "S",
       "As a reader, I want the alert catalogue and the docs kept in step with the code, so that nothing is stale.",
       ["`docs/reference/alerts.md` generated; GUIDE, TUTORIAL, TEST-CASES, security controls, README, backlog updated."]),
     S("S14.4", "Backlog and issues generated from the repo", "S",
       "As a maintainer, I want the backlog page and the GitHub issues generated from data in the repo, so that anyone can regenerate them.",
       ["`scripts/backlog/` holds the data, the page renderer and the issue writer."]),
   ]),
  ]),
 dict(id="E15", track="app", parked=True, title="MOVED: Secure Notes on OpenBao and HashiCorp Vault → openbao-node-poc",
  outcome="A sibling repo shows the same app on OpenBao (primary) and Vault, on Compose and Kubernetes, with SDK/HTTP retrieval and External Secrets Operator, no env vars, auto-refresh and the reveal flag.",
  docs=[d("docs/modernization/parked-openbao-vault.md", "parked plan")], children=[
   F("F15.1", "Decide and set up", [
     S("S15.1", "ADR-002: OpenBao first, Vault second", "S",
       "As an architect, I want the choice recorded with accurate licensing and feature facts, so that the team doesn't rely on myths.",
       ["MPL-2.0 vs BSL 1.1; what OpenBao added (namespaces, standby reads, control groups) and lacks (replication, Sentinel, Transform)."], evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
     S("S15.2", "New repo with version folders v0–v4", "S",
       "As a learner, I want each step in its own folder, so that I can follow the app as it changes.",
       ["v0-env-file, v1-openbao-kv, v2-openbao-dynamic, v3-k8s, v4-vault."], evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
   ], docs=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
   F("F15.2", "Retrieval and refresh", [
     S("S15.0", "One switch: SECRETS_PROVIDER=aws|vault|openbao", "M",
       "As an operator, I want to choose the secrets manager with one setting, so that the same app runs on AWS Secrets Manager, HashiCorp Vault or OpenBao.",
       ["`aws` (default) keeps today's behaviour, with SECRETS_MODE=sdk|agent unchanged.",
        "`vault` and `openbao` share one HTTP fetcher; the value switches only real differences (token prefixes, plugins, namespaces).",
        "Config holds the provider, an address and secret names only; the no-credentials-in-env guard, cache, rotation recovery, masking and reveal flag work with every provider."],
       evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
     S("S15.3", "OpenBao in Compose with KV v2 and AppRole; HTTP client with token renewal", "M",
       "As a developer, I want the app to read from OpenBao over its HTTP API, so that no client library or env var is needed.",
       ["Static seal and self-init for a hands-off demo; reveal flag kept."], evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
     S("S15.4", "Dynamic PostgreSQL credentials with lease renewal", "M",
       "As a DBA, I want per-instance database users that expire, so that a leaked credential is short-lived.",
       ["Lease renewal and re-issue; Valkey replaces Redis (OpenBao has no Redis plugin)."], evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
     S("S15.5", "Kubernetes: Helm and External Secrets Operator, no env vars", "L",
       "As a platform engineer, I want secrets delivered by ESO as a mounted volume the app watches, so that rotation needs no restart and nothing is in the environment.",
       ["Watch the `..data` symlink swap; no `subPath`, no `envFrom`; VaultDynamicSecret generator."], evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
     S("S15.6", "HashiCorp Vault variant", "M",
       "As a Vault user, I want the same app on Vault, so that both products are covered.",
       ["Vault 2.x dev/server mode; Redis database plugin."], evidence=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
   ], docs=[d("docs/modernization/parked-openbao-vault.md", "parked plan")]),
  ]),
]

# ---- local labs on any laptop (E5) and folder READMEs + handover (E7), 2026-10-18 ----
_E = {e["id"]: e for e in EPICS}
_E["E5"]["children"].append(
  F("F5.6", "Local labs on any laptop: kind and OpenShift Local", [
    S("S5.1", "kind cluster: pinned, port-mapped, checked first", "S",
      "As a developer, I want `scripts/kind-up.sh` to build the same cluster on my Mac and in CI, and to open the app without a port-forward, so that the lab just works.",
      ["`deploy/kind/cluster.yaml` pins the node image by digest (amd64 and arm64) and maps the app and the console to 127.0.0.1:3000 and :4575 through NodePorts.",
       "`scripts/preflight.sh` checks bash, Docker and its memory, kind and the node image, kubectl's skew, Node.js and free ports; `kind-up.sh` runs it strictly.",
       "CI's kind job runs the same scripts, reaches both ports with no port-forward, and exports kind's logs on failure."]),
    S("S5.2", "Bootstrap a MacBook and a Linux machine", "S",
      "As a new contributor, I want one command to install what the lab needs, so that I don't assemble the toolchain by hand.",
      ["`scripts/bootstrap/linux.sh`: kind at its pin, checked against the release's SHA-256; kubectl if missing; used by CI.",
       "`scripts/bootstrap/macos.sh`: Homebrew formulae and Docker Desktop, then the preflight; changes no settings.",
       "Run end to end on a real MacBook: Compose and kind (the owner)."]),
    S("S5.3", "OpenShift: Routes for the app and the console; images built on the cluster", "M",
      "As an OpenShift user, I want to open the app and the notification console through Routes, and to build the images on the cluster, so that the lab runs on OpenShift Local on any Mac.",
      ["Routes `secure-notes` and `sns-logger` (edge TLS); a NetworkPolicy lets the router reach the console; `k8s-deploy.sh` points the console link at its Route.",
       "`overlays/openshift-local` with `scripts/openshift-build.sh`: BuildConfigs build both images from HEAD for the cluster's CPU; image lookup resolves the short names.",
       "Run on OpenShift Local (CRC) end to end, including `k8s-check.sh` (the owner: CI has no OpenShift)."]),
  ], docs=[d("deploy/README.md", "deploy/"), d("docs/GUIDE.md", "GUIDE Part B")]))
_E["E7"]["children"].append(
  F("F7.8", "Folder READMEs and a handover", [
    S("S7.7", "A README in every folder, and a docs index", "S",
      "As a reader, I want each folder to say what it holds, so that I can find my way without reading the code.",
      ["`docs/README.md` (where to start, by goal) and `docs/reference/README.md`; READMEs in backend, frontend, deploy, dev, infra, scripts and versions; a repository map in the root README."]),
    S("S7.8", "Handover for the next contributor or AI agent", "S",
      "As the owner, I want a handover in the repo, so that a new session can continue the work or rebuild the lab on my Mac.",
      ["`HANDOVER.md`: state, working rules, map, generated files, open work, CI, lessons, and recreating the lab on a MacBook; `CLAUDE.md` points to it."]),
  ], docs=[d("HANDOVER.md"), d("docs/README.md", "docs index")]))

# ---- progress on E8–E14 (evidence: commits on main, CI runs, docs) ----
def _all_items():
    for e in EPICS:
        for f in e["children"]:
            yield f
            yield from f.get("children", [])

_EVIDENCE = {
    "S8.1": [d("backend/src/alerts/catalogue.js"), d("backend/test/logging.test.js")],
    "S8.2": [d("backend/src/logship/otlp.js"), d("backend/src/log.js")],
    "S8.3": [d("backend/src/logfmt.js")],
    "S9.1": [d("dev/aws-mock/lib/sns.js"), d("dev/aws-mock/sns-logger/server.js"), d("dev/aws-mock/test/mock.test.js")],
    "S9.2": [d("dev/aws-mock/sns-logger/ui/index.html", "sns-logger screen")],
    "S9.3": [d("backend/src/alerts/notifier.js"), d("scripts/alerts-check.sh")],
    "S9.4": [d("backend/src/alerts/recipients.js")],
    "S10.1": [d("docker-compose.observability.yml"), d("deploy/observability/otel-collector.yaml")],
    "S10.2": [d("scripts/sync-alert-rules.js"), d("deploy/observability/vmalert-rules.yaml")],
    "S10.3": [d("deploy/observability/alertmanager.yml")],
    "S10.4": [d("scripts/pipeline-check.sh")],
    "S11.1": [d("dev/aws-mock/lib/principals.js"), d("dev/aws-mock/lib/cloudtrail.js")],
    "S11.2": [d("dev/aws-mock/lib/event-pattern.js"), d("scripts/sync-event-pattern.py"), d("dev/aws-mock/rules/secret-read-alert.json")],
    "S11.3": [d("backend/src/routes.js"), d("frontend/index.html", "dashboard: Detection lab")],
    "S11.4": [d("infra/cloudformation.yaml"), CH7],
    "S11.5": [d("deploy/k8s/components/local-backing-services/sns-logger.yaml"), d("scripts/k8s-check.sh")],
    "S12.1": [d("infra/cloudformation.yaml"), CH7],
    "S12.2": [d("infra/cloudformation.yaml"), d("backend/src/logship/file.js"), d("infra/systemd/secure-notes.service")],
    "S12.3": [d("scripts/sync-alert-rules.js"), d("docs/reference/alerts.md", "alert catalogue")],
    "S12.4": [d("infra/cloudformation.yaml")],
    "S13.1": [d("versions/v0-env-file/README.md", "versions/v0-env-file"), "CI job `v0-leak`"],
    "S14.1": [CH7],
    "S14.3": [d("docs/reference/alerts.md", "alert catalogue"), d("README.md")],
    "S14.4": [d("scripts/backlog/README.md", "scripts/backlog")],
    "S14.2": [d("demo/README.md", "demo test cases 13–18"), d("scripts/capture/alerts.yaml")],
    "S5.1": [d("deploy/kind/cluster.yaml"), d("scripts/preflight.sh"), d("scripts/kind-up.sh"), "CI job `kind`"],
    "S7.7": [d("docs/README.md", "docs index"), d("README.md", "repository map")],
    "S7.8": [d("HANDOVER.md"), d("CLAUDE.md")],
    "S8.4": [d("backend/src/logship/file.js"), d("backend/src/secrets/provider.js"), d("backend/test/logging.test.js")],
    "S9.5": [d("dev/aws-mock/sns-logger/server.js"), d("scripts/alerts-check.sh")],
}
# Built and tested locally/in CI; on AWS still to be proven by S12.5.
_AWS_TO_VERIFY = {"S12.1", "S12.2", "S12.3", "S12.4"}
for _it in _all_items():
    if _it["id"] in _EVIDENCE:
        _it["criteria"] = [(1, t) for _, t in _it["criteria"]]
        _it["status"] = "done"
        _it["evidence"] = _EVIDENCE[_it["id"]]
        if _it["id"] in _AWS_TO_VERIFY:
            _it["criteria"].append((0, "Verified on a real AWS account (S12.5)."))
            _it["aws"] = True
    if _it["id"] == "S4.2":
        _it["criteria"] = [(1 if "S12.1" in t or "S11.4" in t else c, t) for c, t in _it["criteria"]]
    if _it["id"] == "S13.2":
        _it["criteria"] = [(0, "`v1-secrets-manager` and `v2-alerts`, each with a release linking the CI evidence: run the `milestone` workflow (this session can't push tags)."),
                           (1, "Release notes in `docs/releases/`; the `milestone` workflow creates the tag and the release.")]
        _it["evidence"] = [d(".github/workflows/milestone.yaml"), d("docs/releases/v1-secrets-manager.md")]

# Built and checked in CI where possible; the last criterion of each needs the owner's machine.
for _it in _all_items():
    if _it["id"] in ("S5.2", "S5.3"):
        _it["criteria"] = [(1, t) for _, t in _it["criteria"][:-1]] + [(0, _it["criteria"][-1][1])]
        _it["evidence"] = ([d("scripts/bootstrap/macos.sh"), d("scripts/bootstrap/linux.sh")] if _it["id"] == "S5.2"
                           else [d("deploy/k8s/overlays/openshift/console-route.yaml"), d("scripts/openshift-build.sh")])

# S5.2 ran on the owner's MacBook on 2026-10-18, on Podman Desktop (the owner's choice over Docker Desktop).
for _it in _all_items():
    if _it["id"] == "S5.2":
        _it["status"] = "done"
        _it["criteria"] = [(1, t) for _, t in _it["criteria"][:-1]] + [
            (1, "Run end to end on a real MacBook: Compose and kind. Done on Podman (Apple silicon, Podman 6.1.2, rootless, "
                "4 CPUs, 4 GiB): `compose-check.sh` and `k8s-check.sh` passed; the machine used 1582 MiB of 3887 with kind."),
            (1, "`macos.sh --podman`: Podman Desktop and a 4 GiB machine instead of Docker Desktop; the preflight names the engine, "
                "points the docker CLI at Podman's socket (`DOCKER_HOST`) and kind at Podman (`KIND_EXPERIMENTAL_PROVIDER`)."),
            (1, "PyYAML for `sync-event-pattern.py` in `.tmp/venv` at the CI pin (Homebrew's Python refuses `pip install --user`)."),
            (1, "Without Docker Desktop: Homebrew's docker 29.9.1 and docker-compose 5.6.0 (`cliPluginsExtraDirs`) on Podman passed `compose-check.sh`."),
            (1, "`scripts/podman.env` sets both variables, in bash or zsh, on macOS."),
            (0, "CI job `compose (podman)` runs Part A on rootless Podman on Linux (`scripts/podman.env` there too).")]
        _it["evidence"] += [d("demo/test-case-10-kubernetes.md", "test case 10: the lab on Podman"), d("docs/GUIDE.md", "GUIDE B1: Podman instead of Docker")]
    # Parked by the owner on 2026-10-18: CRC was deleted on their Mac on 2026-10-13 and is restored later.
    if _it["id"] == "S5.3":
        _it["parked"] = True
        _it["criteria"][-1] = (0, _it["criteria"][-1][1] + " **Parked** until the owner restores CRC on their Mac (deleted 2026-10-13).")

# ---- E15 moved to its own repo, 2026-10-18 (it continues there as epics B0–B8) ----
NB = "https://github.com/ephico2real2/openbao-node-poc/issues/"
_MOVED = {"S15.1": (7, "B1 · ADR-002"), "S15.2": (3, "B0 · the repo, seeded with the AWS path kept; steps/ folders and tags"),
          "S15.0": (8, "B2 · SECRETS_PROVIDER=aws|openbao|vault"), "S15.3": (12, "B3 · OpenBao KV on Compose"),
          "S15.4": (15, "B4 · dynamic credentials and leases"), "S15.5": (18, "B5 · Kubernetes, ESO, OpenShift"),
          "S15.6": (21, "B6 · the Vault variant")}
for _it in _all_items():
    if _it["id"] in _MOVED:
        n, what = _MOVED[_it["id"]]
        _it["status"] = "done"
        _it["criteria"] = [(1, f"Moved to ephico2real2/openbao-node-poc, where it continues as [#{n}]({NB}{n}) ({what}).")]
        _it["evidence"] = [f"[openbao-node-poc#{n}]({NB}{n})", d("docs/modernization/parked-openbao-vault.md", "plan (moved)")]


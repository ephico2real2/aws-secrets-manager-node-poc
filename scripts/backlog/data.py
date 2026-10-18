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
       ["`scripts/sync-event-pattern.js --check` extracts EventPattern, State and InputTransformer.",
        "Operators: exact, arrays, nesting, $or, anything-but, prefix, exists; unknown operators fail.",
        "Same fixtures run against the mock and against `aws events test-event-pattern`."]),
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
     S("S12.2", "CloudWatch agent ships the app's journald logs", "M",
       "As an operator, I want the app's logs in CloudWatch Logs, so that they survive the instance and can raise alarms.",
       ["Pinned agent with checksum; journald unit `secure-notes`; 30-day log group; ParseJSON transformer.", "Fallback documented: file collection."], aws=True),
     S("S12.3", "Metric filters and alarms generated from the catalogue", "M",
       "As an on-call engineer, I want each catalogued event to raise a CloudWatch alarm, so that AWS alerts match the local ones.",
       ["Filters on transformed logs; alarms notify on ALARM and OK; missing data is not breaching."], aws=True),
     S("S12.5", "Prove it on AWS", "M",
       "As a reviewer, I want the manual AWS workflow to prove both alert paths, so that 'built' becomes 'verified'.",
       ["A denied read by the deploy role publishes to the secret-read topic.", "A test log event trips an alarm.", "TestEventPattern fixtures match the mock."], aws=True),
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
 dict(id="E15", track="app", parked=True, title="PARKED: Secure Notes on OpenBao and HashiCorp Vault (new repo)",
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

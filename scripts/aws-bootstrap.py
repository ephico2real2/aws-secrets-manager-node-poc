#!/usr/bin/env python3
"""One command for the one-time AWS and GitHub setup of the aws (Part C) workflow.

   python3 scripts/aws-bootstrap.py --profile <profile> [--region us-east-1] [--plan] [--yes]
       [--stack-name github-oidc-secure-notes] [--vpc-id vpc-… --app-subnet subnet-… --data-subnets subnet-a,subnet-b]
       [--alert-email ops@example.com] [--reviewer <github login>]

1. AWS, as the signed-in admin (aws login or aws sso login; no keys are stored): finds the network
   (the default VPC and two subnets in different zones, unless given), whether the account already
   has GitHub's OIDC provider and the VPC a Secrets Manager endpoint, then deploys
   infra/github-actions-bootstrap.yaml and reads its outputs.
2. GitHub, as the gh CLI's signed-in user: creates or updates the environment "aws" (that user as
   required reviewer, deployments from main only) and sets its variables from those outputs.

Nothing changes before the plan is printed and confirmed (--yes skips the question, --plan only prints
it). Running it again updates the stack and the variables in place. Standard library only.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = "infra/github-actions-bootstrap.yaml"
SPEC = json.loads((ROOT / "infra/tags.json").read_text())
ENVIRONMENT = "aws"
BRANCH = "main"
# Outside the template's StackPrefix (secure-notes), so the deploy role's stack permissions never cover it.
DEFAULT_STACK = "github-oidc-secure-notes"
STACK_PREFIX = "secure-notes"
GITHUB_OIDC = "token.actions.githubusercontent.com"
OUTPUT_TO_VARIABLE = {
    "DeployRoleArn": "AWS_DEPLOY_ROLE_ARN",
    "CfnExecutionRoleArn": "AWS_CFN_EXEC_ROLE_ARN",
    "ArtifactBucket": "AWS_ARTIFACT_BUCKET",
}


class Failed(Exception):
    """A reason to stop before changing anything more; main prints it and exits 2."""


class Aws:
    """Runs the aws CLI with the chosen profile and region. Tests replace it with canned answers."""

    def __init__(self, profile=None, region=None):
        self.base = [*(["--profile", profile] if profile else []), *(["--region", region] if region else [])]

    def __call__(self, *args):
        """The call's JSON; raises CalledProcessError with AWS's reason on failure."""
        cmd = ["aws", *args, *self.base, "--output", "json"]
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode:
            raise subprocess.CalledProcessError(done.returncode, cmd, done.stdout, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else {}

    def text(self, *args):
        done = subprocess.run(["aws", *args, *self.base], capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else ""

    def stream(self, *args):
        """Runs with the output on the terminal (cloudformation deploy reports as it goes); the exit code."""
        return subprocess.run(["aws", *args, *self.base]).returncode


class Gh:
    """Runs the gh CLI and returns its stdout. Tests replace it."""

    def __call__(self, *args, stdin=None):
        cmd = ["gh", *args]
        done = subprocess.run(cmd, capture_output=True, text=True, input=stdin, cwd=ROOT)
        if done.returncode:
            raise subprocess.CalledProcessError(done.returncode, cmd, done.stdout, done.stderr)
        return done.stdout


def reason(err):
    return (err.stderr or "").strip() or str(err)


def signed_in(aws, profile):
    try:
        who = aws("sts", "get-caller-identity")
    except subprocess.CalledProcessError as err:
        p = f" --profile {profile}" if profile else ""
        raise Failed(f"not signed in to AWS ({reason(err)}). Sign in first: aws login{p} "
                     f"(or aws sso login{p} for an IAM Identity Center profile)") from None
    if who["Arn"].endswith(":root"):
        raise Failed("signed in as the account's root user: use an admin user or role (IAM Identity Center)")
    return who


def default_network(aws):
    """The default VPC, its first subnet for the server and two subnets in different zones for the data."""
    vpcs = aws("ec2", "describe-vpcs", "--filters", "Name=is-default,Values=true")["Vpcs"]
    if not vpcs:
        raise Failed("this region has no default VPC: pass --vpc-id, --app-subnet and --data-subnets "
                     "(private subnets with a NAT gateway, docs/GUIDE.md C2 option B)")
    vpc = vpcs[0]["VpcId"]
    subnets = aws("ec2", "describe-subnets", "--filters", f"Name=vpc-id,Values={vpc}",
                  "Name=default-for-az,Values=true")["Subnets"]
    # The server gets a public IP for its outbound traffic (GUIDE C2 option A); its firewall allows no inbound.
    by_zone = {}
    for s in sorted(subnets, key=lambda s: s["AvailabilityZone"]):
        if s.get("MapPublicIpOnLaunch") and s["State"] == "available":
            by_zone.setdefault(s["AvailabilityZone"], s["SubnetId"])
    if len(by_zone) < 2:
        raise Failed(f"the default VPC {vpc} has no two public default subnets in different zones: "
                     "pass --vpc-id, --app-subnet and --data-subnets")
    first, second = list(by_zone.values())[:2]
    return vpc, first, [first, second]


def given_network(aws, vpc, app_subnet, data_subnets):
    """Checks subnets passed on the command line: all in the VPC, the data subnets in two zones or more."""
    if not (app_subnet and data_subnets):
        raise Failed("with --vpc-id, also pass --app-subnet and --data-subnets (the template cannot guess "
                     "which subnets reach the internet through a NAT gateway)")
    wanted = sorted({app_subnet, *data_subnets})
    found = {s["SubnetId"]: s for s in aws("ec2", "describe-subnets", "--subnet-ids", *wanted)["Subnets"]}
    outside = [s for s in wanted if found.get(s, {}).get("VpcId") != vpc]
    if outside:
        raise Failed(f"not subnets of {vpc}: {', '.join(outside)}")
    if len({found[s]["AvailabilityZone"] for s in data_subnets}) < 2:
        raise Failed("--data-subnets must span two Availability Zones or more (RDS and ElastiCache require it)")
    return vpc, app_subnet, list(data_subnets)


def secrets_manager_endpoint(aws, vpc, region):
    """An existing interface endpoint for Secrets Manager: the stack must reuse it, a second one would clash."""
    found = aws("ec2", "describe-vpc-endpoints", "--filters", f"Name=vpc-id,Values={vpc}",
                f"Name=service-name,Values=com.amazonaws.{region}.secretsmanager")["VpcEndpoints"]
    live = [e["VpcEndpointId"] for e in found if e["State"].lower() == "available"]
    return live[0] if live else None


def existing_stack(aws, stack):
    try:
        return aws("cloudformation", "describe-stacks", "--stack-name", stack)["Stacks"][0]
    except subprocess.CalledProcessError as err:
        if "does not exist" in reason(err):
            return None
        raise


def oidc_choice(aws, stack):
    """CreateOidcProvider: kept as the stack has it, else true only where the account has none yet."""
    if stack:
        params = {p["ParameterKey"]: p["ParameterValue"] for p in stack.get("Parameters", [])}
        return params.get("CreateOidcProvider", "true"), "as the existing stack has it"
    providers = aws("iam", "list-open-id-connect-providers")["OpenIDConnectProviderList"]
    if any(p["Arn"].endswith(f"oidc-provider/{GITHUB_OIDC}") for p in providers):
        return "false", "the account already has GitHub's provider"
    return "true", "the account has no GitHub provider yet"


def roles_of_another_stack(aws, stack):
    """A bootstrap deployed earlier under another name owns the named roles; a second stack would collide."""
    try:
        tags = aws("iam", "list-role-tags", "--role-name", f"{STACK_PREFIX}-github-deploy")["Tags"]
    except subprocess.CalledProcessError:
        return None
    owner = {t["Key"]: t["Value"] for t in tags}.get("aws:cloudformation:stack-name")
    return owner if owner != stack else None


def stack_tags(stack):
    tags = {**SPEC["tags"], "Stack": stack, "Environment": "shared", "DeployedBy": "cli"}
    return [f"{k}={v}" for k, v in tags.items()]


def plan(a, who, region, repo, network, endpoint, oidc, stack):
    vpc, app_subnet, data_subnets = network
    print(f"AWS     account {who['Account']} as {who['Arn']}, region {region}")
    print(f"        stack {a.stack_name} ({'update' if stack else 'create'}) from {TEMPLATE}")
    print(f"        CreateOidcProvider={oidc[0]} ({oidc[1]}); trusts {repo}, environment {ENVIRONMENT}")
    print(f"GitHub  {repo}: environment {ENVIRONMENT}, required reviewer {a.reviewer}, deployments from {BRANCH} only")
    variables = {
        "AWS_REGION": region,
        **{v: f"<{o} from the stack>" for o, v in OUTPUT_TO_VARIABLE.items()},
        "AWS_VPC_ID": vpc,
        "AWS_APP_SUBNET_ID": app_subnet,
        "AWS_DATA_SUBNET_IDS": ",".join(data_subnets),
        "AWS_EXISTING_SM_ENDPOINT_ID": endpoint or "(not set: the VPC has none, so the stack creates its own)",
    }
    if a.alert_email:
        variables["AWS_ALERT_EMAIL"] = a.alert_email
    for name, value in variables.items():
        print(f"        {name} = {value}")


def deploy(aws, stack, repo, oidc):
    owner, name = repo.split("/")
    rc = aws.stream("cloudformation", "deploy", "--stack-name", stack, "--template-file", str(ROOT / TEMPLATE),
                    "--capabilities", "CAPABILITY_NAMED_IAM", "--no-fail-on-empty-changeset",
                    "--tags", *stack_tags(stack),
                    "--parameter-overrides", f"GitHubOwner={owner}", f"GitHubRepo={name}",
                    f"GitHubEnvironment={ENVIRONMENT}", f"StackPrefix={STACK_PREFIX}",
                    f"CreateOidcProvider={oidc}", "DeployedBy=cli")
    if rc:
        raise Failed(f"the stack did not deploy (exit {rc}); its events say why: "
                     f"aws cloudformation describe-stack-events --stack-name {stack}")
    outputs = {o["OutputKey"]: o["OutputValue"] for o in existing_stack(aws, stack).get("Outputs", [])}
    missing = [o for o in OUTPUT_TO_VARIABLE if o not in outputs]
    if missing:
        raise Failed(f"the stack has no output {', '.join(missing)}")
    return outputs


def configure_github(gh, repo, reviewer_id, variables, remove):
    body = {"reviewers": [{"type": "User", "id": reviewer_id}],
            "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}}
    gh("api", "-X", "PUT", f"repos/{repo}/environments/{ENVIRONMENT}", "--input", "-", stdin=json.dumps(body))
    policies = json.loads(gh("api", f"repos/{repo}/environments/{ENVIRONMENT}/deployment-branch-policies"))
    if not any(p["name"] == BRANCH for p in policies["branch_policies"]):
        gh("api", "-X", "POST", f"repos/{repo}/environments/{ENVIRONMENT}/deployment-branch-policies",
           "-f", f"name={BRANCH}", "-f", "type=branch")
    print(f"  ok    environment {ENVIRONMENT}: required reviewer, deployments from {BRANCH} only")
    for name, value in variables.items():
        gh("variable", "set", name, "--env", ENVIRONMENT, "--body", value, "-R", repo)
        print(f"  ok    {name} = {value}")
    existing = {v["name"] for v in json.loads(gh("variable", "list", "--env", ENVIRONMENT, "--json", "name", "-R", repo))}
    for name in sorted(remove & existing):
        gh("variable", "delete", name, "--env", ENVIRONMENT, "-R", repo)
        print(f"  ok    {name} removed")


def main(argv=None, aws=None, gh=None, ask=input):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    p.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"))
    p.add_argument("--stack-name", default=DEFAULT_STACK)
    p.add_argument("--vpc-id")
    p.add_argument("--app-subnet")
    p.add_argument("--data-subnets", type=lambda s: [x for x in s.split(",") if x])
    p.add_argument("--alert-email", help="where the stack's alarms send email (confirm AWS's subscription email)")
    p.add_argument("--reviewer", help="GitHub login that approves each run (default: the gh CLI's user)")
    p.add_argument("--plan", action="store_true", help="print what would be done, change nothing")
    p.add_argument("--yes", action="store_true", help="do not ask before changing AWS and GitHub")
    a = p.parse_args(argv)
    gh = gh or Gh()
    try:
        region = a.region or (Aws(a.profile).text("configure", "get", "region") if aws is None else None)
        if not region:
            raise Failed("no region: pass --region, or set one on the profile (aws configure set region …)")
        aws = aws or Aws(a.profile, region)
        who = signed_in(aws, a.profile)
        repo = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
        a.reviewer = a.reviewer or gh("api", "user", "--jq", ".login").strip()
        reviewer_id = int(gh("api", f"users/{a.reviewer}", "--jq", ".id"))
        network = (given_network(aws, a.vpc_id, a.app_subnet, a.data_subnets) if a.vpc_id
                   else default_network(aws))
        endpoint = secrets_manager_endpoint(aws, network[0], region)
        stack = existing_stack(aws, a.stack_name)
        if not stack and (other := roles_of_another_stack(aws, a.stack_name)):
            raise Failed(f"the stack {other} already holds the bootstrap's roles: rerun with --stack-name {other}")
        # A new stack under the prefix would sit inside the deploy role's own stack permissions; an existing
        # one keeps its name (renaming collides on the role names) and the template denies the role it.
        if not stack and a.stack_name.startswith(STACK_PREFIX):
            raise Failed(f"--stack-name must not start with {STACK_PREFIX}: the deploy role may change and "
                         "delete those stacks, and this one holds the deploy role")
        if stack and stack["StackStatus"] == "ROLLBACK_COMPLETE":
            raise Failed(f"{a.stack_name} failed its first create and holds nothing; see why, delete it, rerun: "
                         f"aws cloudformation describe-stack-events --stack-name {a.stack_name}; "
                         f"aws cloudformation delete-stack --stack-name {a.stack_name}")
        if stack and stack["StackStatus"].endswith("_IN_PROGRESS"):
            raise Failed(f"{a.stack_name} is {stack['StackStatus']}: rerun when it has finished")
        oidc = oidc_choice(aws, stack)
    except Failed as err:
        print(f"aws-bootstrap: {err}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as err:
        print(f"aws-bootstrap: {' '.join(err.cmd[:4])}…: {reason(err)}", file=sys.stderr)
        return 2

    plan(a, who, region, repo, network, endpoint, oidc, stack)
    if a.plan:
        return 0
    if not a.yes and ask("\nDeploy the stack and write these to GitHub? [y/N] ").strip().lower() not in ("y", "yes"):
        print("nothing changed")
        return 1

    try:
        print(f"\n== AWS: {a.stack_name}")
        outputs = deploy(aws, a.stack_name, repo, oidc[0])
        vpc, app_subnet, data_subnets = network
        variables = {"AWS_REGION": region,
                     **{v: outputs[o] for o, v in OUTPUT_TO_VARIABLE.items()},
                     "AWS_VPC_ID": vpc, "AWS_APP_SUBNET_ID": app_subnet,
                     "AWS_DATA_SUBNET_IDS": ",".join(data_subnets)}
        remove = set()
        if endpoint:
            variables["AWS_EXISTING_SM_ENDPOINT_ID"] = endpoint
        else:
            remove.add("AWS_EXISTING_SM_ENDPOINT_ID")  # a stale one would point the stack at a missing endpoint
        if a.alert_email:
            variables["AWS_ALERT_EMAIL"] = a.alert_email
        print(f"\n== GitHub: {repo}")
        configure_github(gh, repo, reviewer_id, variables, remove)
    except Failed as err:
        print(f"aws-bootstrap: {err}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as err:
        print(f"aws-bootstrap: {' '.join(err.cmd[:4])}…: {reason(err)}", file=sys.stderr)
        return 2
    print(f"\nDone. Run it: gh workflow run aws.yaml -R {repo}, then approve it under Actions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

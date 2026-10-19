"""scripts/aws-bootstrap.py against canned AWS and GitHub answers: what it deploys, what it writes, when it stops.

   python3 -m unittest discover -s scripts/test
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("aws_bootstrap", ROOT / "scripts/aws-bootstrap.py")
aws_bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aws_bootstrap)

REPO = "ephico2real2/aws-secrets-manager-node-poc"
STACK = "github-oidc-secure-notes"
OUTPUTS = {"DeployRoleArn": "arn:aws:iam::111122223333:role/secure-notes-github-deploy",
           "CfnExecutionRoleArn": "arn:aws:iam::111122223333:role/secure-notes-cfn-execution",
           "ArtifactBucket": "github-oidc-secure-notes-artifactbucket-abc"}
DEFAULT_SUBNETS = [  # out of zone order on purpose: the picks are sorted by zone
    {"SubnetId": "subnet-c", "AvailabilityZone": "us-east-1c", "VpcId": "vpc-1", "MapPublicIpOnLaunch": True, "State": "available"},
    {"SubnetId": "subnet-a", "AvailabilityZone": "us-east-1a", "VpcId": "vpc-1", "MapPublicIpOnLaunch": True, "State": "available"},
    {"SubnetId": "subnet-b", "AvailabilityZone": "us-east-1b", "VpcId": "vpc-1", "MapPublicIpOnLaunch": True, "State": "available"},
]


def missing(cmd):
    return subprocess.CalledProcessError(254, list(cmd), "", "An error occurred (ValidationError): Stack does not exist")


class FakeAws:
    """Answers the aws CLI calls aws-bootstrap.py makes; records them. deploy creates the stack."""

    def __init__(self, default_vpc=True, providers=(), endpoints=(), stack=None, other_stack_roles=None,
                 subnets=DEFAULT_SUBNETS, signed_in=True, deploy_rc=0):
        self.default_vpc, self.providers, self.endpoints = default_vpc, list(providers), list(endpoints)
        self.stack, self.other_stack_roles, self.subnets = stack, other_stack_roles, subnets
        self.signed_in, self.deploy_rc = signed_in, deploy_rc
        self.calls, self.deploys = [], []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("sts", "get-caller-identity"):
            if not self.signed_in:
                raise subprocess.CalledProcessError(255, list(args), "", "Unable to locate credentials")
            return {"Account": "111122223333", "Arn": "arn:aws:sts::111122223333:assumed-role/Admin/someone"}
        if args[:2] == ("ec2", "describe-vpcs"):
            return {"Vpcs": [{"VpcId": "vpc-1"}] if self.default_vpc else []}
        if args[:2] == ("ec2", "describe-subnets"):
            if "--subnet-ids" in args:
                ids = args[args.index("--subnet-ids") + 1:]
                return {"Subnets": [s for s in self.subnets if s["SubnetId"] in ids]}
            return {"Subnets": self.subnets}
        if args[:2] == ("ec2", "describe-vpc-endpoints"):
            return {"VpcEndpoints": self.endpoints}
        if args[:2] == ("cloudformation", "describe-stacks"):
            if self.stack is None:
                raise missing(args)
            return {"Stacks": [self.stack]}
        if args[:2] == ("iam", "list-open-id-connect-providers"):
            return {"OpenIDConnectProviderList": [{"Arn": a} for a in self.providers]}
        if args[:2] == ("iam", "list-role-tags"):
            if self.other_stack_roles is None:
                raise subprocess.CalledProcessError(254, list(args), "", "NoSuchEntity")
            return {"Tags": [{"Key": "aws:cloudformation:stack-name", "Value": self.other_stack_roles}]}
        raise AssertionError(f"unexpected aws call: {args}")

    def stream(self, *args):
        self.calls.append(args)
        assert args[:2] == ("cloudformation", "deploy"), args
        self.deploys.append(args)
        if not self.deploy_rc:
            self.stack = {"StackStatus": "CREATE_COMPLETE", "Parameters": [],
                          "Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in OUTPUTS.items()]}
        return self.deploy_rc

    def param(self, name):
        args = self.deploys[-1]
        values = args[args.index("--parameter-overrides") + 1:]
        return dict(v.split("=", 1) for v in values)[name]


class FakeGh:
    """Answers the gh CLI calls; keeps the environment's variables and branch policies."""

    def __init__(self, variables=None, policies=()):
        self.variables = dict(variables or {})
        self.policies = list(policies)
        self.environment = None
        self.calls = []

    def __call__(self, *args, stdin=None):
        self.calls.append(args)
        if args[:2] == ("repo", "view"):
            return json.dumps({"nameWithOwner": REPO})
        if args[:2] == ("api", "user"):
            return "ephico2real2\n"
        if args[:2] == ("api", "users/ephico2real2"):
            return "123043136\n"
        if args[:3] == ("api", "-X", "PUT"):
            self.environment = json.loads(stdin)
            return "{}"
        if args[0] == "api" and args[1].endswith("/deployment-branch-policies"):
            return json.dumps({"branch_policies": [{"name": n, "type": "branch"} for n in self.policies]})
        if args[:3] == ("api", "-X", "POST"):
            self.policies.append(args[args.index("-f") + 1].removeprefix("name="))
            return "{}"
        if args[:2] == ("variable", "set"):
            self.variables[args[2]] = args[args.index("--body") + 1]
            return ""
        if args[:2] == ("variable", "list"):
            return json.dumps([{"name": n} for n in self.variables])
        if args[:2] == ("variable", "delete"):
            del self.variables[args[2]]
            return ""
        raise AssertionError(f"unexpected gh call: {args}")

    def writes(self):
        return [c for c in self.calls if c[:3] in (("api", "-X", "PUT"), ("api", "-X", "POST"))
                or c[:2] in (("variable", "set"), ("variable", "delete"))]


def run(argv, aws, gh, answer="y"):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = aws_bootstrap.main(["--region", "us-east-1", *argv], aws=aws, gh=gh, ask=lambda _: answer)
    return rc, out.getvalue() + err.getvalue()


class FreshAccount(unittest.TestCase):
    def test_deploys_then_writes_every_variable_and_the_environment(self):
        aws, gh = FakeAws(), FakeGh()
        rc, out = run([], aws, gh)
        self.assertEqual(rc, 0, out)
        self.assertEqual(aws.param("CreateOidcProvider"), "true")
        self.assertEqual(aws.param("DeployedBy"), "cli")
        self.assertEqual((aws.param("GitHubOwner"), aws.param("GitHubRepo")), tuple(REPO.split("/")))
        self.assertEqual(gh.variables, {
            "AWS_REGION": "us-east-1",
            "AWS_DEPLOY_ROLE_ARN": OUTPUTS["DeployRoleArn"],
            "AWS_CFN_EXEC_ROLE_ARN": OUTPUTS["CfnExecutionRoleArn"],
            "AWS_ARTIFACT_BUCKET": OUTPUTS["ArtifactBucket"],
            "AWS_VPC_ID": "vpc-1",
            "AWS_APP_SUBNET_ID": "subnet-a",
            "AWS_DATA_SUBNET_IDS": "subnet-a,subnet-b",
        })
        self.assertEqual(gh.environment, {"reviewers": [{"type": "User", "id": 123043136}],
                                          "deployment_branch_policy": {"protected_branches": False,
                                                                       "custom_branch_policies": True}})
        self.assertEqual(gh.policies, ["main"])

    def test_the_stack_is_tagged_from_infra_tags_json(self):
        aws = FakeAws()
        run([], aws, FakeGh())
        args = aws.deploys[0]
        tags = args[args.index("--tags") + 1:args.index("--parameter-overrides")]
        want = {**json.loads((ROOT / "infra/tags.json").read_text())["tags"],
                "Stack": STACK, "Environment": "shared", "DeployedBy": "cli"}
        self.assertEqual(dict(t.split("=", 1) for t in tags), want)

    def test_an_existing_github_provider_is_reused(self):
        aws = FakeAws(providers=["arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"])
        rc, out = run([], aws, FakeGh())
        self.assertEqual(rc, 0, out)
        self.assertEqual(aws.param("CreateOidcProvider"), "false")

    def test_an_existing_secrets_manager_endpoint_is_passed_on(self):
        gh = FakeGh()
        run([], FakeAws(endpoints=[{"VpcEndpointId": "vpce-1", "State": "available"}]), gh)
        self.assertEqual(gh.variables["AWS_EXISTING_SM_ENDPOINT_ID"], "vpce-1")

    def test_a_stale_endpoint_variable_is_removed(self):
        gh = FakeGh(variables={"AWS_EXISTING_SM_ENDPOINT_ID": "vpce-gone"})
        rc, out = run([], FakeAws(), gh)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("AWS_EXISTING_SM_ENDPOINT_ID", gh.variables)

    def test_the_alert_email_is_set_only_when_given(self):
        gh = FakeGh()
        run(["--alert-email", "ops@example.com"], FakeAws(), gh)
        self.assertEqual(gh.variables["AWS_ALERT_EMAIL"], "ops@example.com")


class Rerun(unittest.TestCase):
    def test_an_existing_stack_keeps_its_provider_choice_and_branch_policy(self):
        stack = {"StackStatus": "UPDATE_COMPLETE", "Parameters": [{"ParameterKey": "CreateOidcProvider", "ParameterValue": "true"}]}
        aws, gh = FakeAws(stack=stack, providers=["arn:aws:iam::1:oidc-provider/token.actions.githubusercontent.com"]), FakeGh(policies=["main"])
        rc, out = run([], aws, gh)
        self.assertEqual(rc, 0, out)
        self.assertEqual(aws.param("CreateOidcProvider"), "true")  # the provider is this stack's own
        self.assertEqual(gh.policies, ["main"])

    def test_an_older_bootstrap_under_the_prefix_is_updated_in_place(self):
        stack = {"StackStatus": "CREATE_COMPLETE", "Parameters": []}
        aws = FakeAws(stack=stack)
        rc, out = run(["--stack-name", "secure-notes-github"], aws, FakeGh())
        self.assertEqual(rc, 0, out)
        self.assertEqual(aws.deploys[0][aws.deploys[0].index("--stack-name") + 1], "secure-notes-github")


class Stops(unittest.TestCase):
    def assert_no_change(self, aws, gh):
        self.assertEqual(aws.deploys, [])
        self.assertEqual(gh.writes(), [])

    def test_plan_changes_nothing(self):
        aws, gh = FakeAws(), FakeGh()
        rc, out = run(["--plan"], aws, gh)
        self.assertEqual(rc, 0)
        self.assertIn("AWS_DATA_SUBNET_IDS = subnet-a,subnet-b", out)
        self.assert_no_change(aws, gh)

    def test_no_answer_changes_nothing(self):
        aws, gh = FakeAws(), FakeGh()
        rc, out = run([], aws, gh, answer="")
        self.assertEqual(rc, 1)
        self.assertIn("nothing changed", out)
        self.assert_no_change(aws, gh)

    def test_not_signed_in_says_how(self):
        aws, gh = FakeAws(signed_in=False), FakeGh()
        rc, out = run(["--profile", "lab"], aws, gh)
        self.assertEqual(rc, 2)
        self.assertIn("aws login --profile lab", out)
        self.assert_no_change(aws, gh)

    def test_a_new_stack_under_the_prefix_is_refused(self):
        aws, gh = FakeAws(), FakeGh()
        rc, out = run(["--stack-name", "secure-notes-github"], aws, gh)
        self.assertEqual(rc, 2)
        self.assertIn("must not start with secure-notes", out)
        self.assert_no_change(aws, gh)

    def test_roles_held_by_another_stack_name_it(self):
        aws, gh = FakeAws(other_stack_roles="secure-notes-github"), FakeGh()
        rc, out = run([], aws, gh)
        self.assertEqual(rc, 2)
        self.assertIn("rerun with --stack-name secure-notes-github", out)
        self.assert_no_change(aws, gh)

    def test_a_failed_first_create_is_named(self):
        aws, gh = FakeAws(stack={"StackStatus": "ROLLBACK_COMPLETE", "Parameters": []}), FakeGh()
        rc, out = run([], aws, gh)
        self.assertEqual(rc, 2)
        self.assertIn("delete-stack --stack-name github-oidc-secure-notes", out)
        self.assert_no_change(aws, gh)

    def test_no_default_vpc_asks_for_the_network(self):
        aws, gh = FakeAws(default_vpc=False), FakeGh()
        rc, out = run([], aws, gh)
        self.assertEqual(rc, 2)
        self.assertIn("pass --vpc-id, --app-subnet and --data-subnets", out)
        self.assert_no_change(aws, gh)

    def test_a_vpc_without_subnets_is_refused(self):
        rc, out = run(["--vpc-id", "vpc-1"], FakeAws(), FakeGh())
        self.assertEqual(rc, 2)
        self.assertIn("also pass --app-subnet and --data-subnets", out)

    def test_data_subnets_in_one_zone_are_refused(self):
        same_zone = [dict(s, AvailabilityZone="us-east-1a") for s in DEFAULT_SUBNETS]
        rc, out = run(["--vpc-id", "vpc-1", "--app-subnet", "subnet-a", "--data-subnets", "subnet-a,subnet-b"],
                      FakeAws(subnets=same_zone), FakeGh())
        self.assertEqual(rc, 2)
        self.assertIn("two Availability Zones", out)

    def test_a_subnet_of_another_vpc_is_refused(self):
        rc, out = run(["--vpc-id", "vpc-2", "--app-subnet", "subnet-a", "--data-subnets", "subnet-a,subnet-b"],
                      FakeAws(), FakeGh())
        self.assertEqual(rc, 2)
        self.assertIn("not subnets of vpc-2", out)

    def test_a_failed_deploy_writes_nothing_to_github(self):
        aws, gh = FakeAws(deploy_rc=255), FakeGh()
        rc, out = run([], aws, gh)
        self.assertEqual(rc, 2)
        self.assertIn("describe-stack-events", out)
        self.assertEqual(gh.writes(), [])


if __name__ == "__main__":
    unittest.main()

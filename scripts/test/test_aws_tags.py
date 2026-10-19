"""scripts/aws-tags.py against canned AWS answers: what it passes, what it fails, what it fixes.

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
spec = importlib.util.spec_from_file_location("aws_tags", ROOT / "scripts/aws-tags.py")
aws_tags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aws_tags)

STACK = "secure-notes-ci"
WANT = {**json.loads((ROOT / "infra/tags.json").read_text())["tags"],
        "Stack": STACK, "Environment": "dev", "DeployedBy": "github-actions"}


def tag_list(tags):
    return [{"Key": k, "Value": v} for k, v in tags.items()]


def cfn_tags(logical_id):
    return {"aws:cloudformation:stack-name": STACK, "aws:cloudformation:logical-id": logical_id}


class FakeAws:
    """Answers the aws CLI calls aws-tags.py makes, from a dict of state; records every call."""

    def __init__(self, resources=(), tagged=None, roles=None, volume_tags=None, eni_tags=None,
                 secret_tags=None, keys=None, gone=()):
        self.resources = list(resources)
        self.tagged = tagged or {}          # ARN -> tags, as GetResources returns them
        self.roles = roles or {}            # role name -> tags
        self.volume_tags = volume_tags if volume_tags is not None else dict(WANT)
        self.eni_tags = eni_tags if eni_tags is not None else dict(WANT)
        self.secret_tags = secret_tags if secret_tags is not None else dict(WANT)
        self.keys = keys or {}              # KMS ARN -> KeyState
        self.gone = set(gone)               # ARNs whose describe call fails
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("cloudformation", "list-stack-resources"):
            return {"StackResourceSummaries": self.resources}
        if args[:2] == ("resourcegroupstaggingapi", "get-resources"):
            key, value = args[3].removeprefix("Key=").split(",Values=")
            return {"ResourceTagMappingList": [
                {"ResourceARN": arn, "Tags": tag_list(t)} for arn, t in self.tagged.items() if t.get(key) == value]}
        if args[:2] == ("iam", "list-role-tags"):
            return {"Tags": tag_list(self.roles[args[3]])}
        if args[:2] == ("ec2", "describe-instances"):
            return {"Reservations": [{"Instances": [{
                "BlockDeviceMappings": [{"Ebs": {"VolumeId": "vol-1"}}],
                "NetworkInterfaces": [{"NetworkInterfaceId": "eni-1"}]}]}]}
        if args[:2] == ("ec2", "describe-volumes"):
            return {"Volumes": [{"VolumeId": "vol-1", "Tags": tag_list(self.volume_tags)}]}
        if args[:2] == ("ec2", "describe-network-interfaces"):
            return {"NetworkInterfaces": [{"NetworkInterfaceId": "eni-1", "TagSet": tag_list(self.eni_tags)}]}
        if args[:2] == ("rds", "describe-db-instances"):
            return {"DBInstances": [{"MasterUserSecret": {"SecretArn": "arn:aws:secretsmanager:us-east-1:1:secret:rds!db-1"}}]}
        if args[:2] == ("secretsmanager", "describe-secret"):
            if args[3] in self.gone:
                raise subprocess.CalledProcessError(254, args)
            return {"Tags": tag_list(self.secret_tags)}
        if args[:2] == ("secretsmanager", "tag-resource"):
            self.secret_tags.update({t["Key"]: t["Value"] for t in json.loads(args[5])})
            return {}
        if args[:2] == ("kms", "describe-key"):
            if args[3] in self.gone:
                raise subprocess.CalledProcessError(254, args)
            return {"KeyMetadata": {"KeyState": self.keys[args[3]]}}
        raise AssertionError(f"unexpected aws call: {args}")


def stack(*rows):
    return [{"LogicalResourceId": n, "ResourceType": t, "PhysicalResourceId": p, "ResourceStatus": "CREATE_COMPLETE"}
            for n, t, p in rows]


ROWS = [("AppInstance", "AWS::EC2::Instance", "i-1"), ("Database", "AWS::RDS::DBInstance", "db-1"),
        ("AppRole", "AWS::IAM::Role", "secure-notes-ci-AppRole-X"), ("SecretsKey", "AWS::KMS::Key", "k-1"),
        ("SecretsKeyAlias", "AWS::KMS::Alias", "alias/x")]
TAGGED = {f"arn:{n}": {**WANT, **cfn_tags(n)} for n, _, _ in ROWS if n not in ("AppRole", "SecretsKeyAlias")}


def run(argv, aws):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = aws_tags.main(argv, aws=aws)
    return rc, out.getvalue()


class Check(unittest.TestCase):
    def test_every_resource_tagged_passes(self):
        aws = FakeAws(stack(*ROWS), dict(TAGGED), roles={"secure-notes-ci-AppRole-X": dict(WANT)})
        rc, out = run(["check", STACK], aws)
        self.assertEqual(rc, 0, out)
        self.assertIn("AppRole (AWS::IAM::Role, read directly)", out)
        self.assertNotIn("SecretsKeyAlias", out)  # an alias takes no tags: skipped, and counted
        self.assertIn("1 of the stack's resources are of types that take no tags", out)

    def test_a_missing_tag_fails_and_names_it(self):
        tagged = dict(TAGGED)
        tagged["arn:SecretsKey"] = {k: v for k, v in tagged["arn:SecretsKey"].items() if k != "Owner"}
        rc, out = run(["check", STACK], FakeAws(stack(*ROWS), tagged, roles={"secure-notes-ci-AppRole-X": dict(WANT)}))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL  SecretsKey (AWS::KMS::Key): missing Owner", out)

    def test_a_resource_the_tagging_api_does_not_list_fails(self):
        tagged = {k: v for k, v in TAGGED.items() if k != "arn:Database"}
        rc, out = run(["check", STACK], FakeAws(stack(*ROWS), tagged, roles={"secure-notes-ci-AppRole-X": dict(WANT)}))
        self.assertEqual(rc, 1)
        self.assertIn("Database (AWS::RDS::DBInstance): not found by the Resource Groups Tagging API", out)

    def test_a_role_with_a_wrong_value_fails(self):
        roles = {"secure-notes-ci-AppRole-X": {**WANT, "Stack": "another"}}
        rc, out = run(["check", STACK], FakeAws(stack(*ROWS), dict(TAGGED), roles=roles))
        self.assertEqual(rc, 1)
        self.assertIn("Stack='another' (want 'secure-notes-ci')", out)

    def test_an_untagged_root_volume_fails(self):
        rc, out = run(["check", STACK], FakeAws(stack(*ROWS), dict(TAGGED), roles={"secure-notes-ci-AppRole-X": dict(WANT)},
                                                volume_tags={}))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL  root volume vol-1: missing", out)

    def test_the_rds_secret_is_tagged_when_asked_and_only_then(self):
        roles = {"secure-notes-ci-AppRole-X": dict(WANT)}
        rc, out = run(["check", STACK], FakeAws(stack(*ROWS), dict(TAGGED), roles=roles, secret_tags={}))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL  the RDS-managed secret: missing", out)
        aws = FakeAws(stack(*ROWS), dict(TAGGED), roles=roles, secret_tags={})
        rc, out = run(["check", STACK, "--fix-rds-secret"], aws)
        self.assertEqual(rc, 0, out)
        self.assertTrue(any(c[:2] == ("secretsmanager", "tag-resource") for c in aws.calls))
        self.assertIn("ok    the RDS-managed secret", out)


class Leftovers(unittest.TestCase):
    KEY = "arn:aws:kms:us-east-1:1:key/abc"

    def test_only_pending_keys_and_the_kept_bucket_pass(self):
        tagged = {self.KEY: {**WANT, **cfn_tags("SecretsKey")}, "arn:aws:s3:::trail": {**WANT, **cfn_tags("TrailBucket")}}
        rc, out = run(["leftovers", STACK, "--wait-seconds", "0"], FakeAws(tagged=tagged, keys={self.KEY: "PendingDeletion"}))
        self.assertEqual(rc, 0, out)
        self.assertIn("KMS key PendingDeletion", out)
        self.assertIn("TrailBucket, kept on purpose", out)

    def test_anything_else_fails_after_the_wait(self):
        tagged = {"arn:aws:sns:us-east-1:1:topic": {**WANT, **cfn_tags("OpsAlertsTopic")}}
        rc, out = run(["leftovers", STACK, "--wait-seconds", "0"], FakeAws(tagged=tagged))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL  arn:aws:sns:us-east-1:1:topic: still there after the stack was deleted", out)

    def test_a_key_that_is_not_pending_fails(self):
        tagged = {self.KEY: {**WANT, **cfn_tags("SecretsKey")}}
        rc, out = run(["leftovers", STACK, "--wait-seconds", "0"], FakeAws(tagged=tagged, keys={self.KEY: "Enabled"}))
        self.assertEqual(rc, 1)

    def test_a_resource_already_gone_but_still_indexed_passes(self):
        secret = "arn:aws:secretsmanager:us-east-1:1:secret:/elasticache/dev/secure-notes-ci/app"
        tagged = {secret: {**WANT, **cfn_tags("RedisAppSecret")}}
        rc, out = run(["leftovers", STACK, "--wait-seconds", "0"], FakeAws(tagged=tagged, gone={secret}))
        self.assertEqual(rc, 0, out)
        self.assertIn("already gone (the tagging API still lists it)", out)

    def test_it_waits_out_the_tagging_apis_lag(self):
        topic = "arn:aws:sns:us-east-1:1:topic"
        aws = FakeAws(tagged={topic: {**WANT, **cfn_tags("OpsAlertsTopic")}})
        naps = []

        def nap(seconds):  # the topic drops out of the index during the first wait
            naps.append(seconds)
            aws.tagged.clear()

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = aws_tags.leftovers(aws, STACK, wait_seconds=600, sleep=nap)
        self.assertEqual(rc, 0, out.getvalue())
        self.assertEqual(naps, [30])
        self.assertIn("1 not gone yet; the tagging API lags behind deletes, retrying", out.getvalue())

    def test_nothing_left_passes(self):
        rc, out = run(["leftovers", STACK, "--wait-seconds", "0"], FakeAws())
        self.assertEqual(rc, 0)
        self.assertIn("ok    nothing", out)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""The tags on a deployed Secure Notes stack, and what a teardown left behind (real AWS).

   python3 scripts/aws-tags.py check <stack> [--environment dev] [--deployed-by github-actions] [--fix-rds-secret]
   python3 scripts/aws-tags.py leftovers <stack> [--wait-seconds 600]

check:     every resource of the stack that takes tags carries the tags of infra/tags.json, with
           Stack=<stack>, and so do the resources AWS makes for it: the instance's root volume and
           network interface, and the secret RDS creates for the database. --fix-rds-secret tags
           that secret first (AWS does not document whether RDS copies the database's tags to it).
leftovers: after delete-stack, nothing is tagged Stack=<stack> except what stays on purpose: the
           KMS keys pending deletion, and the trail bucket (DeletionPolicy: Retain). The Resource
           Groups Tagging API lags behind deletes, so it retries for up to --wait-seconds.

Exit 1 on a finding; each line says ok or FAIL. Standard library only: it calls the aws CLI.
The plan: docs/modernization/plan-tags-and-teardown.md.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "infra/tags.json").read_text())
FIXED = SPEC["tags"]
UNTAGGABLE = set(SPEC["untaggableTypes"]["types"])
CFN_STACK_TAG = "aws:cloudformation:stack-name"
CFN_LOGICAL_TAG = "aws:cloudformation:logical-id"
# Kept on purpose by the template: the trail's log bucket (DeletionPolicy: Retain).
RETAINED_LOGICAL_IDS = {"TrailBucket"}
# GetResources "does not currently support IAM users and roles" (Resource Groups Tagging API
# reference, Welcome): their tags are read with IAM's own call instead.
DIRECT = {"AWS::IAM::Role": lambda aws, name: aws("iam", "list-role-tags", "--role-name", name).get("Tags")}


class Aws:
    """Runs the aws CLI and returns its JSON. Tests replace it with canned answers."""

    def __call__(self, *args):
        cmd = ["aws", *args, "--output", "json"]
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode:
            # Say which call failed and AWS's reason (AccessDenied names the missing permission).
            print(f"        aws {' '.join(args)}: {done.stderr.strip()}", file=sys.stderr)
            raise subprocess.CalledProcessError(done.returncode, cmd, done.stdout, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else {}


def as_dict(tags):
    """[{Key, Value}] -> {Key: Value} (EC2 and the tagging API both use this shape)."""
    return {t["Key"]: t["Value"] for t in tags or []}


def problems(tags, want):
    """What is missing or wrong in tags, against the wanted {Key: Value}."""
    missing = sorted(k for k in want if k not in tags)
    wrong = sorted(f"{k}={tags[k]!r} (want {want[k]!r})" for k in want if k in tags and tags[k] != want[k])
    return ([f"missing {', '.join(missing)}"] if missing else []) + wrong


class Report:
    def __init__(self):
        self.failures = []

    def ok(self, msg):
        print(f"  ok    {msg}")

    def bad(self, msg):
        print(f"  FAIL  {msg}")
        self.failures.append(msg)

    def verdict(self, name, done):
        print()
        if self.failures:
            print(f"aws-tags {name}: {len(self.failures)} problem(s)")
            return 1
        print(f"aws-tags {name}: {done}")
        return 0


def want_tags(stack, environment, deployed_by):
    return {**FIXED, "Stack": stack, "Environment": environment, "DeployedBy": deployed_by}


def tagged_by_logical_id(aws, stack):
    """Every resource the Resource Groups Tagging API knows for this stack: {logical id: (arn, tags)}."""
    found = {}
    for key in (CFN_STACK_TAG, "Stack"):
        page = aws("resourcegroupstaggingapi", "get-resources", "--tag-filters", f"Key={key},Values={stack}")
        for m in page.get("ResourceTagMappingList", []):
            tags = as_dict(m.get("Tags"))
            found.setdefault(tags.get(CFN_LOGICAL_TAG, m["ResourceARN"]), (m["ResourceARN"], tags))
    return found


def check(aws, stack, environment, deployed_by, fix_rds_secret):
    want = want_tags(stack, environment, deployed_by)
    report = Report()
    resources = aws("cloudformation", "list-stack-resources", "--stack-name", stack)["StackResourceSummaries"]
    live = [r for r in resources if r["ResourceStatus"] not in ("DELETE_COMPLETE", "DELETE_SKIPPED")]
    by_id = {r["LogicalResourceId"]: r for r in live}

    print(f"== the stack's resources ({len(live)}): every one that takes tags carries all {len(want)}")
    found = tagged_by_logical_id(aws, stack)
    skipped = 0
    for r in sorted(live, key=lambda r: r["LogicalResourceId"]):
        name, rtype = r["LogicalResourceId"], r["ResourceType"]
        if rtype in UNTAGGABLE:
            skipped += 1
            continue
        if rtype in DIRECT:
            issues = problems(as_dict(DIRECT[rtype](aws, r["PhysicalResourceId"])), want)
            (report.bad if issues else report.ok)(f"{name} ({rtype}, read directly)" + (f": {'; '.join(issues)}" if issues else ""))
            continue
        if name not in found:
            report.bad(f"{name} ({rtype}): not found by the Resource Groups Tagging API under this stack")
            continue
        issues = problems(found[name][1], want)
        if issues:
            report.bad(f"{name} ({rtype}): {'; '.join(issues)}")
        else:
            report.ok(f"{name} ({rtype})")
    print(f"        ({skipped} of the stack's resources are of types that take no tags: infra/tags.json)")

    print("== what AWS makes for the stack")
    instance = by_id.get("AppInstance", {}).get("PhysicalResourceId")
    if instance:
        desc = aws("ec2", "describe-instances", "--instance-ids", instance)["Reservations"][0]["Instances"][0]
        volumes = [b["Ebs"]["VolumeId"] for b in desc.get("BlockDeviceMappings", []) if "Ebs" in b]
        enis = [n["NetworkInterfaceId"] for n in desc.get("NetworkInterfaces", [])]
        for v in aws("ec2", "describe-volumes", "--volume-ids", *volumes).get("Volumes", []) if volumes else []:
            issues = problems(as_dict(v.get("Tags")), want)
            (report.bad if issues else report.ok)(f"root volume {v['VolumeId']}" + (f": {'; '.join(issues)}" if issues else ""))
        for n in aws("ec2", "describe-network-interfaces", "--network-interface-ids", *enis).get("NetworkInterfaces", []) if enis else []:
            issues = problems(as_dict(n.get("TagSet")), want)
            (report.bad if issues else report.ok)(f"network interface {n['NetworkInterfaceId']}" + (f": {'; '.join(issues)}" if issues else ""))
    else:
        report.bad("AppInstance: not in the stack, so its volume and network interface were not checked")

    db = by_id.get("Database", {}).get("PhysicalResourceId")
    if db:
        secret = aws("rds", "describe-db-instances", "--db-instance-identifier", db)["DBInstances"][0].get("MasterUserSecret", {}).get("SecretArn")
        if not secret:
            report.bad(f"Database {db}: no RDS-managed secret")
        else:
            issues = problems(as_dict(aws("secretsmanager", "describe-secret", "--secret-id", secret).get("Tags")), want)
            if issues and fix_rds_secret:
                print(f"  fix   the RDS-managed secret: {'; '.join(issues)}; tagging it")
                aws("secretsmanager", "tag-resource", "--secret-id", secret,
                    "--tags", json.dumps([{"Key": k, "Value": v} for k, v in want.items()]))
                issues = problems(as_dict(aws("secretsmanager", "describe-secret", "--secret-id", secret).get("Tags")), want)
            (report.bad if issues else report.ok)("the RDS-managed secret" + (f": {'; '.join(issues)}" if issues else ""))
    else:
        report.bad("Database: not in the stack, so its RDS-managed secret was not checked")
    return report.verdict("check", f"every resource of {stack} carries the tags of infra/tags.json")


def expected_leftover(aws, arn, tags):
    """Why a resource may still be listed after its stack, or None if it must not be."""
    try:
        if ":kms:" in arn and ":key/" in arn:
            state = aws("kms", "describe-key", "--key-id", arn)["KeyMetadata"]["KeyState"]
            return f"KMS key {state}, deleted by AWS at the end of its window" if state == "PendingDeletion" else None
        if ":secretsmanager:" in arn:
            deleted = aws("secretsmanager", "describe-secret", "--secret-id", arn).get("DeletedDate")
            return f"secret scheduled for deletion ({deleted})" if deleted else None
    except subprocess.CalledProcessError:
        return "already gone (the tagging API still lists it)"
    if tags.get(CFN_LOGICAL_TAG) in RETAINED_LOGICAL_IDS:
        return f"{tags[CFN_LOGICAL_TAG]}, kept on purpose (DeletionPolicy: Retain)"
    return None


def leftovers(aws, stack, wait_seconds, sleep=time.sleep):
    report = Report()
    print(f"== after the teardown: what is still tagged Stack={stack}")
    deadline = time.monotonic() + wait_seconds
    while True:
        found = tagged_by_logical_id(aws, stack)
        unexpected = {}
        expected = {}
        for _, (arn, tags) in found.items():
            why = expected_leftover(aws, arn, tags)
            (expected if why else unexpected)[arn] = why
        if not unexpected or time.monotonic() >= deadline:
            break
        print(f"        {len(unexpected)} not gone yet; the tagging API lags behind deletes, retrying")
        sleep(30)
    for arn, why in sorted(expected.items()):
        report.ok(f"{arn}: {why}")
    for arn in sorted(unexpected):
        report.bad(f"{arn}: still there after the stack was deleted")
    if not found:
        report.ok("nothing")
    # Only tagged resources can be found this way, which is why everything is tagged at create
    # time; IAM roles are not indexed (see DIRECT), and CloudFormation deletes them with the stack.
    return report.verdict("leftovers", f"nothing of {stack} is left but what stays on purpose")


def main(argv=None, aws=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("stack")
    c.add_argument("--environment", default="dev")
    c.add_argument("--deployed-by", default="github-actions")
    c.add_argument("--fix-rds-secret", action="store_true")
    l = sub.add_parser("leftovers")
    l.add_argument("stack")
    l.add_argument("--wait-seconds", type=int, default=600)
    a = p.parse_args(argv)
    aws = aws or Aws()
    if a.command == "check":
        return check(aws, a.stack, a.environment, a.deployed_by, a.fix_rds_secret)
    return leftovers(aws, a.stack, a.wait_seconds)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Hold the AWS templates and the Part C workflow to infra/tags.json, without AWS.

   python3 scripts/tags-check.py

Fails (exit 1) when:
  - a resource type in a template is on neither list in infra/tags.json (review it first);
  - a tag list the templates write themselves (the launch template's, the bootstrap's) misses
    a required tag, or gives a fixed tag another value;
  - the main template loses CopyTagsToSnapshot on the database, the KMS keys' 7-day window,
    or its DeployedBy parameter;
  - the aws (Part C) workflow stops passing the stack tags from infra/tags.json.
Every other taggable resource gets the tags as stack tags, which CloudFormation passes on.
The run on AWS checks the result (docs/modernization/plan-tags-and-teardown.md).
"""
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAIN = "infra/cloudformation.yaml"
BOOTSTRAP = "infra/github-actions-bootstrap.yaml"
WORKFLOW = ".github/workflows/aws.yaml"


class CfnLoader(yaml.SafeLoader):
    """Reads !Ref, !Sub and the other short forms as {"!Ref": value}, so values can be compared."""


def _short_form(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {"!" + suffix: value}


CfnLoader.add_multi_constructor("!", _short_form)

spec = json.loads((ROOT / "infra/tags.json").read_text())
FIXED = spec["tags"]
PER_DEPLOY = set(spec["perDeploy"])
REQUIRED = set(FIXED) | PER_DEPLOY
TAGGABLE = set(spec["taggableTypes"]["types"])
UNTAGGABLE = set(spec["untaggableTypes"]["types"])

failures = []


def ok(msg):
    print(f"  ok    {msg}")


def bad(msg):
    print(f"  FAIL  {msg}")
    failures.append(msg)


def check_tag_list(where, tags):
    """A tag list must carry every required key; a fixed key must carry its value from infra/tags.json."""
    got = {t["Key"]: t["Value"] for t in tags or []}
    missing = sorted(REQUIRED - set(got))
    wrong = sorted(k for k, v in FIXED.items() if k in got and got[k] != v)
    if missing:
        bad(f"{where}: missing {', '.join(missing)}")
    if wrong:
        bad(f"{where}: {', '.join(f'{k}={got[k]!r} (want {FIXED[k]!r})' for k in wrong)}")
    if not missing and not wrong:
        ok(f"{where}: all {len(REQUIRED)} tags")


def load(path):
    return yaml.load((ROOT / path).read_text(), Loader=CfnLoader)


print("== resource types: each one reviewed (infra/tags.json)")
for path in (MAIN, BOOTSTRAP):
    resources = load(path)["Resources"]
    unknown = sorted({r["Type"] for r in resources.values()} - TAGGABLE - UNTAGGABLE)
    if unknown:
        bad(f"{path}: {', '.join(unknown)} on neither list: check its schema's taggable flag, then add it")
    else:
        ok(f"{path}: {len(resources)} resources, every type classified")

print("== where stack tags don't reach, the template names the tags")
main = load(MAIN)
lt = main["Resources"]["AppLaunchTemplate"]["Properties"]
own = {s["ResourceType"]: s["Tags"] for s in lt.get("TagSpecifications", [])}
made = {s["ResourceType"]: s["Tags"] for s in lt.get("LaunchTemplateData", {}).get("TagSpecifications", [])}
check_tag_list("AppLaunchTemplate itself", own.get("launch-template"))
check_tag_list("AppLaunchTemplate: the root volume", made.get("volume"))
check_tag_list("AppLaunchTemplate: the network interface", made.get("network-interface"))

db = main["Resources"]["Database"]["Properties"]
if db.get("CopyTagsToSnapshot") is True:
    ok("Database: CopyTagsToSnapshot (the final snapshot is tagged)")
else:
    bad("Database: CopyTagsToSnapshot must be true, or the final snapshot left on delete has no tags")
for name, r in main["Resources"].items():
    if r["Type"] == "AWS::KMS::Key":
        days = r["Properties"].get("PendingWindowInDays")
        if days == 7:
            ok(f"{name}: deleted 7 days after the stack")
        else:
            bad(f"{name}: PendingWindowInDays is {days}, want 7 (the owner's choice for this test stack)")
if "DeployedBy" in main.get("Parameters", {}):
    ok("the DeployedBy parameter exists")
else:
    bad("the DeployedBy parameter is gone: the DeployedBy tag has no value")

print("== the bootstrap stack names its own tags (it is deployed once, from the console)")
for name, r in load(BOOTSTRAP)["Resources"].items():
    if r["Type"] in TAGGABLE:
        check_tag_list(f"{BOOTSTRAP} {name}", r["Properties"].get("Tags"))

print("== the workflow passes the stack tags")
workflow = (ROOT / WORKFLOW).read_text()
for needle, why in [
    ("infra/tags.json", "it reads the fixed tags from infra/tags.json"),
    ("--tags", "aws cloudformation deploy gets --tags"),
    ("DeployedBy=github-actions", "it tags the stack DeployedBy=github-actions"),
]:
    if needle in workflow:
        ok(f"{WORKFLOW}: {why}")
    else:
        bad(f"{WORKFLOW}: {why} (no {needle!r})")

print()
if failures:
    print(f"tags-check: {len(failures)} problem(s)")
    sys.exit(1)
print("tags-check: every AWS resource is tagged from infra/tags.json")

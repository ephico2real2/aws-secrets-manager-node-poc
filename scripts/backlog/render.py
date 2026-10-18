import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data import EPICS, B

state = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "issue-numbers.json")))
ISS = "https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues/"
# Links inside the repo become relative to docs/modernization/.
def rel(md):
    def fix(m):
        path = m.group(2)
        target = os.path.relpath(path.rstrip("/") or ".", "docs/modernization") + ("/" if path.endswith("/") else "")
        return f"[{m.group(1)}]({target})"
    return re.sub(r"\[([^\]]+)\]\(" + re.escape(B) + r"([^)]+)\)", fix, md)

def closed(item):
    kids = item.get("children", [])
    if "criteria" not in item:
        return all(closed(k) for k in kids) if kids else item.get("status") == "done"
    return item.get("status") == "done" and all(c for c, _ in item["criteria"]) and all(closed(k) for k in kids)

def mark(item):
    if closed(item): return "✅"
    if item.get("status") == "done" and item.get("aws"): return "✅ built · 🔎 verify on AWS"
    kids = item.get("children", [])
    if kids and "criteria" not in item and all(k.get("status") == "done" for k in kids): return "✅ built · 🔎 verify on AWS"
    return "🔜"

def link(item):
    n = state[item["id"]]["number"]
    return f"[#{n}]({ISS}{n})"

def block(item, level):
    out = []
    size = f" · {item['size']}" if item.get("size") else ""
    head = f"**{item['id']} · {item['title']}**{size} · {mark(item)} · {link(item)}"
    out.append(("#### " + head.strip("*").replace("** ", " ", 1)) if level == "feature-group" else head)
    if item.get("story"): out.append(f"*{item['story']}*")
    for c, t in item.get("criteria", []):
        out.append(f"- [{'x' if c else ' '}] {t}")
    ev = item.get("evidence") or []
    if ev: out.append("")
    if ev: out.append("Evidence: " + ", ".join(rel(x) for x in ev))
    return "\n".join(out) + "\n"

doc = [
"# Backlog — epics, features and stories",
"",
"[← Initiative](README.md) · [Source review](01-source-review.md) · [ADR-001](02-adr-001-secrets-manager-selection.md) · [GitHub issues](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atype%3Aepic)",
"",
"**How to read it:** an **epic** is an outcome; a **feature** is a capability; a **story** is",
"one deliverable with acceptance criteria (each one testable). Size: S ≤ 1 day, M ≤ 3",
"days, L ≤ 1 week. Status: ✅ done, with evidence · 🔎 built, to verify on AWS · 🔜 to do.",
"",
"Every item is also a GitHub issue (linked as #N), with sub-issues for the hierarchy and",
"labels `app|tutorial`, `type:epic|feature|story`, `epic:E0…E7`, `size:S|M|L` and",
"`needs-aws-verification`.",
"",
"**Two tracks.** Issue titles start with the track, so the two kinds of work never mix:",
"",
"| Track | Prefix and label | What it is | Epics |",
"| --- | --- | --- | --- |",
"| **APP** | `APP:` · [`app`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Aapp) | The modernization itself: what a team does to move an app from `.env` passwords to a secrets manager | E0–E6, E8–E12 (E15 parked) |",
"| **TUTORIAL** | `TUTORIAL:` · [`tutorial`](https://github.com/ephico2real2/aws-secrets-manager-node-poc/issues?q=is%3Aissue+label%3Atutorial) | Building this tutorial about it: learning path, guide, demos, version folders | E7, E13–E14 |",
"",
"Done items are closed with their evidence. This page and the issues are generated from",
"the same list, so they say the same thing.",
"",
"Order: see the [epic map](README.md#how-the-work-is-organized). E0 then E1; E2 and E3 after",
"E1; E4, E5 and E6 in parallel once E3 is in place; E7 throughout. A small feature with",
"one deliverable is written as its own story (persona and acceptance criteria) rather",
"than split into stories.",
"",
]
TRACKS = {"app": "Track APP — modernizing the app", "tutorial": "Track TUTORIAL — building the tutorial",
          "parked": "Parked — planned, not scheduled"}
def section(e): return "parked" if e.get("parked") else e["track"]
for key in ["app", "tutorial", "parked"]:
    group = [e for e in EPICS if section(e) == key]
    if not group: continue
    doc.append(f"## {TRACKS[key]}")
    doc.append("")
    for e in group:
        doc.append(f"### {e['id']} — {e['title']}")
        doc.append("")
        doc.append(f"{link(e)} · {mark(e)} · **Outcome:** {e['outcome']} Docs: " + ", ".join(rel(x) for x in e["docs"]))
        doc.append("")
        for f in e["children"]:
            if f.get("children"):
                doc.append(f"#### {f['id']} · {f['title']} · {mark(f)} · {link(f)}")
                doc.append("")
                for s in f["children"]:
                    doc.append(block(s, "story"))
            else:
                doc.append(block(f, "feature"))
doc_text = "\n".join(doc).rstrip() + "\n"
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "modernization", "backlog.md"), "w").write(doc_text)
print("written", len(doc_text))

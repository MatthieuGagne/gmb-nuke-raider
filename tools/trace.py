#!/usr/bin/env python3
"""
trace.py — traceability chain for a spec issue: issue -> plan -> branch -> PR -> merge.

Chain mode renders the full chain for one issue number, resolving the plan from
the working tree first and from git history second (plans are sometimes deleted
after a feature merges).

Exit codes:
    0  chain rendered
    2  operational error (gh/git failed, unreadable input)

Usage:
    python3 tools/trace.py 435              # render the chain for issue #435
    python3 tools/trace.py 435 --json       # machine-readable output
    or imported:  trace.trace(435) -> dict
"""
import argparse
import json
import os
import re
import subprocess
import sys

REPO = "MatthieuGagne/gmb-nuke-raider"
PLAN_DIR = "docs/plans"

# Plans created on or after this date must carry the issue header and the
# issue number in their filename (convention adopted by #435).
ADOPTION_DATE = "2026-07-26"

PLAN_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-issue(\d+)-[a-z0-9][a-z0-9-]*\.md$")
PLAN_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
ISSUE_HEADER_RE = re.compile(r"(?m)^\*\*Issue:\*\*\s*#(\d+)\s*$")
# GitHub's full auto-close keyword set — a narrower set would reject "Fixed #12",
# which GitHub does auto-close.
CLOSES_RE = re.compile(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def parse_plan_name(filename):
    """Return (date, issue_number) parsed from a plan filename.

    issue_number is None for filenames predating the -issue<N>- convention;
    date is None when there is no YYYY-MM-DD prefix at all.
    """
    m = PLAN_NAME_RE.match(filename)
    if m:
        return m.group(1), int(m.group(2))
    m = PLAN_DATE_RE.match(filename)
    return (m.group(1) if m else None), None


def plan_header_issue(text):
    """Return the issue number from a plan's '**Issue:** #N' header line, else None."""
    m = ISSUE_HEADER_RE.search(text)
    return int(m.group(1)) if m else None


def closes_refs(body):
    """Return every issue number a PR body closes (Closes/Fixes/Resolves #N)."""
    return [int(n) for n in CLOSES_RE.findall(body or "")]


def _run(cmd):
    """Run a command and return stdout. Raise RuntimeError on non-zero exit."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {result.stderr.strip()}")
    return result.stdout


def _gh_json(args):
    """Run `gh <args>` and parse its JSON output ([] when output is empty)."""
    return json.loads(_run(["gh", *args]).strip() or "[]")


def fetch_issue(number):
    """Issue metadata via gh. Raise RuntimeError if the issue does not exist."""
    return _gh_json(["issue", "view", str(number), "--repo", REPO,
                     "--json", "number,title,state,url"])


def find_pr(number):
    """Return the PR whose body closes issue #number, or None."""
    prs = _gh_json(["pr", "list", "--repo", REPO, "--state", "all",
                    "--search", f"#{number} in:body", "--limit", "20",
                    "--json",
                    "number,title,state,mergedAt,headRefName,mergeCommit,body,url"])
    for pr in prs:
        if number in closes_refs(pr.get("body")):
            return pr
    return None


def _history_plans(root="."):
    """Yield (commit_sha, path) for every plan file ever added under docs/plans/."""
    out = _run(["git", "-C", root, "log", "--diff-filter=A", "--name-only",
                "--format=%H", "--", PLAN_DIR])
    commit = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if SHA_RE.match(line):
            commit = line
        elif commit:
            yield commit, line


def find_plan(number, root="."):
    """Locate the plan for an issue: working tree first, then git history.

    Returns {"path", "removed", "commit"} or None.
    """
    plan_dir = os.path.join(root, *PLAN_DIR.split("/"))
    if os.path.isdir(plan_dir):
        for name in sorted(os.listdir(plan_dir)):
            if not name.endswith(".md"):
                continue
            _, name_issue = parse_plan_name(name)
            with open(os.path.join(plan_dir, name), encoding="utf-8") as fh:
                text = fh.read()
            if name_issue == number or plan_header_issue(text) == number:
                return {"path": f"{PLAN_DIR}/{name}", "removed": False,
                        "commit": None}
    try:
        history = list(_history_plans(root))
    except RuntimeError:
        history = []      # not a git repo (or git unavailable) — tree result stands
    for commit, path in history:
        _, name_issue = parse_plan_name(os.path.basename(path))
        if name_issue == number:
            return {"path": path, "removed": True, "commit": commit}
    return None


def find_branch(number, root="."):
    """Branch whose name ends in -<issue number>; used when no PR exists yet."""
    try:
        out = _run(["git", "-C", root, "branch", "--all",
                    "--format=%(refname:short)"])
    except RuntimeError:
        return None
    for line in out.splitlines():
        name = line.strip()
        if name.endswith(f"-{number}"):
            return name
    return None


def trace(number, root="."):
    """Resolve the full chain for one issue number."""
    issue = fetch_issue(number)
    pr = find_pr(number)
    plan = find_plan(number, root)
    branch = pr["headRefName"] if pr else find_branch(number, root)
    merge = None
    if pr and pr.get("mergedAt"):
        merge = {"merged_at": pr["mergedAt"],
                 "commit": (pr.get("mergeCommit") or {}).get("oid")}
    return {
        "issue": {"number": issue["number"], "title": issue["title"],
                  "state": issue["state"], "url": issue["url"]},
        "plan": plan,
        "branch": branch,
        "pr": ({"number": pr["number"], "title": pr["title"],
                "state": pr["state"], "url": pr["url"]} if pr else None),
        "merge": merge,
    }


def render_chain(chain):
    """Human-readable chain."""
    issue = chain["issue"]
    lines = [f"issue  #{issue['number']}  {issue['state']}  {issue['title']}"]

    plan = chain["plan"]
    if plan is None:
        lines.append("plan   (not found)")
    else:
        lines.append(f"plan   {plan['path']}")
        if plan["removed"]:
            lines.append(
                f"       (removed from tree; added in {(plan['commit'] or '?')[:7]})")

    lines.append(f"branch {chain['branch'] or '(not found)'}")

    pr = chain["pr"]
    lines.append(f"PR     #{pr['number']}  {pr['state']}  {pr['title']}"
                 if pr else "PR     (not found)")

    merge = chain["merge"]
    lines.append(f"merge  {merge['merged_at'][:10]}  {(merge['commit'] or '?')[:7]}"
                 if merge else "merge  (not merged)")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Trace a spec issue through plan, branch, PR and merge.")
    parser.add_argument("issue", type=int, help="issue number to trace")
    parser.add_argument("--root", default=".", help="repo root (default: .)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        result = trace(args.issue, args.root)
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"trace: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2) if args.as_json else render_chain(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

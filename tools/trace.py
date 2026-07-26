#!/usr/bin/env python3
"""
trace.py — traceability chain for a spec issue: issue -> plan -> branch -> PR -> merge.

Chain mode renders the full chain for one issue number, resolving the plan from
the working tree first and from git history second (plans are sometimes deleted
after a feature merges). Check mode applies the same invariants repo-wide:
every plan carries an "**Issue:** #N" header and an issue number in its
filename; every PR body references an issue with Closes/Fixes/Resolves #N.
Violations on artifacts dated on/after ADOPTION_DATE are errors; older
artifacts produce warnings only.

Exit codes:
    0  chain rendered, or check passed (warnings allowed)
    1  check found violations (errors)
    2  operational error (gh/git failed, unreadable input)

Usage:
    python3 tools/trace.py 435                    # render the chain for issue #435
    python3 tools/trace.py 435 --json
    python3 tools/trace.py --check                # repo-wide invariants
    python3 tools/trace.py --check --plans-only   # offline: plans only, no gh
    python3 tools/trace.py --check --json
    or imported:  trace.trace(435) / trace.check(plans, prs) -> dict
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

# gh pr list page size for check mode. The adoption-date filter keeps the
# result set small; this is a safety cap, not a paging loop.
PR_PAGE_LIMIT = 200

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


def collect_plans(root="."):
    """Read every plan under docs/plans/ into check()'s input shape."""
    plan_dir = os.path.join(root, *PLAN_DIR.split("/"))
    plans = []
    if not os.path.isdir(plan_dir):
        return plans
    for name in sorted(os.listdir(plan_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(plan_dir, name), encoding="utf-8") as fh:
            plans.append({"path": f"{PLAN_DIR}/{name}", "name": name,
                          "text": fh.read()})
    return plans


def find_plan(number, root="."):
    """Locate the plan for an issue: working tree first, then git history.

    Returns {"path", "removed", "commit"} or None.
    """
    for plan in collect_plans(root):
        _, name_issue = parse_plan_name(plan["name"])
        if name_issue == number or plan_header_issue(plan["text"]) == number:
            return {"path": plan["path"], "removed": False, "commit": None}
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


def check(plans, prs, adoption_date=ADOPTION_DATE):
    """Validate traceability invariants over already-collected artifacts.

    plans: [{"path", "name", "text"}]
    prs:   [{"number", "created_at", "body"}]

    Artifacts dated on/after adoption_date produce errors; older ones produce
    warnings. Returns {"ok", "errors", "warnings"}.
    """
    errors, warnings = [], []

    for plan in plans:
        date, name_issue = parse_plan_name(plan["name"])
        header_issue = plan_header_issue(plan["text"])
        legacy = date is None or date < adoption_date

        if date is None:
            errors.append(f"{plan['path']}: filename has no YYYY-MM-DD prefix")
        if header_issue is None:
            bucket = warnings if legacy else errors
            bucket.append(f"{plan['path']}: missing '**Issue:** #N' header")
        if name_issue is None and date is not None:
            bucket = warnings if legacy else errors
            bucket.append(f"{plan['path']}: filename does not follow "
                          f"YYYY-MM-DD-issue<N>-<slug>.md")
        if (name_issue is not None and header_issue is not None
                and name_issue != header_issue):
            errors.append(f"{plan['path']}: filename says #{name_issue} but "
                          f"header says #{header_issue}")

    for pr in prs:
        if closes_refs(pr.get("body")):
            continue
        created = (pr.get("created_at") or "")[:10]
        bucket = warnings if created < adoption_date else errors
        bucket.append(f"PR #{pr['number']}: body has no "
                      f"Closes/Fixes/Resolves #N reference")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def collect_prs(adoption_date=ADOPTION_DATE):
    """PRs subject to the Closes-#N invariant.

    Everything created on/after the adoption date (error-eligible), plus every
    still-open PR from before it (warning-eligible). Closed PRs older than the
    adoption date are out of scope and never fetched.
    """
    seen, prs = set(), []
    queries = [
        ["--state", "all", "--search", f"created:>={adoption_date}"],
        ["--state", "open"],
    ]
    for extra in queries:
        for pr in _gh_json(["pr", "list", "--repo", REPO, "--limit",
                            str(PR_PAGE_LIMIT), "--json",
                            "number,createdAt,body,url", *extra]):
            if pr["number"] in seen:
                continue
            seen.add(pr["number"])
            prs.append({"number": pr["number"], "created_at": pr["createdAt"],
                        "body": pr.get("body") or ""})
    return prs


def render_check(result):
    """Human-readable check verdict."""
    lines = [f"WARN  {w}" for w in result["warnings"]]
    lines += [f"ERROR {e}" for e in result["errors"]]
    lines.append("PASS - traceability invariants hold" if result["ok"]
                 else f"FAIL - {len(result['errors'])} traceability violation(s)")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Trace a spec issue through plan, branch, PR and merge.")
    parser.add_argument("issue", nargs="?", type=int,
                        help="issue number to trace")
    parser.add_argument("--check", action="store_true",
                        help="validate repo-wide traceability invariants")
    parser.add_argument("--plans-only", action="store_true",
                        help="with --check: skip the PR invariant (no gh calls)")
    parser.add_argument("--root", default=".", help="repo root (default: .)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    if args.check == (args.issue is not None):
        parser.error("give an issue number or --check, not both")

    try:
        if args.check:
            prs = [] if args.plans_only else collect_prs()
            result = check(collect_plans(args.root), prs)
        else:
            result = trace(args.issue, args.root)
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"trace: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result, indent=2))
    elif args.check:
        print(render_check(result),
              file=sys.stdout if result["ok"] else sys.stderr)
    else:
        print(render_chain(result))
    return 0 if (not args.check or result["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())

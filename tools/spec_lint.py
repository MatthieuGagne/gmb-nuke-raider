#!/usr/bin/env python3
"""
spec_lint.py — validate a PRD issue body against the project's PRD template.

A "spec" passes lint when every required section is present and non-empty, and
each of Requirements / Acceptance Criteria / Files Impacted carries at least one
entry. The spec is additionally classified doc-only or code from its impacted
file list.

Exit codes:
    0  spec is valid
    1  spec is invalid (structural lint failure)
    2  operational error (could not fetch/read the input)

Usage:
    python3 tools/spec_lint.py --issue 433          # fetch via gh, lint
    python3 tools/spec_lint.py --file spec.md       # lint a local file
    python3 tools/spec_lint.py --stdin < spec.md    # lint stdin
    python3 tools/spec_lint.py --issue 433 --json   # machine-readable output
    or imported:  spec_lint.lint(body_text) -> dict
"""
import argparse
import json
import re
import subprocess
import sys

REPO = "MatthieuGagne/gmb-nuke-raider"

# Required sections in canonical order (## Notes is optional — not listed).
REQUIRED_SECTIONS = [
    "Goal",
    "Requirements",
    "Acceptance Criteria",
    "Out of Scope",
    "Files Impacted",
]


def _strip_comments(text):
    """Remove HTML comments and surrounding whitespace."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def _is_doc_only_path(path):
    """Doc-only rules (CLAUDE.md): *.md, *.txt, *.json except bank-manifest.json,
    and any file under .claude/skills/ or .claude/agents/."""
    p = path.strip().strip("`").strip()
    if not p:
        return False
    if p.startswith(".claude/skills/") or p.startswith(".claude/agents/"):
        return True
    if p.endswith(".md") or p.endswith(".txt"):
        return True
    if p.endswith(".json"):
        return not p.endswith("bank-manifest.json")
    return False


def _parse_impacted_files(section_text):
    """Extract the first backtick-quoted path from each '- ' bullet line."""
    files = []
    for line in _strip_comments(section_text).splitlines():
        if not re.match(r"^\s*-\s+", line):
            continue
        m = re.search(r"`([^`]+)`", line)
        if m:
            files.append(m.group(1).strip())
    return files


def _parse_sections(body):
    """Return {heading: section_body_text} for every top-level '## ' heading."""
    sections = {}
    current = None
    lines = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = m.group(1).strip()
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def lint(body):
    """Lint a PRD body string. Never raises on content — returns a result dict.

    Keys:
        valid          bool
        doc_only       bool              every impacted file is a doc-only path
        errors         list[str]
        sections       dict[str, bool]   presence+non-empty per required section
        impacted_files list[str]         paths parsed from ## Files Impacted
    """
    errors = []
    sections = _parse_sections(body)

    present = {}
    for name in REQUIRED_SECTIONS:
        if name not in sections:
            present[name] = False
            errors.append(f"Missing required section: ## {name}")
        elif not _strip_comments(sections[name]):
            present[name] = False
            errors.append(f"Section is empty: ## {name}")
        else:
            present[name] = True

    # R2: Requirements must have at least one '- R' requirement line.
    if present.get("Requirements"):
        req_body = _strip_comments(sections["Requirements"])
        if not re.search(r"(?m)^\s*-\s*R\d*\b", req_body):
            errors.append("Requirements section has no '- R' requirement lines")

    # R2: Acceptance Criteria must have at least one '- [ ]' checkbox.
    if present.get("Acceptance Criteria"):
        ac_body = _strip_comments(sections["Acceptance Criteria"])
        if not re.search(r"(?m)^\s*-\s*\[[ xX]\]", ac_body):
            errors.append("Acceptance Criteria section has no '- [ ]' checkboxes")

    # R2: Files Impacted must have at least one bullet entry.
    if present.get("Files Impacted"):
        fi_body = _strip_comments(sections["Files Impacted"])
        if not any(re.match(r"^\s*-\s+\S", ln) for ln in fi_body.splitlines()):
            errors.append("Files Impacted section has no entries")

    # R3: classify the spec from its impacted-file list.
    impacted_files = _parse_impacted_files(sections.get("Files Impacted", ""))
    doc_only = bool(impacted_files) and all(
        _is_doc_only_path(f) for f in impacted_files
    )

    return {
        "valid": not errors,
        "doc_only": doc_only,
        "errors": errors,
        "sections": present,
        "impacted_files": impacted_files,
    }


def _fetch_issue_body(issue_number):
    """Fetch a GitHub issue body via gh. Raise RuntimeError on failure."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number),
         "--repo", REPO, "--json", "body"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh failed: {result.stderr.strip()}")
    return json.loads(result.stdout)["body"]


def _render(result):
    """Human-readable verdict."""
    if result["valid"]:
        kind = "doc-only" if result["doc_only"] else "code"
        return f"PASS - spec is valid ({kind} workflow)"
    lines = ["FAIL - spec is not valid:"]
    lines += [f"  - {e}" for e in result["errors"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lint a PRD spec issue/file.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--issue", type=int, help="GitHub issue number (via gh)")
    src.add_argument("--file", help="path to a local spec file")
    src.add_argument("--stdin", action="store_true", help="read spec from stdin")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        if args.issue is not None:
            body = _fetch_issue_body(args.issue)
        elif args.file:
            with open(args.file, encoding="utf-8") as fh:
                body = fh.read()
        else:
            body = sys.stdin.read()
    except (RuntimeError, OSError) as exc:
        print(f"spec_lint: {exc}", file=sys.stderr)
        return 2

    result = lint(body)
    if args.as_json:
        print(json.dumps(result, indent=2))
    elif result["valid"]:
        print(_render(result))
    else:
        print(_render(result), file=sys.stderr)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
spec_lint.py — validate a PRD issue body against the project's PRD template.

A "spec" passes lint when every required section is present and non-empty.
(Task 3 adds minimum-entry-count checks; Task 4 adds doc-only classification.)

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
import re

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
        doc_only       bool   (filled in by Task 4; False until then)
        errors         list[str]
        sections       dict[str, bool]   presence+non-empty per required section
        impacted_files list[str]         (filled in by Task 4; [] until then)
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

    return {
        "valid": not errors,
        "doc_only": False,
        "errors": errors,
        "sections": present,
        "impacted_files": [],
    }

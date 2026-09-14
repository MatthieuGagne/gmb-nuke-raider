#!/usr/bin/env python3
"""PreToolUse hook: run bank_check for any src/*.c or src/*.h write/edit.

Reads tool-use JSON from stdin. Exits 2 — the blocking PreToolUse exit code in
both Claude Code and the omp hook bridge — if bank_check fails. Exits 0 silently for
files outside src/, non-C/H files, parse errors, or paths that resolve outside
CLAUDE_PROJECT_DIR (or, absent it, outside the payload's repo root).

Two payload keys are accepted: ``file_path`` (Claude Code) with a ``path``
fallback, since omp's edit tool key is not pinned.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_common


def project_dir(payload_root):
    """The directory a path must resolve inside to be gated (#728 R5).

    CLAUDE_PROJECT_DIR when the harness sets it; otherwise the repo root the
    payload's cwd implies, which is what every existing test relies on."""
    declared = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if declared and os.path.isdir(declared):
        return os.path.normcase(os.path.realpath(declared))
    if payload_root:
        return os.path.normcase(os.path.realpath(payload_root))
    return None


def repo_relative(file_path, root, base):
    """The path relative to *base*, or None when it resolves outside it.

    Relative paths are anchored on *root* — the repo root the payload's cwd
    implies — never on *base*, so a declared CLAUDE_PROJECT_DIR elsewhere makes
    an in-repo relative path read as outside, which is the point.
    normcase+realpath on both sides: a case, junction or 8.3 difference must not
    silently disable the gate."""
    anchor = root or base
    candidate = file_path if os.path.isabs(file_path) else os.path.join(anchor, file_path)
    candidate = os.path.normcase(os.path.realpath(candidate))
    try:
        rel = os.path.relpath(candidate, base)
    except ValueError:                      # different drive on Windows
        return None
    rel = rel.replace('\\', '/')
    if rel == '..' or rel.startswith('../'):
        return None
    return rel


def main():
    data = hook_common.read_payload()
    if data is None:
        sys.exit(0)  # Can't parse stdin — don't block
    root = hook_common.reroot(data)

    tool_input = data.get('tool_input', {})
    # Claude Code sends file_path; omp may send path. file_path wins when
    # truthy; an empty file_path falls through to path.
    file_path = tool_input.get('file_path') or tool_input.get('path') or ''

    if not file_path:
        sys.exit(0)

    if not isinstance(file_path, str):
        sys.exit(0)  # malformed payload — fail open quietly, never traceback

    norm = file_path.replace('\\', '/')
    # Only act on .c and .h files under src/
    if not (norm.endswith('.c') or norm.endswith('.h')):
        sys.exit(0)
    if '/src/' not in norm and not norm.startswith('src/'):
        sys.exit(0)

    # Repository membership (#728 R5). The pattern test above matched on the
    # src/*.c shape alone, so a scratch fixture five directory levels outside
    # the repo was refused with a ../../../../../ path — the relativised path
    # escaping the root was the tell. Resolve, then gate only what stays inside.
    base = project_dir(root)
    if base is None:
        sys.exit(0)                         # no root to judge against — fail open
    rel = repo_relative(file_path, root, base)
    if rel is None:
        sys.exit(0)

    # Run single-file check. CWD = worktree/repo root.
    result = subprocess.run(
        [sys.executable, 'tools/bank_check.py', rel],
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)

    # bank_check exits 1 on failure, but 1 is a *non-blocking* hook error: the
    # hook bridge only aborts the tool call on exit 2, and Claude Code
    # documents the same. Exit 1 is why this gate reported but never blocked.
    sys.exit(2 if result.returncode != 0 else 0)


if __name__ == '__main__':
    main()

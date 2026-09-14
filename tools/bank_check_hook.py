#!/usr/bin/env python3
"""PreToolUse hook: run bank_check for any src/*.c or src/*.h write/edit.

Reads tool-use JSON from stdin. Exits 2 — the blocking PreToolUse exit code in
both Claude Code and the omp hook bridge — if bank_check fails. Exits 0 silently for
files outside src/, non-C/H files, parse errors, or paths that resolve outside
BOTH the payload's repo root and CLAUDE_PROJECT_DIR. Either base is enough:
under this project's worktree policy those two routinely name different trees,
and requiring the declared one alone turned the gate off for every worktree
write (#728).

Two payload keys are accepted: ``file_path`` (Claude Code) with a ``path``
fallback, since omp's edit tool key is not pinned.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_common


def gate_bases(payload_root):
    """Every directory a src path may legitimately live under (#728 R5).

    Two bases, not one. This project mandates that all work happens in an Orca
    worktree while the session is frequently rooted at the main repo, so
    CLAUDE_PROJECT_DIR and the payload's repo root routinely name different
    trees. Judging membership against CLAUDE_PROJECT_DIR *alone* made every
    worktree write resolve outside it, and the hard bank gate exited 0 in
    silence — a check that cannot run reading as a pass, which is the defect
    #728 exists to eliminate.

    The payload root comes first: it is a real repo root, so it is the base
    that actually holds tools/bank_check.py and bank-manifest.json. An ancestor
    CLAUDE_PROJECT_DIR would otherwise win and yield a manifest key prefixed
    with the worktree's own directory name."""
    bases = []
    if payload_root:
        bases.append(payload_root)
    declared = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if declared and os.path.isdir(declared):
        bases.append(declared)
    return bases


def repo_relative(file_path, root, bases):
    """Return (base, rel) for the first base containing *file_path*, else None.

    Relative paths are anchored on *root* — the repo root the payload's cwd
    implies — because that is the directory the harness reported working in.
    normcase+realpath on both sides of the containment comparison: a case,
    junction or 8.3 difference must not silently disable the gate. The returned
    *rel* is derived from the UNFOLDED resolved path, so the manifest key and
    the message a developer reads keep the spelling they typed (#728)."""
    anchor = root or (bases[0] if bases else None)
    if not anchor and not os.path.isabs(file_path):
        return None
    candidate = file_path if os.path.isabs(file_path) else os.path.join(anchor, file_path)
    candidate = os.path.realpath(candidate)
    folded = os.path.normcase(candidate)
    for base in bases:
        base_folded = os.path.normcase(os.path.realpath(base))
        try:
            probe = os.path.relpath(folded, base_folded)
        except ValueError:                  # different drive on Windows
            continue
        probe = probe.replace('\\', '/')
        if probe == '..' or probe.startswith('../'):
            continue
        # Inside. Recompute against the unfolded base so the spelling survives;
        # relpath is purely lexical here, both sides already realpath'd.
        rel = os.path.relpath(candidate, os.path.realpath(base)).replace('\\', '/')
        return base, rel
    return None


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
    # escaping every base was the tell. Resolve, then gate only what stays
    # inside one of them.
    bases = gate_bases(root)
    if not bases:
        sys.exit(0)                         # no root to judge against — fail open
    matched = repo_relative(file_path, root, bases)
    if matched is None:
        sys.exit(0)
    base, rel = matched

    # Run the single-file check IN the base that matched, with a path relative
    # to it (#728). bank_check resolves both bank-manifest.json and the source
    # against its own cwd, so cwd and rel must share one base or it looks up a
    # manifest key that cannot exist. The checker is addressed by an absolute
    # path anchored on that same base — never a bare relative path, which would
    # run whichever copy the inherited cwd happened to expose.
    checker = os.path.join(base, 'tools', 'bank_check.py')
    if not os.path.isfile(checker):
        # The matched base is not a checkout (e.g. CLAUDE_PROJECT_DIR names a
        # bare parent directory). Nothing to run against — fail open, but say
        # so: a gate that cannot run must not read as a silent pass (#781 R1).
        print('bank-check hook: skipping bank gate — no tools/bank_check.py under %s'
              % base, file=sys.stderr)
        sys.exit(0)
    result = subprocess.run(
        [sys.executable, checker, rel],
        capture_output=True,
        text=True,
        cwd=base,
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

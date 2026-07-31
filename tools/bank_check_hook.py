#!/usr/bin/env python3
"""PreToolUse hook: run bank_check for any src/*.c or src/*.h write/edit.

Reads tool-use JSON from stdin. Exits 2 — the blocking PreToolUse exit code in
both Claude Code and pi-hooks — if bank_check fails. Exits 0 silently for
files outside src/, non-C/H files, or parse errors.

Two payload shapes are accepted: Claude Code's Write/Edit send ``file_path``,
Pi's write/edit send ``path`` (#497).
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_common


def main():
    data = hook_common.read_payload()
    if data is None:
        sys.exit(0)  # Can't parse stdin — don't block
    hook_common.reroot(data)

    tool_input = data.get('tool_input', {})
    # Claude Code sends file_path; Pi sends path. Claude wins when both are
    # present so a Claude payload can never be reinterpreted.
    file_path = tool_input.get('file_path') or tool_input.get('path') or ''

    if not file_path:
        sys.exit(0)

    norm = file_path.replace('\\', '/')
    # Only act on .c and .h files under src/
    if not (norm.endswith('.c') or norm.endswith('.h')):
        sys.exit(0)
    if '/src/' not in norm and not norm.startswith('src/'):
        sys.exit(0)

    # Run single-file check. CWD = worktree/repo root.
    result = subprocess.run(
        [sys.executable, 'tools/bank_check.py', file_path],
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)

    # bank_check exits 1 on failure, but 1 is a *non-blocking* hook error in
    # both harnesses: pi-hooks only aborts the tool call on exit 2
    # (@hsingjui/pi-hooks src/hooks/tool-hooks.ts), and Claude Code documents
    # the same. Exit 1 is why this gate reported but never blocked.
    sys.exit(2 if result.returncode != 0 else 0)


if __name__ == '__main__':
    main()

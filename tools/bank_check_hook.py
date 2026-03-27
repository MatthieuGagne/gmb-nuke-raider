#!/usr/bin/env python3
"""PreToolUse hook: run bank_check for any src/*.c or src/*.h write/edit.

Reads tool-use JSON from stdin. Exits 1 (blocking) if bank_check fails.
Exits 0 silently for files outside src/, non-C/H files, or parse errors.
"""
import json
import os
import subprocess
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)  # Can't parse stdin — don't block

    tool_input = data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')

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

    sys.exit(result.returncode)


if __name__ == '__main__':
    main()

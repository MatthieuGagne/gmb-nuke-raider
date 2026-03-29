#!/usr/bin/env python3
"""PostToolUse hook: run bank-post-build + memory-check after make commands.

Reads Bash tool-use JSON from stdin. Always exits 0 (non-blocking).
Skips: make clean, make test, make bank-post-build, make memory-check.
"""
import json
import re
import subprocess
import sys


_SKIP_PATTERN = re.compile(
    r'\bmake\s+(clean|test|bank-post-build|memory-check)\b'
)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')

    if 'make' not in command:
        sys.exit(0)

    if _SKIP_PATTERN.search(command):
        sys.exit(0)

    # Run bank-post-build then memory-check; capture and surface output
    print('--- [hook] bank-post-build ---', flush=True)
    r1 = subprocess.run(
        ['make', 'bank-post-build'],
        capture_output=True, text=True
    )
    sys.stdout.write(r1.stdout)
    if r1.stderr:
        sys.stderr.write(r1.stderr)

    if r1.returncode == 0:
        print('--- [hook] memory-check ---', flush=True)
        r2 = subprocess.run(
            ['make', 'memory-check'],
            capture_output=True, text=True
        )
        sys.stdout.write(r2.stdout)
        if r2.stderr:
            sys.stderr.write(r2.stderr)
    else:
        print('[hook] bank-post-build failed — skipping memory-check', flush=True)

    sys.exit(0)  # Always non-blocking


if __name__ == '__main__':
    main()

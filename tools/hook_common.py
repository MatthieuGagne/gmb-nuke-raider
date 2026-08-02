#!/usr/bin/env python3
"""Shared helpers for Claude Code hook scripts.

Hook commands are registered with a project-root-anchored script path, so the
interpreter finds the script whatever the working directory is (#526): Claude
Code's ``.claude/settings.json`` uses its ``${CLAUDE_PROJECT_DIR}`` placeholder,
Pi's ``.pi/settings.json`` uses ``$(git rev-parse --show-toplevel)`` because
pi-hooks substitutes no placeholders and runs the command under ``bash -c``.

That anchor only locates the *script*. The *working directory* a hook inherits
is still whatever the session last used, which can be a subdirectory or a path
outside the repository, so every hook re-roots itself from the payload's
``cwd`` before doing work that assumes the repo root.
"""
import json
import os
import sys


def read_payload():
    """Return the hook JSON payload from stdin, or None if unusable."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return None


def find_repo_root(start):
    """Walk up from *start* to the nearest directory holding a .git entry.

    In a git worktree .git is a file, not a directory, so both are accepted.
    Falls back to this script's own tree when *start* is unusable.
    """
    if not start or not os.path.isdir(start):
        start = os.path.dirname(os.path.abspath(__file__))
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, '.git')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def reroot(payload):
    """chdir to the repo root implied by *payload*. Returns the root or None."""
    root = find_repo_root((payload or {}).get('cwd', ''))
    if root:
        os.chdir(root)
    return root

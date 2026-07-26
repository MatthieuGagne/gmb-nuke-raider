#!/usr/bin/env python3
"""Shared helpers for Claude Code hook scripts.

Hook commands are registered with repo-relative script paths so the script that
runs is always the current worktree's copy. The *working directory* a hook
inherits is whatever the session last used, which can be a subdirectory, so
every hook re-roots itself from the payload's ``cwd`` before doing work that
assumes the repo root.
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

#!/usr/bin/env python3
"""Fail this repository's tool suite when src/config.h holds a #define that
Garage's classification file does not classify (#612 R4).

Garage carries its own drift check, so an unclassified #define is reported
the next time Garage runs. That report arrives late: the #define enters
*this* repository through a commit here, and the commit that introduces it
is the moment its author can classify it. This check moves the report to
that moment -- tests/test_garage_drift_lint.py exercises it, discovery
gates that module, and both `make test-tools` and .githooks/pre-commit run
discovery.

The classification file lives in the Garage repository, which is NOT a
requirement of this one. When no Garage checkout is found beside this
repository, this check succeeds and says it did not run (AC5).

This module imports nothing from Garage, on purpose. Reading its schema
module would make this repository's suite break whenever a repository it
does not depend on refactors, and the comparison here is a set difference.

Usage: python tools/garage_drift_lint.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

GARAGE_REMOTE_MARKER = "nuke-raiders-garage"
TUNABLES_RELPATH = os.path.join("tools", "garage", "tunables.json")

# `#define` at the start of a line (leading whitespace allowed), then the
# name. Anchored so the word inside a comment or a string is not a match.
_DEFINE_RE = re.compile(r'^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)', re.MULTILINE)


def find_defines(text: str) -> list:
    """Every #define name in `text`, in the order the header declares them."""
    return _DEFINE_RE.findall(text)


def load_classified(tunables_path: str) -> set:
    """The set of #define names tunables.json classifies.

    Every class counts. The file's four classes -- tunable, structural,
    derived, marker -- all mean "someone decided what this is"; only a name
    the file never mentions is unclassified.
    """
    with open(tunables_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return set(data.get('entries', {}).keys())


def git_remote(path: str):
    """The `origin` URL of the checkout at `path`, or None when `path` is not
    a git checkout, has no origin, or git is unavailable.
    """
    try:
        proc = subprocess.run(
            ['git', '-C', path, 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def find_garage_checkout(repo_root: str, remote_reader=None):
    """The Garage checkout beside `repo_root`, or None when there is none.

    A sibling qualifies when it holds tools/garage/tunables.json AND its
    origin remote names the Garage repository. The remote is what confirms
    it: the checkout on the author's machine is named 'nuke-raider-garage'
    while the repository is 'nuke-raiders-garage', so a directory-name match
    would silently never fire -- and a check that never fires looks exactly
    like a check that passes.
    """
    if remote_reader is None:
        remote_reader = git_remote
    repo_root = os.path.abspath(repo_root)
    parent = os.path.dirname(repo_root)
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return None
    for name in names:
        candidate = os.path.join(parent, name)
        if os.path.abspath(candidate) == repo_root:
            continue
        if not os.path.isfile(os.path.join(candidate, TUNABLES_RELPATH)):
            continue
        remote = remote_reader(candidate)
        if remote and GARAGE_REMOTE_MARKER in remote:
            return candidate
    return None


def repository_root() -> str:
    """This repository's root, derived from this file's location:
    tools/garage_drift_lint.py -> the root is two levels up.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(repo_root: str = None, tunables_path: str = None) -> int:
    """Run the drift check. Returns a process exit code (0 = pass).

    Both arguments are override hooks for tests; a real invocation leaves
    them None and resolves this repository and the Garage checkout beside
    it normally.
    """
    if repo_root is None:
        repo_root = repository_root()

    if tunables_path is None:
        garage = find_garage_checkout(repo_root)
        if garage is None:
            print(
                "garage_drift_lint: no Garage checkout was found beside "
                f"'{repo_root}', so the config.h drift check did not run. "
                "This is not a failure -- Garage is not a requirement of "
                "this repository."
            )
            return 0
        tunables_path = os.path.join(garage, TUNABLES_RELPATH)

    config_h = os.path.join(repo_root, 'src', 'config.h')
    with open(config_h, 'r', encoding='utf-8') as f:
        defines = find_defines(f.read())

    classified = load_classified(tunables_path)

    seen = set()
    unclassified = []
    for name in defines:
        if name not in classified and name not in seen:
            seen.add(name)
            unclassified.append(name)

    if not unclassified:
        print(
            f"garage_drift_lint: OK -- all {len(defines)} #defines in "
            "src/config.h are classified in Garage's tunables.json."
        )
        return 0

    print(
        "garage_drift_lint: FAIL -- src/config.h has drifted ahead of "
        "Garage's tunables.json"
    )
    for name in unclassified:
        print(
            f"  - '{name}' is defined in src/config.h but is not classified "
            f"in {tunables_path} (add it as tunable/structural/derived/"
            "marker)."
        )
    return 1


def main() -> int:
    return run()


if __name__ == '__main__':
    sys.exit(main())

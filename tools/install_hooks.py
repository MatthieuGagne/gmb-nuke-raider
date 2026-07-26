#!/usr/bin/env python3
"""Point git at the tracked .githooks/ directory, idempotently.

Repository hooks are only a gate if they are installed by default: a gate that
requires reading a setup doc is opt-in, which is the failure mode #441 exists
to remove. `make` invokes this, so any clone that builds once is gated
(ADR 0002).

The write is local-scope and idempotent, and is undone with
`git config --unset core.hooksPath`. It lands in the *common* repository
config, so it covers the main checkout and every linked worktree at once; a
relative hooksPath is resolved against the top level of whichever working tree
git is running the hook in, and a branch without .githooks/ simply runs no hook.

Usage:
    python tools/install_hooks.py [repo_root]
"""
import os
import subprocess
import sys

HOOKS_DIR = '.githooks'

# git exports these into every hook's environment, and they override cwd — so
# a call made from inside a hook would silently act on the repository that
# invoked the hook rather than on repo_root. Scrubbing them is what makes the
# repo_root argument mean what it says (#441).
GIT_ENV_OVERRIDES = (
    'GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
    'GIT_OBJECT_DIRECTORY', 'GIT_PREFIX',
)


def clean_env(environ=None):
    """Return *environ* without the git variables that override cwd."""
    src = os.environ if environ is None else environ
    return {k: v for k, v in src.items() if k not in GIT_ENV_OVERRIDES}


def _git(args, repo_root):
    """Run git in *repo_root*, immune to an inherited hook environment."""
    return subprocess.run(['git'] + args, cwd=repo_root, env=clean_env(),
                          capture_output=True, text=True, check=False)


def current_hooks_path(repo_root='.'):
    """Return the repo's configured core.hooksPath, or None when unset."""
    result = _git(['config', '--local', '--get', 'core.hooksPath'], repo_root)
    return result.stdout.strip() or None


def needs_install(configured, wanted=HOOKS_DIR):
    """True when core.hooksPath must be written."""
    return configured != wanted


def install(repo_root='.', wanted=HOOKS_DIR):
    """Set core.hooksPath unless it is already *wanted*.

    Returns True when the config was written, False when it was already right.
    """
    if not needs_install(current_hooks_path(repo_root), wanted):
        return False
    result = _git(['config', '--local', 'core.hooksPath', wanted], repo_root)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, 'git config', result.stdout, result.stderr)
    return True


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    if not os.path.isdir(os.path.join(repo_root, HOOKS_DIR)):
        sys.stderr.write('install_hooks: %s/ is missing — repository hooks '
                         'NOT installed\n' % HOOKS_DIR)
        return 1
    if install(repo_root):
        print('install_hooks: core.hooksPath -> %s' % HOOKS_DIR)
    return 0


if __name__ == '__main__':
    sys.exit(main())

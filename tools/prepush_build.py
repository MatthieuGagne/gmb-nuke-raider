#!/usr/bin/env python3
"""Clean-build gate, run by the pre-push repository hook (#441, ADR 0002).

CLAUDE.md has always required a clean build immediately before a push; this
makes that rule enforceable instead of leaving it to discipline. It runs on the
rare action (push, ~29s) rather than the frequent one (commit, gated by the
~6s tool suite instead).

Machine-specific values arrive from the environment so this file stays free of
absolute paths (ADR 0001):

  GBDK_HOME          GBDK install root, consumed by the Makefile.
  MAKE_PATH_PREPEND  Optional. Prepended to PATH so make finds bash and the
                     coreutils it shells out to.

Exit 1 blocks the push, exit 0 allows it. When there is no make on PATH the
gate cannot run: it says so and allows the push. CI is the authority, and a
hook that blocks every push on a machine that cannot build is worse than no
hook.
"""
import os
import shutil
import subprocess
import sys

TARGETS = ('clean', '')


def build_env(environ):
    """Return the environment for the build, honouring MAKE_PATH_PREPEND."""
    env = dict(environ)
    prepend = env.get('MAKE_PATH_PREPEND')
    if prepend:
        env['PATH'] = prepend + os.pathsep + env.get('PATH', '')
    return env


def find_make(env):
    """Return the make executable visible on *env*'s PATH, or None."""
    return shutil.which('make', path=env.get('PATH'))


def run_build(env, runner=subprocess.run, cwd=None):
    """Run `make clean` then `make`. Returns (ok, message).

    *cwd* selects the tree to build; the factory's reference-ROM cache builds a
    detached `origin/master` worktree with it (#437 R5).
    """
    for target in TARGETS:
        argv = ['make'] + ([target] if target else [])
        result = runner(argv, env=env, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, '%s%s\npre-push build gate failed on "%s".\n' % (
                result.stdout[-4000:], result.stderr[-4000:], ' '.join(argv))
    return True, ''


def main():
    env = build_env(os.environ)
    if find_make(env) is None:
        sys.stderr.write('pre-push: no make on PATH — clean-build gate '
                         'skipped (CI still runs it).\n')
        return 0
    ok, message = run_build(env)
    if not ok:
        sys.stderr.write(message)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

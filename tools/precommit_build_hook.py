#!/usr/bin/env python3
"""PreToolUse hook: clean-build gate before a git commit via the Bash tool.

Machine-specific values come from the environment, supplied by the user
settings tier (~/.claude/settings.json), so this script and its registration
stay free of absolute paths:

  GBDK_HOME          GBDK install root, consumed by the Makefile.
  MAKE_PATH_PREPEND  Optional. Prepended to PATH so make finds bash and the
                     coreutils it shells out to.

Exit 2 blocks the commit — it is the only non-zero code Claude Code treats as
blocking. Exit 0 allows it.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_common

_COMMIT = re.compile(r'\bgit\b[^\n;|&]*?\bcommit\b')


def is_commit(command):
    """True when *command* is a git commit invocation."""
    return bool(command) and bool(_COMMIT.search(command))


def build_env(environ):
    """Return the environment for the build, honouring MAKE_PATH_PREPEND."""
    env = dict(environ)
    prepend = env.get('MAKE_PATH_PREPEND')
    if prepend:
        env['PATH'] = prepend + os.pathsep + env.get('PATH', '')
    return env


def main():
    data = hook_common.read_payload()
    if data is None:
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')
    if not is_commit(command):
        sys.exit(0)

    hook_common.reroot(data)
    env = build_env(os.environ)

    for target in ('clean', ''):
        argv = ['make'] + ([target] if target else [])
        result = subprocess.run(argv, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            sys.stderr.write(result.stdout[-4000:])
            sys.stderr.write(result.stderr[-4000:])
            sys.stderr.write('\nPre-commit build gate failed on "%s".\n'
                             % ' '.join(argv))
            sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()

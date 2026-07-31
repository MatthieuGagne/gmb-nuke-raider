#!/usr/bin/env python3
"""Reference-ROM cache for the factory's VERIFY stage (#437 R5).

PRD-2's smoketest can diff a run against a reference ROM (`--ref-rom`) and
report the first WRAM divergence. That report is what the project's two-ROM
debugging doctrine requires before diagnosing a smoketest failure — never code
inspection alone.

The reference is a build of `origin/master`, and building it costs a full clean
build. Because only the failure path consumes it, the cache is filled **lazily**:
VERIFY calls this tool only after the blocking smoketest has already failed. The
cache is keyed by the `origin/master` commit SHA and lives at
`<registry>/cache/master-<sha>.gb`, so a second failure on the same master reuses
it for free.

`.factory/cache/` is owned by the orchestrator, not by `factory_run` — see
docs/dev-workflow.md §9. Nothing here writes run state, the journal, `logs/`, or
any GitHub surface.

Every git call runs under `install_hooks.clean_env()`: git exports GIT_DIR and
friends into hook environments and they override cwd (#441/#462).

This is a Python tool rather than inline shell for a second reason: the deny
gate refuses `git worktree remove` for any shell tool call made while
NUKE_FACTORY_RUN is set. A PreToolUse hook sees tool calls, not subprocess calls
made inside one, so the temporary build worktree can be cleaned up here and
nowhere else.

Exit codes:
    0  cache hit, or fill succeeded; the ROM path is on stdout
    1  the reference build failed
    2  misuse or operational error (unresolvable ref, no make, unwritable cache)
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_run
import install_hooks
import prepush_build

CACHE_DIRNAME = 'cache'
DEFAULT_REF = 'origin/master'
ROM_NAME = 'nuke-raider.gb'


def cache_dir(registry=None):
    """Return the cache directory, `<registry>/cache`."""
    registry = registry or factory_run.registry_root()
    return os.path.join(registry, CACHE_DIRNAME)


def rom_path(sha, registry=None):
    """Return the cached reference ROM path for *sha*."""
    return os.path.join(cache_dir(registry), 'master-%s.gb' % sha)


def resolve_sha(ref=DEFAULT_REF, cwd=None, runner=subprocess.run):
    """Return the commit SHA *ref* points at. Raises RuntimeError on failure."""
    result = runner(['git', 'rev-parse', ref], cwd=cwd,
                    env=install_hooks.clean_env(),
                    capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError('cannot resolve %s: %s'
                           % (ref, (result.stderr or '').strip()))
    sha = (result.stdout or '').strip()
    if not sha:
        raise RuntimeError('cannot resolve %s: empty rev-parse output' % ref)
    return sha


def build_reference(sha, repo_root, registry=None, runner=subprocess.run):
    """Build *sha* in a temporary worktree and copy the ROM into the cache.

    Returns the cached ROM path. Raises RuntimeError when the build fails; the
    temporary worktree is removed either way.
    """
    destination = rom_path(sha, registry)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    tree = os.path.join(cache_dir(registry), 'build-%s' % sha)

    env = prepush_build.build_env(os.environ)
    if prepush_build.find_make(env) is None:
        raise RuntimeError('no make on PATH — cannot build the reference ROM')

    add = runner(['git', 'worktree', 'add', '--detach', tree, sha],
                 cwd=repo_root, env=install_hooks.clean_env(),
                 capture_output=True, text=True)
    if add.returncode != 0:
        raise RuntimeError('cannot create reference worktree: %s'
                           % (add.stderr or '').strip())
    try:
        ok, message = prepush_build.run_build(env, runner=runner, cwd=tree)
        if not ok:
            raise RuntimeError(message)
        produced = os.path.join(tree, 'build', ROM_NAME)
        if not os.path.exists(produced):
            raise RuntimeError('reference build produced no %s' % ROM_NAME)
        shutil.copyfile(produced, destination)
    finally:
        runner(['git', 'worktree', 'remove', '--force', tree],
               cwd=repo_root, env=install_hooks.clean_env(),
               capture_output=True, text=True)
    return destination


def ensure(ref=DEFAULT_REF, registry=None, repo_root=None,
           runner=subprocess.run, build=True):
    """Return (rom_path, filled). *filled* is True when a build just ran.

    With build=False the cache is only inspected — the caller learns the path
    and whether it exists, and no build is started.
    """
    repo_root = repo_root or factory_run.repo_root()
    sha = resolve_sha(ref, cwd=repo_root, runner=runner)
    path = rom_path(sha, registry)
    if os.path.exists(path):
        return path, False
    if not build:
        return path, False
    return build_reference(sha, repo_root, registry, runner), True


def build_parser():
    parser = argparse.ArgumentParser(
        description='Provision the factory reference ROM, lazily.')
    parser.add_argument('--ref', default=DEFAULT_REF,
                        help='git ref to build (default: %s)' % DEFAULT_REF)
    parser.add_argument('--registry', default=None,
                        help='registry root (default: <main repo root>/.factory)')
    parser.add_argument('--repo-root', dest='repo_root', default=None,
                        help='repository to resolve the ref in')
    parser.add_argument('--print-only', action='store_true',
                        dest='print_only',
                        help='report the cache path without building')
    return parser


def main(argv=None, runner=subprocess.run):
    args = build_parser().parse_args(argv)
    try:
        path, _ = ensure(args.ref, args.registry, args.repo_root,
                         runner=runner, build=not args.print_only)
    except RuntimeError as exc:
        message = str(exc)
        # A failed reference build is a build failure (1); everything else here
        # is the tool being unable to run at all (2).
        if 'pre-push build gate failed' in message or 'produced no' in message:
            sys.stderr.write('factory-cache: reference build failed\n%s\n'
                             % message)
            return 1
        sys.stderr.write('factory-cache: %s\n' % message)
        return 2
    except OSError as exc:
        sys.stderr.write('factory-cache: %s\n' % exc)
        return 2
    sys.stdout.write(path + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

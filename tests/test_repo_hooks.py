#!/usr/bin/env python3
"""Tests for the tracked repository hooks in .githooks/.

The pre-commit hook deliberately bypasses `make` (Makefile pins SHELL := bash
and needs GBDK_HOME; a commit from a bare cmd.exe would die on
"make: bash: command not found" for a reason unrelated to the tests). Bypassing
make is also exactly what lets the hook and the Makefile drift, so the
agreement is asserted here.
"""
import ast
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import install_hooks

ROOT = os.path.join(os.path.dirname(__file__), '..')
HOOKS_DIR = os.path.join(ROOT, '.githooks')
MAKEFILE = os.path.join(ROOT, 'Makefile')
PRE_COMMIT = os.path.join(HOOKS_DIR, 'pre-commit')
PRE_PUSH = os.path.join(HOOKS_DIR, 'pre-push')
SETTINGS = os.path.join(ROOT, '.claude', 'settings.json')

DISCOVERY = "-m unittest discover -s tests -p 'test_*.py'"


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


class DiscoveryAgreementTests(unittest.TestCase):
    def test_makefile_recipe_uses_the_discovery_command(self):
        self.assertIn(DISCOVERY, read(MAKEFILE))

    def test_pre_commit_uses_the_same_discovery_command(self):
        self.assertIn(DISCOVERY, read(PRE_COMMIT))

    def test_makefile_names_no_test_module(self):
        # The hardcoded list is what let two modules go ungated for months.
        self.assertNotRegex(read(MAKEFILE), r'tests\.test_\w+')

    def test_pre_commit_does_not_shell_out_to_make(self):
        self.assertNotRegex(read(PRE_COMMIT), r'(?m)^\s*make\b')


class HookScriptTests(unittest.TestCase):
    def test_pre_commit_has_a_posix_shebang(self):
        self.assertTrue(read(PRE_COMMIT).startswith('#!/bin/sh'))

    def test_pre_commit_blocks_with_a_nonzero_exit(self):
        self.assertRegex(read(PRE_COMMIT), r'exit 1')


class MakefileWiringTests(unittest.TestCase):
    """R6: a gate that needs a setup step is opt-in."""

    def test_hooks_target_exists(self):
        self.assertRegex(read(MAKEFILE), r'(?m)^hooks:')

    def test_hooks_target_runs_the_installer(self):
        self.assertIn('python tools/install_hooks.py', read(MAKEFILE))

    def test_all_depends_on_hooks(self):
        self.assertRegex(read(MAKEFILE), r'(?m)^all:.*\bhooks\b')

    def test_test_tools_depends_on_hooks(self):
        self.assertRegex(read(MAKEFILE), r'(?m)^test-tools:.*\bhooks\b')

    def test_hooks_is_phony(self):
        phony = re.search(r'(?m)^\.PHONY:(.*)$', read(MAKEFILE)).group(1)
        self.assertIn('hooks', phony.split())


class GitEnvScrubTests(unittest.TestCase):
    """git exports GIT_DIR and friends into every hook's environment, and they
    override cwd. The tool suite runs inside pre-commit and contains tests that
    shell out to git (tests/test_factory_run.py builds a scratch repo), so
    without this scrub those tests commit to the real repository using the very
    index being committed. That happened — a merge commit came out titled
    "init" with a test fixture file in it (#441)."""

    def _unset_names(self, path):
        m = re.search(r'(?ms)^unset ((?:[A-Z_ ]+\\\n\s*)*[A-Z_ ]+)$', read(path))
        return set(m.group(1).replace('\\\n', ' ').split()) if m else set()

    def test_pre_commit_scrubs_the_git_environment(self):
        self.assertIn('GIT_DIR', self._unset_names(PRE_COMMIT))

    def test_pre_push_scrubs_the_git_environment(self):
        self.assertIn('GIT_DIR', self._unset_names(PRE_PUSH))

    def test_hooks_scrub_exactly_the_documented_variables(self):
        # One definition, two consumers: drift here is how the scrub silently
        # stops covering a variable git later starts exporting.
        expected = set(install_hooks.GIT_ENV_OVERRIDES)
        self.assertEqual(self._unset_names(PRE_COMMIT), expected)
        self.assertEqual(self._unset_names(PRE_PUSH), expected)


class GitInTestsTests(unittest.TestCase):
    """Any test that shells out to git must scrub too — cwd alone is not enough
    once the suite runs inside a hook."""

    # AST, not a regex: a regex cannot span a multi-line call, and it matches
    # its own specimen strings inside this very file. Both mistakes were made
    # before this comment existed — the first version missed
    # `subprocess.run(['git', 'config', ...], cwd=d)`, which is the exact call
    # that reset this repository's core.hooksPath mid-commit.
    def _offending_calls(self, src):
        out = []
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == 'run'
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == 'subprocess' and node.args):
                continue
            argv = node.args[0]
            if isinstance(argv, ast.BinOp):      # ('git',) + args
                argv = argv.left
            first = argv
            if isinstance(argv, (ast.List, ast.Tuple)):
                first = argv.elts[0] if argv.elts else None
            if not (isinstance(first, ast.Constant) and first.value == 'git'):
                continue
            kwargs = {k.arg for k in node.keywords}
            if 'cwd' in kwargs and 'env' not in kwargs:
                out.append(node.lineno)
        return out

    def test_the_detector_catches_the_list_form(self):
        bad = "subprocess.run(['git', 'config', '--local', 'x'], cwd=d)"
        self.assertEqual(len(self._offending_calls(bad)), 1)

    def test_the_detector_catches_the_tuple_form(self):
        bad = "subprocess.run(('git',) + args, cwd=self.main, check=True)"
        self.assertEqual(len(self._offending_calls(bad)), 1)

    def test_the_detector_spans_a_multiline_call(self):
        bad = ("subprocess.run(['git', 'init', '-q', d],\n"
               "               check=True,\n"
               "               cwd=d)")
        self.assertEqual(len(self._offending_calls(bad)), 1)

    def test_the_detector_accepts_a_scrubbed_call(self):
        good = ("subprocess.run(['git', 'init', d], cwd=d, "
                "env=install_hooks.clean_env())")
        self.assertEqual(self._offending_calls(good), [])

    def test_the_detector_ignores_non_git_calls(self):
        self.assertEqual(
            self._offending_calls("subprocess.run(['make'], cwd=d)"), [])

    def test_no_test_runs_git_with_cwd_but_no_env(self):
        offenders = []
        tests_dir = os.path.dirname(__file__)
        for name in sorted(os.listdir(tests_dir)):
            if not (name.startswith('test_') and name.endswith('.py')):
                continue
            if self._offending_calls(read(os.path.join(tests_dir, name))):
                offenders.append(name)
        self.assertEqual(offenders, [],
                         'git subprocess with cwd= but no env= — see '
                         'install_hooks.clean_env')


class PrePushTests(unittest.TestCase):
    def test_pre_push_has_a_posix_shebang(self):
        self.assertTrue(read(PRE_PUSH).startswith('#!/bin/sh'))

    def test_pre_push_runs_the_build_gate(self):
        self.assertIn('tools/prepush_build.py', read(PRE_PUSH))


class AgentHookMigrationTests(unittest.TestCase):
    """R5: the clean build now gates the action it is actually about. The old
    agent hook must be gone, not merely superseded — a registration pointing at
    a deleted script fails on every tool call."""

    def test_settings_no_longer_register_the_precommit_build_hook(self):
        self.assertNotIn('precommit_build_hook', read(SETTINGS))

    def test_settings_json_is_valid(self):
        json.loads(read(SETTINGS))


if __name__ == '__main__':
    unittest.main()

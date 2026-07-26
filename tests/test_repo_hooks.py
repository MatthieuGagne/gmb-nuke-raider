#!/usr/bin/env python3
"""Tests for the tracked repository hooks in .githooks/.

The pre-commit hook deliberately bypasses `make` (Makefile pins SHELL := bash
and needs GBDK_HOME; a commit from a bare cmd.exe would die on
"make: bash: command not found" for a reason unrelated to the tests). Bypassing
make is also exactly what lets the hook and the Makefile drift, so the
agreement is asserted here.
"""
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')
HOOKS_DIR = os.path.join(ROOT, '.githooks')
MAKEFILE = os.path.join(ROOT, 'Makefile')
PRE_COMMIT = os.path.join(HOOKS_DIR, 'pre-commit')

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


if __name__ == '__main__':
    unittest.main()

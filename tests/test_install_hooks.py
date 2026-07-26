#!/usr/bin/env python3
"""Tests for tools/install_hooks.py."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import install_hooks


class NeedsInstallTests(unittest.TestCase):
    def test_unset_needs_install(self):
        self.assertTrue(install_hooks.needs_install(None))

    def test_correct_value_needs_nothing(self):
        self.assertFalse(install_hooks.needs_install('.githooks'))

    def test_other_value_needs_install(self):
        self.assertTrue(install_hooks.needs_install('.git/hooks'))


class InstallTests(unittest.TestCase):
    """A gate that requires reading a setup doc is opt-in, which is the
    failure mode #441 exists to remove — so `make` runs this, and it must be
    safe to run on every single build."""

    def _repo(self, d):
        subprocess.run(['git', 'init', '-q', d], check=True)
        os.makedirs(os.path.join(d, '.githooks'), exist_ok=True)
        return d

    def test_first_run_writes_the_config(self):
        with tempfile.TemporaryDirectory() as d:
            self._repo(d)
            self.assertTrue(install_hooks.install(d))
            self.assertEqual(install_hooks.current_hooks_path(d), '.githooks')

    def test_second_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self._repo(d)
            install_hooks.install(d)
            self.assertFalse(install_hooks.install(d))

    def test_wrong_existing_value_is_corrected(self):
        with tempfile.TemporaryDirectory() as d:
            self._repo(d)
            subprocess.run(['git', 'config', '--local', 'core.hooksPath',
                            '.git/hooks'], cwd=d, check=True)
            self.assertTrue(install_hooks.install(d))
            self.assertEqual(install_hooks.current_hooks_path(d), '.githooks')

    def test_unset_repo_reports_none(self):
        with tempfile.TemporaryDirectory() as d:
            self._repo(d)
            self.assertIsNone(install_hooks.current_hooks_path(d))

    def test_main_refuses_when_the_hooks_directory_is_missing(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['git', 'init', '-q', d], check=True)
            argv = [sys.executable,
                    os.path.join(os.path.dirname(__file__), '..', 'tools',
                                 'install_hooks.py'), d]
            p = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            self.assertIn('.githooks', p.stderr)


if __name__ == '__main__':
    unittest.main()

"""Tests for tools/precommit_build_hook.py"""
import json
import os
import subprocess
import sys
import unittest

from tools.precommit_build_hook import build_env, is_commit

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'precommit_build_hook.py')


class TriggerTests(unittest.TestCase):
    def test_detects_plain_commit(self):
        self.assertTrue(is_commit('git commit -m "x"'))

    def test_detects_commit_with_flags(self):
        self.assertTrue(is_commit('git -C . commit --amend'))

    def test_ignores_other_git_commands(self):
        self.assertFalse(is_commit('git status'))

    def test_ignores_commit_as_a_word_elsewhere(self):
        self.assertFalse(is_commit('echo "commit this later"'))

    def test_ignores_empty(self):
        self.assertFalse(is_commit(''))


class BuildEnvTests(unittest.TestCase):
    def test_prepends_make_path(self):
        env = build_env({'PATH': '/usr/bin', 'MAKE_PATH_PREPEND': '/git/bin'})
        self.assertTrue(env['PATH'].startswith('/git/bin'))
        self.assertIn('/usr/bin', env['PATH'])

    def test_leaves_path_alone_when_unset(self):
        env = build_env({'PATH': '/usr/bin'})
        self.assertEqual(env['PATH'], '/usr/bin')

    def test_passes_gbdk_home_through(self):
        env = build_env({'PATH': '/usr/bin', 'GBDK_HOME': 'C:/gbdk'})
        self.assertEqual(env['GBDK_HOME'], 'C:/gbdk')


class NonTriggerExitTests(unittest.TestCase):
    def _run(self, command):
        payload = json.dumps({'cwd': os.getcwd(), 'tool_name': 'Bash',
                              'tool_input': {'command': command}})
        return subprocess.run([sys.executable, SCRIPT], input=payload,
                              capture_output=True, text=True).returncode

    def test_non_commit_exits_zero_without_building(self):
        self.assertEqual(self._run('git status'), 0)

    def test_garbage_stdin_exits_zero(self):
        p = subprocess.run([sys.executable, SCRIPT], input='not json',
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


if __name__ == '__main__':
    unittest.main()

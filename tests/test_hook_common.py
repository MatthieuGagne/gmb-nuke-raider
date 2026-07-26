"""Tests for tools/hook_common.py"""
import json
import io
import os
import sys
import tempfile
import unittest

from tools.hook_common import find_repo_root, read_payload, reroot


class FindRepoRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.deep = os.path.join(self.tmp, 'a', 'b', 'c')
        os.makedirs(self.deep)

    def test_finds_root_with_git_directory(self):
        os.makedirs(os.path.join(self.tmp, '.git'))
        self.assertEqual(
            os.path.realpath(find_repo_root(self.deep)),
            os.path.realpath(self.tmp))

    def test_finds_root_with_git_file(self):
        # A git worktree has .git as a FILE, not a directory.
        with open(os.path.join(self.tmp, '.git'), 'w') as fh:
            fh.write('gitdir: /somewhere/else\n')
        self.assertEqual(
            os.path.realpath(find_repo_root(self.deep)),
            os.path.realpath(self.tmp))

    def test_returns_nearest_root_not_outermost(self):
        os.makedirs(os.path.join(self.tmp, '.git'))
        inner = os.path.join(self.tmp, 'a', 'b')
        with open(os.path.join(inner, '.git'), 'w') as fh:
            fh.write('gitdir: /elsewhere\n')
        self.assertEqual(
            os.path.realpath(find_repo_root(self.deep)),
            os.path.realpath(inner))

    def test_falls_back_when_start_is_not_a_directory(self):
        # Empty cwd must not crash; it falls back to the script's own tree,
        # which is this repository and therefore has a .git.
        self.assertIsNotNone(find_repo_root(''))


class RerootTests(unittest.TestCase):
    def setUp(self):
        self.origin = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, '.git'))
        self.deep = os.path.join(self.tmp, 'x', 'y')
        os.makedirs(self.deep)

    def tearDown(self):
        os.chdir(self.origin)

    def test_chdirs_to_repo_root(self):
        reroot({'cwd': self.deep})
        self.assertEqual(os.path.realpath(os.getcwd()),
                         os.path.realpath(self.tmp))

    def test_handles_none_payload(self):
        self.assertIsNotNone(reroot(None))


class ReadPayloadTests(unittest.TestCase):
    def setUp(self):
        self.stdin = sys.stdin

    def tearDown(self):
        sys.stdin = self.stdin

    def test_reads_valid_json(self):
        sys.stdin = io.StringIO('{"cwd": "/tmp"}')
        self.assertEqual(read_payload(), {'cwd': '/tmp'})

    def test_returns_none_on_garbage(self):
        sys.stdin = io.StringIO('not json')
        self.assertIsNone(read_payload())

    def test_returns_none_on_empty(self):
        sys.stdin = io.StringIO('')
        self.assertIsNone(read_payload())


class ExistingHooksUseRerootTests(unittest.TestCase):
    """Both pre-existing hooks must re-root rather than trust inherited cwd."""

    def _source(self, name):
        path = os.path.join(os.path.dirname(__file__), '..', 'tools', name)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_bank_check_hook_reroots(self):
        src = self._source('bank_check_hook.py')
        self.assertIn('hook_common', src)
        self.assertIn('reroot(', src)

    def test_post_build_hook_reroots(self):
        src = self._source('post_build_hook.py')
        self.assertIn('hook_common', src)
        self.assertIn('reroot(', src)


if __name__ == '__main__':
    unittest.main()

"""Tests for tools/factory_cache.py — the reference-ROM cache (#437 R5)."""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import factory_cache

SHA = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'


class FakeRunner:
    """Records argv lists and replays canned CompletedProcess results."""

    def __init__(self, results=None):
        self.calls = []
        self.results = results or {}

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        key = ' '.join(argv[:3])
        code, out = self.results.get(key, (0, ''))
        return subprocess.CompletedProcess(argv, code, stdout=out, stderr='')


class PathTest(unittest.TestCase):
    def test_rom_path_is_keyed_by_sha(self):
        path = factory_cache.rom_path(SHA, registry='/reg')
        self.assertEqual(os.path.basename(path), 'master-%s.gb' % SHA)
        self.assertEqual(os.path.basename(os.path.dirname(path)), 'cache')

    def test_cache_dir_sits_under_the_registry(self):
        self.assertEqual(
            os.path.normpath(factory_cache.cache_dir(registry='/reg')),
            os.path.normpath('/reg/cache'))


class ResolveShaTest(unittest.TestCase):
    def test_returns_the_stripped_sha(self):
        runner = FakeRunner({'git rev-parse origin/master': (0, SHA + '\n')})
        self.assertEqual(factory_cache.resolve_sha(cwd='.', runner=runner), SHA)

    def test_scrubs_git_dir_from_the_environment(self):
        runner = FakeRunner({'git rev-parse origin/master': (0, SHA + '\n')})
        factory_cache.resolve_sha(cwd='.', runner=runner)
        env = runner.calls[0][1]['env']
        self.assertNotIn('GIT_DIR', env)
        self.assertNotIn('GIT_WORK_TREE', env)

    def test_nonzero_exit_raises(self):
        runner = FakeRunner({'git rev-parse origin/master': (128, '')})
        with self.assertRaises(RuntimeError):
            factory_cache.resolve_sha(cwd='.', runner=runner)


class EnsureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def _seed_cache(self):
        os.makedirs(factory_cache.cache_dir(self.registry), exist_ok=True)
        path = factory_cache.rom_path(SHA, self.registry)
        with open(path, 'wb') as fh:
            fh.write(b'ROM')
        return path

    def test_cache_hit_never_builds(self):
        expected = self._seed_cache()
        runner = FakeRunner({'git rev-parse origin/master': (0, SHA)})
        path, filled = factory_cache.ensure(registry=self.registry,
                                            repo_root='.', runner=runner)
        self.assertEqual(path, expected)
        self.assertFalse(filled)
        self.assertEqual(len(runner.calls), 1)  # only rev-parse

    def test_print_only_reports_a_miss_without_building(self):
        runner = FakeRunner({'git rev-parse origin/master': (0, SHA)})
        path, filled = factory_cache.ensure(registry=self.registry,
                                            repo_root='.', runner=runner,
                                            build=False)
        self.assertFalse(os.path.exists(path))
        self.assertFalse(filled)
        self.assertEqual(len(runner.calls), 1)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_print_only_on_a_hit_prints_the_path(self):
        os.makedirs(factory_cache.cache_dir(self.registry), exist_ok=True)
        with open(factory_cache.rom_path(SHA, self.registry), 'wb') as fh:
            fh.write(b'ROM')
        runner = FakeRunner({'git rev-parse origin/master': (0, SHA)})
        out = io.StringIO()
        with redirect_stdout(out):
            code = factory_cache.main(['--registry', self.registry,
                                       '--repo-root', '.', '--print-only'],
                                      runner=runner)
        self.assertEqual(code, 0)
        self.assertIn('master-%s.gb' % SHA, out.getvalue())

    def test_unresolvable_ref_is_misuse(self):
        runner = FakeRunner({'git rev-parse origin/nope': (128, '')})
        with redirect_stderr(io.StringIO()):
            code = factory_cache.main(['--registry', self.registry,
                                       '--repo-root', '.',
                                       '--ref', 'origin/nope', '--print-only'],
                                      runner=runner)
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()

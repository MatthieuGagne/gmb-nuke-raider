"""Tests for tools/prepush_build.py — the pre-push clean-build gate."""
import os
import subprocess
import tempfile
import unittest

from tools.prepush_build import build_env, find_make, run_build


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


class FindMakeTests(unittest.TestCase):
    def _make_name(self):
        return 'make.exe' if os.name == 'nt' else 'make'

    def test_finds_make_on_the_supplied_path(self):
        with tempfile.TemporaryDirectory() as d:
            exe = os.path.join(d, self._make_name())
            open(exe, 'w').close()
            os.chmod(exe, 0o755)
            # normcase: on Windows shutil.which returns the extension with
            # PATHEXT's casing ("make.EXE"), not the file's own.
            self.assertEqual(os.path.normcase(find_make({'PATH': d})),
                             os.path.normcase(exe))

    def test_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(find_make({'PATH': d}))


class RunBuildTests(unittest.TestCase):
    def _runner(self, codes):
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, codes.pop(0),
                                               stdout='out', stderr='err')
        return runner, calls

    def test_runs_clean_then_build(self):
        runner, calls = self._runner([0, 0])
        ok, message = run_build({}, runner=runner)
        self.assertTrue(ok)
        self.assertEqual(calls, [['make', 'clean'], ['make']])
        self.assertEqual(message, '')

    def test_stops_and_reports_on_the_first_failure(self):
        runner, calls = self._runner([1])
        ok, message = run_build({}, runner=runner)
        self.assertFalse(ok)
        self.assertEqual(calls, [['make', 'clean']])
        self.assertIn('make clean', message)

    def test_reports_the_build_failure_output(self):
        runner, _ = self._runner([0, 1])
        ok, message = run_build({}, runner=runner)
        self.assertFalse(ok)
        self.assertIn('out', message)
        self.assertIn('err', message)


if __name__ == '__main__':
    unittest.main()

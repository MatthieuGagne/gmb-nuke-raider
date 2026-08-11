"""Tests for tools/smoketest_headless.py (#588 R13-R15, AC8, AC9).

No ROM and no PyBoy: every test here exercises the parts that decide an exit
code, an output path or a result file.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import smoketest_headless as sh


class TestExitCodes(unittest.TestCase):
    def test_the_four_codes_are_distinct(self):
        codes = (sh.EXIT_PASS, sh.EXIT_FAIL, sh.EXIT_USAGE,
                 sh.EXIT_SCENARIO_INVALID)
        self.assertEqual(codes, (0, 1, 2, 3))

    def test_invalid_scenario_beats_pass(self):
        self.assertEqual(sh.resolve_exit_code([{'verdict': 'pass'},
                                               {'verdict': 'scenario-invalid'}]),
                         sh.EXIT_SCENARIO_INVALID)

    def test_invalid_scenario_wins_when_it_is_the_only_problem(self):
        self.assertEqual(
            sh.resolve_exit_code([{'verdict': 'scenario-invalid',
                                   'blocking': False}]),
            sh.EXIT_SCENARIO_INVALID)

    def test_a_blocking_game_failure_outranks_an_invalid_scenario(self):
        self.assertEqual(
            sh.resolve_exit_code([{'verdict': 'scenario-invalid', 'blocking': True},
                                  {'verdict': 'fail', 'blocking': True}]),
            sh.EXIT_FAIL)

    def test_a_non_blocking_game_failure_still_passes(self):
        self.assertEqual(
            sh.resolve_exit_code([{'verdict': 'fail', 'blocking': False}]),
            sh.EXIT_PASS)

    def test_all_passing_is_zero(self):
        self.assertEqual(
            sh.resolve_exit_code([{'verdict': 'pass', 'blocking': True}]),
            sh.EXIT_PASS)


class TestOutputLocation(unittest.TestCase):
    def test_the_default_is_under_the_main_tree_and_names_this_checkout(self):
        """AC9 + decision 11.

        Asserted unconditionally: the default must sit under the tree that
        `git rev-parse --git-common-dir` names, and its last element must be
        this checkout's directory name. In the main tree those two are the same
        directory, so the check still holds there — it is not weaker off a
        worktree, it is the same statement.
        """
        import factory_run
        here = os.path.dirname(os.path.dirname(os.path.abspath(sh.__file__)))
        default = os.path.abspath(sh.default_out_dir())
        expected = os.path.abspath(os.path.join(
            factory_run.repo_root(here), 'build', 'smoketest',
            os.path.basename(os.path.normpath(here))))
        self.assertEqual(default, expected)

    def test_the_default_leaves_a_worktree_when_run_from_one(self):
        """The half that only bites off a worktree, stated separately so the
        assertion above is never silently weakened on master."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(sh.__file__)))
        marker = os.sep + os.path.join('.claude', 'worktrees') + os.sep
        if marker not in here + os.sep:
            raise unittest.SkipTest('not running from a linked worktree')
        self.assertFalse(
            os.path.abspath(sh.default_out_dir()).startswith(
                os.path.abspath(here) + os.sep),
            'the default output directory is inside the worktree')

    def test_an_explicit_out_dir_wins(self):
        args = sh.build_parser().parse_args(['--out-dir', 'X'])
        self.assertEqual(args.out_dir, 'X')

    def test_a_relative_screenshot_path_is_rebased(self):
        steps = [{'action': 'screenshot', 'out': 'build/smoketest/x/shot.png'},
                 {'action': 'advance', 'frames': 1}]
        sh.rebase_screenshots(steps, os.path.join('OUT', 'x'))
        self.assertEqual(steps[0]['out'], os.path.join('OUT', 'x', 'shot.png'))
        self.assertEqual(steps[1], {'action': 'advance', 'frames': 1})

    def test_an_absolute_screenshot_path_is_left_alone(self):
        absolute = os.path.abspath(os.path.join('somewhere', 'shot.png'))
        steps = [{'action': 'screenshot', 'out': absolute}]
        sh.rebase_screenshots(steps, os.path.join('OUT', 'x'))
        self.assertEqual(steps[0]['out'], absolute)


class TestCombinedResults(unittest.TestCase):
    def test_write_combined_results_holds_every_scenario(self):
        results = [{'scenario': 'a', 'verdict': 'pass'},
                   {'scenario': 'b', 'verdict': 'fail'}]
        with tempfile.TemporaryDirectory() as d:
            path = sh.write_combined_results(results, d)
            with open(path) as f:
                payload = json.load(f)
        self.assertEqual(payload['verdicts'], {'a': 'pass', 'b': 'fail'})
        self.assertEqual(len(payload['scenarios']), 2)


class TestDocstring(unittest.TestCase):
    def test_the_docstring_lists_exit_code_three(self):
        """AC10: the documented codes and the real codes must agree."""
        self.assertIn('3 = scenario invalid', sh.__doc__)


class TestScenarioLibrary(unittest.TestCase):
    def test_no_library_scenario_hardcodes_a_build_path(self):
        """AC9: a hardcoded build/ path would write inside the worktree."""
        library = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'tools', 'scenarios')
        for name in sorted(os.listdir(library)):
            if not name.endswith('.json'):
                continue
            with open(os.path.join(library, name)) as f:
                text = f.read()
            self.assertNotIn('build/smoketest', text, name)


class _ZeroMemory(dict):
    """PyBoy's memory view reads as zero everywhere the test does not set it."""

    def __missing__(self, key):
        return 0


class _FakeScreen:
    def __init__(self, emu):
        self._emu = emu

    @property
    def image(self):
        return self._emu          # FakeEmu implements tobytes()/save()


class FakeEmu:
    """Enough of the PyBoy surface for run_one(). No emulation, no ROM."""

    def __init__(self, rom=None, **kwargs):
        self.memory = _ZeroMemory()
        self.screen = _FakeScreen(self)
        self.frames = 0

    def tick(self, n=1, render=False):
        self.frames += int(n)

    def button(self, name, delay=1):
        pass

    def stop(self):
        pass

    # --- screen.image surface -------------------------------------------
    def tobytes(self):
        # Changes every frame, so the freeze watchdog never fires.
        return bytes([self.frames % 251])

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.tobytes())


BAD = {'name': 'a-bad', 'steps': [
    {'action': 'assert_memory', 'address': '_nope', 'value': 0}]}
GOOD = {'name': 'b-good', 'blocking': True, 'steps': [
    {'action': 'advance', 'frames': 2}]}


class ScenarioErrorDuringRun(unittest.TestCase):
    """#507: an unresolvable symbol must not kill the whole run."""

    def setUp(self):
        module = types.ModuleType('pyboy')
        module.PyBoy = FakeEmu
        saved = sys.modules.get('pyboy')
        sys.modules['pyboy'] = module
        self.addCleanup(lambda: sys.modules.__setitem__('pyboy', saved)
                        if saved is not None else sys.modules.pop('pyboy', None))
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.library = os.path.join(self.dir, 'scenarios')
        os.makedirs(self.library)
        self.out = os.path.join(self.dir, 'out')
        self.rom = os.path.join(self.dir, 'rom.gb')
        with open(self.rom, 'wb') as f:
            f.write(b'\x00')
        self.manifest = os.path.join(self.dir, 'game-manifest.json')
        with open(self.manifest, 'w') as f:
            json.dump({'symbols': {'_hp': '0xC000'}}, f)

    # --- helpers ---------------------------------------------------------
    def write_scenario(self, stem, payload):
        path = os.path.join(self.library, stem + '.json')
        with open(path, 'w') as f:
            if isinstance(payload, str):
                f.write(payload)
            else:
                json.dump(payload, f)
        return path

    def run_main(self, *extra):
        argv = ['smoketest_headless.py', '--rom', self.rom,
                '--manifest', self.manifest, '--library', self.library,
                '--out-dir', self.out, '--freeze-frames', '0',
                '--noi', os.path.join(self.dir, 'absent.noi'),
                '--map', os.path.join(self.dir, 'absent.map')] + list(extra)
        with mock.patch.object(sys, 'argv', argv), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return sh.main()

    def read_result(self, name):
        with open(os.path.join(self.out, name, 'results.json')) as f:
            return json.load(f)

    # --- AC1 -------------------------------------------------------------
    def test_a_non_blocking_scenario_error_keeps_the_exit_code_at_zero(self):
        self.write_scenario('a-bad', dict(BAD, blocking=False))
        self.write_scenario('b-good', GOOD)
        self.assertEqual(self.run_main('--all'), sh.EXIT_PASS)

    def test_the_scenarios_after_the_failing_one_still_run(self):
        self.write_scenario('a-bad', dict(BAD, blocking=False))
        self.write_scenario('b-good', GOOD)
        self.run_main('--all')
        self.assertEqual(self.read_result('a-bad')['verdict'], 'fail')
        self.assertEqual(self.read_result('b-good')['verdict'], 'pass')

    # --- AC2 -------------------------------------------------------------
    def test_a_blocking_scenario_error_exits_one(self):
        self.write_scenario('a-bad', dict(BAD, blocking=True))
        self.assertEqual(self.run_main('--scenario', 'a-bad'), sh.EXIT_FAIL)

    # --- AC3 -------------------------------------------------------------
    def test_the_failure_block_names_the_unresolved_symbol(self):
        for blocking in (False, True):
            with self.subTest(blocking=blocking):
                self.write_scenario('a-bad', dict(BAD, blocking=blocking))
                self.run_main('--scenario', 'a-bad')
                failure = self.read_result('a-bad')['failure']
                self.assertIsNotNone(failure)
                self.assertIn('_nope', failure['message'])
                self.assertEqual(failure['kind'], 'scenario')
                self.assertEqual(failure['action'], 'assert_memory')
                self.assertEqual(failure['step'], 0)

    # --- AC4 -------------------------------------------------------------
    def test_a_malformed_scenario_file_still_exits_two(self):
        self.write_scenario('c-broken', {'name': 'c-broken'})   # no 'steps'
        self.assertEqual(self.run_main('--scenario', 'c-broken'), sh.EXIT_USAGE)

    def test_unreadable_json_still_exits_two(self):
        self.write_scenario('d-broken', '{ this is not json')
        self.assertEqual(self.run_main('--scenario', 'd-broken'), sh.EXIT_USAGE)

    # --- R5: StepFailure is unchanged ------------------------------------
    def test_an_assertion_failure_is_still_reported_as_an_assert(self):
        self.write_scenario('e-assert', {
            'name': 'e-assert', 'blocking': True, 'steps': [
                {'action': 'assert_memory', 'address': '_hp', 'value': 99}]})
        self.assertEqual(self.run_main('--scenario', 'e-assert'), sh.EXIT_FAIL)
        self.assertEqual(self.read_result('e-assert')['failure']['kind'], 'assert')

    # --- R5: the differential path keeps the verdict it has today --------
    def test_a_scenario_error_on_both_roms_stays_scenario_invalid(self):
        """Global Constraints: the --ref-rom promotion is not bypassed.

        Both runs fail the same way, so main() promotes the verdict and the
        process exits 3. This test exists so that a later change to the
        promotion is a test failure, not a silent behaviour change.
        """
        self.write_scenario('a-bad', dict(BAD, blocking=True))
        ref = os.path.join(self.dir, 'ref.gb')
        with open(ref, 'wb') as f:
            f.write(b'\x00')
        code = self.run_main('--scenario', 'a-bad', '--ref-rom', ref)
        self.assertEqual(code, sh.EXIT_SCENARIO_INVALID)
        self.assertEqual(self.read_result('a-bad')['verdict'], 'scenario-invalid')


if __name__ == '__main__':
    unittest.main()

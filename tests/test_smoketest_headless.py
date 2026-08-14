"""Tests for tools/smoketest_headless.py (#588 R13-R15, AC8, AC9; #507).

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

    def test_no_library_scenario_carries_a_require_or_a_state_action(self):
        """Two reasons neither belongs in a scenario shipped in this library.

        `resolve_exit_code` computes the `scenario-invalid` verdict without
        consulting `blocking`, so a false `require` on ANY library scenario —
        blocking or not — can gate the whole `--all` run. And `assert_state`
        / `wait_state` need the debug symbol file, which nothing in the build
        pipeline produces, so a library scenario using them would reject the
        whole library at the pre-flight check.

        `include` steps are read raw here, not inlined — the raw `steps` list
        of every file in the library is still exactly what this asserts over,
        since every include target is itself one of these same files.
        """
        library = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'tools', 'scenarios')
        for name in sorted(os.listdir(library)):
            if not name.endswith('.json'):
                continue
            with open(os.path.join(library, name)) as f:
                data = json.load(f)
            steps = data['steps'] if isinstance(data, dict) else data
            for i, step in enumerate(steps):
                with self.subTest(file=name, step=i):
                    self.assertNotIn('require', step)
                    self.assertNotIn(step.get('action'),
                                     ('assert_state', 'wait_state'))

    def test_a_scenario_that_sends_a_command_declares_that_it_needs_the_debug_rom(self):
        """`--all` runs against the release ROM, and `resolve_exit_code` ignores `blocking`
        for a scenario-invalid verdict, so an undeclared mailbox scenario would gate the
        whole library run (#590)."""
        library = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'tools', 'scenarios')
        for name in sorted(os.listdir(library)):
            if not name.endswith('.json'):
                continue
            with open(os.path.join(library, name)) as f:
                data = json.load(f)
            steps = data['steps'] if isinstance(data, dict) else data
            if any(s.get('action') == 'command' for s in steps):
                with self.subTest(file=name):
                    self.assertTrue(isinstance(data, dict)
                                    and data.get('requires_debug_rom') is True,
                                    f'{name} sends a command but does not declare '
                                    f'requires_debug_rom')


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

    # --- R11 (final review Finding 2) -------------------------------------
    def test_a_scenario_kind_failure_carries_a_context_and_its_own_hint(self):
        """A mid-run ScenarioError (#507) is wrapped into a fresh StepFailure
        OUTSIDE ps.run()'s except clause, so nothing ever attached a context
        to it. R11 requires every failure record to hold one.
        """
        self.write_scenario('a-bad', dict(BAD, blocking=True))
        self.run_main('--scenario', 'a-bad')
        failure = self.read_result('a-bad')['failure']
        self.assertIsNotNone(failure['context'])
        self.assertEqual(
            failure['context']['hint'],
            "the scenario names something the build does not carry, "
            "so the scenario is wrong, not the game")

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


class FakeFailure:
    def __init__(self, kind, context=None):
        self.step, self.action, self.kind = 0, 'advance', kind
        self.message = kind
        self.context = context


class FakeCtx:
    def __init__(self):
        self.step, self.frame, self.screenshots = 0, 10, []


class TestPreconditionVerdict(unittest.TestCase):

    def test_a_precondition_failure_is_scenario_invalid_with_one_rom(self):
        self.assertEqual(sh.verdict_for(FakeFailure('precondition'), None),
                         'scenario-invalid')

    def test_a_precondition_failure_never_reads_as_a_game_failure(self):
        self.assertNotEqual(sh.verdict_for(FakeFailure('precondition'), None),
                            'fail')

    def test_an_ordinary_failure_keeps_the_default_verdict(self):
        self.assertIsNone(sh.verdict_for(FakeFailure('stale-symbol'), None))

    def test_two_failing_roms_are_still_scenario_invalid(self):
        self.assertEqual(
            sh.verdict_for(FakeFailure('stale-symbol'),
                           FakeFailure('stale-symbol')),
            'scenario-invalid')

    def test_no_failure_has_no_verdict_override(self):
        self.assertIsNone(sh.verdict_for(None, None))

    def test_the_exit_code_for_a_precondition_failure_is_three(self):
        """AC1, through the code that decides the process result."""
        verdict = sh.verdict_for(FakeFailure('precondition'), None)
        self.assertEqual(
            sh.resolve_exit_code([{'verdict': verdict, 'blocking': True}]),
            sh.EXIT_SCENARIO_INVALID)


class TestFailureContextIsSerialised(unittest.TestCase):

    def test_the_context_reaches_the_result_record(self):
        block = {'state_at_start': 'playing', 'hint': 'the game left it'}
        result = sh.build_result('x', FakeCtx(),
                                 failure=FakeFailure('stale-symbol', block))
        self.assertEqual(result['failure']['context'], block)

    def test_a_failure_without_a_context_serialises_null(self):
        result = sh.build_result('x', FakeCtx(), failure=FakeFailure('assert'))
        self.assertIsNone(result['failure']['context'])

    def test_a_passing_result_has_no_failure_block(self):
        self.assertIsNone(sh.build_result('x', FakeCtx())['failure'])


class TestDebugNoi(unittest.TestCase):

    def test_the_default_points_at_the_debug_build(self):
        args = sh.build_parser().parse_args([])
        self.assertTrue(args.debug_noi.replace('\\', '/')
                        .endswith('build/debug/nuke-raider.noi'))

    def test_it_can_be_overridden(self):
        self.assertEqual(
            sh.build_parser().parse_args(['--debug-noi', 'X.noi']).debug_noi,
            'X.noi')

    def test_a_missing_debug_file_contributes_nothing_and_raises_nothing(self):
        import pyboy_scenario as ps
        self.assertEqual(ps.load_symbols(None, None, None,
                                         debug_noi_path='absent.noi'), {})


class TestPreflightChecksAreNotBypassable(unittest.TestCase):
    """Pins the two lines the brief singled out as easy silent reverts:
    `state_names=set(state_table)` weakening to `set(state_table) or None`,
    and the `validate_state_support` loop moving after `run_one`.

    `build/probe_ac7.py` (the brief's own falsification harness) lives
    under `build/`, which is gitignored, so nothing committed noticed
    either revert. With an EMPTY state table both gates fire on an unknown
    name, so "exit code 2" alone proves nothing — these tests discriminate
    on which gate answered (its exact message) and on whether the emulator
    was ever reached, using a real subprocess and a real `pyboy` import so
    a wrongly-reached PyBoy on a garbage ROM cannot be mistaken for success
    by a permissive fake.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.rom = os.path.join(self.dir, 'rom.gb')
        with open(self.rom, 'wb') as f:
            f.write(b'\x00' * 64)                  # exists, not a real ROM
        self.manifest = os.path.join(self.dir, 'game-manifest.json')
        with open(self.manifest, 'w') as f:
            json.dump({'symbols': {}}, f)
        self.absent_noi = os.path.join(self.dir, 'absent.noi')
        self.absent_debug_noi = os.path.join(self.dir, 'absent-debug.noi')
        self.absent_map = os.path.join(self.dir, 'absent.map')
        self.script = os.path.join(os.path.dirname(__file__), '..',
                                   'tools', 'smoketest_headless.py')

    def write_scenario(self, stem, state):
        path = os.path.join(self.dir, stem + '.json')
        with open(path, 'w') as f:
            json.dump({'name': stem, 'blocking': True, 'steps': [
                {'action': 'assert_state', 'state': state}]}, f)
        return path

    def run_smoketest(self, scenario_path, noi):
        return subprocess.run(
            [sys.executable, self.script, '--scenario', scenario_path,
             '--rom', self.rom, '--manifest', self.manifest,
             '--noi', noi, '--debug-noi', self.absent_debug_noi,
             '--map', self.absent_map],
            capture_output=True, text=True, timeout=60)

    def test_an_unknown_state_name_is_named_by_the_name_check(self):
        """Test A: an empty state table must still reject 'flying' by name.

        `state_names=set(state_table)` (never `or None`) is what makes an
        empty table still say "no" to a named state, instead of silently
        skipping the name check and letting `validate_state_support`
        answer with a message that never mentions the state at all.
        """
        scenario = self.write_scenario('bad-name', 'flying')
        proc = self.run_smoketest(scenario, self.absent_noi)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn('flying', proc.stderr)
        self.assertIn('known:', proc.stderr)
        self.assertNotIn('build-debug', proc.stderr)

    def test_the_state_support_check_runs_before_the_emulator_starts(self):
        """Test B: validate_state_support gates before run_one/PyBoy.

        A hand-written .noi carries just enough to make 'playing' a known
        state (so the name check passes and cannot be the thing catching
        this), while `_sm_depth`/`_sm_slot_src` stay unresolved (--debug-noi
        and --map both absent) so state_readable is false and only
        validate_state_support can object. The ROM is a garbage file, so if
        this check ever moved after run_one, PyBoy would be constructed on
        it and this test would see a crash or a different exit code instead
        of a clean, pre-flight exit 2.
        """
        noi = os.path.join(self.dir, 'release.noi')
        with open(noi, 'w') as f:
            f.write('DEF ___bank_state_playing 0x1\n'
                    'DEF _state_playing 0x17EED\n')
        scenario = self.write_scenario('good-name', 'playing')
        proc = self.run_smoketest(scenario, noi)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn('build-debug', proc.stderr)
        self.assertNotIn('Traceback', proc.stderr)


if __name__ == '__main__':
    unittest.main()

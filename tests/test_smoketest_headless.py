"""Tests for tools/smoketest_headless.py (#588 R13-R15, AC8, AC9).

No ROM and no PyBoy: every test here exercises the parts that decide an exit
code, an output path or a result file.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

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


if __name__ == '__main__':
    unittest.main()

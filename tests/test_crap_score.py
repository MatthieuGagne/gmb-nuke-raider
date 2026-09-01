"""Tests for tools/crap_score.py"""
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import crap_score

ROOT = os.path.join(os.path.dirname(__file__), '..')


class CrapFormulaTests(unittest.TestCase):
    def test_fully_covered_function_scores_its_complexity(self):
        self.assertAlmostEqual(crap_score.crap(12, 1.0), 12.0)

    def test_uncovered_function_scores_the_standard_formula(self):
        # 12**2 * 1**3 + 12
        self.assertAlmostEqual(crap_score.crap(12, 0.0), 156.0)

    def test_half_covered_function_sits_between(self):
        # 12**2 * 0.5**3 + 12 == 18 + 12
        self.assertAlmostEqual(crap_score.crap(12, 0.5), 30.0)

    def test_simple_uncovered_function_stays_under_the_default_threshold(self):
        self.assertLess(crap_score.crap(2, 0.0), 8)


class ExemptionTests(unittest.TestCase):
    def test_main_and_the_five_untested_screens_are_declared(self):
        self.assertEqual(
            set(crap_score.EXEMPT_SCREENS),
            {
                'src/main.c',
                'src/state_game_over.c',
                'src/state_overmap.c',
                'src/state_prerace.c',
                'src/state_results.c',
                'src/state_title.c',
            },
        )

    def test_tested_state_screens_are_not_exempt(self):
        for path in ('src/state_hub.c', 'src/state_manager.c', 'src/state_playing.c'):
            self.assertNotIn(path, crap_score.EXEMPT_FILES)

    def test_every_declared_exempt_file_exists(self):
        # A rename must fail loudly here rather than silently widen the gate.
        for path in crap_score.EXEMPT_FILES:
            self.assertTrue(
                os.path.isfile(os.path.join(ROOT, path)), f'declared exempt but missing: {path}'
            )

    def test_generated_asset_data_is_exempt(self):
        for path in ('src/track_map.c', 'src/player_sprite.c', 'src/music_data.c',
                     'src/hub_data.c'):
            self.assertIn(path, crap_score.EXEMPT_GENERATED)

    def test_score_drops_exempt_files_even_when_complex(self):
        complexity = {'src/main.c': [{'name': 'main', 'line': 1, 'end_line': 90,
                                      'complexity': 40}]}
        records = crap_score.score(['src/main.c'], {}, complexity, threshold=8)
        self.assertEqual(records, [])


class ScoreTests(unittest.TestCase):
    # foo_hairy is complexity 6, not 12, and that is load-bearing: CRAP is
    # comp**2 * (1-cov)**3 + comp, so it can never fall below `comp`. A
    # complexity-12 function is over a threshold of 8 at ANY coverage, which
    # would make the "fully covered function passes" cases below unsatisfiable.
    # 6 straddles the threshold: 42 uncovered, 6 fully covered.
    def _complexity(self):
        return {
            'src/foo.c': [
                {'name': 'foo_simple', 'line': 5, 'end_line': 8, 'complexity': 1},
                {'name': 'foo_hairy', 'line': 10, 'end_line': 40, 'complexity': 6},
            ]
        }

    def test_clean_function_is_not_over_threshold(self):
        cov = {'src/foo.c': {'foo_simple': 1.0, 'foo_hairy': 1.0}}
        records = crap_score.score(['src/foo.c'], cov, self._complexity(), threshold=8)
        self.assertFalse(any(r['over'] for r in records))

    def test_complex_untested_function_is_over_threshold(self):
        cov = {'src/foo.c': {'foo_simple': 1.0, 'foo_hairy': 0.0}}
        records = crap_score.score(['src/foo.c'], cov, self._complexity(), threshold=8)
        over = [r for r in records if r['over']]
        self.assertEqual([r['function'] for r in over], ['foo_hairy'])
        self.assertEqual(over[0]['line'], 10)
        self.assertEqual(over[0]['file'], 'src/foo.c')

    def test_adding_coverage_brings_the_same_function_under_threshold(self):
        # The arithmetic half of AC4: 6**2 * (1-0.95)**3 + 6 == 6.0045, under
        # the threshold of 8, where the same function scores 42 uncovered. The
        # end-to-end half, against real gcov data, is Task 3 Step 6 — this test
        # alone does not prove AC4.
        cov = {'src/foo.c': {'foo_simple': 1.0, 'foo_hairy': 0.95}}
        records = crap_score.score(['src/foo.c'], cov, self._complexity(), threshold=8)
        self.assertFalse(any(r['over'] for r in records))

    def test_missing_coverage_entry_counts_as_zero_coverage(self):
        records = crap_score.score(['src/foo.c'], {'src/foo.c': {}}, self._complexity(),
                                   threshold=8)
        hairy = [r for r in records if r['function'] == 'foo_hairy'][0]
        self.assertEqual(hairy['coverage'], 0.0)
        self.assertTrue(hairy['over'])

    def test_records_are_sorted_worst_first(self):
        cov = {'src/foo.c': {'foo_simple': 0.0, 'foo_hairy': 0.0}}
        records = crap_score.score(['src/foo.c'], cov, self._complexity(), threshold=8)
        self.assertEqual([r['function'] for r in records], ['foo_hairy', 'foo_simple'])


class ToolDetectionTests(unittest.TestCase):
    def test_missing_lizard_names_the_install_command(self):
        saved = crap_score._find_spec
        crap_score._find_spec = lambda name: None
        try:
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score._import_lizard()
        finally:
            crap_score._find_spec = saved
        self.assertIn('lizard', str(ctx.exception))
        self.assertIn('pip install -r requirements.txt', str(ctx.exception))

    def test_missing_gcov_names_what_to_install(self):
        saved = crap_score._which
        crap_score._which = lambda name: None
        try:
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score._gcov_path()
        finally:
            crap_score._which = saved
        self.assertIn('gcov', str(ctx.exception))
        self.assertIn('make coverage', str(ctx.exception))

    def test_empty_coverage_dir_is_a_loud_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.collect_coverage(tmp)
        self.assertIn('make coverage', str(ctx.exception))


class RelPathTests(unittest.TestCase):
    """The AC2 filter. A path is in scope only when it is exactly src/<name>.c
    relative to the repo root — never because it merely contains a 'src'
    component, which tests/unity/src/unity.c and lib/hUGEDriver/src/ both do."""

    def test_repo_src_file_is_accepted(self):
        self.assertEqual(crap_score._rel_src_path('src/foo.c'), 'src/foo.c')

    def test_unity_under_a_nested_src_is_rejected(self):
        self.assertIsNone(crap_score._rel_src_path('tests/unity/src/unity.c'))

    def test_vendored_library_under_a_nested_src_is_rejected(self):
        self.assertIsNone(crap_score._rel_src_path('lib/hUGEDriver/src/hUGEDriver.c'))

    def test_mock_and_test_sources_are_rejected(self):
        self.assertIsNone(crap_score._rel_src_path('tests/mocks/gb.c'))
        self.assertIsNone(crap_score._rel_src_path('tests/test_economy.c'))

    def test_absolute_path_is_made_relative_to_the_repo_root(self):
        root = os.path.abspath(os.path.join('a', 'b'))
        self.assertEqual(
            crap_score._rel_src_path(os.path.join(root, 'src', 'foo.c'), root), 'src/foo.c'
        )


class GcovParsingTests(unittest.TestCase):
    # Shaped like real gcov output on MinGW-W64 15.1.0: one document per .gcda,
    # and "file" is the path exactly as it was passed to gcc — relative here,
    # because `make coverage` compiles with relative source paths.
    PAYLOAD = {
        'format_version': '2',
        'files': [
            {
                'file': 'src/foo.c',
                'functions': [
                    {'name': 'foo_hairy', 'start_line': 10, 'end_line': 40},
                ],
                'lines': [
                    {'line_number': 11, 'function_name': 'foo_hairy', 'count': 3},
                    {'line_number': 11, 'function_name': 'foo_hairy', 'count': 0},
                    {'line_number': 12, 'function_name': 'foo_hairy', 'count': 0},
                    {'line_number': 13, 'function_name': 'foo_hairy', 'count': 7},
                    {'line_number': 14, 'function_name': 'foo_hairy', 'count': 0},
                ],
            },
            {
                'file': 'tests/unity/src/unity.c',
                'functions': [{'name': 'UnityBegin', 'start_line': 1, 'end_line': 4}],
                'lines': [{'line_number': 2, 'function_name': 'UnityBegin', 'count': 9}],
            },
        ],
    }

    def test_line_coverage_is_per_function_and_deduped_by_line(self):
        # lines 11 and 13 covered, 12 and 14 not -> 2 of 4
        got = crap_score._coverage_from_payload(self.PAYLOAD)
        self.assertAlmostEqual(got['src/foo.c']['foo_hairy'], 0.5)

    def test_unity_and_test_sources_are_excluded(self):
        got = crap_score._coverage_from_payload(self.PAYLOAD)
        self.assertEqual(list(got), ['src/foo.c'])


if __name__ == '__main__':
    unittest.main()

"""Tests for tools/crap_score.py"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import crap_score
import install_hooks

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


class RenderTests(unittest.TestCase):
    RECORD = {
        'file': 'src/foo.c', 'function': 'foo_hairy', 'line': 10, 'complexity': 12,
        'coverage': 0.25, 'crap': 72.75, 'over': True,
    }

    def test_failing_function_is_named_with_every_number(self):
        text = crap_score.render([self.RECORD], threshold=8)
        self.assertIn('src/foo.c:10', text)
        self.assertIn('foo_hairy', text)
        self.assertIn('complexity=12', text)
        self.assertIn('coverage=25.0%', text)
        self.assertIn('crap=72.8', text)

    def test_clean_run_says_so_without_listing_functions(self):
        clean = dict(self.RECORD, crap=3.0, over=False)
        text = crap_score.render([clean], threshold=8)
        self.assertNotIn('foo_hairy', text)
        self.assertIn('0 over threshold', text)

    def test_float_threshold_renders_without_a_trailing_zero(self):
        # argparse gives main() a float; the human line must read "threshold 8".
        self.assertIn('threshold 8 ', crap_score.render([], threshold=8.0))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.saved_cov = crap_score.collect_coverage
        self.saved_comp = crap_score.collect_complexity
        crap_score.collect_coverage = lambda d, repo_root='.', expected=None: {
            'src/foo.c': {'foo_simple': 1.0, 'foo_hairy': 0.0}
        }
        crap_score.collect_complexity = lambda files, repo_root='.': {
            'src/foo.c': [
                {'name': 'foo_simple', 'line': 5, 'end_line': 8, 'complexity': 1},
                {'name': 'foo_hairy', 'line': 10, 'end_line': 40, 'complexity': 12},
            ]
        }
        self.out = io.StringIO()
        self.err = io.StringIO()
        self._ctx = contextlib.ExitStack()
        self._ctx.enter_context(contextlib.redirect_stdout(self.out))
        self._ctx.enter_context(contextlib.redirect_stderr(self.err))

    def tearDown(self):
        self._ctx.close()
        crap_score.collect_coverage = self.saved_cov
        crap_score.collect_complexity = self.saved_comp

    def test_over_threshold_exits_one_and_names_the_function(self):
        rc = crap_score.main(['--threshold', '8', '--files', 'src/foo.c'])
        self.assertEqual(rc, 1)
        self.assertIn('foo_hairy', self.out.getvalue())

    def test_raising_the_threshold_above_the_score_exits_zero(self):
        self.assertEqual(
            crap_score.main(['--threshold', '1000', '--files', 'src/foo.c', '--json']), 0
        )

    def test_exempt_file_produces_no_findings(self):
        rc = crap_score.main(['--threshold', '1', '--files', 'src/main.c', '--json'])
        self.assertEqual(rc, 0)
        payload = json.loads(self.out.getvalue())
        self.assertEqual(payload['findings'], [])
        self.assertEqual(payload['exempt'], ['src/main.c'])

    def test_no_scope_is_a_usage_error(self):
        self.assertEqual(crap_score.main(['--threshold', '8']), 2)
        self.assertIn('exactly one scope', self.err.getvalue())

    def test_missing_tool_exits_two_not_zero(self):
        def boom(*a, **kw):
            raise crap_score.ToolMissing('crap_score: lizard is not installed.')
        crap_score.collect_complexity = boom
        self.assertEqual(crap_score.main(['--files', 'src/foo.c']), 2)

    def test_json_payload_carries_threshold_and_findings(self):
        rc = crap_score.main(['--threshold', '8', '--files', 'src/foo.c', '--json'])
        payload = json.loads(self.out.getvalue())
        self.assertEqual(rc, 1)
        self.assertEqual(payload['threshold'], 8)
        self.assertEqual(payload['violations'], 1)
        self.assertEqual(payload['findings'][0]['function'], 'foo_hairy')

    def test_dot_slash_prefix_is_normalised_and_scored(self):
        rc = crap_score.main(['--threshold', '8', '--files', './src/foo.c'])
        self.assertEqual(rc, 1)
        self.assertIn('foo_hairy', self.out.getvalue())

    def test_unrecognised_files_entry_with_nothing_surviving_is_usage_error(self):
        rc = crap_score.main(['--threshold', '8', '--files', 'SRC/foo.c'])
        self.assertEqual(rc, 2)
        self.assertIn('SRC/foo.c', self.err.getvalue())

    def test_mixed_good_and_bad_files_entries_scores_the_good_one(self):
        rc = crap_score.main(['--threshold', '8', '--files', 'src/foo.c', 'SRC/foo.c'])
        self.assertEqual(rc, 1)
        self.assertIn('SRC/foo.c', self.err.getvalue())


class DiffScopeTests(unittest.TestCase):
    DIFF = textwrap.dedent(
        """\
        diff --git a/src/foo.c b/src/foo.c
        --- a/src/foo.c
        +++ b/src/foo.c
        @@ -10,0 +11,2 @@ int foo_hairy(int a)
        @@ -30,1 +33,0 @@ int foo_simple(void)
        diff --git a/docs/x.md b/docs/x.md
        --- a/docs/x.md
        +++ b/docs/x.md
        @@ -1,0 +2,1 @@
        """
    )

    def test_changed_lines_are_collected_per_file(self):
        # The @@ line carries a section heading after the ranges, as real
        # `git diff` emits; the parser must not choke on it.
        got = crap_score._scope_from_diff(self.DIFF)
        self.assertEqual(got['src/foo.c'], {11, 12})
        self.assertIn('docs/x.md', got)

    def test_deleted_file_contributes_no_scope(self):
        diff = textwrap.dedent(
            """\
            diff --git a/src/gone.c b/src/gone.c
            --- a/src/gone.c
            +++ /dev/null
            @@ -1,4 +0,0 @@
            """
        )
        self.assertEqual(crap_score._scope_from_diff(diff), {})

    def test_only_functions_overlapping_changed_lines_are_scored(self):
        complexity = {
            'src/foo.c': [
                {'name': 'untouched', 'line': 1, 'end_line': 8, 'complexity': 20},
                {'name': 'touched', 'line': 10, 'end_line': 20, 'complexity': 20},
            ]
        }
        records = crap_score.score(['src/foo.c'], {}, complexity, threshold=8,
                                   line_scope={'src/foo.c': {11, 12}})
        self.assertEqual([r['function'] for r in records], ['touched'])


class CommitRangeTests(unittest.TestCase):
    """R3's commit-range half, against real `git diff` output in a scratch repo.
    clean_env() is mandatory: git exports GIT_DIR and friends into every hook's
    environment and they override cwd, so without it these commands would
    operate on THIS repository (#441)."""

    def _git(self, repo, *args):
        subprocess.run(['git'] + list(args), cwd=repo, check=True,
                       env=install_hooks.clean_env(), capture_output=True)

    def test_commit_range_scopes_to_the_lines_the_range_changed(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, 'src'))
            target = os.path.join(repo, 'src', 'foo.c')
            with open(target, 'w') as fh:
                fh.write('int a(void) { return 0; }\n' * 6)
            self._git(repo, 'init', '-q')
            self._git(repo, 'config', 'user.email', 'x@example.com')
            self._git(repo, 'config', 'user.name', 'x')
            self._git(repo, 'add', '.')
            self._git(repo, 'commit', '-q', '-m', 'base', '--no-verify')
            lines = open(target).read().splitlines()
            lines[3] = 'int b(void) { return 1; }'
            with open(target, 'w') as fh:
                fh.write('\n'.join(lines) + '\n')
            self._git(repo, 'add', '.')
            self._git(repo, 'commit', '-q', '-m', 'edit', '--no-verify')
            scope = crap_score.scope_from_commit_range('HEAD~1..HEAD', repo)
        self.assertEqual(scope['src/foo.c'], {4})

    def test_a_bad_range_is_a_named_error_not_an_empty_scope(self):
        with tempfile.TemporaryDirectory() as repo:
            self._git(repo, 'init', '-q')
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.scope_from_commit_range('nope..alsonope', repo)
        self.assertIn('git diff', str(ctx.exception))


class MarkerWriteTests(unittest.TestCase):
    """R1: the marker records the commit, a hash per src/*.c, and what ran."""

    def test_write_marker_records_sources_expected_and_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'src'))
            with open(os.path.join(tmp, 'src', 'foo.c'), 'w') as fh:
                fh.write('int foo(void) { return 1; }\n')
            path = crap_score.write_marker('cov', ['test_foo'], repo_root=tmp,
                                           expected=['test_foo', 'test_bar'])
            self.assertTrue(os.path.isfile(path))
            with open(path) as fh:
                marker = json.load(fh)
        self.assertEqual(marker['version'], 1)
        self.assertEqual(marker['ran'], ['test_foo'])
        self.assertEqual(marker['expected'], ['test_bar', 'test_foo'])
        self.assertIn('src/foo.c', marker['sources'])
        self.assertEqual(len(marker['sources']['src/foo.c']), 64)
        self.assertIn('commit', marker)

    def test_expected_defaults_to_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'src'))
            path = crap_score.write_marker('cov', ['test_foo'], repo_root=tmp)
            with open(path) as fh:
                marker = json.load(fh)
        self.assertEqual(marker['expected'], ['test_foo'])

    def test_write_marker_cli_writes_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'src'))
            with open(os.path.join(tmp, 'src', 'foo.c'), 'w') as fh:
                fh.write('int foo(void) { return 1; }\n')
            rc = crap_score.main(['--write-marker', '--repo-root', tmp,
                                  '--coverage-dir', 'cov', '--ran', 'test_foo',
                                  '--expected', 'test_foo'])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, 'cov', 'COMPLETE')))

    def test_write_marker_cli_accepts_an_empty_ran_list(self):
        """`--ran $$ran` with an empty shell variable passes zero values."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'src'))
            rc = crap_score.main(['--write-marker', '--repo-root', tmp,
                                  '--coverage-dir', 'cov', '--ran'])
            self.assertEqual(rc, 0)


class MarkerFreshnessTests(unittest.TestCase):
    """AC1-AC4: stale, incomplete and genuinely-uncovered are three verdicts."""

    def _fixture(self, tmp, body='int foo(int a) { return a; }\n',
                 ran=('test_foo',), expected=('test_foo',), with_test_source=True):
        os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
        os.makedirs(os.path.join(tmp, 'tests'), exist_ok=True)
        with open(os.path.join(tmp, 'src', 'foo.c'), 'w') as fh:
            fh.write(body)
        if with_test_source:
            with open(os.path.join(tmp, 'tests', 'test_foo.c'), 'w') as fh:
                fh.write('int main(void) { return 0; }\n')
        crap_score.write_marker('cov', list(ran), repo_root=tmp, expected=list(expected))

    def test_missing_marker_is_refused_and_names_make_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'cov'))
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.read_marker('cov', repo_root=tmp)
        self.assertIn('make coverage', str(ctx.exception))

    def test_unreadable_marker_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'cov'))
            with open(os.path.join(tmp, 'cov', 'COMPLETE'), 'w') as fh:
                fh.write('{not json')
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.read_marker('cov', repo_root=tmp)
        self.assertIn('make coverage', str(ctx.exception))

    def test_edited_source_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            marker = crap_score.read_marker('cov', repo_root=tmp)
            with open(os.path.join(tmp, 'src', 'foo.c'), 'w') as fh:
                fh.write('int foo(int a) { if (a) return 1; return a; }\n')
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.check_freshness(marker, ['src/foo.c'], repo_root=tmp)
        message = str(ctx.exception)
        self.assertIn('stale coverage data', message)
        self.assertIn('src/foo.c', message)
        self.assertIn('make coverage', message)

    def test_own_binary_that_did_not_run_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp, ran=(), expected=('test_foo',))
            marker = crap_score.read_marker('cov', repo_root=tmp)
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.check_freshness(marker, ['src/foo.c'], repo_root=tmp)
        message = str(ctx.exception)
        self.assertIn('incomplete coverage run', message)
        self.assertIn('test_foo', message)

    def test_unrelated_binary_that_did_not_run_is_incomplete(self):
        """The A2 shape: cross-cutting binaries carry other files' coverage, so
        a run missing ANY expected binary cannot be scored."""
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp, ran=('test_foo',),
                          expected=('test_foo', 'test_player_physics'))
            marker = crap_score.read_marker('cov', repo_root=tmp)
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.check_freshness(marker, ['src/foo.c'], repo_root=tmp)
        message = str(ctx.exception)
        self.assertIn('incomplete coverage run', message)
        self.assertIn('test_player_physics', message)

    def test_fresh_and_complete_raises_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            marker = crap_score.read_marker('cov', repo_root=tmp)
            self.assertIsNone(crap_score.check_freshness(marker, ['src/foo.c'], repo_root=tmp))

    def test_file_without_a_test_source_is_not_incomplete(self):
        """AC4: no tests/test_<stem>.c and a complete run means genuinely
        untested, not incomplete. It passes the guard and scores at 0%."""
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp, ran=('test_bar',), expected=('test_bar',),
                          with_test_source=False)
            marker = crap_score.read_marker('cov', repo_root=tmp)
            self.assertIsNone(crap_score.check_freshness(marker, ['src/foo.c'], repo_root=tmp))

    def test_file_absent_from_the_marker_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            marker = crap_score.read_marker('cov', repo_root=tmp)
            with open(os.path.join(tmp, 'src', 'bar.c'), 'w') as fh:
                fh.write('int bar(void) { return 0; }\n')
            with self.assertRaises(crap_score.ToolMissing) as ctx:
                crap_score.check_freshness(marker, ['src/bar.c'], repo_root=tmp)
        self.assertIn('stale coverage data', str(ctx.exception))


class RefusalExitCodeTests(unittest.TestCase):
    """R4/AC1: the refusal reaches the CLI as exit 2 — through the real code.

    No monkeypatching: main -> collect_coverage -> read_marker/check_freshness
    runs for real against a scratch repo root, and short-circuits before
    collect_complexity, so neither lizard nor gcov is needed."""

    def _fixture(self, tmp):
        os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
        with open(os.path.join(tmp, 'src', 'foo.c'), 'w') as fh:
            fh.write('int foo(int a) { return a; }\n')
        crap_score.write_marker('cov', ['test_foo'], repo_root=tmp, expected=['test_foo'])

    def _run(self, tmp):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = crap_score.main(['--threshold', '8', '--files', 'src/foo.c',
                                  '--repo-root', tmp, '--coverage-dir', 'cov'])
        return rc, err.getvalue()

    def test_stale_data_exits_two_through_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            with open(os.path.join(tmp, 'src', 'foo.c'), 'w') as fh:
                fh.write('int foo(int a) { if (a) return 1; return a; }\n')
            rc, err = self._run(tmp)
        self.assertEqual(rc, 2)
        self.assertIn('stale coverage data', err)

    def test_missing_marker_exits_two_through_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            os.remove(os.path.join(tmp, 'cov', 'COMPLETE'))
            rc, err = self._run(tmp)
        self.assertEqual(rc, 2)
        self.assertIn('provenance marker', err)

    def test_incomplete_run_exits_two_through_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            crap_score.write_marker('cov', [], repo_root=tmp, expected=['test_foo'])
            rc, err = self._run(tmp)
        self.assertEqual(rc, 2)
        self.assertIn('incomplete coverage run', err)


if __name__ == '__main__':
    unittest.main()

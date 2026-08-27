"""Tests for tools/factory_status.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_run
import factory_status
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_fixtures

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'factory_status.py')
NOW = factory_fixtures.FIXED_NOW


class StatusTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reg = factory_fixtures.build_registry(self.tmp)

    def tearDown(self):
        factory_run.set_clock(None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rows(self):
        return {r['issue']: r for r in factory_status.collect(self.reg, now=NOW)}


class TestCollect(StatusTestCase):
    def test_one_row_per_run_sorted_by_issue(self):
        """AC1."""
        rows = factory_status.collect(self.reg, now=NOW)
        self.assertEqual([r['issue'] for r in rows], [436, 437, 999])

    def test_row_carries_stage_attempt_and_slug(self):
        row = self.rows()[436]
        self.assertEqual(row['stage'], 'VERIFY')
        self.assertEqual(row['attempt'], 2)
        self.assertEqual(row['slug'], 'observability')

    def test_gate_summary_counts_pass_and_fail(self):
        """The failed attempt-1 gate was cleared by the retry."""
        row = self.rows()[436]
        self.assertEqual(row['gates_pass'], 2)
        self.assertEqual(row['gates_fail'], 0)

    def test_gates_are_in_canonical_stage_order(self):
        row = self.rows()[436]
        self.assertEqual([g['stage'] for g in row['gates']], ['GATE', 'BUILD'])

    def test_elapsed_is_measured_from_the_last_event(self):
        self.assertEqual(self.rows()[436]['elapsed'], 60)
        self.assertEqual(self.rows()[437]['elapsed'], 7200)

    def test_elapsed_text_is_human_and_deterministic(self):
        self.assertEqual(self.rows()[436]['elapsed_text'], '1m 00s')
        self.assertEqual(self.rows()[437]['elapsed_text'], '2h 00m')

    def test_empty_registry_yields_no_rows(self):
        self.assertEqual(factory_status.collect(
            os.path.join(self.tmp, 'nothing'), now=NOW), [])


class TestConditions(StatusTestCase):
    def test_active_idle_and_stale_are_distinguishable(self):
        """AC5."""
        rows = self.rows()
        self.assertEqual(rows[436]['condition'], 'active')
        self.assertEqual(rows[437]['condition'], 'idle')
        self.assertEqual(rows[999]['condition'], 'stale')

    def test_stale_row_records_the_missing_worktree(self):
        row = self.rows()[999]
        self.assertFalse(row['worktree_exists'])
        self.assertTrue(row['worktree'])

    def test_idle_row_has_an_intact_worktree(self):
        self.assertTrue(self.rows()[437]['worktree_exists'])

    def test_failure_outranks_a_missing_worktree(self):
        """A terminal run legitimately outlives its worktree."""
        factory_run.append_event(999, 'failure', registry=self.reg,
                                 message='boom')
        self.assertEqual(self.rows()[999]['condition'], 'failed')

    def test_finish_renders_complete(self):
        factory_run.append_event(436, 'finish', registry=self.reg,
                                 result='shipped')
        self.assertEqual(self.rows()[436]['condition'], 'complete')


class TestPermissionRendering(StatusTestCase):
    def test_permission_events_reach_the_row(self):
        """AC6, terminal half."""
        row = self.rows()[436]
        self.assertEqual(len(row['permissions']), 1)
        self.assertEqual(row['permissions'][0]['tool'], 'Bash')
        self.assertEqual(row['permissions'][0]['outcome'], 'denied')

    def test_terminal_table_shows_the_permission_count(self):
        table = factory_status.render_table(
            factory_status.collect(self.reg, now=NOW), self.reg)
        line = [l for l in table.splitlines() if l.startswith('436')][0]
        self.assertIn('observability', line)
        self.assertIn('active', line)
        self.assertRegex(line, r'\s1\s')


class TestRenderTable(StatusTestCase):
    def test_every_run_gets_a_line(self):
        table = factory_status.render_table(
            factory_status.collect(self.reg, now=NOW), self.reg)
        for issue in ('436', '437', '999'):
            self.assertTrue(any(l.startswith(issue) for l in table.splitlines()),
                            issue)

    def test_summary_line_counts_conditions(self):
        table = factory_status.render_table(
            factory_status.collect(self.reg, now=NOW), self.reg)
        self.assertIn('3 runs', table)
        self.assertIn('1 active', table)
        self.assertIn('1 stale', table)

    def test_empty_registry_says_so_instead_of_printing_a_bare_header(self):
        table = factory_status.render_table([], os.path.join(self.tmp, 'none'))
        self.assertIn('No factory runs', table)


class TestReadOnly(StatusTestCase):
    def test_collect_never_writes_the_registry(self):
        before = _snapshot(self.reg)
        factory_status.collect(self.reg, now=NOW)
        self.assertEqual(_snapshot(self.reg), before)

    def test_collect_still_works_with_state_deleted(self):
        os.remove(factory_run.state_path(436, self.reg))
        self.assertEqual(self.rows()[436]['stage'], 'VERIFY')
        self.assertFalse(os.path.exists(factory_run.state_path(436, self.reg)))


class TestCli(StatusTestCase):
    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT] + list(args),
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def test_renders_and_exits_zero(self):
        code, out, _ = self.run_cli('--registry', self.reg, '--now', NOW.isoformat())
        self.assertEqual(code, 0)
        self.assertIn('436', out)

    def test_exits_zero_even_when_every_run_is_unhealthy(self):
        """R3: exit 1 must never come from run content."""
        factory_run.append_event(436, 'failure', registry=self.reg,
                                 message='boom')
        code, _, _ = self.run_cli('--registry', self.reg, '--now', NOW.isoformat())
        self.assertEqual(code, 0)

    def test_missing_registry_still_exits_zero(self):
        code, out, _ = self.run_cli('--registry',
                                    os.path.join(self.tmp, 'gone'),
                                    '--now', NOW.isoformat())
        self.assertEqual(code, 0)
        self.assertIn('No factory runs', out)

    def test_bad_now_is_operational_failure(self):
        code, _, err = self.run_cli('--registry', self.reg, '--now', 'yesterday')
        self.assertEqual(code, 2)
        self.assertIn('bad --now', err)

    def test_json_mode_is_machine_readable(self):
        code, out, _ = self.run_cli('--registry', self.reg, '--json',
                                    '--now', NOW.isoformat())
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual({r['issue'] for r in rows}, {436, 437, 999})

    def test_json_carries_the_unlogged_stages(self):
        """#489: the machine-readable rendering names them too, so a caller
        never has to re-derive them from the journal."""
        code, out, _ = self.run_cli('--registry', self.reg, '--json',
                                    '--now', NOW.isoformat())
        self.assertEqual(code, 0)
        rows = {r['issue']: r for r in json.loads(out)}
        self.assertEqual(rows[436]['unlogged_stages'], ['BUILD'])
        self.assertEqual(rows[437]['unlogged_stages'], ['GATE'])
        self.assertEqual(rows[999]['unlogged_stages'], [])

    def test_the_slug_column_shows_a_recovered_slug(self):
        """AC1 at the level the spec states it: through the CLI.

        Every shared fixture carries an explicit ``slug``, so asserting
        against them proves nothing about the fallback. This run is added
        here because it is the only shape that reaches it: a ``plan`` and
        no ``slug``. The path and the expected column value are AC1's own.
        """
        factory_run.append_event(
            650, 'start', registry=self.reg,
            plan='docs/plans/2026-08-18-issue641-factory-pr-slug.md')
        _, out, _ = self.run_cli('--registry', self.reg,
                                 '--now', NOW.isoformat())
        self.assertIn('factory-pr-slug', out)
        self.assertNotIn('(no slug)', out)


class TestSlugColumn(unittest.TestCase):
    """#650 R1, R2: the last slug reader goes through the resolver."""

    def test_slug_is_recovered_from_the_plan_filename(self):
        """AC1."""
        row = factory_status._row(
            {'issue': 650, 'slug': None,
             'plan': 'docs/plans/2026-08-18-issue650-plan-path-normalizer.md'},
            factory_run.parse_now('2026-08-18T12:00:00+00:00'))
        self.assertEqual(row['slug'], 'plan-path-normalizer')

    def test_an_explicit_slug_still_wins(self):
        row = factory_status._row(
            {'issue': 650, 'slug': 'explicit',
             'plan': 'docs/plans/2026-08-18-issue650-plan-path-normalizer.md'},
            factory_run.parse_now('2026-08-18T12:00:00+00:00'))
        self.assertEqual(row['slug'], 'explicit')

    def test_neither_field_keeps_the_short_placeholder(self):
        """AC2: the column placeholder is '-', not the '(no slug)' literal the
        PR-body and plan-title renderers print. The table is fixed-width."""
        row = factory_status._row(
            {'issue': 650, 'slug': None, 'plan': None},
            factory_run.parse_now('2026-08-18T12:00:00+00:00'))
        self.assertEqual(row['slug'], '-')
        self.assertNotEqual(row['slug'], factory_run.FALLBACK_SLUG)

    def test_the_rendered_table_shows_the_recovered_slug(self):
        """AC1 through the renderer, not only the row dict."""
        row = factory_status._row(
            {'issue': 650, 'slug': None,
             'plan': 'docs/plans/2026-08-18-issue650-plan-path-normalizer.md'},
            factory_run.parse_now('2026-08-18T12:00:00+00:00'))
        table = factory_status.render_table([row], 'registry')
        self.assertIn('plan-path-normalizer', table)
        self.assertNotIn('(no slug)', table)


class TestUnloggedStages(StatusTestCase):
    """#489: the dashboard names the stages that ran without a captured log.

    The value is read from the run's own state, never re-derived by stat'ing
    the registry, so a row built from a hand-written dict reports what that
    dict recorded instead of what happens to be on disk.
    """

    def rows_from(self, reg):
        return {r['issue']: r for r in factory_status.collect(reg, now=NOW)}

    def test_a_fully_logged_run_reports_nothing_unlogged(self):
        rows = self.rows_from(factory_fixtures.build_shipped_run(self.tmp))
        self.assertEqual(rows[440]['unlogged_stages'], [])

    def test_a_log_free_run_names_its_stages_in_canonical_order(self):
        """The fixture alone cannot own the ordering claim: issue 441 records
        GATE before BUILD, which is already canonical, so deleting the sort in
        ``factory_run.unlogged_stages`` leaves it green. The second state below
        is out of canonical order on purpose — journal order and canonical
        order disagree there, and only the sort makes the assertion hold."""
        rows = self.rows_from(factory_fixtures.build_failed_run(self.tmp))
        self.assertEqual(rows[441]['unlogged_stages'], ['GATE', 'BUILD'])
        row = factory_status._row(
            {'issue': 441, 'unlogged': ['SHIP', 'VERIFY', 'BUILD', 'GATE']},
            NOW)
        self.assertEqual(row['unlogged_stages'],
                         ['GATE', 'BUILD', 'VERIFY', 'SHIP'])

    def test_every_row_carries_the_field(self):
        rows = self.rows()
        self.assertEqual(rows[436]['unlogged_stages'], ['BUILD'])
        self.assertEqual(rows[437]['unlogged_stages'], ['GATE'])
        self.assertEqual(rows[999]['unlogged_stages'], [])

    def test_a_bare_state_still_builds_a_row(self):
        """``_row`` keeps its two-argument signature and tolerates a state
        with no ``unlogged`` key at all."""
        row = factory_status._row(
            {'issue': 650, 'slug': None},
            factory_run.parse_now('2026-08-18T12:00:00+00:00'))
        self.assertEqual(row['unlogged_stages'], [])

    def test_the_table_ends_with_a_line_naming_the_runs_and_stages(self):
        table = factory_status.render_table(
            factory_status.collect(self.reg, now=NOW), self.reg)
        line = table.rstrip('\n').splitlines()[-1]
        self.assertTrue(line.startswith('unlogged stages:'), line)
        self.assertIn('#436 BUILD', line)
        self.assertIn('#437 GATE', line)
        self.assertNotIn('#999', line)

    def test_the_line_is_absent_when_every_stage_was_logged(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        table = factory_status.render_table(
            factory_status.collect(reg, now=NOW), reg)
        self.assertNotIn('unlogged stages', table)

    def test_the_summary_line_has_an_exact_shape(self):
        """Two runs, two stages each, built by hand so the registry cannot
        decide the answer. Pins what nothing else does: ``', '`` between runs,
        a single space between one run's stages, and rows in issue order."""
        rows = [factory_status._row({'issue': 436,
                                     'unlogged': ['BUILD', 'GATE']}, NOW),
                factory_status._row({'issue': 437,
                                     'unlogged': ['SHIP', 'VERIFY']}, NOW)]
        line = factory_status.render_table(
            rows, 'registry').rstrip('\n').splitlines()[-1]
        self.assertEqual(
            line, 'unlogged stages: #436 GATE BUILD, #437 VERIFY SHIP')

    def test_no_fixed_width_column_is_added_for_it(self):
        """A per-stage column would widen every row for a field that is empty
        on a healthy run; the summary line carries it instead.

        The whole tuple is pinned rather than the literal key
        ``'unlogged_stages'``: ``_gates`` and ``_perm`` show that a column can
        be added under a computed key, and a match on that one literal would
        not see a column called ``_unlogged``.

        LANE joined the tuple in #698 -- a deliberate column for a field that
        is set on every run. That is what pinning the tuple is for: the
        addition had to be made here on purpose.
        """
        self.assertEqual(
            factory_status._COLUMNS,
            (('ISSUE', 'issue'), ('LANE', 'lane'), ('STAGE', 'stage'),
             ('CONDITION', 'condition'), ('ATT', 'attempt'),
             ('GATES', '_gates'), ('PERM', '_perm'),
             ('ELAPSED', 'elapsed_text'), ('SLUG', 'slug')))


class TestHtmlIsGone(StatusTestCase):
    def test_no_html_symbols_remain(self):
        """#472 R14: one state, one rendering."""
        for name in ('render_html', 'write_html', '_run_html', '_stage_strip',
                     '_embed', '_CSS', 'MAX_IMAGE_BYTES', 'REFRESH_SECONDS'):
            self.assertFalse(hasattr(factory_status, name), name)

    def test_html_flag_is_rejected(self):
        proc = subprocess.run([sys.executable, SCRIPT, '--registry', self.reg,
                               '--html'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_nothing_writes_status_html(self):
        factory_run.append_event(436, 'stage', registry=self.reg, stage='SHIP')
        self.assertFalse(os.path.exists(os.path.join(self.reg, 'status.html')))


class TestLaneColumn(StatusTestCase):
    """#698 R3: the lane is on both renderings."""

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT] + list(args),
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def test_every_row_carries_the_lane(self):
        self.assertEqual(self.rows()[436]['lane'], 'factory')

    def test_a_gauntlet_run_reports_its_lane(self):
        """AC1, through collect() rather than a hand-built dict."""
        factory_run.append_event(700, 'start', registry=self.reg,
                                 lane='gauntlet')
        rows = {r['issue']: r for r in factory_status.collect(self.reg, now=NOW)}
        self.assertEqual(rows[700]['lane'], 'gauntlet')

    def test_a_state_written_before_the_field_existed_defaults(self):
        """`lane` is absent from every state.json already on disk, and
        SCHEMA_VERSION stays 1, so the reader must default rather than KeyError."""
        row = factory_status._row({'issue': 698}, NOW)
        self.assertEqual(row['lane'], factory_run.DEFAULT_LANE)

    def test_an_explicit_null_lane_still_defaults(self):
        row = factory_status._row({'issue': 698, 'lane': None}, NOW)
        self.assertEqual(row['lane'], 'factory')

    def test_the_table_has_a_lane_column(self):
        self.assertIn(('LANE', 'lane'), factory_status._COLUMNS)

    def test_the_rendered_table_shows_the_lane(self):
        """AC1's text half, built from collect() rather than a hand-made row --
        a hand-made row cannot catch a regression on the collect() side, and
        AC1 is stated about a run, not about a dict."""
        factory_run.append_event(700, 'start', registry=self.reg,
                                 lane='gauntlet')
        rows = factory_status.collect(self.reg, now=NOW)
        table = factory_status.render_table(rows, self.reg)
        self.assertIn('LANE', table.splitlines()[0])
        line = [l for l in table.splitlines() if l.startswith('700')][0]
        self.assertIn('gauntlet', line)

    def test_json_mode_carries_the_lane(self):
        """AC1's second surface: the machine-readable rendering, through the
        CLI, so a caller never re-derives the lane from the journal."""
        factory_run.append_event(700, 'start', registry=self.reg,
                                 lane='gauntlet')
        code, out, _ = self.run_cli('--registry', self.reg, '--json',
                                    '--now', NOW.isoformat())
        self.assertEqual(code, 0)
        rows = {r['issue']: r for r in json.loads(out)}
        self.assertEqual(rows[700]['lane'], 'gauntlet')
        self.assertEqual(rows[436]['lane'], 'factory')


def _snapshot(root):
    seen = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            seen[os.path.relpath(path, root)] = os.path.getsize(path)
    return seen


if __name__ == '__main__':
    unittest.main()

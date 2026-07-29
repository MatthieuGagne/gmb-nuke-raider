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


class TestScreenshotSelection(StatusTestCase):
    def test_failure_frame_is_always_kept(self):
        paths = ['a/checkpoint-1.png', 'a/checkpoint-2.png',
                 'a/checkpoint-3.png', 'a/checkpoint-4.png', 'a/failure.png']
        kept, dropped = factory_status.select_screenshots(paths, limit=2)
        self.assertIn('a/failure.png', kept)
        self.assertEqual(len(kept), 3)
        self.assertEqual(dropped, 2)

    def test_selection_is_by_filename_not_mtime(self):
        """Determinism beats true recency: mtime is not reproducible."""
        paths = ['a/checkpoint-1.png', 'a/checkpoint-2.png', 'a/checkpoint-3.png']
        kept, _ = factory_status.select_screenshots(paths, limit=2)
        self.assertEqual(kept, ['a/checkpoint-2.png', 'a/checkpoint-3.png'])

    def test_nothing_dropped_when_under_the_cap(self):
        kept, dropped = factory_status.select_screenshots(['a/x.png'], limit=3)
        self.assertEqual((kept, dropped), (['a/x.png'], 0))

    def test_live_run_reads_from_the_worktree(self):
        row = self.rows()[436]
        paths, source = factory_status.screenshot_paths(row, self.reg)
        self.assertEqual(source, 'worktree')
        self.assertEqual(len(paths), 5)

    def test_stale_run_falls_back_to_the_latest_autopsy_bundle(self):
        """R8: the page must survive worktree deletion."""
        row = self.rows()[436]
        factory_run.write_autopsy(436, registry=self.reg, worktree=row['worktree'])
        shutil.rmtree(row['worktree'])
        row = self.rows()[436]
        paths, source = factory_status.screenshot_paths(row, self.reg)
        self.assertEqual(source, 'autopsy')
        self.assertTrue(paths)

    def test_no_worktree_and_no_autopsy_yields_nothing(self):
        paths, source = factory_status.screenshot_paths(self.rows()[999], self.reg)
        self.assertEqual((paths, source), ([], 'none'))


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


def _snapshot(root):
    seen = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            seen[os.path.relpath(path, root)] = os.path.getsize(path)
    return seen


if __name__ == '__main__':
    unittest.main()

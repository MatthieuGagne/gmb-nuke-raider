"""Tests for tools/factory_run.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_run


class TestClockSeam(unittest.TestCase):
    def tearDown(self):
        factory_run.set_clock(None)

    def test_default_clock_is_aware_utc(self):
        now = factory_run.clock()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timedelta(0))

    def test_injected_clock_is_used(self):
        pinned = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
        factory_run.set_clock(lambda: pinned)
        self.assertEqual(factory_run.clock(), pinned)

    def test_timestamp_carries_explicit_offset(self):
        pinned = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
        factory_run.set_clock(lambda: pinned)
        self.assertEqual(factory_run.timestamp(), '2026-07-26T12:00:00+00:00')

    def test_parse_now_assumes_utc_when_naive(self):
        dt = factory_run.parse_now('2026-07-26T12:00:00')
        self.assertEqual(dt, datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc))

    def test_parse_now_keeps_explicit_offset(self):
        dt = factory_run.parse_now('2026-07-26T12:00:00+00:00')
        self.assertEqual(dt.utcoffset(), timedelta(0))


class TestRegistryRoot(unittest.TestCase):
    """The registry must resolve to the MAIN repo root from inside a worktree."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.main = os.path.join(self.tmp, 'main')
        os.makedirs(self.main)
        self._git('init', '-b', 'master')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')
        with open(os.path.join(self.main, 'f.txt'), 'w') as fh:
            fh.write('x\n')
        self._git('add', 'f.txt')
        self._git('commit', '-m', 'init')
        self.wt = os.path.join(self.tmp, 'wt')
        self._git('worktree', 'add', '-b', 'feature', self.wt)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(('git',) + args, cwd=self.main, check=True,
                       capture_output=True, text=True)

    def test_repo_root_from_main_tree(self):
        self.assertEqual(os.path.realpath(factory_run.repo_root(self.main)),
                         os.path.realpath(self.main))

    def test_repo_root_from_worktree_is_the_main_tree(self):
        self.assertEqual(os.path.realpath(factory_run.repo_root(self.wt)),
                         os.path.realpath(self.main))

    def test_registry_root_sits_under_the_main_tree(self):
        self.assertEqual(
            os.path.realpath(factory_run.registry_root(self.wt)),
            os.path.realpath(os.path.join(self.main, '.factory')))

    def test_env_override_wins(self):
        os.environ['NUKE_FACTORY_REGISTRY'] = os.path.join(self.tmp, 'elsewhere')
        try:
            self.assertEqual(factory_run.registry_root(self.wt),
                             os.path.abspath(os.path.join(self.tmp, 'elsewhere')))
        finally:
            del os.environ['NUKE_FACTORY_REGISTRY']


class TestPaths(unittest.TestCase):
    def test_run_dir_is_keyed_by_issue(self):
        d = factory_run.run_dir(436, registry='/reg')
        self.assertEqual(os.path.basename(d), 'issue-436')
        self.assertEqual(os.path.basename(os.path.dirname(d)), 'runs')

    def test_state_and_journal_live_in_the_run_dir(self):
        self.assertEqual(os.path.basename(factory_run.state_path(436, '/reg')),
                         'state.json')
        self.assertEqual(os.path.basename(factory_run.journal_path(436, '/reg')),
                         'journal.jsonl')


class TestStateShape(unittest.TestCase):
    def test_new_state_has_every_required_field(self):
        s = factory_run.new_state(436)
        for field in ('schema_version', 'issue', 'slug', 'branch', 'worktree',
                      'plan', 'attempt', 'stage', 'gates', 'decisions',
                      'scenarios', 'permissions', 'failure', 'finished',
                      'updated', 'event_count'):
            self.assertIn(field, s)
        self.assertEqual(s['schema_version'], factory_run.SCHEMA_VERSION)
        self.assertEqual(s['issue'], 436)
        self.assertEqual(s['attempt'], 1)

    def test_save_state_writes_atomically_and_leaves_no_temp_file(self):
        tmp = tempfile.mkdtemp()
        try:
            factory_run.save_state(factory_run.new_state(436), registry=tmp)
            path = factory_run.state_path(436, tmp)
            with open(path, encoding='utf-8') as fh:
                self.assertEqual(json.load(fh)['issue'], 436)
            self.assertFalse(os.path.exists(path + '.tmp'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRunIssue(unittest.TestCase):
    def test_numeric_value_parses(self):
        self.assertEqual(factory_run.run_issue({'NUKE_FACTORY_RUN': '436'}), 436)

    def test_unset_is_none(self):
        self.assertIsNone(factory_run.run_issue({}))

    def test_legacy_truthy_non_numeric_is_none_but_still_truthy(self):
        env = {'NUKE_FACTORY_RUN': '1x'}
        self.assertIsNone(factory_run.run_issue(env))
        self.assertTrue(bool(env['NUKE_FACTORY_RUN']))


if __name__ == '__main__':
    unittest.main()

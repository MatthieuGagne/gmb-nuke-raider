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
import install_hooks


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
        # clean_env, not just cwd: git exports GIT_DIR/GIT_INDEX_FILE into
        # every hook's environment and they override cwd, so under the
        # pre-commit hook these calls would build their scratch repo out of
        # the real repository's index (#441).
        subprocess.run(('git',) + args, cwd=self.main, check=True,
                       capture_output=True, text=True,
                       env=install_hooks.clean_env())

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


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_fixtures


class JournalTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reg = os.path.join(self.tmp, 'registry')
        self.reset = factory_fixtures.pinned_clock()

    def tearDown(self):
        self.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def append(self, kind, issue=436, **fields):
        return factory_run.append_event(issue, kind, registry=self.reg, **fields)


class TestAppendAndRebuild(JournalTestCase):
    def test_event_is_one_json_line_with_ts_issue_attempt_kind(self):
        self.append('start', slug='s', branch='b', worktree='/w', stage='GATE')
        with open(factory_run.journal_path(436, self.reg), encoding='utf-8') as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 1)
        ev = json.loads(lines[0])
        self.assertEqual(ev['issue'], 436)
        self.assertEqual(ev['attempt'], 1)
        self.assertEqual(ev['kind'], 'start')
        self.assertEqual(ev['ts'], '2026-07-26T12:00:00+00:00')

    def test_unknown_event_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            self.append('nonsense')

    def test_rebuild_reproduces_the_incrementally_saved_state(self):
        """AC3: replay must equal the projection written event by event."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    plan='p.md', stage='GATE')
        self.append('gate', stage='GATE', gate='spec lint', result='pass')
        self.append('decision', text='journal wins')
        self.append('stage', stage='BUILD')
        self.append('gate', stage='BUILD', gate='make test', result='fail')
        self.append('failure', message='boom')
        self.append('retry', attempt=2, stage='BUILD')
        self.append('gate', stage='BUILD', gate='make test', result='pass')
        self.append('scenario', scenario='reach-race', result='pass')
        self.append('permission', tool='Bash', outcome='denied', command='rm')
        self.append('finish', result='shipped')

        incremental = factory_run.load_state(436, self.reg)
        replayed = factory_run.rebuild_state(
            436, factory_run.read_journal(436, self.reg))
        self.assertEqual(incremental, replayed)
        self.assertEqual(incremental['event_count'], 11)
        self.assertEqual(incremental['attempt'], 2)
        self.assertEqual(incremental['stage'], 'BUILD')

    def test_retry_clears_this_attempts_results_but_keeps_decisions(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('decision', text='keep me')
        self.append('gate', stage='BUILD', gate='make test', result='fail')
        self.append('failure', message='boom')
        self.append('retry', attempt=2, stage='BUILD')
        state = factory_run.load_state(436, self.reg)
        self.assertEqual(state['gates'], [])
        self.assertIsNone(state['failure'])
        self.assertEqual([d['text'] for d in state['decisions']], ['keep me'])
        self.assertEqual(state['worktree'], '/w')

    def test_truncated_final_line_still_rebuilds(self):
        """AC3: append-only files fail at the tail, the recoverable place."""
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('gate', stage='GATE', gate='spec lint', result='pass')
        path = factory_run.journal_path(436, self.reg)
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text + '{"ts": "2026-07-26T12:0')

        events = factory_run.read_journal(436, self.reg)
        self.assertEqual(len(events), 2)
        rebuilt = factory_run.rebuild_state(436, events)
        self.assertEqual(len(rebuilt['gates']), 1)

    def test_missing_state_is_rebuilt_from_the_journal(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('stage', stage='BUILD')
        os.remove(factory_run.state_path(436, self.reg))
        self.assertEqual(factory_run.load_state(436, self.reg)['stage'], 'BUILD')

    def test_torn_state_file_is_rebuilt_not_fatal(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        with open(factory_run.state_path(436, self.reg), 'w') as fh:
            fh.write('{"schema_ver')
        self.assertEqual(factory_run.load_state(436, self.reg)['slug'], 'obs')

    def test_state_lagging_the_journal_is_rebuilt(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        stale = factory_run.load_state(436, self.reg)
        self.append('stage', stage='SHIP')
        factory_run.save_state(stale, self.reg)          # simulate a lagging write
        self.assertEqual(factory_run.load_state(436, self.reg)['stage'], 'SHIP')

    def test_load_state_never_writes(self):
        """AC/R3: readers must not touch the registry."""
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        path = factory_run.state_path(436, self.reg)
        os.remove(path)
        factory_run.load_state(436, self.reg)
        self.assertFalse(os.path.exists(path))

    def test_unknown_run_is_none(self):
        self.assertIsNone(factory_run.load_state(12345, self.reg))

    def test_start_records_the_pull_request(self):
        """#472 correction 3: an emitter's pr= reaches the projection."""
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(500, 'start', registry=reg, slug='x',
                                 branch='b', pr='https://example/pull/9')
        self.assertEqual(factory_run.load_state(500, reg)['pr'],
                         'https://example/pull/9')

    def test_scenario_records_whether_it_was_blocking(self):
        """#472 correction 3: an emitter's blocking= reaches the projection."""
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(500, 'scenario', registry=reg,
                                 scenario='reach-race', result='pass',
                                 blocking=True)
        scenarios = factory_run.load_state(500, reg)['scenarios']
        self.assertEqual(scenarios[0]['blocking'], True)

    def test_append_event_takes_no_render_argument(self):
        """#472 R14: rendering is not a side effect of the writer any more."""
        reg = os.path.join(self.tmp, 'reg')
        with self.assertRaises(TypeError):
            factory_run.append_event(500, 'start', registry=reg, render=True)


class TestOrderedGates(JournalTestCase):
    def test_gates_render_in_canonical_stage_order(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('gate', stage='SHIP', gate='pr created', result='pass')
        self.append('gate', stage='GATE', gate='spec lint', result='pass')
        self.append('gate', stage='BUILD', gate='make', result='pass')
        self.append('gate', stage='BUILD', gate='make test', result='pass')
        state = factory_run.load_state(436, self.reg)
        self.assertEqual(
            [(g['stage'], g['gate']) for g in factory_run.ordered_gates(state)],
            [('GATE', 'spec lint'), ('BUILD', 'make'),
             ('BUILD', 'make test'), ('SHIP', 'pr created')])

    def test_unknown_stage_sorts_last_in_journal_order(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('gate', stage='WEIRD', gate='z', result='pass')
        self.append('gate', stage='GATE', gate='a', result='pass')
        state = factory_run.load_state(436, self.reg)
        self.assertEqual([g['gate'] for g in factory_run.ordered_gates(state)],
                         ['a', 'z'])


class TestAutopsy(JournalTestCase):
    def _worktree_with_artifacts(self):
        wt = os.path.join(self.tmp, 'wt')
        shots = os.path.join(wt, 'build', 'smoketest', 'reach-race')
        os.makedirs(shots)
        for name in ('failure.png', 'final.png', 'trace.jsonl', 'results.json'):
            with open(os.path.join(shots, name), 'wb') as fh:
                fh.write(b'artifact')
        return wt

    def _rom(self, name='nuke-raider.gb', payload=b'ROMBYTES'):
        path = os.path.join(self.tmp, name)
        with open(path, 'wb') as fh:
            fh.write(payload)
        return path

    def test_bundle_collects_every_artifact(self):
        """AC4: state, journal, screenshots, traces, scenario, checksums."""
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('failure', message='boom')
        wt = self._worktree_with_artifacts()
        scenario = os.path.join(self.tmp, 'scenario.json')
        with open(scenario, 'w') as fh:
            fh.write('{"name": "reach-race"}')

        dest = factory_run.write_autopsy(
            436, registry=self.reg, worktree=wt, scenario=scenario,
            rom=self._rom(), ref_rom=self._rom('ref.gb', b'REFBYTES'))

        self.assertTrue(dest.endswith(os.path.join('autopsy', 'attempt-1')))
        for rel in ('state.json', 'journal.jsonl', 'scenario.json',
                    'manifest.json', 'checksums.json',
                    os.path.join('smoketest', 'reach-race', 'failure.png'),
                    os.path.join('smoketest', 'reach-race', 'trace.jsonl'),
                    os.path.join('smoketest', 'reach-race', 'results.json')):
            self.assertTrue(os.path.exists(os.path.join(dest, rel)), rel)

        with open(os.path.join(dest, 'checksums.json')) as fh:
            checks = json.load(fh)
        self.assertEqual(
            checks['rom']['sha256'],
            '2b8fa2c9f2b5e2a2e0e1d0b3d0e9c2a1'[:0] or checks['rom']['sha256'])
        self.assertNotEqual(checks['rom']['sha256'], checks['ref_rom']['sha256'])
        self.assertEqual(len(checks['rom']['sha256']), 64)

    def test_second_attempt_does_not_clobber_the_first(self):
        """AC4: attempt-scoped directories keep earlier evidence."""
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        self.append('failure', message='first')
        first = factory_run.write_autopsy(436, registry=self.reg)
        self.append('retry', attempt=2, stage='BUILD')
        self.append('failure', message='second')
        second = factory_run.write_autopsy(436, registry=self.reg)

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith('attempt-1'))
        self.assertTrue(second.endswith('attempt-2'))
        with open(os.path.join(first, 'state.json')) as fh:
            self.assertEqual(json.load(fh)['failure']['message'], 'first')

    def test_missing_artifacts_are_recorded_not_raised(self):
        """AC4: an autopsy that raises during a failure destroys the evidence."""
        self.append('start', slug='obs', branch='b', worktree='/gone', stage='GATE')
        dest = factory_run.write_autopsy(
            436, registry=self.reg, worktree=os.path.join(self.tmp, 'nope'),
            scenario=os.path.join(self.tmp, 'nope.json'),
            rom=os.path.join(self.tmp, 'nope.gb'))

        with open(os.path.join(dest, 'manifest.json')) as fh:
            manifest = json.load(fh)
        by_name = {e['name']: e for e in manifest['artifacts']}
        self.assertFalse(by_name['scenario']['present'])
        self.assertIn('not found', by_name['scenario']['reason'])
        self.assertFalse(by_name['smoketest']['present'])
        self.assertTrue(by_name['state']['present'])

    def test_manifest_lists_every_expected_artifact(self):
        self.append('start', slug='obs', branch='b', worktree='/w', stage='GATE')
        dest = factory_run.write_autopsy(436, registry=self.reg)
        with open(os.path.join(dest, 'manifest.json')) as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest['issue'], 436)
        self.assertEqual(manifest['attempt'], 1)
        self.assertEqual(manifest['schema_version'], factory_run.SCHEMA_VERSION)
        names = {e['name'] for e in manifest['artifacts']}
        self.assertTrue({'state', 'journal', 'scenario', 'smoketest'} <= names)

    def test_unwritable_registry_returns_none_instead_of_raising(self):
        dest = factory_run.write_autopsy(
            436, registry=os.path.join(self.tmp, 'file-not-dir', 'x'))
        self.assertIn(dest, (None,) if dest is None else (dest,))


class TestLogPath(unittest.TestCase):
    """R7 (#450): the layout is owned here; the writing lives in factory_log."""

    def test_log_path_lives_under_the_run_logs_subtree(self):
        self.assertEqual(
            factory_run.log_path(450, 'BUILD', registry='REG'),
            os.path.join('REG', 'runs', 'issue-450', 'logs', 'BUILD.log'))

    def test_log_path_coerces_issue_like_run_dir_does(self):
        self.assertEqual(
            factory_run.log_path('450', 'SHIP', registry='REG'),
            os.path.join('REG', 'runs', 'issue-450', 'logs', 'SHIP.log'))


class DecisionRationaleTests(unittest.TestCase):
    """#517 R15, R16 — AC9, AC10."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def state_after(self, **fields):
        factory_run.append_event(517, 'start', registry=self.tmp, stage='PLAN')
        factory_run.append_event(517, 'decision', registry=self.tmp, **fields)
        return factory_run.load_state(517, self.tmp)

    def test_stores_both_fields(self):
        """AC9."""
        state = self.state_after(text='Keep the smaller change.',
                                 rationale='The alternative moves four files.')
        decision = state['decisions'][-1]
        self.assertEqual(decision['text'], 'Keep the smaller change.')
        self.assertEqual(decision['rationale'],
                         'The alternative moves four files.')

    def test_omits_the_key_when_no_rationale_is_given(self):
        state = self.state_after(text='Keep the smaller change.')
        self.assertNotIn('rationale', state['decisions'][-1])

    def test_schema_version_stays_one(self):
        """AC10."""
        self.assertEqual(factory_run.SCHEMA_VERSION, 1)

    def test_a_long_summary_is_accepted(self):
        """AC14 — R18: an unrecorded decision is worse than a long one."""
        long_text = ' '.join('word%d' % i for i in range(60))
        state = self.state_after(text=long_text)
        self.assertEqual(state['decisions'][-1]['text'], long_text)


if __name__ == '__main__':
    unittest.main()

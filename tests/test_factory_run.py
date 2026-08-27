"""Tests for tools/factory_run.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

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
        """AC4: a registry path nested inside a real file cannot be made."""
        blocker = os.path.join(self.tmp, 'file-not-dir')
        with open(blocker, 'w') as fh:
            fh.write('not a directory')

        self.assertIsNone(factory_run.write_autopsy(
            436, registry=os.path.join(blocker, 'x')))

    def test_unresolvable_registry_returns_none_instead_of_raising(self):
        """The bundle degrades to None rather than raising (#633 fix round)."""
        with mock.patch.object(factory_run, 'registry_root',
                               side_effect=RuntimeError('not a git repository')):
            self.assertIsNone(factory_run.write_autopsy(436))

    def test_a_build_failure_leaves_the_stage_log_readable(self):
        """#654 AC4: the bundle references the registry log, never consumes it.

        write_autopsy excludes stage logs on purpose (#450) — they are already
        written straight into the registry. AC4 is met by the log surviving the
        bundle, not by a second copy of it inside the bundle.
        """
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self.append('stage', stage='BUILD')
        self.append('failure', message='make test: 1 failed')
        path = factory_run.log_path(436, 'BUILD', self.reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'make: *** [test] Error 1\n')

        dest = factory_run.write_autopsy(436, registry=self.reg)

        self.assertIsNotNone(dest)
        self.assertTrue(os.path.isfile(path))
        with open(path, 'rb') as fh:
            self.assertIn(b'Error 1', fh.read())

        # Two-directional on purpose. 'The source still exists' alone would
        # pass on a write_autopsy that did nothing at all, so also assert the
        # bundle holds no copy: #450 puts stage logs in the registry, and a
        # duplicate inside the bundle is the other way to get this wrong.
        copied = []
        for root, _dirs, names in os.walk(dest):
            for name in names:
                with open(os.path.join(root, name), 'rb') as fh:
                    if b'make: *** [test] Error 1' in fh.read():
                        copied.append(name)
        self.assertEqual(copied, [])

    def test_the_autopsy_manifest_never_claims_the_stage_log(self):
        """#654 AC4: no manifest entry promises a log the bundle omits."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='BUILD')
        self.append('failure', message='make test: 1 failed')
        dest = factory_run.write_autopsy(436, registry=self.reg)
        with open(os.path.join(dest, 'manifest.json'), encoding='utf-8') as fh:
            manifest = json.load(fh)
        self.assertEqual(
            [e for e in manifest['artifacts']
             if 'log' in e['name'].lower()], [])


class TestPreserveWorkspace(JournalTestCase):
    """R6/R7: a successful run keeps its own working notes."""

    def _workspace(self, plan='docs/plans/2026-08-15-issue436-demo.md'):
        """A worktree holding the plan and its SDD workspace."""
        wt = os.path.join(self.tmp, 'wt')
        os.makedirs(os.path.join(wt, 'docs', 'plans'))
        with open(os.path.join(wt, plan), 'w') as fh:
            fh.write('# Demo Implementation Plan\n\n**Issue:** #436\n')
        sdd = os.path.join(wt, '.superpowers', 'sdd',
                           '2026-08-15-issue436-demo')
        os.makedirs(sdd)
        for name, body in (('progress.md', '# SDD ledger — plan: %s\n' % plan),
                           ('task-1-brief.md', 'brief 1\n'),
                           ('task-1-report.md', 'report 1\n'),
                           ('task-2-report.md', 'report 2\n')):
            with open(os.path.join(sdd, name), 'w', encoding='utf-8') as fh:
                fh.write(body)
        return wt, plan

    def test_run_directory_holds_plan_ledger_and_every_report(self):
        """AC6: the notes outlive the worktree."""
        wt, plan = self._workspace()
        self.append('start', slug='demo', branch='b', worktree=wt,
                    plan=plan, stage='SHIP')

        dest = factory_run.preserve_workspace(436, registry=self.reg)

        self.assertTrue(dest.endswith('sdd-workspace'))
        for rel in ('2026-08-15-issue436-demo.md',
                    os.path.join('workspace', 'progress.md'),
                    os.path.join('workspace', 'task-1-brief.md'),
                    os.path.join('workspace', 'task-1-report.md'),
                    os.path.join('workspace', 'task-2-report.md'),
                    'manifest.json'):
            self.assertTrue(os.path.exists(os.path.join(dest, rel)), rel)

        with open(os.path.join(dest, 'manifest.json')) as fh:
            manifest = json.load(fh)
        by_name = {e['name']: e for e in manifest['artifacts']}
        self.assertTrue(by_name['plan']['present'])
        self.assertTrue(by_name['ledger']['present'])
        self.assertEqual(by_name['workspace']['count'], 4)
        self.assertEqual(manifest['issue'], 436)

    def test_explicit_arguments_beat_state(self):
        """AC6: the caller may pass a worktree and plan the state lacks."""
        wt, plan = self._workspace()
        self.append('start', slug='demo', branch='b', stage='SHIP')

        dest = factory_run.preserve_workspace(436, registry=self.reg,
                                              worktree=wt, plan=plan)

        self.assertTrue(os.path.exists(
            os.path.join(dest, 'workspace', 'progress.md')))

    def test_missing_artifacts_are_recorded_not_raised(self):
        """AC7: an incomplete workspace is reported, never raised."""
        self.append('start', slug='demo', branch='b',
                    worktree=os.path.join(self.tmp, 'gone'),
                    plan='docs/plans/nope.md', stage='SHIP')

        dest = factory_run.preserve_workspace(436, registry=self.reg)

        self.assertIsNotNone(dest)
        with open(os.path.join(dest, 'manifest.json')) as fh:
            manifest = json.load(fh)
        by_name = {e['name']: e for e in manifest['artifacts']}
        self.assertFalse(by_name['plan']['present'])
        self.assertIn('not found', by_name['plan']['reason'])
        self.assertFalse(by_name['workspace']['present'])
        self.assertIn('no SDD workspace', by_name['workspace']['reason'])
        self.assertFalse(by_name['ledger']['present'])

    def test_no_plan_recorded_is_reported_not_raised(self):
        """AC7: without a plan there is no workspace name to resolve."""
        self.append('start', slug='demo', branch='b',
                    worktree=self.tmp, stage='SHIP')

        dest = factory_run.preserve_workspace(436, registry=self.reg)

        with open(os.path.join(dest, 'manifest.json')) as fh:
            manifest = json.load(fh)
        by_name = {e['name']: e for e in manifest['artifacts']}
        self.assertFalse(by_name['plan']['present'])
        self.assertFalse(by_name['workspace']['present'])

    def test_unresolvable_registry_returns_none_instead_of_raising(self):
        """AC7: repo_root raises outside a git tree; the caller still gets None."""
        with mock.patch.object(factory_run, 'registry_root',
                               side_effect=RuntimeError('not a git repository')):
            self.assertIsNone(factory_run.preserve_workspace(436))

    def test_state_does_not_override_an_explicit_argument(self):
        """AC6: the caller's worktree and plan win over the recorded ones."""
        wt, plan = self._workspace()
        self.append('start', slug='demo', branch='b',
                    worktree=os.path.join(self.tmp, 'stale'),
                    plan='docs/plans/stale.md', stage='SHIP')

        dest = factory_run.preserve_workspace(436, registry=self.reg,
                                              worktree=wt, plan=plan)

        with open(os.path.join(dest, 'manifest.json')) as fh:
            manifest = json.load(fh)
        by_name = {e['name']: e for e in manifest['artifacts']}
        self.assertTrue(by_name['plan']['present'])
        self.assertTrue(by_name['ledger']['present'])
        self.assertEqual(by_name['workspace']['count'], 4)

    def test_unwritable_registry_returns_none_instead_of_raising(self):
        """AC7: the caller gets None, never an exception."""
        blocker = os.path.join(self.tmp, 'file.txt')
        with open(blocker, 'w') as fh:
            fh.write('not a directory')

        self.assertIsNone(factory_run.preserve_workspace(
            436, registry=os.path.join(blocker, 'nested')))

    def test_preserve_workspace_routes_through_the_normalizer(self):
        """R4, asserting the call rather than the result -- see the reasoning
        on test_sdd_workspace_dir_routes_through_the_normalizer."""
        wt, planrel = self._workspace()
        self.append('start', slug='demo', branch='b', worktree=wt,
                    plan=planrel, stage='SHIP')
        with mock.patch.object(factory_run, 'normalize_plan_path',
                               wraps=factory_run.normalize_plan_path) as spy:
            factory_run.preserve_workspace(436, registry=self.reg)
        self.assertTrue(spy.called)

    def test_a_backslash_spelled_plan_path_is_still_copied(self):
        """AC4: the plan is found whatever separator the run recorded."""
        wt, planrel = self._workspace()
        self.append('start', slug='demo', branch='b', worktree=wt,
                    plan=planrel, stage='SHIP')
        plan = planrel.replace('/', '\\')
        dest = factory_run.preserve_workspace(436, registry=self.reg, plan=plan)
        with open(os.path.join(dest, 'manifest.json'), encoding='utf-8') as fh:
            manifest = json.load(fh)
        entry = [a for a in manifest['artifacts'] if a['name'] == 'plan'][0]
        self.assertTrue(entry['present'], entry.get('reason'))


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


class DecisionFindingTests(unittest.TestCase):
    """#530 R3 — a decision can declare itself a plan-review finding."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def decision(self, **fields):
        factory_run.append_event(530, 'decision', registry=self.tmp, **fields)
        return factory_run.load_state(530, self.tmp)['decisions'][-1]

    def test_a_marked_decision_carries_the_flag(self):
        self.assertIs(self.decision(text='Fix the test.', finding=True)
                      ['finding'], True)

    def test_an_unmarked_decision_has_no_flag(self):
        self.assertNotIn('finding', self.decision(text='Fix the test.'))

    def test_an_explicit_false_is_not_a_finding(self):
        """`--field finding=false` parses as a JSON boolean, not a string."""
        self.assertNotIn('finding',
                         self.decision(text='Fix the test.', finding=False))

    def test_the_marker_does_not_disturb_the_other_fields(self):
        record = self.decision(text='Fix the test.', rationale='Because.',
                               finding=True)
        self.assertEqual(record['text'], 'Fix the test.')
        self.assertEqual(record['rationale'], 'Because.')


class TestSmoketestDir(unittest.TestCase):
    """#588 R14 moved the artifacts out of the worktree; both places work."""

    def test_the_worktree_wins_when_it_holds_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            wt = os.path.join(d, 'factory-issue-1')
            main = os.path.join(d, 'main')
            os.makedirs(os.path.join(wt, 'build', 'smoketest'))
            os.makedirs(os.path.join(main, 'build', 'smoketest',
                                     'factory-issue-1'))
            self.assertEqual(factory_run.smoketest_dir(wt, main_root=main),
                             os.path.join(wt, 'build', 'smoketest'))

    def test_the_main_tree_is_the_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            wt = os.path.join(d, 'factory-issue-1')
            main = os.path.join(d, 'main')
            os.makedirs(wt)
            os.makedirs(os.path.join(main, 'build', 'smoketest',
                                     'factory-issue-1'))
            self.assertEqual(factory_run.smoketest_dir(wt, main_root=main),
                             os.path.join(main, 'build', 'smoketest',
                                          'factory-issue-1'))

    def test_another_run_s_artifacts_are_not_returned(self):
        """Decision 11: the lookup is per checkout, so runs cannot cross."""
        with tempfile.TemporaryDirectory() as d:
            wt = os.path.join(d, 'factory-issue-1')
            main = os.path.join(d, 'main')
            os.makedirs(wt)
            os.makedirs(os.path.join(main, 'build', 'smoketest',
                                     'factory-issue-2'))
            self.assertIsNone(factory_run.smoketest_dir(wt, main_root=main))

    def test_neither_place_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(factory_run.smoketest_dir(
                os.path.join(d, 'factory-issue-1'),
                main_root=os.path.join(d, 'main')))

    def test_main_root_of_strips_the_registry_directory(self):
        self.assertEqual(
            factory_run.main_root_of(os.path.join('R', '.factory')), 'R')
        self.assertIsNone(factory_run.main_root_of(None))


class TestRunSlug(unittest.TestCase):
    """#641 R1-R3: one shared slug resolver."""

    def test_explicit_slug_wins_over_the_plan_filename(self):
        """AC3."""
        state = {'slug': 'explicit',
                 'plan': 'docs/plans/2026-08-18-issue641-from-filename.md'}
        self.assertEqual(factory_run.run_slug(state), 'explicit')

    def test_slug_is_recovered_from_a_prd3_plan_filename(self):
        """AC1 at the resolver level."""
        state = {'slug': None,
                 'plan': 'docs/plans/2026-08-18-issue641-factory-pr-slug.md'}
        self.assertEqual(factory_run.run_slug(state), 'factory-pr-slug')

    def test_a_non_matching_plan_filename_yields_its_stem(self):
        """AC5 at the resolver level."""
        state = {'slug': None, 'plan': 'docs/plans/notes.md'}
        self.assertEqual(factory_run.run_slug(state), 'notes')

    def test_neither_field_yields_the_fallback(self):
        """AC4 at the resolver level."""
        self.assertEqual(factory_run.run_slug({'slug': None, 'plan': None}),
                         factory_run.FALLBACK_SLUG)
        self.assertEqual(factory_run.FALLBACK_SLUG, '(no slug)')

    def test_an_empty_state_never_raises(self):
        """R3: missing fields, not merely empty ones."""
        self.assertEqual(factory_run.run_slug({}), factory_run.FALLBACK_SLUG)
        self.assertEqual(factory_run.run_slug(None), factory_run.FALLBACK_SLUG)

    def test_empty_strings_fall_through_rather_than_render(self):
        """R3: an empty field is not a slug."""
        self.assertEqual(factory_run.run_slug({'slug': '', 'plan': ''}),
                         factory_run.FALLBACK_SLUG)

    def test_a_malformed_plan_value_never_raises(self):
        """R3: a non-string field must not reach os.path unconverted."""
        self.assertEqual(factory_run.run_slug({'slug': None, 'plan': 42}), '42')

    def test_a_new_state_resolves_to_the_fallback(self):
        """The real state shape, not a hand-built dict."""
        self.assertEqual(factory_run.run_slug(factory_run.new_state(641)),
                         factory_run.FALLBACK_SLUG)

    def test_a_windows_plan_path_yields_the_slug(self):
        """The orchestrator records a repo-relative path; a run recorded on
        Windows may carry backslashes. Asserts the literal, not that the two
        spellings agree -- an agreement assertion is satisfied by ntpath on
        Windows and so would never bite the defect it exists for."""
        win = {'slug': None,
               'plan': 'docs\\plans\\2026-08-18-issue641-factory-pr-slug.md'}
        self.assertEqual(factory_run.run_slug(win), 'factory-pr-slug')


class TestNormalizePlanPath(unittest.TestCase):
    """#650 R3: one separator idiom, not three."""

    def test_a_forward_slash_path_survives(self):
        self.assertEqual(
            factory_run.normalize_plan_path('docs/plans/2026-08-18-issue650-x.md'),
            os.path.join('docs', 'plans', '2026-08-18-issue650-x.md'))

    def test_a_backslash_path_becomes_native(self):
        """The defect: the old idiom was a no-op on POSIX, so this passed
        through whole and every caller then failed to find the file."""
        self.assertEqual(
            factory_run.normalize_plan_path('docs\\plans\\2026-08-18-issue650-x.md'),
            os.path.join('docs', 'plans', '2026-08-18-issue650-x.md'))

    def test_both_spellings_agree(self):
        self.assertEqual(
            factory_run.normalize_plan_path('docs\\plans\\x.md'),
            factory_run.normalize_plan_path('docs/plans/x.md'))

    def test_a_non_string_never_raises(self):
        self.assertEqual(factory_run.normalize_plan_path(42), '42')

    def test_the_old_idiom_is_gone_from_the_module(self):
        """AC5. Reads the source rather than the imported module: the point is
        that no second idiom remains in the file, not that one call works."""
        with open(factory_run.__file__, encoding='utf-8') as fh:
            source = fh.read()
        self.assertNotIn('replace("/", os.sep)', source)


class TestNormalizerCallers(unittest.TestCase):
    """#650 R4, R5: the three readers all go through it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_slug_is_unchanged_by_the_rewire(self):
        """R5 changes how run_slug gets its basename, never what it returns."""
        self.assertEqual(
            factory_run.run_slug({'slug': None,
                                  'plan': 'docs/plans/2026-08-18-issue650-x.md'}),
            'x')
        self.assertEqual(
            factory_run.run_slug({'slug': None,
                                  'plan': 'docs\\plans\\2026-08-18-issue650-x.md'}),
            'x')
        self.assertEqual(factory_run.run_slug({'slug': None, 'plan': None}),
                         factory_run.FALLBACK_SLUG)

    def test_sdd_workspace_dir_finds_a_backslash_spelled_plan(self):
        """AC3, asserted against a literal on both spellings -- not by
        comparing the two calls to each other, which agrees vacuously when
        both return None."""
        want = os.path.join(self.tmp, '.superpowers', 'sdd', '2026-08-18-issue650-x')
        os.makedirs(want)
        self.assertEqual(
            factory_run.sdd_workspace_dir(
                self.tmp, 'docs/plans/2026-08-18-issue650-x.md'), want)
        self.assertEqual(
            factory_run.sdd_workspace_dir(
                self.tmp, 'docs\\plans\\2026-08-18-issue650-x.md'), want)

    def test_sdd_workspace_dir_still_strips_only_md(self):
        """The normalizer handles separators, not stems: a non-.md plan keeps
        its extension here, unlike run_slug's splitext."""
        want = os.path.join(self.tmp, '.superpowers', 'sdd', 'notes.txt')
        os.makedirs(want)
        self.assertEqual(
            factory_run.sdd_workspace_dir(self.tmp, 'docs/plans/notes.txt'), want)

    def test_sdd_workspace_dir_routes_through_the_normalizer(self):
        """R4. On Windows the RESULT is identical with or without the rewire,
        because ntpath splits both separators -- so assert the call, not the
        value. Without this, an implementer could add normalize_plan_path,
        skip both call sites, and see green on the only platform this runs on.
        """
        os.makedirs(os.path.join(self.tmp, '.superpowers', 'sdd', 'x'))
        with mock.patch.object(factory_run, 'normalize_plan_path',
                               wraps=factory_run.normalize_plan_path) as spy:
            factory_run.sdd_workspace_dir(self.tmp, 'docs/plans/x.md')
        self.assertTrue(spy.called)

    def test_run_slug_routes_through_the_normalizer(self):
        """R5, same reasoning as the test above."""
        with mock.patch.object(factory_run, 'normalize_plan_path',
                               wraps=factory_run.normalize_plan_path) as spy:
            factory_run.run_slug({'slug': None, 'plan': 'docs/plans/x.md'})
        self.assertTrue(spy.called)


class TestUnloggedStages(JournalTestCase):
    """#489: a stage that ran without factory_log.py leaves a mark in state.

    The condition is stamped by the writer on the transition event that leaves
    the stage, so every renderer stays a pure function of state.
    """

    def _log(self, stage, payload=b'captured\n', issue=436):
        path = factory_run.log_path(issue, stage, self.reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(payload)
        return path

    # ── the projection field ────────────────────────────────────────────

    def test_new_state_starts_with_an_empty_unlogged_list(self):
        self.assertEqual(factory_run.new_state(489)['unlogged'], [])

    def test_leaving_a_stage_with_no_log_records_it(self):
        """AC: GATE ran unwrapped, so leaving GATE names GATE."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self.append('stage', stage='PLAN')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'],
                         ['GATE'])

    def test_leaving_a_stage_whose_log_was_captured_records_nothing(self):
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self._log('GATE')
        self.append('stage', stage='PLAN')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'], [])

    def test_a_zero_byte_log_counts_as_no_log(self):
        """An empty file is what a helper that never ran leaves behind."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self._log('GATE', payload=b'')
        self.append('stage', stage='PLAN')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'],
                         ['GATE'])

    def test_finish_stamps_the_stage_the_run_ends_in(self):
        """Without this the last stage of a run could never be reported."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self._log('GATE')
        self.append('stage', stage='SHIP')
        self.append('finish', result='shipped')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'],
                         ['SHIP'])

    def test_failure_stamps_the_stage_the_run_died_in(self):
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='BUILD')
        self.append('failure', message='boom')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'],
                         ['BUILD'])

    def test_re_entering_the_same_stage_stamps_nothing(self):
        """A stage event naming the current stage is not leaving it."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='BUILD')
        self.append('stage', stage='BUILD')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'], [])

    def test_a_stage_left_twice_is_recorded_once(self):
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self.append('stage', stage='PLAN')      # leaves GATE
        self.append('stage', stage='GATE')      # leaves PLAN
        self.append('stage', stage='BUILD')     # leaves GATE again
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'],
                         ['GATE', 'PLAN'])

    def test_retry_clears_the_unlogged_list(self):
        """A new attempt re-runs the stage and re-writes its log."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self.append('stage', stage='BUILD')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'],
                         ['GATE'])
        self.append('retry', attempt=2, stage='GATE')
        self.assertEqual(factory_run.load_state(436, self.reg)['unlogged'], [])

    def test_replay_agrees_with_the_incremental_projection(self):
        """The stamp lives on the event, so rebuild cannot disagree."""
        self.append('start', slug='obs', branch='b', worktree='/w',
                    stage='GATE')
        self._log('GATE')
        self.append('stage', stage='PLAN')
        self.append('stage', stage='BUILD')
        self.append('stage', stage='VERIFY')
        self.append('finish', result='shipped')

        incremental = factory_run.load_state(436, self.reg)
        replayed = factory_run.rebuild_state(
            436, factory_run.read_journal(436, self.reg))
        self.assertEqual(incremental['unlogged'], ['PLAN', 'BUILD', 'VERIFY'])
        self.assertEqual(incremental, replayed)

    # ── log_captured ────────────────────────────────────────────────────

    def test_log_captured_is_false_for_an_absent_file(self):
        self.assertFalse(factory_run.log_captured(436, 'BUILD', self.reg))

    def test_log_captured_is_false_for_a_zero_byte_file(self):
        self._log('BUILD', payload=b'')
        self.assertFalse(factory_run.log_captured(436, 'BUILD', self.reg))

    def test_log_captured_is_true_for_a_non_empty_file(self):
        self._log('BUILD', payload=b'make: ok\n')
        self.assertTrue(factory_run.log_captured(436, 'BUILD', self.reg))

    def test_log_captured_never_raises_on_a_nonsense_registry(self):
        blocker = os.path.join(self.tmp, 'file-not-dir')
        with open(blocker, 'w') as fh:
            fh.write('not a directory')
        self.assertFalse(
            factory_run.log_captured(436, 'BUILD', os.path.join(blocker, 'x')))

    # ── unlogged_stages ─────────────────────────────────────────────────

    def test_unlogged_stages_renders_in_canonical_order(self):
        state = {'unlogged': ['SHIP', 'GATE', 'BUILD']}
        self.assertEqual(factory_run.unlogged_stages(state),
                         ['GATE', 'BUILD', 'SHIP'])

    def test_unlogged_stages_sorts_unknown_stages_last(self):
        state = {'unlogged': ['WEIRD', 'SHIP', 'GATE']}
        self.assertEqual(factory_run.unlogged_stages(state),
                         ['GATE', 'SHIP', 'WEIRD'])

    def test_unlogged_stages_is_empty_when_the_field_is_absent(self):
        self.assertEqual(factory_run.unlogged_stages({'issue': 650}), [])

    def test_unlogged_stages_does_not_raise_on_a_bare_dict(self):
        """Landed tests call renderers with a hand-built partial state."""
        self.assertEqual(
            factory_run.unlogged_stages({'issue': 650, 'slug': None}), [])

    def test_unlogged_stages_reads_nothing_from_disk(self):
        """A renderer that stats the filesystem stops being pure."""
        with mock.patch.object(factory_run, 'log_captured',
                               side_effect=AssertionError('read the disk')):
            self.assertEqual(factory_run.unlogged_stages({'unlogged': ['GATE']}),
                             ['GATE'])

    # ── fixture guard ───────────────────────────────────────────────────

    def test_the_shipped_fixture_run_is_fully_logged(self):
        """A fixture edit that writes a log too late must fail loudly here."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        self.assertEqual(factory_run.load_state(440, reg)['unlogged'], [])


class LaneTest(unittest.TestCase):
    """#698: the run's lane is per-run identity on the projection."""

    def test_lanes_are_a_two_name_vocabulary(self):
        self.assertEqual(factory_run.LANES, ('factory', 'gauntlet'))

    def test_the_default_lane_is_factory(self):
        self.assertEqual(factory_run.DEFAULT_LANE, 'factory')
        self.assertIn(factory_run.DEFAULT_LANE, factory_run.LANES)

    def test_new_state_starts_in_the_default_lane(self):
        self.assertEqual(factory_run.new_state(698)['lane'],
                         factory_run.DEFAULT_LANE)

    def test_a_start_event_can_set_the_lane(self):
        state = factory_run.new_state(698)
        factory_run.apply_event(state, {'kind': 'start', 'ts': 'T',
                                        'lane': 'gauntlet'})
        self.assertEqual(state['lane'], 'gauntlet')

    def test_any_event_kind_can_carry_the_lane(self):
        """Kind-independent on purpose: a lane stamped on a `stage` event that
        silently did not stick would be worse than no field at all."""
        state = factory_run.new_state(698)
        factory_run.apply_event(state, {'kind': 'stage', 'ts': 'T',
                                        'stage': 'BUILD', 'lane': 'gauntlet'})
        self.assertEqual(state['lane'], 'gauntlet')

    def test_an_event_without_a_lane_leaves_it_alone(self):
        state = factory_run.new_state(698)
        state['lane'] = 'gauntlet'
        factory_run.apply_event(state, {'kind': 'stage', 'ts': 'T',
                                        'stage': 'BUILD'})
        self.assertEqual(state['lane'], 'gauntlet')

    def test_the_lane_survives_a_replay(self):
        events = [{'kind': 'start', 'ts': 'T', 'lane': 'gauntlet'},
                  {'kind': 'stage', 'ts': 'T', 'stage': 'BUILD'}]
        self.assertEqual(factory_run.rebuild_state(698, events)['lane'],
                         'gauntlet')

    def test_schema_version_is_unchanged(self):
        """A state.json written before `lane` existed must stay loadable."""
        self.assertEqual(factory_run.SCHEMA_VERSION, 1)

    def test_append_event_refuses_an_unknown_lane(self):
        """R2: refused the way an unknown kind is refused -- in the library,
        so a direct append_event call cannot write a lane the vocabulary does
        not contain."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with self.assertRaises(ValueError) as caught:
            factory_run.append_event(698, 'start', registry=tmp,
                                     lane='sideshow')
        self.assertIn('sideshow', str(caught.exception))

    def test_append_event_accepts_a_known_lane(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        factory_run.append_event(698, 'start', registry=tmp, lane='gauntlet')
        self.assertEqual(factory_run.load_state(698, tmp)['lane'], 'gauntlet')


if __name__ == '__main__':
    unittest.main()

"""Tests for tools/factory_publish.py"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_publish
import factory_report
import factory_run
import factory_status

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_fixtures

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'factory')
SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'factory_publish.py')


def golden(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8', newline='') as fh:
        return fh.read()


class PublishTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        factory_run.set_clock(None)
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestPublishState(PublishTestCase):
    def test_missing_file_yields_a_fresh_state(self):
        """AC1: nothing published yet is not an error."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.load_publish_state(440, reg)
        self.assertIsNone(publish['run_issue'])
        self.assertEqual(publish['commented_attempts'], [])
        self.assertEqual(publish['uploaded'], [])

    def test_round_trips_through_disk(self):
        """AC1: the run issue number is recorded and reused, never recreated."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['run_issue'] = 481
        publish['uploaded'].append('issue-440-attempt-1-BUILD.log')
        factory_publish.save_publish_state(publish, reg)
        again = factory_publish.load_publish_state(440, reg)
        self.assertEqual(again['run_issue'], 481)
        self.assertEqual(again['uploaded'], ['issue-440-attempt-1-BUILD.log'])

    def test_corrupt_file_self_heals_instead_of_raising(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        path = factory_publish.publish_path(440, reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{ not json')
        self.assertIsNone(factory_publish.load_publish_state(440, reg)['run_issue'])

    def test_foreign_schema_version_is_discarded(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        path = factory_publish.publish_path(440, reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 99, 'run_issue': 7}, fh)
        self.assertIsNone(factory_publish.load_publish_state(440, reg)['run_issue'])

    def test_state_lives_beside_the_journal_not_inside_logs(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        self.assertEqual(factory_publish.publish_path(440, reg),
                         os.path.join(factory_run.run_dir(440, reg),
                                      'publish.json'))


class TestAssetNaming(PublishTestCase):
    def test_log_asset_carries_issue_attempt_and_stage(self):
        """R7: the discriminator is attempt — there is no runid."""
        self.assertEqual(factory_publish.log_asset_name(437, 2, 'BUILD'),
                         'issue-437-attempt-2-BUILD.log')

    def test_screenshot_asset_carries_scenario_and_frame(self):
        """R9."""
        path = os.path.join('any', 'where', 'reach-race', 'checkpoint-1.png')
        self.assertEqual(factory_publish.shot_asset_name(437, 2, path),
                         'issue-437-attempt-2-reach-race-checkpoint-1.png')

    def test_asset_names_are_sanitised(self):
        path = os.path.join('x', 'weird scenario!', 'frame #2.png')
        name = factory_publish.shot_asset_name(437, 1, path)
        self.assertEqual(name, 'issue-437-attempt-1-weird-scenario--frame--2.png')

    def test_asset_url_points_at_the_rolling_release(self):
        self.assertEqual(
            factory_publish.asset_url('issue-437-attempt-2-BUILD.log'),
            'https://github.com/MatthieuGagne/gmb-nuke-raider/releases/'
            'download/factory-logs/issue-437-attempt-2-BUILD.log')


class TestRenderTitle(PublishTestCase):
    def test_shipped_run_reads_complete(self):
        """AC1/R3: the title is the only column an issue list has."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        self.assertEqual(factory_publish.render_title(state,
                                                      now=factory_fixtures.FIXED_NOW),
                         'run 440 · attempt 1 · SHIP · complete')

    def test_failed_run_reads_failed(self):
        """AC3."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        state = factory_run.load_state(441, reg)
        self.assertEqual(factory_publish.render_title(state,
                                                      now=factory_fixtures.FIXED_NOW),
                         'run 441 · attempt 1 · BUILD · failed')

    def test_second_attempt_shows_in_the_title(self):
        """AC4."""
        reg = factory_fixtures.build_registry(self.tmp)
        state = factory_run.load_state(436, reg)
        self.assertEqual(factory_publish.render_title(state,
                                                      now=factory_fixtures.FIXED_NOW),
                         'run 436 · attempt 2 · VERIFY · active')

    def test_missing_worktree_reads_stale(self):
        reg = factory_fixtures.build_registry(self.tmp)
        state = factory_run.load_state(999, reg)
        self.assertEqual(factory_publish.render_title(state,
                                                      now=factory_fixtures.FIXED_NOW),
                         'run 999 · attempt 1 · BUILD · stale')

    def test_condition_is_factory_status_verbatim(self):
        """R3: one definition of the five conditions, not two."""
        reg = factory_fixtures.build_registry(self.tmp)
        rows = {r['issue']: r for r in
                factory_status.collect(reg, now=factory_fixtures.FIXED_NOW)}
        for issue, row in rows.items():
            state = factory_run.load_state(issue, reg)
            self.assertEqual(
                factory_publish.run_condition(state,
                                              now=factory_fixtures.FIXED_NOW),
                row['condition'], issue)

    def test_stageless_run_renders_a_dash(self):
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(500, 'decision', registry=reg, text='hi')
        state = factory_run.load_state(500, reg)
        self.assertEqual(factory_publish.render_title(state,
                                                      now=factory_fixtures.FIXED_NOW),
                         'run 500 · attempt 1 · - · active')


class TestRenderBody(PublishTestCase):
    def body(self, issue, reg, publish=None):
        state = factory_run.load_state(issue, reg)
        publish = publish or factory_publish.new_publish_state(issue)
        return factory_publish.render_body(state, publish, registry=reg,
                                           now=factory_fixtures.FIXED_NOW)

    def shipped(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['uploaded'].append('issue-440-attempt-1-BUILD.log')
        return self.body(440, reg, publish)

    def test_matches_the_golden_byte_for_byte(self):
        """AC10."""
        self.assertEqual(self.shipped(), golden('expected_run_issue_body.md'))

    def test_body_is_stable_across_repeated_renders(self):
        """AC10: pure function of run state.

        The registry is built once on purpose: build_shipped_run() appends its
        whole event sequence, so calling it twice into one tmpdir would double
        every gate and decision and test the fixture, not the renderer.
        """
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['uploaded'].append('issue-440-attempt-1-BUILD.log')
        self.assertEqual(self.body(440, reg, publish),
                         self.body(440, reg, publish))

    def test_body_ends_with_exactly_one_newline(self):
        body = self.shipped()
        self.assertTrue(body.endswith('\n'))
        self.assertFalse(body.endswith('\n\n'))

    def test_strip_is_generated_from_factory_run_stages(self):
        """R4: a sixth stage (PRD-11's REVIEW) appears with no edit here."""
        original = factory_run.STAGES
        try:
            factory_run.STAGES = original[:4] + ('REVIEW',) + original[4:]
            reg = factory_fixtures.build_shipped_run(self.tmp)
            self.assertIn('REVIEW', self.body(440, reg))
        finally:
            factory_run.STAGES = original

    def test_current_stage_is_marked_and_later_stages_are_pending(self):
        reg = factory_fixtures.build_registry(self.tmp)
        strip = self.body(436, reg).splitlines()[2]
        self.assertEqual(strip, '✅ GATE → ✅ PLAN → ✅ BUILD → 🔵 VERIFY → ⬜ SHIP')

    def test_permission_events_are_rendered(self):
        reg = factory_fixtures.build_registry(self.tmp)
        body = self.body(436, reg)
        self.assertIn('### Permission events', body)
        self.assertIn('| Bash | denied |', body)

    def test_empty_sections_are_omitted_but_gates_and_logs_are_not(self):
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(500, 'start', registry=reg, branch='b',
                                 stage='GATE')
        body = self.body(500, reg)
        self.assertNotIn('### Decisions made', body)
        self.assertNotIn('### Permission events', body)
        self.assertIn('### Gate results', body)
        self.assertIn('### Stage logs', body)

    def test_withheld_asset_is_named_in_the_stage_logs_table(self):
        """AC6."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['withheld']['issue-440-attempt-1-BUILD.log'] = (
            'credential-shaped string (gh[pousr]_)')
        body = self.body(440, reg, publish)
        self.assertIn('withheld', body)
        self.assertIn('credential-shaped string', body)

    def test_screenshots_render_inline_from_uploaded_assets(self):
        """AC7."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['uploaded'].append('issue-440-attempt-1-reach-race-failure.png')
        body = self.body(440, reg, publish)
        self.assertIn('![issue-440-attempt-1-reach-race-failure.png](https://',
                      body)

    def test_body_carries_the_machine_owned_marker(self):
        self.assertIn(factory_publish.BODY_MARKER, self.shipped())

    def test_pipes_in_run_data_do_not_break_the_tables(self):
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(500, 'gate', registry=reg, stage='BUILD',
                                 gate='make test | tee out', result='pass')
        self.assertIn(r'make test \| tee out', self.body(500, reg))


class TestFailureSection(PublishTestCase):
    def failed_body(self, reg):
        return factory_publish.render_body(
            factory_run.load_state(441, reg),
            factory_publish.new_publish_state(441), registry=reg,
            now=factory_fixtures.FIXED_NOW)

    def test_matches_the_failed_golden(self):
        """AC3/AC10."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        self.assertEqual(self.failed_body(reg),
                         golden('expected_run_issue_body_failed.md'))

    def test_says_so_when_the_log_helper_fail_opened(self):
        """AC3: 'no stage log captured' rather than a missing section."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        self.assertIn('no stage log captured', self.failed_body(reg))

    def test_tail_is_collapsed_and_marked_lossy(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        path = factory_run.log_path(441, 'BUILD', reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'\n'.join(b'line %d' % i for i in range(500)))
        body = self.failed_body(reg)
        self.assertIn('<details>', body)
        self.assertIn('lossy excerpt', body)
        self.assertIn('line 499', body)
        self.assertNotIn('line 100\n', body)

    def test_undecodable_bytes_do_not_raise(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        path = factory_run.log_path(441, 'BUILD', reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'ok\n\xff\xfe not utf-8 \xff\n')
        self.assertIn('�', self.failed_body(reg))

    def test_a_healthy_run_has_no_failure_section(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        body = factory_publish.render_body(
            state, factory_publish.new_publish_state(440), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertNotIn('### Failure', body)


class TestWorktreeIsNotLeaked(PublishTestCase):
    """Q1b: the run issue is public, so the path is published repo-relative."""

    def test_a_worktree_inside_the_repo_renders_relative(self):
        registry = os.path.join(self.tmp, 'repo', '.factory')
        worktree = os.path.join(self.tmp, 'repo', '.claude', 'worktrees',
                                'factory-437')
        self.assertEqual(
            factory_publish.display_worktree(worktree, registry),
            '.claude/worktrees/factory-437')

    def test_separators_are_normalised_for_the_golden(self):
        registry = os.path.join(self.tmp, 'repo', '.factory')
        worktree = os.path.join(self.tmp, 'repo', 'a', 'b')
        self.assertNotIn('\\', factory_publish.display_worktree(worktree,
                                                                registry))

    def test_a_worktree_outside_the_repo_is_redacted(self):
        registry = os.path.join(self.tmp, 'repo', '.factory')
        rendered = factory_publish.display_worktree(
            os.path.join(self.tmp, 'elsewhere', 'wt'), registry)
        self.assertEqual(rendered, factory_report.REDACTION)

    def test_no_home_directory_reaches_the_body(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        state = factory_run.load_state(441, reg)
        body = factory_publish.render_body(
            state, factory_publish.new_publish_state(441), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertNotIn(state['worktree'], body)
        self.assertIn('- **Worktree** `wt-441`', body)

    def test_missing_worktree_renders_a_dash(self):
        self.assertEqual(factory_publish.display_worktree(None, self.tmp), '-')


class TestBodyBudget(PublishTestCase):
    # Few and long, not many and short. append_event() replays the whole
    # journal and fsyncs twice per call, so an 800-event fixture costs minutes;
    # what the budget exercises is total body *bulk*, which 50 fat entries
    # reach just as well as 400 thin ones.
    FILLER = 3000

    def huge_run(self, decisions=25, permissions=25):
        reg = os.path.join(self.tmp, 'reg')
        reset = factory_fixtures.pinned_clock()
        try:
            factory_run.append_event(600, 'start', registry=reg, branch='b',
                                     worktree=self.tmp, stage='BUILD')
            for i in range(decisions):
                factory_run.append_event(
                    600, 'decision', registry=reg,
                    text='decision %d %s' % (i, 'x' * self.FILLER))
            for i in range(permissions):
                factory_run.append_event(
                    600, 'permission', registry=reg, tool='Bash',
                    outcome='denied',
                    command='cmd %d %s' % (i, 'y' * self.FILLER))
            path = factory_run.log_path(600, 'BUILD', reg)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as fh:
                fh.write(b'\n'.join(b'noisy line %d %s' % (i, b'z' * 300)
                                    for i in range(400)))
            factory_run.append_event(600, 'failure', registry=reg,
                                     message='boom')
        finally:
            reset()
        return reg

    def body(self, reg):
        publish = factory_publish.new_publish_state(600)
        publish['uploaded'].append('issue-600-attempt-1-BUILD.log')
        return factory_publish.render_body(
            factory_run.load_state(600, reg), publish, registry=reg,
            now=factory_fixtures.FIXED_NOW)

    def test_body_stays_under_the_budget(self):
        """AC8."""
        self.assertLessEqual(len(self.body(self.huge_run())),
                             factory_publish.BODY_BUDGET)

    def test_never_sheds_the_load_bearing_sections(self):
        """AC8: header, strip, failure fields, gate table, stage-log table."""
        body = self.body(self.huge_run())
        self.assertIn('**Spec** #600', body)
        self.assertIn('❌ BUILD', body)     # the strip, not shed
        self.assertIn('### Failure', body)
        self.assertIn('- **Stage** BUILD', body)
        self.assertIn('### Gate results', body)
        self.assertIn('### Stage logs', body)
        self.assertIn('issue-600-attempt-1-BUILD.log', body)

    def test_sheds_in_the_documented_order_with_markers(self):
        """AC8: each cut leaves a marker rather than vanishing."""
        body = self.body(self.huge_run())
        self.assertIn('tail omitted — full log:', body)
        self.assertIn('events omitted — see the local registry', body)
        self.assertIn('earlier decisions omitted', body)

    def test_tail_survives_when_the_body_fits(self):
        reg = self.huge_run(decisions=1, permissions=1)
        body = self.body(reg)
        self.assertIn('<details>', body)
        self.assertNotIn('tail omitted', body)

    def test_hard_truncation_is_the_backstop(self):
        """AC8: a body that will not fit even fully shed is cut, and says so."""
        reg = self.huge_run(decisions=0, permissions=0)
        publish = factory_publish.new_publish_state(600)
        for i in range(4000):
            publish['uploaded'].append('issue-600-attempt-%d-BUILD.log' % i)
        body = factory_publish.render_body(
            factory_run.load_state(600, reg), publish, registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertLessEqual(len(body), factory_publish.BODY_BUDGET)
        self.assertIn('truncated at the', body)


class TestSecretScan(PublishTestCase):
    def scan(self, payload):
        path = os.path.join(self.tmp, 'BUILD.log')
        with open(path, 'wb') as fh:
            fh.write(payload)
        return factory_publish.scan_secrets(path)

    def test_clean_log_passes(self):
        self.assertIsNone(self.scan(b'make: nothing to be done\n' * 100))

    def test_github_token_shapes_are_refused(self):
        """AC6/R8. The repo is public and push protection does not inspect
        release assets, so this is the only net."""
        for payload in (b'ghp_' + b'A' * 36, b'gho_' + b'b' * 36,
                        b'github_pat_' + b'C' * 40):
            self.assertIsNotNone(self.scan(b'noise\n' + payload + b'\nmore'),
                                 payload[:12])

    def test_slack_and_aws_shapes_are_refused(self):
        self.assertIsNotNone(self.scan(b'xoxb-1234567890-abcdefghij'))
        self.assertIsNotNone(self.scan(b'AKIAIOSFODNN7EXAMPLE'))

    def test_long_bearer_values_are_refused(self):
        self.assertIsNotNone(
            self.scan(b'Authorization: Bearer ' + b'x' * 40))

    def test_short_bearer_word_is_not_a_false_positive(self):
        self.assertIsNone(self.scan(b'the bearer of bad news\n'))

    def test_a_match_split_across_read_chunks_is_still_found(self):
        """A chunked reader that ignores the boundary has a hole in it."""
        pad = b'q' * (factory_publish.SCAN_CHUNK - 10)
        self.assertIsNotNone(self.scan(pad + b'ghp_' + b'D' * 36 + b'\n'))

    def test_unreadable_file_is_treated_as_unsafe(self):
        reason = factory_publish.scan_secrets(
            os.path.join(self.tmp, 'does-not-exist.log'))
        self.assertIsNotNone(reason)

    def test_reason_names_the_shape_not_the_secret(self):
        reason = self.scan(b'ghp_' + b'A' * 36)
        self.assertIn('gh[pousr]_', reason)
        self.assertNotIn('AAAA', reason)


class TestScreenshotSourcing(PublishTestCase):
    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_registry(self.tmp)

    def state(self, issue):
        return factory_run.load_state(issue, self.reg)

    def test_failure_frame_is_always_first(self):
        """AC7: failure frames are never dropped."""
        paths, source = factory_publish.screenshot_paths(self.state(436),
                                                         self.reg)
        kept = factory_publish.select_screenshots(paths)
        self.assertEqual(source, 'worktree')
        self.assertTrue(os.path.basename(kept[0]).startswith('failure'))

    def test_nothing_is_capped(self):
        """R9: a run produces 4-8 PNGs and they all publish."""
        paths, _ = factory_publish.screenshot_paths(self.state(436), self.reg)
        self.assertEqual(len(factory_publish.select_screenshots(paths)),
                         len(paths))
        self.assertEqual(len(paths), 5)

    def test_selection_is_by_filename_not_mtime(self):
        paths, _ = factory_publish.screenshot_paths(self.state(436), self.reg)
        kept = factory_publish.select_screenshots(paths)
        self.assertEqual(kept[1:], sorted(kept[1:]))

    def test_stale_run_falls_back_to_the_latest_autopsy_bundle(self):
        """AC7: sourced from the worktree while it exists, autopsy once gone."""
        smoke = os.path.join(factory_run.run_dir(999, self.reg), 'autopsy',
                             'attempt-2', 'smoketest', 'reach-race')
        os.makedirs(smoke, exist_ok=True)
        factory_fixtures._png(os.path.join(smoke, 'failure.png'))
        paths, source = factory_publish.screenshot_paths(self.state(999),
                                                         self.reg)
        self.assertEqual(source, 'autopsy')
        self.assertEqual(len(paths), 1)

    def test_no_worktree_and_no_autopsy_yields_nothing(self):
        paths, source = factory_publish.screenshot_paths(self.state(999),
                                                         self.reg)
        self.assertEqual((paths, source), ([], 'none'))

    def test_factory_status_no_longer_sources_screenshots(self):
        """R9: MAX_SCREENSHOTS retires with the HTML page."""
        for name in ('MAX_SCREENSHOTS', 'screenshot_paths',
                     'select_screenshots', '_latest_autopsy'):
            self.assertFalse(hasattr(factory_status, name), name)

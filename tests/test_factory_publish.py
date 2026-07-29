"""Tests for tools/factory_publish.py"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_publish
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

"""Tests for tools/factory_publish.py"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr

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

    def test_a_build_failure_renders_real_command_output(self):
        """#654 AC3/AC4: the tail replaces the placeholder once a log exists."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        path = factory_run.log_path(441, 'BUILD', reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'tests/test_factory_run.py .. FAIL\n'
                     b'AssertionError: expected 3, got 4\n')
        dest = factory_run.write_autopsy(
            441, registry=reg,
            worktree=factory_run.load_state(441, reg)['worktree'])

        # AC4 is a claim about a bundle AND a tail, so assert both. Without
        # the manifest assertion the write_autopsy call is decorative: the
        # tail is read straight from the registry and does not need it.
        self.assertTrue(os.path.isfile(os.path.join(dest, 'manifest.json')))
        body = self.failed_body(reg)
        self.assertNotIn('no stage log captured', body)
        self.assertIn('AssertionError: expected 3, got 4', body)
        self.assertIn('lossy excerpt', body)


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
        self.assertIn('log tail —', body)
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


def big_plan(tasks=8, filler=300):
    """A plan the size of a real one, with headings hidden inside fences.

    docs/plans/2026-08-01-issue471-adversarial-review-stage.md is 3199 lines
    and quotes whole markdown documents inside ```` blocks. The fenced
    'Task 999' and 'Smoketest Checkpoint 9' lines below are what a scanner
    that ignores fences trips over.
    """
    lines = ['# Demo Implementation Plan', '',
             '**Issue:** #514', '',
             '**Goal:** demonstrate the structural summary.', '',
             '**Architecture:** one module, three layers.', '',
             '## Global Constraints', '',
             '- Python 3 stdlib only.', '',
             '## File Structure', '',
             '- `tools/factory_publish.py` — the publisher.', '']
    for n in range(1, tasks + 1):
        lines += ['## Task %d: component %d' % (n, n), '',
                  '**Depends on:** Task %d' % (n - 1), '',
                  '**Parallelizable with:** none — shares the module.', '',
                  '**Files:**',
                  '- Modify: `tools/factory_publish.py`',
                  '- Test: `tests/test_factory_publish.py`', '',
                  '- [ ] **Step 1: Write the failing test**', '',
                  '````python']
        lines += ['# %d fenced comment line %d' % (n, i)
                  for i in range(filler)]
        lines += ['## Task 999: a heading that lives inside a fence',
                  '```',
                  '### Smoketest Checkpoint 9 — also fenced',
                  '````', '']
    return '\n'.join(lines) + '\n'


class TestSummarizePlan(PublishTestCase):
    def summary(self, text=None):
        preamble, tasks, _unterminated = factory_publish.summarize_plan(
            big_plan() if text is None else text)
        return preamble, tasks

    def test_preamble_stops_at_the_first_task_heading(self):
        """R3: everything above the first batch/task heading."""
        preamble, _tasks = self.summary()
        self.assertIn('# Demo Implementation Plan', preamble)
        self.assertIn('## Global Constraints', preamble)
        self.assertIn('## File Structure', preamble)
        self.assertFalse([l for l in preamble if l.startswith('## Task ')])

    def test_every_task_heading_is_kept(self):
        _preamble, tasks = self.summary()
        self.assertEqual([t[0] for t in tasks],
                         ['## Task %d: component %d' % (n, n)
                          for n in range(1, 9)])

    def test_files_and_depends_lines_ride_with_their_task(self):
        """R3: the heading plus its **Files:** and **Depends on:** lines."""
        _preamble, tasks = self.summary()
        self.assertIn('**Depends on:** Task 0', tasks[0])
        self.assertIn('**Files:**', tasks[0])
        self.assertIn('- Modify: `tools/factory_publish.py`', tasks[0])

    def test_task_steps_are_dropped(self):
        _preamble, tasks = self.summary()
        self.assertFalse([l for l in tasks[0] if 'Step 1' in l])

    def test_headings_inside_a_fence_are_not_tasks(self):
        """The whole reason the scanner tracks fences."""
        preamble, tasks = self.summary()
        blob = '\n'.join(preamble + [l for t in tasks for l in t])
        self.assertNotIn('Task 999', blob)
        self.assertNotIn('Smoketest Checkpoint 9', blob)

    def test_no_fenced_content_survives(self):
        preamble, tasks = self.summary()
        blob = '\n'.join(preamble + [l for t in tasks for l in t])
        self.assertNotIn('```', blob)
        self.assertNotIn('fenced comment line', blob)

    def test_a_batch_heading_also_ends_the_preamble(self):
        text = ('# T\n\n**Goal:** g\n\n'
                '### Smoketest Checkpoint 1 — thing\n\nbody\n')
        preamble, tasks = self.summary(text)
        self.assertIn('**Goal:** g', preamble)
        self.assertNotIn('### Smoketest Checkpoint 1 — thing', preamble)
        self.assertEqual(tasks, [])

    def test_a_plan_with_no_tasks_is_all_preamble(self):
        preamble, tasks = self.summary('# T\n\nprose\n')
        self.assertEqual(preamble, ['# T', '', 'prose'])
        self.assertEqual(tasks, [])

    def test_an_empty_plan_does_not_raise(self):
        self.assertEqual(factory_publish.summarize_plan(''), ([], [], False))

    def test_an_unterminated_fence_is_reported_not_swallowed(self):
        text = ('# T\n\nprose\n\n## Task 1: kept\n\n**Files:**\n- a\n\n'
                '```python\nopened and never closed\n\n'
                '## Task 2: lost inside the fence\n')
        preamble, tasks, unterminated = factory_publish.summarize_plan(text)
        self.assertTrue(unterminated)
        self.assertEqual([t[0] for t in tasks], ['## Task 1: kept'])

    def test_a_balanced_document_is_not_reported_as_unterminated(self):
        _p, _t, unterminated = factory_publish.summarize_plan(big_plan())
        self.assertFalse(unterminated)


class TestRenderPlanBody(PublishTestCase):
    def body(self, text=None, publish=None, budget=None):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        publish = publish or factory_publish.new_publish_state(440)
        kw = {} if budget is None else {'budget': budget}
        # `text if text is not None`, never `text or`: '' is a meaningful
        # value here — it is what publish_plan passes when the scan refused
        # the file — and `or` would silently swap it for the full plan.
        return factory_publish.render_plan_body(
            state, publish, big_plan() if text is None else text, **kw)

    def test_a_2400_line_plan_renders_under_the_budget(self):
        """AC3."""
        body = self.body()
        self.assertLessEqual(len(body), factory_publish.BODY_BUDGET)

    def test_every_task_heading_and_its_files_line_survive(self):
        """AC3: assert on the content, not that a body was produced."""
        body = self.body()
        for n in range(1, 9):
            self.assertIn('## Task %d: component %d' % (n, n), body)
        self.assertIn('**Files:**', body)
        self.assertIn('- Test: `tests/test_factory_publish.py`', body)

    def test_no_fenced_code_block_reaches_the_body(self):
        """AC3."""
        self.assertNotIn('```', self.body())

    def test_body_links_the_full_plan_asset(self):
        """R3: an explicit truncation marker and a link to the asset."""
        body = self.body()
        self.assertIn('issue-440-plan.md', body)
        self.assertIn('Structural summary', body)

    def test_body_cross_links_the_run_issue(self):
        """R11."""
        publish = factory_publish.new_publish_state(440)
        publish['run_issue'] = 481
        self.assertIn('Run issue: #481', self.body(publish=publish))

    def test_body_names_the_spec_issue(self):
        """R11: either surface is reachable from the other."""
        self.assertIn('**Spec** #440', self.body())

    def test_withheld_asset_says_so_instead_of_linking(self):
        publish = factory_publish.new_publish_state(440)
        publish['withheld']['issue-440-plan.md'] = 'credential-shaped string'
        body = self.body(publish=publish)
        self.assertIn('withheld', body)
        self.assertNotIn('releases/download', body)

    def test_empty_text_renders_a_body_with_no_summary(self):
        """The withheld path: publish_plan passes '' so no plan text can
        reach a public issue when the scan refused the file."""
        publish = factory_publish.new_publish_state(440)
        publish['withheld']['issue-440-plan.md'] = 'credential-shaped string'
        body = self.body(text='', publish=publish)
        self.assertIn('**Spec** #440', body)
        self.assertIn('withheld', body)
        self.assertNotIn('## Task', body)

    def test_over_budget_sheds_the_file_lists_first(self):
        """R3: the shed doctrine, each cut leaving its own marker.

        Assert the marker constant, never the word 'omitted': that word is
        also in PLAN_SUMMARY_LINK, which is in *every* body, so a substring
        test would pass on a body that shed nothing at all.
        """
        body = self.body(budget=1200)
        self.assertLessEqual(len(body), 1200)
        self.assertIn('## Task 1: component 1', body)
        self.assertIn(factory_publish.PLAN_SHED_FILES, body)
        self.assertNotIn('- Modify: `tools/factory_publish.py`', body)
        self.assertNotIn(factory_publish.PLAN_SHED_PREAMBLE, body)
        self.assertIn('## Global Constraints', body)
        self.assertNotIn('truncated at the', body)

    def test_a_tighter_budget_sheds_the_preamble_too(self):
        """R3: the second shed level, which budget=1200 never reaches."""
        body = self.body(budget=750)
        self.assertLessEqual(len(body), 750)
        self.assertIn(factory_publish.PLAN_SHED_PREAMBLE, body)
        self.assertNotIn('## Global Constraints', body)
        self.assertIn('## Task 1: component 1', body)
        self.assertNotIn('truncated at the', body)

    def test_hard_truncation_is_the_backstop(self):
        body = self.body(budget=400)
        self.assertLessEqual(len(body), 400)
        self.assertIn('truncated at the', body)

    def test_body_carries_a_machine_owned_marker(self):
        self.assertIn(factory_publish.PLAN_BODY_MARKER, self.body())

    def test_body_ends_with_exactly_one_newline(self):
        body = self.body()
        self.assertTrue(body.endswith('\n'))
        self.assertFalse(body.endswith('\n\n'))

    def test_an_absolute_path_in_the_header_is_redacted(self):
        """The body is a public issue; every other path here is redacted."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        state['plan'] = r'C:\Users\someone\repo\docs\plans\p.md'
        body = factory_publish.render_plan_body(
            state, factory_publish.new_publish_state(440), big_plan())
        self.assertNotIn('someone', body)
        self.assertIn(factory_report.REDACTION, body)

    def test_an_absolute_path_in_the_plan_text_is_redacted(self):
        """Plans name machine-specific toolchain paths in their preamble."""
        text = big_plan().replace(
            '- Python 3 stdlib only.',
            '- gcc lives at C:/Users/someone/mingw64/bin/gcc.exe')
        body = self.body(text=text)
        self.assertNotIn('someone', body)

    def test_a_url_in_the_plan_survives_redaction(self):
        """redact() alone turns https://host/x into http<path>."""
        text = big_plan().replace(
            '- Python 3 stdlib only.',
            '- See https://github.com/MatthieuGagne/gmb-nuke-raider/issues/514')
        body = self.body(text=text)
        self.assertIn(
            'https://github.com/MatthieuGagne/gmb-nuke-raider/issues/514',
            body)

    def test_a_file_url_is_still_redacted(self):
        text = big_plan().replace('- Python 3 stdlib only.',
                                  '- see file:///C:/Users/someone/x.md')
        body = self.body(text=text)
        self.assertNotIn('someone', body)

    def test_a_path_inside_a_url_query_string_is_redacted(self):
        """The hole the URL-holdout approach had: text inside a URL match
        was copied out verbatim, so a path glued to one rode through."""
        text = big_plan().replace(
            '- Python 3 stdlib only.',
            '- log: https://ci.example.com/b?out=C:\\Users\\alice\\log.txt')
        body = self.body(text=text)
        self.assertNotIn('alice', body)

    def test_a_posix_home_path_inside_a_url_is_redacted(self):
        text = big_plan().replace(
            '- Python 3 stdlib only.',
            '- log: https://ci.example.com/b?p=/home/alice/z')
        body = self.body(text=text)
        self.assertNotIn('alice', body)

    def test_an_unterminated_fence_says_so_in_the_body(self):
        body = self.body(text='# T\n\np\n\n## Task 1: a\n\n```\nunclosed\n')
        self.assertIn(factory_publish.PLAN_UNTERMINATED, body)


class TestPlanSourcing(PublishTestCase):
    def state_with_plan(self, text='# T\n\nprose\n', name='p.md'):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        rel = 'docs/plans/' + name
        full = os.path.join(state['worktree'], 'docs', 'plans', name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        state['plan'] = rel
        return state, full

    def test_plan_is_read_from_the_worktree(self):
        """R5: docs/plans/ is gitignored — the working copy is the only copy."""
        state, full = self.state_with_plan()
        self.assertEqual(factory_publish.plan_path(state), full)
        self.assertEqual(factory_publish.read_plan(state), '# T\n\nprose\n')

    def test_no_plan_recorded_reads_as_none(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        state['plan'] = None
        self.assertIsNone(factory_publish.plan_path(state))
        self.assertIsNone(factory_publish.read_plan(state))

    def test_a_missing_file_reads_as_none_rather_than_raising(self):
        """R10: a vanished worktree is a degradation, never an exception."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        self.assertIsNone(factory_publish.read_plan(state))

    def test_an_absolute_plan_path_is_used_as_given(self):
        state, full = self.state_with_plan()
        state['plan'] = full
        self.assertEqual(factory_publish.plan_path(state), full)

    def test_undecodable_bytes_do_not_raise(self):
        state, full = self.state_with_plan()
        with open(full, 'wb') as fh:
            fh.write(b'# T\n\xff\xfe not utf-8\n')
        self.assertIn('�', factory_publish.read_plan(state))

    def test_asset_name_is_per_issue_not_per_attempt(self):
        """R5 makes this asset a living mirror, so it carries no attempt."""
        self.assertEqual(factory_publish.plan_asset_name(514),
                         'issue-514-plan.md')

    def test_asset_name_is_neither_a_log_nor_a_screenshot(self):
        """It must not be picked up by the stage-log or scenario tables."""
        name = factory_publish.plan_asset_name(514)
        self.assertIsNone(factory_publish._parse_log_asset(name))
        self.assertFalse(name.endswith('.png'))


class TestRenderPlanTitle(PublishTestCase):
    def title(self, **overrides):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        state.update(overrides)
        return factory_publish.render_plan_title(state)

    def test_title_is_plan_slug_and_spec_number(self):
        """R1."""
        self.assertEqual(self.title(), 'plan: observability (#440)')

    def test_slug_falls_back_to_the_plan_filename(self):
        self.assertEqual(
            self.title(slug=None,
                       plan='docs/plans/2026-08-01-issue440-body-budget.md'),
            'plan: body-budget (#440)')

    def test_slug_falls_back_again_when_there_is_no_plan_path(self):
        self.assertEqual(self.title(slug=None, plan=None),
                         'plan: (no slug) (#440)')

    def test_an_undated_plan_filename_falls_back_to_its_stem(self):
        self.assertEqual(self.title(slug=None, plan='docs/plans/notes.md'),
                         'plan: notes (#440)')


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


class FakeGh:
    """Records gh invocations and replays canned results. No network, ever.

    Each `issue create` returns a *distinct* issue number, starting at 481.
    A run now publishes two issues — the run issue and the plan issue — and a
    fake that gave both the same number made every assertion about "which
    issue" silently unfalsifiable.
    """

    ISSUE_BASE = 481

    def __init__(self, results=None, default=(0, '', '')):
        self.calls = []
        self.results = dict(results or {})
        self.default = default
        self.created = 0

    def key(self, argv):
        """First two non-flag words, e.g. 'issue create' or 'release upload'."""
        words = [a for a in argv[1:] if not a.startswith('-')]
        return ' '.join(words[:2])

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        key = self.key(argv)
        code, out, err = self.results.get(key, self.default)
        if key == 'issue create' and code == 0 and '/issues/' in (out or ''):
            number = self.ISSUE_BASE + self.created
            self.created += 1
            out = re.sub(r'/issues/\d+', '/issues/%d' % number, out).strip()
            out += '\n'
        return subprocess.CompletedProcess(list(argv), code, out, err)

    def argv_for(self, key):
        return [argv for argv, _ in self.calls if self.key(argv) == key]


class CapturingGh(FakeGh):
    """FakeGh that reads each uploaded file while the upload is in flight.

    The staged copy lives in a temp directory that is removed as soon as the
    upload returns (#530 R4), so a test that resolves the path afterwards
    reads nothing. `uploads` maps asset name to the exact bytes sent.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uploads = {}

    def __call__(self, argv, **kwargs):
        if self.key(argv) == 'release upload':
            # argv is ['gh', 'release', 'upload', <tag>, <path>, ...]
            path = argv[4]
            try:
                with open(path, 'rb') as fh:
                    self.uploads[os.path.basename(path)] = fh.read()
            except OSError:
                pass
        return super().__call__(argv, **kwargs)


class TestGhSeam(PublishTestCase):
    def test_every_call_is_prefixed_with_gh_and_a_scrubbed_env(self):
        """Global constraint: GIT_DIR leakage broke factory_run before (#462)."""
        fake = FakeGh()
        factory_publish.gh(['issue', 'view', '1'], runner=fake)
        argv, kwargs = fake.calls[0]
        self.assertEqual(argv[0], 'gh')
        self.assertNotIn('GIT_DIR', kwargs['env'])
        self.assertTrue(kwargs['capture_output'])
        self.assertEqual(kwargs['encoding'], 'utf-8')

    def test_a_missing_gh_binary_is_not_an_exception(self):
        def explode(argv, **kwargs):
            raise OSError('no gh on PATH')
        proc = factory_publish.gh(['issue', 'view', '1'], runner=explode)
        self.assertEqual(proc.returncode, 127)


class TestEnsureLabelAndRelease(PublishTestCase):
    def test_label_is_created_once(self):
        """R13."""
        fake = FakeGh()
        warnings = []
        self.assertTrue(factory_publish.ensure_label(warnings, runner=fake))
        self.assertEqual(warnings, [])
        self.assertIn('log', fake.argv_for('label create')[0])

    def test_existing_label_is_not_a_degradation(self):
        fake = FakeGh({'label create': (1, '', 'label already exists')})
        warnings = []
        self.assertTrue(factory_publish.ensure_label(warnings, runner=fake))
        self.assertEqual(warnings, [])

    def test_label_failure_warns_once_and_does_not_raise(self):
        """AC9/R11."""
        fake = FakeGh({'label create': (1, '', 'HTTP 403')})
        warnings = []
        self.assertFalse(factory_publish.ensure_label(warnings, runner=fake))
        self.assertEqual(len(warnings), 1)

    def test_existing_release_is_not_recreated(self):
        fake = FakeGh({'release view': (0, '{}', '')})
        warnings = []
        self.assertTrue(factory_publish.ensure_release(warnings, runner=fake))
        self.assertEqual(fake.argv_for('release create'), [])

    def test_missing_release_is_created_not_latest(self):
        """R13: repo tags stay clean."""
        fake = FakeGh({'release view': (1, '', 'release not found')})
        warnings = []
        self.assertTrue(factory_publish.ensure_release(warnings, runner=fake))
        argv = fake.argv_for('release create')[0]
        self.assertIn('factory-logs', argv)
        self.assertIn('--latest=false', argv)


ISSUE_URL = 'https://github.com/MatthieuGagne/gmb-nuke-raider/issues/481'
FIELD_LIST = json.dumps({'fields': [
    {'id': 'F_type', 'name': 'Type',
     'options': [{'id': 'O_adr', 'name': 'ADR'}, {'id': 'O_log', 'name': 'Log'}]},
    {'id': 'F_status', 'name': 'Status',
     'options': [{'id': 'O_todo', 'name': 'Todo'},
                 {'id': 'O_inprogress', 'name': 'In Progress'},
                 {'id': 'O_done', 'name': 'Done'}]}]})
PLAN_FIELD_LIST = json.dumps({'fields': [
    {'id': 'F_type', 'name': 'Type',
     'options': [{'id': 'O_adr', 'name': 'ADR'},
                 {'id': 'O_log', 'name': 'Log'},
                 {'id': 'O_plan', 'name': 'Plan'}]},
    {'id': 'F_status', 'name': 'Status',
     'options': [{'id': 'O_todo', 'name': 'Todo'},
                 {'id': 'O_inprogress', 'name': 'In Progress'},
                 {'id': 'O_done', 'name': 'Done'}]}]})


class TestRunIssueLifecycle(PublishTestCase):
    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_shipped_run(self.tmp)
        self.state = factory_run.load_state(440, self.reg)
        self.publish = factory_publish.new_publish_state(440)

    def ensure(self, fake, warnings=None):
        return factory_publish.ensure_run_issue(
            self.state, self.publish, 'run 440 · attempt 1 · SHIP · complete',
            'body text', warnings if warnings is not None else [],
            registry=self.reg, runner=fake)

    def test_first_publish_creates_a_labelled_issue(self):
        """AC1."""
        fake = FakeGh({'issue create': (0, ISSUE_URL + '\n', '')})
        self.assertEqual(self.ensure(fake), 481)
        argv = fake.argv_for('issue create')[0]
        self.assertIn('--label', argv)
        self.assertIn('log', argv)
        self.assertEqual(self.publish['run_issue'], 481)

    def test_the_body_goes_through_a_file_never_argv(self):
        """The body carries emoji; argv encoding on Windows is not utf-8."""
        fake = FakeGh({'issue create': (0, ISSUE_URL + '\n', '')})
        self.ensure(fake)
        argv = fake.argv_for('issue create')[0]
        self.assertIn('--body-file', argv)
        path = argv[argv.index('--body-file') + 1]
        with open(path, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'body text')

    def test_second_publish_edits_the_same_issue(self):
        """AC1: reused forever after, never recreated."""
        self.publish['run_issue'] = 481
        fake = FakeGh()
        self.assertEqual(self.ensure(fake), 481)
        self.assertEqual(fake.argv_for('issue create'), [])
        self.assertIn('481', fake.argv_for('issue edit')[0])

    def test_title_is_re_rendered_on_every_edit(self):
        """AC2/R3."""
        self.publish['run_issue'] = 481
        fake = FakeGh()
        self.ensure(fake)
        argv = fake.argv_for('issue edit')[0]
        self.assertIn('--title', argv)
        self.assertIn('run 440 · attempt 1 · SHIP · complete', argv)

    def test_create_failure_warns_once_and_returns_none(self):
        """AC9."""
        fake = FakeGh({'issue create': (1, '', 'HTTP 502')})
        warnings = []
        self.assertIsNone(self.ensure(fake, warnings))
        self.assertEqual(len(warnings), 1)
        self.assertIsNone(self.publish['run_issue'])

    def test_edit_failure_warns_once_and_keeps_the_number(self):
        """AC9: a failed edit never loses the issue we already own."""
        self.publish['run_issue'] = 481
        fake = FakeGh({'issue edit': (1, '', 'HTTP 502')})
        warnings = []
        self.assertEqual(self.ensure(fake, warnings), 481)
        self.assertEqual(len(warnings), 1)

    def test_unparseable_create_output_warns(self):
        fake = FakeGh({'issue create': (0, 'not a url\n', '')})
        warnings = []
        self.assertIsNone(self.ensure(fake, warnings))
        self.assertEqual(len(warnings), 1)

    def test_reopen_and_close_are_idempotent(self):
        """AC4: a later attempt reopens the same issue."""
        fake = FakeGh({'issue reopen': (1, '', 'issue is already open')})
        warnings = []
        self.assertTrue(factory_publish.set_issue_state(481, True, warnings,
                                                        runner=fake))
        self.assertEqual(warnings, [])


class TestProjectTypeLog(PublishTestCase):
    def fake(self, **overrides):
        results = {'project item-add': (0, json.dumps({'id': 'PVTI_x'}), ''),
                   'project field-list': (0, FIELD_LIST, ''),
                   'project item-edit': (0, '', '')}
        results.update(overrides)
        return FakeGh(results)

    def test_item_is_added_and_typed_log(self):
        """AC1."""
        publish = factory_publish.new_publish_state(440)
        fake = self.fake()
        self.assertTrue(factory_publish.ensure_project_type_log(
            publish, ISSUE_URL, [], runner=fake))
        edit = fake.argv_for('project item-edit')[0]
        self.assertIn('PVTI_x', edit)
        self.assertIn('F_type', edit)
        self.assertIn('O_log', edit)
        self.assertTrue(publish['projected'])

    def test_a_projected_run_is_not_re_added_on_every_publish(self):
        publish = factory_publish.new_publish_state(440)
        publish['projected'] = True
        fake = self.fake()
        self.assertTrue(factory_publish.ensure_project_type_log(
            publish, ISSUE_URL, [], runner=fake))
        self.assertEqual(fake.calls, [])

    def test_missing_type_option_warns_once(self):
        """AC9."""
        fake = self.fake(**{'project field-list': (0, '{"fields": []}', '')})
        warnings = []
        publish = factory_publish.new_publish_state(440)
        self.assertFalse(factory_publish.ensure_project_type_log(
            publish, ISSUE_URL, warnings, runner=fake))
        self.assertEqual(len(warnings), 1)

    def test_item_add_failure_warns_once(self):
        fake = self.fake(**{'project item-add': (1, '', 'HTTP 403')})
        warnings = []
        publish = factory_publish.new_publish_state(440)
        self.assertFalse(factory_publish.ensure_project_type_log(
            publish, ISSUE_URL, warnings, runner=fake))
        self.assertEqual(len(warnings), 1)

    def test_joining_the_board_also_sets_status_in_progress(self):
        """AC3: Type = Log and Status = In Progress in one join."""
        publish = factory_publish.new_publish_state(440)
        fake = self.fake()
        warnings = []
        self.assertTrue(factory_publish.ensure_project_type_log(
            publish, ISSUE_URL, warnings, runner=fake))
        self.assertEqual(warnings, [])
        edits = fake.argv_for('project item-edit')
        self.assertEqual(len(edits), 2)
        self.assertIn('O_log', edits[0])
        self.assertIn('F_status', edits[1])
        self.assertIn('O_inprogress', edits[1])
        self.assertEqual(publish['run_item_id'], 'PVTI_x')


class TestRunStart(PublishTestCase):
    """--run-start: the spec issue goes In Progress, and nothing else (R1)."""

    def fake(self, **overrides):
        results = {'project item-add': (0, json.dumps({'id': 'PVTI_spec'}), ''),
                   'project field-list': (0, FIELD_LIST, ''),
                   'project item-edit': (0, '', '')}
        results.update(overrides)
        return FakeGh(results)

    def test_sets_status_in_progress_and_writes_nothing_else(self):
        """AC1."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        result = factory_publish.run_start(440, registry=reg, runner=fake)
        self.assertEqual(result.warnings, [])
        edit = fake.argv_for('project item-edit')[0]
        self.assertIn('PVTI_spec', edit)
        self.assertIn('F_status', edit)
        self.assertIn('O_inprogress', edit)
        keys = [fake.key(argv) for argv, _ in fake.calls]
        self.assertEqual(keys, ['project item-add', 'project field-list',
                                'project item-edit'])

    def test_adds_the_item_first_and_never_sets_type(self):
        """AC2: item-add, then the Status edit — and no Type edit, ever."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        factory_publish.run_start(440, registry=reg, runner=fake)
        keys = [fake.key(argv) for argv, _ in fake.calls]
        self.assertLess(keys.index('project item-add'),
                        keys.index('project item-edit'))
        add = fake.argv_for('project item-add')[0]
        self.assertIn('--url', add)
        self.assertIn('https://github.com/MatthieuGagne/gmb-nuke-raider/'
                      'issues/440', add)
        edits = fake.argv_for('project item-edit')
        self.assertEqual(len(edits), 1)
        flat = ' '.join(a for argv in edits for a in argv)
        self.assertNotIn('F_type', flat)
        self.assertNotIn('O_log', flat)

    def test_option_ids_come_from_field_list_not_a_constant(self):
        """AC6: option ids are regenerated when the option set is edited."""
        altered = json.dumps({'fields': [
            {'id': 'F_status_v2', 'name': 'Status',
             'options': [{'id': 'O_inprogress_v2', 'name': 'In Progress'}]}]})
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake(**{'project field-list': (0, altered, '')})
        factory_publish.run_start(440, registry=reg, runner=fake)
        edit = fake.argv_for('project item-edit')[0]
        self.assertIn('F_status_v2', edit)
        self.assertIn('O_inprogress_v2', edit)

    def test_total_project_failure_warns_once_and_exits_one(self):
        """AC7."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = FakeGh(default=(1, '', 'HTTP 403'))
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = factory_publish.run_start(440, registry=reg, runner=fake)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(buf.getvalue().count(factory_publish.WARNING_PREFIX), 1)
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_DEGRADED)

    def test_second_call_reuses_the_cached_item_id(self):
        """AC8: no duplicate item-add, and publish.json still loads."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        factory_publish.run_start(440, registry=reg, runner=self.fake())
        second = self.fake()
        factory_publish.run_start(440, registry=reg, runner=second)
        self.assertEqual(second.argv_for('project item-add'), [])
        self.assertEqual(
            factory_publish.load_publish_state(440, reg)['spec_item_id'],
            'PVTI_spec')

    def test_field_list_failure_is_reported_not_the_schema_message(self):
        """Review item 6: a failed ``field-list`` (403/network) must not be
        reported as "no such field" — that misdirects the reader at the
        board schema instead of at auth. spec_item_id is already cached, so
        the only remaining GitHub call is the failing field-list."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['spec_item_id'] = 'PVTI_spec'
        factory_publish.save_publish_state(publish, reg)
        fake = self.fake(**{'project field-list': (1, '', 'HTTP 403')})
        result = factory_publish.run_start(440, registry=reg, runner=fake)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn('HTTP 403', result.warnings[0])
        self.assertNotIn('no Status field', result.warnings[0])

    def stub_gh(self, fake):
        """Replace the module-global gh() so main() touches no network."""
        real = factory_publish.gh
        factory_publish.gh = lambda argv, runner=None: fake(['gh'] + list(argv))
        self.addCleanup(setattr, factory_publish, 'gh', real)

    def test_cli_routes_to_run_start(self):
        """AC1 through main(): one Status edit, no other GitHub write."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        self.stub_gh(fake)
        code = factory_publish.main(['--issue', '440', '--registry', reg,
                                     '--run-start'])
        self.assertEqual(code, factory_publish.EXIT_OK)
        self.assertTrue(fake.argv_for('project item-edit'))
        self.assertEqual(fake.argv_for('issue create'), [])
        self.assertEqual(fake.argv_for('issue edit'), [])
        self.assertEqual(fake.argv_for('release upload'), [])
        self.assertEqual(fake.argv_for('label create'), [])

    def test_cli_exits_one_when_the_board_is_unreachable(self):
        """AC7: the CLI half — 1 is a degradation, never a run failure."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        self.stub_gh(FakeGh(default=(1, '', 'HTTP 403')))
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(['--issue', '440', '--registry', reg,
                                         '--run-start'])
        self.assertEqual(code, factory_publish.EXIT_DEGRADED)

    def test_run_start_with_dry_run_is_misuse(self):
        """--dry-run promises to touch no network; --run-start is a write."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        self.stub_gh(fake)
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(['--issue', '440', '--registry', reg,
                                         '--run-start', '--dry-run'])
        self.assertEqual(code, factory_publish.EXIT_MISUSE)
        self.assertEqual(fake.calls, [])

    def test_run_start_with_open_pr_is_misuse(self):
        """--run-start makes exactly one write; --open-pr is a different one.

        --branch/--title/--body-file are supplied (a real, existing body
        file) so this would genuinely reach ``pr create`` if the combined-flag
        guard were removed — without them the missing-args check alone would
        already return EXIT_MISUSE and the guard's removal would go unnoticed.
        """
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        self.stub_gh(fake)
        body_path = os.path.join(self.tmp, 'pr-body.md')
        with open(body_path, 'w', encoding='utf-8') as fh:
            fh.write('body\n')
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(['--issue', '440', '--registry', reg,
                                         '--run-start', '--open-pr',
                                         '--branch', 'b', '--title', 't',
                                         '--body-file', body_path])
        self.assertEqual(code, factory_publish.EXIT_MISUSE)
        self.assertEqual(fake.calls, [])

    def test_run_start_with_stage_completed_is_misuse(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        self.stub_gh(fake)
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(['--issue', '440', '--registry', reg,
                                         '--run-start',
                                         '--stage-completed', 'BUILD'])
        self.assertEqual(code, factory_publish.EXIT_MISUSE)
        self.assertEqual(fake.calls, [])

    def test_run_start_with_terminal_is_misuse(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        fake = self.fake()
        self.stub_gh(fake)
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(['--issue', '440', '--registry', reg,
                                         '--run-start', '--terminal'])
        self.assertEqual(code, factory_publish.EXIT_MISUSE)
        self.assertEqual(fake.calls, [])


class TestPublishStateIsAdditive(PublishTestCase):
    def test_a_record_written_before_the_item_cache_still_loads(self):
        """AC9: no schema_version bump, so no orphaned run issue."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        path = factory_publish.publish_path(440, reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'issue': 440, 'run_issue': 481,
                       'projected': True, 'commented_attempts': [1],
                       'uploaded': [], 'withheld': {}}, fh)
        publish = factory_publish.load_publish_state(440, reg)
        self.assertEqual(publish['run_issue'], 481)
        self.assertIsNone(publish['spec_item_id'])
        self.assertIsNone(publish['run_item_id'])
        self.assertEqual(factory_publish.PUBLISH_SCHEMA_VERSION, 1)


class TestAssetUpload(PublishTestCase):
    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_registry(self.tmp)
        self.state = factory_run.load_state(436, self.reg)
        self.publish = factory_publish.new_publish_state(436)

    def write_log(self, stage, payload=b'make: ok\n'):
        path = factory_run.log_path(436, stage, self.reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(payload)
        return path

    def publish_log(self, stage, fake, warnings=None):
        return factory_publish.publish_stage_log(
            self.state, self.publish, stage,
            warnings if warnings is not None else [], registry=self.reg,
            runner=fake)

    def test_uploaded_asset_is_a_byte_exact_copy(self):
        """AC5: the published asset equals the local log, byte for byte."""
        payload = b'\x00\x01binary\xff\n' * 40
        self.write_log('BUILD', payload)
        fake = CapturingGh()
        self.assertTrue(self.publish_log('BUILD', fake))
        self.assertEqual(fake.uploads['issue-436-attempt-2-BUILD.log'],
                         payload)

    def test_asset_is_named_by_issue_attempt_and_stage(self):
        """AC4: attempt 2's asset does not disturb attempt 1's."""
        self.write_log('BUILD')
        fake = FakeGh()
        self.publish_log('BUILD', fake)
        self.assertIn('issue-436-attempt-2-BUILD.log',
                      os.path.basename(fake.argv_for('release upload')[0][-1]))

    def test_an_uploaded_asset_is_never_re_uploaded(self):
        """R7: never clobbered."""
        self.write_log('BUILD')
        fake = FakeGh()
        self.publish_log('BUILD', fake)
        self.publish_log('BUILD', fake)
        self.assertEqual(len(fake.argv_for('release upload')), 1)
        self.assertEqual(self.publish['uploaded'],
                         ['issue-436-attempt-2-BUILD.log'])

    def test_missing_log_warns_and_is_not_a_failure(self):
        """AC3: the fail-open case reads 'no stage log captured'."""
        warnings = []
        self.assertFalse(self.publish_log('SHIP', FakeGh(), warnings))
        self.assertEqual(len(warnings), 1)

    def test_an_empty_log_is_treated_as_no_log_at_all(self):
        """#489: a zero-byte log is no more evidence than a missing one.

        Exactly one warning, the same sentence an absent log already gets:
        a helper that was never really run leaves a zero-byte file behind,
        and uploading it would publish an empty asset as if it were output.
        """
        self.write_log('BUILD', b'')
        fake = FakeGh()
        warnings = []
        self.assertFalse(self.publish_log('BUILD', fake, warnings))
        self.assertEqual(fake.argv_for('release upload'), [])
        self.assertEqual(self.publish['uploaded'], [])
        self.assertEqual(len(warnings), 1)
        self.assertIn('no stage log captured for BUILD', warnings[0])

    def test_credential_shaped_log_is_withheld_and_named(self):
        """AC6."""
        self.write_log('BUILD', b'token ghp_' + b'A' * 36 + b'\n')
        fake = FakeGh()
        warnings = []
        self.assertFalse(self.publish_log('BUILD', fake, warnings))
        self.assertEqual(fake.argv_for('release upload'), [])
        self.assertEqual(len(warnings), 1)
        withheld = self.publish['withheld']['issue-436-attempt-2-BUILD.log']
        self.assertIn('credential-shaped', withheld)
        self.assertIn('logs', withheld)

    def test_one_withheld_asset_does_not_block_the_others(self):
        """AC6."""
        self.write_log('BUILD', b'ghp_' + b'A' * 36)
        self.write_log('GATE', b'clean\n')
        fake = FakeGh()
        self.publish_log('BUILD', fake, [])
        self.assertTrue(self.publish_log('GATE', fake, []))
        self.assertEqual(self.publish['uploaded'],
                         ['issue-436-attempt-2-GATE.log'])

    def test_upload_failure_warns_once_and_is_not_recorded(self):
        """AC9."""
        self.write_log('BUILD')
        fake = FakeGh({'release upload': (1, '', 'HTTP 502')})
        warnings = []
        self.assertFalse(self.publish_log('BUILD', fake, warnings))
        self.assertEqual(len(warnings), 1)
        self.assertEqual(self.publish['uploaded'], [])

    def test_screenshots_upload_uncapped_with_failure_frames(self):
        """AC7/R9."""
        fake = FakeGh()
        names = factory_publish.publish_screenshots(
            self.state, self.publish, [], registry=self.reg, runner=fake)
        self.assertEqual(len(names), 5)
        self.assertTrue(any('failure' in n for n in names))
        self.assertTrue(all(n.startswith('issue-436-attempt-2-reach-race-')
                            for n in names))

    def test_screenshots_are_not_re_uploaded(self):
        fake = FakeGh()
        factory_publish.publish_screenshots(self.state, self.publish, [],
                                            registry=self.reg, runner=fake)
        factory_publish.publish_screenshots(self.state, self.publish, [],
                                            registry=self.reg, runner=fake)
        self.assertEqual(len(fake.argv_for('release upload')), 5)

    def test_screenshots_are_not_secret_scanned(self):
        """R8 is about logs; a PNG has no credential shape to find and the
        scan must not become a reason evidence goes missing."""
        fake = FakeGh()
        names = factory_publish.publish_screenshots(
            self.state, self.publish, [], registry=self.reg, runner=fake)
        self.assertEqual(self.publish['withheld'], {})
        self.assertEqual(len(names), 5)


class TestUnloggedStagesInTheRunIssue(PublishTestCase):
    """#489 AC3: the run issue names the stages that left no log.

    The wording is ``factory_report.UNLOGGED_STAGES_NOTE`` verbatim — the PR
    body and the run issue must not drift apart — and it is prose, not a
    table cell, so it is asserted as a whole line.
    """

    def body(self, issue, reg, publish=None):
        state = factory_run.load_state(issue, reg)
        publish = publish or factory_publish.new_publish_state(issue)
        return factory_publish.render_body(state, publish, registry=reg,
                                           now=factory_fixtures.FIXED_NOW)

    def note(self, stages='GATE, BUILD'):
        return factory_report.UNLOGGED_STAGES_NOTE % stages

    def test_the_note_names_the_unlogged_stages(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        body = self.body(441, reg)
        self.assertIn('### Stage logs', body)
        self.assertIn(self.note(), body)

    def test_a_blank_line_separates_the_note_from_the_table_header(self):
        """GFM refuses to parse a table that interrupts a paragraph."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        publish = factory_publish.new_publish_state(441)
        publish['uploaded'].append('issue-441-attempt-1-BUILD.log')
        lines = self.body(441, reg, publish).splitlines()
        index = lines.index(self.note())
        self.assertEqual(lines[index + 1], '')
        self.assertEqual(lines[index + 2], '| Stage | Attempt | Log |')

    def test_the_placeholder_also_sits_below_a_blank_line(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        lines = self.body(441, reg).splitlines()
        index = lines.index(self.note())
        self.assertEqual(lines[index + 1], '')
        self.assertEqual(lines[index + 2], '_No stage logs published yet._')

    def test_a_fully_logged_run_carries_no_note(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        publish['uploaded'].append('issue-440-attempt-1-BUILD.log')
        body = self.body(440, reg, publish)
        self.assertIn('### Stage logs', body)
        self.assertNotIn('No log was captured for', body)
        self.assertNotIn('no stage log captured', body)


class PlanRunTestCase(PublishTestCase):
    """A shipped run whose plan file actually exists on disk."""

    PLAN_REL = 'docs/plans/2026-08-01-issue440-demo.md'

    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, self.reg)
        self.plan_file = os.path.join(state['worktree'], 'docs', 'plans',
                                      '2026-08-01-issue440-demo.md')
        os.makedirs(os.path.dirname(self.plan_file), exist_ok=True)
        self.write_plan(big_plan())
        # Every stage this class publishes needs its log on disk, or
        # publish_stage_log adds a 'no stage log captured' warning of its own
        # and every warning count below is off by one — including the AC7
        # assertion, whose entire point is 'exactly one'.
        for stage in ('PLAN', 'BUILD'):
            path = factory_run.log_path(440, stage, self.reg)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as fh:
                fh.write(b'make: ok\n')
        # A second 'start' overrides only the fields it carries: apply_event
        # skips None fields and only touches 'stage' when the event has one,
        # so the fixture's SHIP stage, attempt 1 and slug all survive. The
        # unpinned clock is safe because every condition asserted in this
        # class is decided by 'finished'/'failure', which outrank elapsed.
        factory_run.append_event(440, 'start', registry=self.reg,
                                 plan=self.PLAN_REL)
        self.state = factory_run.load_state(440, self.reg)
        self.publish = factory_publish.new_publish_state(440)

    def write_plan(self, text):
        with open(self.plan_file, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        return text

    def fake(self, **overrides):
        results = {'issue create': (0, ISSUE_URL + '\n', ''),
                   'project item-add': (0, json.dumps({'id': 'PVTI_x'}), ''),
                   'project field-list': (0, PLAN_FIELD_LIST, '')}
        results.update(overrides)
        return FakeGh(results)

    def publish_plan(self, fake, warnings=None):
        return factory_publish.publish_plan(
            self.state, self.publish,
            warnings if warnings is not None else [], registry=self.reg,
            runner=fake)

    def body_sent(self, fake, key='issue create'):
        argv = fake.argv_for(key)[-1]
        with open(argv[argv.index('--body-file') + 1], encoding='utf-8') as fh:
            return fh.read()


class TestPlanIssueLifecycle(PlanRunTestCase):
    def test_first_publish_creates_a_labelled_plan_issue(self):
        """R1/AC2."""
        fake = self.fake()
        self.assertEqual(self.publish_plan(fake), 481)
        argv = fake.argv_for('issue create')[0]
        self.assertIn('--label', argv)
        self.assertIn('plan', argv)
        self.assertIn('plan: observability (#440)', argv)
        self.assertEqual(self.publish['plan_issue'], 481)

    def test_a_second_publish_edits_and_never_creates_a_second(self):
        """AC2: exactly one plan issue, whatever the call count."""
        first = self.fake()
        self.publish_plan(first)
        second = self.fake()
        self.publish_plan(second)
        self.assertEqual(second.argv_for('issue create'), [])
        self.assertIn('481', second.argv_for('issue edit')[0])

    def test_the_plan_issue_is_typed_plan_in_the_project(self):
        """R1."""
        fake = self.fake()
        self.publish_plan(fake)
        edit = fake.argv_for('project item-edit')[0]
        self.assertIn('O_plan', edit)
        self.assertTrue(self.publish['plan_projected'])

    def test_project_typing_happens_once_not_per_publish(self):
        fake = self.fake()
        self.publish_plan(fake)
        again = self.fake()
        self.publish_plan(again)
        self.assertEqual(again.argv_for('project item-add'), [])

    def test_the_body_goes_through_a_file_never_argv(self):
        fake = self.fake()
        self.publish_plan(fake)
        self.assertIn('## Task 1: component 1', self.body_sent(fake))

    def test_a_missing_plan_costs_exactly_one_warning(self):
        """AC7/R10: one read, so one failure point, so one warning."""
        os.remove(self.plan_file)
        warnings = []
        fake = self.fake()
        self.assertIsNone(self.publish_plan(fake, warnings))
        self.assertEqual(len(warnings), 1)
        self.assertIn('cannot read', warnings[0])
        self.assertEqual(fake.argv_for('issue create'), [])

    def test_a_warning_never_leaks_an_absolute_path(self):
        """The run issue is public; factory_report keeps paths out of the PR."""
        os.remove(self.plan_file)
        warnings = []
        self.publish_plan(self.fake(), warnings)
        self.assertNotIn(self.tmp, warnings[0])
        self.assertIn(self.PLAN_REL, warnings[0])

    def test_an_absolute_plan_path_is_redacted_from_the_warning(self):
        """The sibling test above uses the relative fixture path, so it
        passes whether or not the redaction is there.

        plan_path() explicitly supports an absolute state["plan"], and the
        warning text reaches the stage log, which is published as a release
        asset.
        """
        self.state['plan'] = os.path.join(self.tmp, 'gone', 'plan.md')
        warnings = []
        self.assertIsNone(self.publish_plan(self.fake(), warnings))
        self.assertEqual(len(warnings), 1)
        self.assertNotIn(self.tmp, warnings[0])
        self.assertIn(factory_report.REDACTION, warnings[0])

    def test_a_run_with_no_plan_recorded_is_silent(self):
        """Every publish before PLAN step 4 — not a degradation."""
        self.state['plan'] = None
        warnings = []
        fake = self.fake()
        self.assertIsNone(self.publish_plan(fake, warnings))
        self.assertEqual(warnings, [])
        self.assertEqual(fake.calls, [])

    def test_create_failure_warns_once_and_returns_none(self):
        """R10."""
        warnings = []
        fake = self.fake(**{'issue create': (1, '', 'HTTP 502')})
        self.assertIsNone(self.publish_plan(fake, warnings))
        self.assertIn('plan issue not created', ' '.join(warnings))
        self.assertIsNone(self.publish['plan_issue'])

    def test_edit_failure_keeps_the_number_we_already_own(self):
        self.publish['plan_issue'] = 481
        warnings = []
        self.publish_plan(self.fake(**{'issue edit': (1, '', 'HTTP 502')}),
                          warnings)
        self.assertEqual(self.publish['plan_issue'], 481)
        self.assertEqual(len(warnings), 1)


class TestPlanResync(PlanRunTestCase):
    def test_editing_the_plan_updates_the_body(self):
        """AC5."""
        fake = self.fake()
        self.publish_plan(fake)
        self.assertIn('## Task 1: component 1', self.body_sent(fake))
        self.write_plan(big_plan().replace('component 1', 'renamed unit'))
        second = self.fake()
        self.publish_plan(second)
        body = self.body_sent(second, 'issue edit')
        self.assertIn('renamed unit', body)
        self.assertNotIn('component 1', body)

    def test_editing_the_plan_re_uploads_the_asset(self):
        """AC5: the asset is a mirror, so it is clobbered, not duplicated."""
        fake = self.fake()
        self.publish_plan(fake)
        self.write_plan(big_plan(tasks=9))
        second = self.fake()
        self.publish_plan(second)
        argv = second.argv_for('release upload')[0]
        self.assertIn('--clobber', argv)
        self.assertEqual(self.publish['uploaded'].count('issue-440-plan.md'), 1)

    def test_an_unchanged_plan_is_not_re_uploaded(self):
        fake = self.fake()
        self.publish_plan(fake)
        second = self.fake()
        self.publish_plan(second)
        self.assertEqual(second.argv_for('release upload'), [])


class TestPlanAsset(PlanRunTestCase):
    def test_uploaded_asset_is_byte_identical_to_the_plan(self):
        """AC4: bytes, not 'an upload was attempted'."""
        fake = self.fake()
        capture = CapturingGh(fake.results)
        self.publish_plan(capture)
        with open(self.plan_file, 'rb') as fh:
            self.assertEqual(
                capture.uploads[factory_publish.plan_asset_name(440)],
                fh.read())

    def test_the_ledger_records_the_asset(self):
        """R4."""
        fake = self.fake()
        self.publish_plan(fake)
        self.assertIn('issue-440-plan.md', self.publish['uploaded'])
        self.assertEqual(self.publish['plan_sha256'],
                         factory_run.sha256_file(self.plan_file))

    def test_a_credential_shaped_plan_is_withheld_from_both_surfaces(self):
        """The scan guards the issue body as well as the asset.

        Withholding only the asset would be worse than useless: the summary
        renders plan text straight into a public, indexed issue, so a plan
        that trips the scanner must not reach the body either.
        """
        self.write_plan('# T\n\ntoken ghp_' + 'A' * 36 + '\n')
        warnings = []
        fake = self.fake()
        self.publish_plan(fake, warnings)
        self.assertEqual(fake.argv_for('release upload'), [])
        self.assertIn('issue-440-plan.md', self.publish['withheld'])
        body = self.body_sent(fake)
        self.assertIn('withheld', body)
        self.assertNotIn('ghp_', body)

    def test_a_cleaned_plan_stops_being_withheld(self):
        """R5's re-sync is two-way: the marker clears when the plan does."""
        self.write_plan('# T\n\ntoken ghp_' + 'A' * 36 + '\n')
        self.publish_plan(self.fake(), [])
        self.write_plan(big_plan())
        fake = self.fake()
        self.publish_plan(fake, [])
        self.assertEqual(self.publish['withheld'], {})
        self.assertIn('releases/download', self.body_sent(fake, 'issue edit'))

    def test_an_upload_failure_does_not_stop_the_issue(self):
        """R10: the summary is still worth publishing without the asset."""
        warnings = []
        fake = self.fake(**{'release upload': (1, '', 'HTTP 502')})
        self.assertEqual(self.publish_plan(fake, warnings), 481)
        self.assertIsNone(self.publish['plan_sha256'])
        self.assertEqual(len(warnings), 1)

    def test_the_withheld_marker_in_the_body_carries_no_absolute_path(self):
        """The withheld reason is formatted into a public issue verbatim.

        The plan path must be absolute AND exist: an absolute path that does
        not exist takes publish_plan's 'cannot read' early return and never
        reaches the scanner, so the withheld branch is never entered and the
        test proves nothing.
        """
        self.state['plan'] = self.plan_file
        self.write_plan('# T\n\ntoken ghp_' + 'A' * 36 + '\n')
        fake = self.fake()
        self.publish_plan(fake, [])
        withheld = self.publish['withheld']['issue-440-plan.md']
        self.assertNotIn(self.tmp, withheld)
        self.assertIn(factory_report.REDACTION, withheld)
        self.assertNotIn(self.tmp, self.body_sent(fake))

    def test_an_unreadable_plan_does_not_leak_its_path_into_the_body(self):
        """scan_secrets' 'unreadable' reason embeds str(OSError), which
        embeds the absolute path it could not open.

        The credential-shaped case above cannot catch this: its reason is a
        fixed literal with no path in it, so it only ever exercised the
        second half of the withheld string.
        """
        self.state['plan'] = self.plan_file
        original = factory_publish.scan_secrets
        factory_publish.scan_secrets = lambda path: (
            "unreadable, not scanned: [Errno 13] Permission denied: %r" % path)
        try:
            fake = self.fake()
            self.publish_plan(fake, [])
        finally:
            factory_publish.scan_secrets = original
        withheld = self.publish['withheld']['issue-440-plan.md']
        self.assertIn(factory_report.REDACTION, withheld)
        self.assertNotIn(self.tmp, withheld)
        self.assertNotIn(self.tmp, self.body_sent(fake))


class TestPublishRunPlan(PlanRunTestCase):
    def run_publish(self, fake, **kw):
        kw.setdefault('registry', self.reg)
        kw.setdefault('now', factory_fixtures.FIXED_NOW)
        return factory_publish.publish_run(440, runner=fake, **kw)

    def test_stage_completed_plan_publishes_both_surfaces(self):
        """AC1: run issue and plan issue, and nothing else."""
        fake = self.fake()
        result = self.run_publish(fake, stage_completed='PLAN')
        self.assertEqual(result.warnings, [])
        self.assertEqual(len(fake.argv_for('issue create')), 2)
        publish = factory_publish.load_publish_state(440, self.reg)
        # publish_plan runs before ensure_run_issue in publish_run, so the
        # plan issue claims the first 'issue create' (481) and the run issue
        # the second (482) — two distinct GitHub objects, not one shared
        # number.
        self.assertEqual(publish['plan_issue'], 481)
        self.assertEqual(publish['run_issue'], 482)
        self.assertNotEqual(publish['run_issue'], publish['plan_issue'])

    def test_calling_stage_completed_plan_twice_creates_one_plan_issue(self):
        """AC2."""
        self.run_publish(self.fake(), stage_completed='PLAN')
        second = self.fake()
        self.run_publish(second, stage_completed='PLAN')
        self.assertEqual(second.argv_for('issue create'), [])

    def test_the_run_body_cross_links_the_plan_issue(self):
        """R11."""
        fake = self.fake()
        self.run_publish(fake, stage_completed='PLAN')
        second = self.fake()
        self.run_publish(second, stage_completed='BUILD')
        self.assertIn('**Plan** #481',
                      self.body_sent(second, 'issue edit'))

    def test_a_deleted_plan_still_updates_the_run_issue(self):
        """AC7: exit 1, one warning, run issue unaffected."""
        os.remove(self.plan_file)
        fake = self.fake()
        result = self.run_publish(fake, stage_completed='PLAN')
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_DEGRADED)
        self.assertTrue(fake.argv_for('issue create'))

    def test_terminal_never_closes_the_plan_issue(self):
        """AC8/R9: only a merged PR closes it."""
        self.run_publish(self.fake(), stage_completed='PLAN')
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        closed = [argv[argv.index('close') + 1]
                  for argv in fake.argv_for('issue close')]
        # The run issue, never the plan: the first publish above creates the
        # plan issue first (481) and the run issue second (482) — only 482
        # is ever closed.
        self.assertEqual(closed, ['482'])

    def test_a_failed_run_leaves_the_plan_issue_open(self):
        """AC8: a run that never ships leaves standing evidence.

        Asserts what is *closed*, not what is absent: 'no reopen call' is
        true of any terminal publish and would not fail if the plan issue
        were closed alongside the run issue.
        """
        self.run_publish(self.fake(), stage_completed='PLAN')
        factory_run.append_event(440, 'failure', registry=self.reg,
                                 message='boom')
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        publish = factory_publish.load_publish_state(440, self.reg)
        closed = [argv[argv.index('close') + 1]
                  for argv in fake.argv_for('issue close')]
        self.assertEqual(closed, [str(publish['run_issue'])])
        self.assertTrue(publish['plan_issue'])

    def test_a_dry_run_creates_the_plan_issue_and_leaves_it_open(self):
        """AC8's other half.

        `/factory --dry-run` is a skill-level flag with no code path in this
        module: stages.md PLAN step 8 says it stops after the PLAN publish.
        So a dry run *is* exactly one `--stage-completed PLAN` and nothing
        after it, which is what this simulates. `factory_publish --dry-run`
        is a different flag entirely — it renders to stdout and touches no
        network — and is not what AC8 is about.
        """
        fake = self.fake()
        self.run_publish(fake, stage_completed='PLAN')
        self.assertEqual(fake.argv_for('issue close'), [])
        self.assertTrue(
            factory_publish.load_publish_state(440, self.reg)['plan_issue'])

    def test_no_code_path_closes_a_plan_issue(self):
        """AC8, as a canary over the whole module rather than one scenario.

        Three occurrences today: the definition, and the two calls in
        publish_run that reopen and close the *run* issue. A fourth means a
        new caller exists and must be read against R9 by hand. This is a
        canary, not a proof — the two scenario tests above it are the
        evidence.
        """
        with open(factory_publish.__file__, encoding='utf-8') as fh:
            source = fh.read()
        self.assertEqual(source.count('set_issue_state('), 3)


class TestPublishRun(PublishTestCase):
    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_shipped_run(self.tmp)
        path = factory_run.log_path(440, 'BUILD', self.reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'make: ok\n')
        # The fixture records a plan path but never writes the file, and
        # publish_run now reads it. Without this the whole class degrades on
        # a missing plan and every 'no warnings' assertion below is false.
        state = factory_run.load_state(440, self.reg)
        plan = os.path.join(state['worktree'], state['plan'].replace('/', os.sep))
        os.makedirs(os.path.dirname(plan), exist_ok=True)
        with open(plan, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('# Demo Implementation Plan\n\n**Issue:** #440\n\n'
                     '## Task 1: demo\n\n**Files:**\n- Modify: `x.py`\n')

    def fake(self, **overrides):
        results = {'issue create': (0, ISSUE_URL + '\n', ''),
                   'project item-add': (0, json.dumps({'id': 'PVTI_x'}), ''),
                   'project field-list': (0, PLAN_FIELD_LIST, '')}
        results.update(overrides)
        return FakeGh(results)

    def run_publish(self, fake, **kw):
        kw.setdefault('registry', self.reg)
        kw.setdefault('now', factory_fixtures.FIXED_NOW)
        return factory_publish.publish_run(440, runner=fake, **kw)

    def seed_items(self, issue=440, registry=None):
        """A run already on the board: both item ids cached, so the terminal
        writes are distinguishable by item id in the recorded argv.

        The seeded number is deliberately far from ``FakeGh.ISSUE_BASE``
        (481): the run issue here is never actually created through the fake
        (it is pre-cached), so the class's own plan file makes the plan
        issue the first real ``issue create`` call and it claims 481. A
        seeded run issue of 481 would coincidentally collide with a
        genuinely distinct plan issue and make item-add calls for the two
        indistinguishable by URL.
        """
        publish = factory_publish.new_publish_state(issue)
        publish.update({'run_issue': 900, 'projected': True,
                        'run_item_id': 'PVTI_run',
                        'spec_item_id': 'PVTI_spec'})
        factory_publish.save_publish_state(publish, registry or self.reg)

    def status_edits(self, fake):
        """(item id, option id) for every Status item-edit, in call order."""
        out = []
        for argv in fake.argv_for('project item-edit'):
            if 'F_status' not in argv:
                continue
            out.append((argv[argv.index('--id') + 1],
                        argv[argv.index('--single-select-option-id') + 1]))
        return out

    def test_first_publish_creates_labels_and_types_the_issue(self):
        """AC1."""
        fake = self.fake()
        result = self.run_publish(fake, stage_completed='BUILD')
        # publish_plan runs before ensure_run_issue in publish_run, and the
        # class's setUp gives this run a real plan file — so the plan issue
        # is the first 'issue create' this publish makes (481) and the run
        # issue is the second (482).
        self.assertEqual(result.run_issue, 482)
        self.assertEqual(result.warnings, [])
        self.assertTrue(fake.argv_for('label create'))
        self.assertTrue(fake.argv_for('issue create'))
        self.assertTrue(fake.argv_for('project item-edit'))

    def test_stage_transition_posts_no_comment(self):
        """AC2."""
        fake = self.fake()
        self.run_publish(fake, stage_completed='BUILD')
        self.assertEqual(fake.argv_for('issue comment'), [])

    def test_state_survives_between_publishes(self):
        """AC1: a second publish edits, never creates."""
        fake = self.fake()
        self.run_publish(fake, stage_completed='BUILD')
        second = self.fake()
        self.run_publish(second, stage_completed='VERIFY')
        self.assertEqual(second.argv_for('issue create'), [])
        self.assertTrue(second.argv_for('issue edit'))

    def test_terminal_closes_the_issue_and_comments_exactly_once(self):
        """AC3/R10."""
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        self.assertTrue(fake.argv_for('issue close'))
        self.assertEqual(len(fake.argv_for('issue comment')), 1)
        self.assertIn('440', fake.argv_for('issue comment')[0])

    def test_a_second_terminal_publish_does_not_comment_again(self):
        """R10: one comment per attempt is the whole notification budget."""
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        again = self.fake()
        self.run_publish(again, terminal=True)
        self.assertEqual(again.argv_for('issue comment'), [])

    def test_a_new_attempt_reopens_and_comments_again(self):
        """AC4."""
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        factory_run.append_event(440, 'retry', registry=self.reg, attempt=2,
                                 stage='BUILD')
        second = self.fake()
        self.run_publish(second, stage_completed='BUILD')
        self.assertTrue(second.argv_for('issue reopen'))
        # Select by title, never by position: publish_plan edits the plan
        # issue before ensure_run_issue edits the run issue, so 'the second
        # issue edit call' is not a stable way to mean 'the run issue'.
        titles = [argv[argv.index('--title') + 1]
                  for argv in second.argv_for('issue edit')]
        self.assertTrue(
            any(t.startswith('run 440') and 'attempt 2' in t for t in titles),
            titles)
        self.assertTrue(any('attempt-2-BUILD.log' in a
                            for a in second.argv_for('release upload')[0]))

    def test_every_gh_failure_leaves_the_outcome_unchanged(self):
        """AC9: one marked warning each, never an exception."""
        for key in ('issue create', 'issue edit', 'release upload',
                    'issue comment', 'label create', 'release create',
                    'project item-add', 'project item-edit'):
            with self.subTest(key=key):
                reg = factory_fixtures.build_shipped_run(
                    tempfile.mkdtemp(dir=self.tmp))
                fake = self.fake(**{key: (1, '', 'HTTP 502'),
                                    'release view': (1, '', 'not found')})
                result = factory_publish.publish_run(
                    440, registry=reg, terminal=True, runner=fake,
                    now=factory_fixtures.FIXED_NOW)
                self.assertGreaterEqual(len(result.warnings), 1)

    def test_the_journal_is_never_written_by_publishing(self):
        """AC2: append_event makes no network call and publish makes no event."""
        before = len(factory_run.read_journal(440, self.reg))
        self.run_publish(self.fake(), stage_completed='BUILD')
        self.assertEqual(len(factory_run.read_journal(440, self.reg)), before)

    def test_terminal_failure_settles_run_done_and_spec_todo(self):
        """AC4."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        self.seed_items(441, reg)
        fake = self.fake()
        factory_publish.publish_run(441, registry=reg, terminal=True,
                                    runner=fake,
                                    now=factory_fixtures.FIXED_NOW)
        self.assertEqual(self.status_edits(fake),
                         [('PVTI_run', 'O_done'), ('PVTI_spec', 'O_todo')])

    def test_terminal_success_leaves_the_spec_alone(self):
        """AC5: the PR is open, not merged — the merge closes the spec."""
        self.seed_items()
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        self.assertEqual(self.status_edits(fake), [('PVTI_run', 'O_done')])

    def test_terminal_status_is_not_behind_the_projected_guard(self):
        """The trap in #513's Notes: `projected` covers membership and the
        one-time Type write only."""
        self.seed_items()
        fake = self.fake()
        self.run_publish(fake, terminal=True)
        # Scoped to the run issue's own URL, not a bare "no item-add at all":
        # this class's plan file makes the plan issue a fresh create every
        # run, and it correctly makes its own item-add — that is a different
        # issue from the run issue this test is actually about (#514).
        run_url = '/issues/%d' % factory_publish.load_publish_state(
            440, self.reg)['run_issue']
        self.assertEqual(
            [a for a in fake.argv_for('project item-add') if run_url in a],
            [])
        self.assertTrue(self.status_edits(fake))

    def test_the_spec_returns_to_todo_even_with_no_run_issue(self):
        """R4 is conditioned on the run having failed, not on the dashboard
        issue existing — that is the case where the board would lie longest."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        publish = factory_publish.new_publish_state(441)
        publish['spec_item_id'] = 'PVTI_spec'
        factory_publish.save_publish_state(publish, reg)
        fake = self.fake(**{'issue create': (1, '', 'HTTP 502')})
        result = factory_publish.publish_run(441, registry=reg, terminal=True,
                                             runner=fake,
                                             now=factory_fixtures.FIXED_NOW)
        self.assertIsNone(result.run_issue)
        self.assertEqual(self.status_edits(fake), [('PVTI_spec', 'O_todo')])

    def test_a_failing_status_write_leaves_the_outcome_unchanged(self):
        """AC7: the call is still made, the warning is marked, and
        publish_run still returns its PublishResult."""
        self.seed_items()
        fake = self.fake(**{'project item-edit': (1, '', 'HTTP 403')})
        result = self.run_publish(fake, terminal=True)
        self.assertEqual(result.run_issue, 900)
        self.assertEqual(self.status_edits(fake), [('PVTI_run', 'O_done')])
        self.assertTrue(any('Status=Done' in w for w in result.warnings),
                        result.warnings)

    def test_a_fresh_terminal_run_never_retries_a_failed_run_item_add(self):
        """Regression for the reviewer's Finding 1: a fresh run (no cached
        item ids) whose first publish is also terminal and whose Documents
        board is unreachable must warn about the run issue's own failed
        add exactly once, not once from ensure_project_type_log and again
        from finish_project_status — and the spec issue's own add warning,
        a distinct call against a distinct URL, must still be there."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        fake = FakeGh({'issue create': (0, ISSUE_URL + '\n', '')},
                     default=(1, '', 'HTTP 403'))
        result = factory_publish.publish_run(441, registry=reg, terminal=True,
                                             runner=fake,
                                             now=factory_fixtures.FIXED_NOW)
        run_warning = "%s not added to the Documents project: HTTP 403" % (
            ISSUE_URL)
        spec_warning = "%s not added to the Documents project: HTTP 403" % (
            factory_publish.issue_url(441))
        self.assertEqual(result.warnings.count(run_warning), 1)
        self.assertIn(spec_warning, result.warnings)

    def test_a_cached_run_item_still_gets_its_done_write_when_type_fails(self):
        """Regression for the re-reviewer's "new breakage" finding: a fresh
        run where ``project item-add`` succeeds (the id gets cached) but the
        immediately-following ``Type`` write fails must still resolve the
        run item and issue its terminal ``Done`` write — the id is perfectly
        usable, only the unrelated ``Type`` edit failed. Uses a field list
        that carries ``Status`` but not ``Type`` (rather than the empty
        ``{"fields": []}`` from test_missing_type_option_warns_once) so the
        Status writes this test asserts on can still resolve their field and
        option ids."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        status_only = json.dumps({'fields': [
            {'id': 'F_status', 'name': 'Status',
             'options': [{'id': 'O_todo', 'name': 'Todo'},
                         {'id': 'O_inprogress', 'name': 'In Progress'},
                         {'id': 'O_done', 'name': 'Done'}]}]})
        fake = self.fake(**{'project field-list': (0, status_only, '')})
        result = factory_publish.publish_run(441, registry=reg, terminal=True,
                                             runner=fake,
                                             now=factory_fixtures.FIXED_NOW)
        run_url = factory_publish.issue_url(result.run_issue)
        adds_for_run = [a for a in fake.argv_for('project item-add')
                       if run_url in a]
        self.assertEqual(len(adds_for_run), 1)
        self.assertIn(('PVTI_x', 'O_done'), self.status_edits(fake))

    def test_a_previously_projected_record_with_no_cached_id_still_adds_and_marks_done(self):
        """Case 4: a publish.json written before ``run_item_id`` existed —
        ``projected`` True, no cached id. The add inside
        ``finish_project_status`` is the first attempt this publish, not a
        retry, and it must still resolve to a terminal ``Done`` write."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = factory_publish.new_publish_state(440)
        # 900, not 481: this reuses setUp's worktree (build_shipped_run is
        # deterministic per tmpdir), so its plan file is on disk and this
        # publish's own plan issue is a fresh create — the first one, since
        # the run issue below is only cached, never actually created through
        # the fake. A seeded 481 here would coincidentally collide with that
        # genuinely distinct plan issue.
        publish.update({'run_issue': 900, 'projected': True})
        factory_publish.save_publish_state(publish, reg)
        fake = self.fake()
        self.run_publish(fake, terminal=True, registry=reg)
        run_url = factory_publish.issue_url(900)
        adds_for_run = [a for a in fake.argv_for('project item-add')
                       if run_url in a]
        self.assertEqual(len(adds_for_run), 1)
        self.assertEqual(self.status_edits(fake), [('PVTI_x', 'O_done')])


class TestCli(PublishTestCase):
    def test_unknown_stage_is_misuse(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        proc = subprocess.run([sys.executable, SCRIPT, '--issue', '440',
                               '--registry', reg, '--stage-completed',
                               'DEPLOY'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, factory_publish.EXIT_MISUSE)

    def test_bad_now_is_misuse(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        proc = subprocess.run([sys.executable, SCRIPT, '--issue', '440',
                               '--registry', reg, '--now', 'yesterday'],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, factory_publish.EXIT_MISUSE)

    def test_unknown_run_is_misuse(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        proc = subprocess.run([sys.executable, SCRIPT, '--issue', '9999',
                               '--registry', reg], capture_output=True,
                              text=True)
        self.assertEqual(proc.returncode, factory_publish.EXIT_MISUSE)

    def test_dry_run_writes_the_body_and_touches_no_network(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        proc = subprocess.run([sys.executable, SCRIPT, '--issue', '440',
                               '--registry', reg, '--dry-run', '--now',
                               '2026-07-26T14:00:00+00:00'],
                              capture_output=True)
        self.assertEqual(proc.returncode, factory_publish.EXIT_OK)
        self.assertIn(b'**Spec** #440', proc.stdout)
        self.assertIn(factory_publish.BODY_MARKER.encode('utf-8'), proc.stdout)

    def test_degradation_exits_one_not_zero(self):
        """Exit codes: 1 is reportable, and never a run failure."""
        result = factory_publish.PublishResult(None, ['boom'], [])
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_DEGRADED)
        self.assertEqual(
            factory_publish.exit_code(factory_publish.PublishResult(1, [], [])),
            factory_publish.EXIT_OK)


class OpenPrTest(unittest.TestCase):
    """factory_publish is the only thing that may create a PR (#481 R2)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        self.body = os.path.join(self.registry, 'pr-body.md')
        with open(self.body, 'w', encoding='utf-8') as fh:
            fh.write('## Summary\n\nbody\n')

    def _runner(self, code=0, out='https://github.com/o/r/pull/7\n', err=''):
        calls = []

        def runner(argv, **kwargs):
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, code, out, err)

        return runner, calls

    def test_creates_the_pr_and_returns_its_url(self):
        runner, calls = self._runner()
        url, created = factory_publish.open_pr(
            461, 'factory-issue-461', 'fix: thing (#461)', self.body,
            runner=runner)
        self.assertEqual(url, 'https://github.com/o/r/pull/7')
        self.assertTrue(created)
        self.assertEqual(calls[0][:3], ['gh', 'pr', 'create'])
        self.assertIn('--body-file', calls[0])
        self.assertIn(self.body, calls[0])

    def test_passes_the_branch_as_head(self):
        runner, calls = self._runner()
        factory_publish.open_pr(461, 'factory-issue-461', 't', self.body,
                                runner=runner)
        self.assertIn('--head', calls[0])
        self.assertIn('factory-issue-461', calls[0])

    def test_scrubs_git_dir_from_the_environment(self):
        seen = {}

        def runner(argv, **kwargs):
            seen.update(kwargs.get('env') or {})
            return subprocess.CompletedProcess(argv, 0, 'u\n', '')

        factory_publish.open_pr(461, 'b', 't', self.body, runner=runner)
        self.assertNotIn('GIT_DIR', seen)
        self.assertNotIn('GIT_WORK_TREE', seen)

    def test_existing_pr_is_not_an_error(self):
        runner, _ = self._runner(
            code=1, out='',
            err='a pull request for branch "factory-issue-461" already exists: #7')
        warnings = []
        url, created = factory_publish.open_pr(
            461, 'factory-issue-461', 't', self.body, warnings=warnings,
            runner=runner)
        self.assertFalse(created)
        self.assertEqual(warnings, [])

    def test_real_failure_reports_and_does_not_raise(self):
        runner, _ = self._runner(code=1, out='', err='HTTP 502')
        warnings = []
        url, created = factory_publish.open_pr(
            461, 'b', 't', self.body, warnings=warnings, runner=runner)
        self.assertIsNone(url)
        self.assertFalse(created)
        self.assertEqual(len(warnings), 1)
        self.assertIn('502', warnings[0])

    def test_missing_body_file_is_reported_not_raised(self):
        runner, calls = self._runner()
        warnings = []
        url, created = factory_publish.open_pr(
            461, 'b', 't', os.path.join(self.registry, 'nope.md'),
            warnings=warnings, runner=runner)
        self.assertIsNone(url)
        self.assertEqual(calls, [])
        self.assertEqual(len(warnings), 1)


class PrBodyWithPlanTest(PublishTestCase):
    """R7: the Closes line is appended by the publisher, not the reporter."""

    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_shipped_run(self.tmp)
        self.body = os.path.join(self.tmp, 'pr-body.md')
        with open(self.body, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('## Summary\n\nbody\n\nCloses #440\n')

    def with_plan(self, number=482, **kw):
        if number is not None:
            publish = factory_publish.new_publish_state(440)
            publish['plan_issue'] = number
            factory_publish.save_publish_state(publish, self.reg)
        return factory_publish.pr_body_with_plan(
            440, self.body, registry=self.reg, **kw)

    def read(self, path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_body_ends_with_closes_the_plan_issue(self):
        """AC6."""
        self.assertTrue(self.read(self.with_plan()).endswith('Closes #482\n'))

    def test_the_specs_own_closes_line_survives(self):
        """factory_report's Closes #<spec> is what actually closes the spec."""
        self.assertIn('Closes #440\n', self.read(self.with_plan()))

    def test_no_plan_issue_returns_the_original_path_untouched(self):
        self.assertEqual(self.with_plan(number=None), self.body)

    def test_the_closing_reference_is_appended_in_place(self):
        """AC5: one rendered body, and the plan link is in it."""
        path = self.with_plan()
        self.assertEqual(path, self.body)
        self.assertTrue(self.read(self.body).endswith('Closes #482\n'))

    def test_both_closing_references_are_present(self):
        """AC5: the spec's own Closes line survives the append."""
        body = self.read(self.with_plan())
        self.assertIn('Closes #440\n', body)
        self.assertIn('Closes #482\n', body)

    def test_no_second_copy_of_the_body_is_written(self):
        """AC5, AC4."""
        self.with_plan()
        root = factory_run.run_dir(440, self.reg)
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                self.assertNotIn('pr-body', name)

    def test_a_body_without_a_trailing_newline_still_gets_one(self):
        with open(self.body, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('## Summary\n\nbody\n\nCloses #440')
        self.assertTrue(self.read(self.with_plan()).endswith(
            'Closes #440\nCloses #482\n'))

    def test_a_second_call_does_not_append_twice(self):
        self.with_plan()
        self.assertEqual(self.read(self.with_plan()).count('Closes #482'), 1)

    def test_a_missing_body_file_warns_and_falls_back(self):
        """R10: never terminal — --open-pr reports the real failure itself."""
        warnings = []
        missing = os.path.join(self.tmp, 'nope.md')
        publish = factory_publish.new_publish_state(440)
        publish['plan_issue'] = 482
        factory_publish.save_publish_state(publish, self.reg)
        path = factory_publish.pr_body_with_plan(440, missing,
                                                 registry=self.reg,
                                                 warnings=warnings)
        self.assertEqual(path, missing)
        self.assertEqual(len(warnings), 1)

    def test_factory_report_still_closes_only_the_spec_issue(self):
        """AC6: the ADR 0006 boundary is not widened."""
        state = factory_run.load_state(440, self.reg)
        rendered = factory_report.render(state)
        self.assertIn('Closes #440', rendered)
        self.assertNotIn('482', rendered)
        self.assertNotIn('plan_issue', rendered)


class OpenPrCliTest(unittest.TestCase):
    def test_open_pr_without_branch_is_misuse(self):
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(
                ['--issue', '461', '--open-pr', '--title', 't',
                 '--body-file', 'x.md'])
        self.assertEqual(code, 2)


class DecisionShapeTests(unittest.TestCase):
    """#517 R17 — AC11, AC12."""

    def test_a_decision_without_a_rationale_is_a_plain_bullet(self):
        """AC12 — an existing journal still renders."""
        lines = factory_publish.decision_lines({'text': 'Keep it.'})
        self.assertEqual(lines, ['- Keep it.'])

    def test_a_decision_with_a_rationale_is_bold_plus_details(self):
        """AC11."""
        lines = factory_publish.decision_lines(
            {'text': 'Keep it.', 'rationale': 'Because the other way is worse.'})
        self.assertEqual(lines, [
            '- **Keep it.**',
            '  <details><summary>Rationale</summary>',
            '',
            '  Because the other way is worse.',
            '',
            '  </details>',
        ])

    def test_a_multiline_rationale_is_indented_line_by_line(self):
        lines = factory_publish.decision_lines(
            {'text': 'Keep it.', 'rationale': 'First.\n\nSecond.'})
        self.assertIn('  First.', lines)
        self.assertIn('  Second.', lines)
        for line in lines:
            self.assertEqual(line, line.rstrip())

    def test_an_empty_rationale_falls_back_to_a_plain_bullet(self):
        self.assertEqual(factory_publish.decision_lines(
            {'text': 'Keep it.', 'rationale': ''}), ['- Keep it.'])

    def test_a_missing_text_keeps_the_existing_placeholder(self):
        self.assertEqual(factory_publish.decision_lines({}), ['- -'])


class PlanReviewFindingsSectionTests(PublishTestCase):
    """#530 R3 — AC3."""

    def body(self, publish=None):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = publish or factory_publish.new_publish_state(440)
        return factory_publish.render_body(
            factory_run.load_state(440, reg), publish, registry=reg,
            now=factory_fixtures.FIXED_NOW)

    def test_findings_have_their_own_section(self):
        body = self.body()
        self.assertIn('### Plan review findings', body)
        self.assertIn('Screenshots become data URIs.', body)

    def test_a_finding_is_not_repeated_in_the_decisions_section(self):
        body = self.body()
        decisions = body.split('### Decisions made')[1] \
                        .split('### Plan review findings')[0]
        self.assertNotIn('Screenshots become data URIs.', decisions)
        self.assertIn('Journal is the source of truth', decisions)

    def test_the_section_is_absent_when_there_are_no_findings(self):
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(500, 'start', registry=reg, stage='GATE')
        factory_run.append_event(500, 'decision', registry=reg, text='Keep it.')
        body = factory_publish.render_body(
            factory_run.load_state(500, reg),
            factory_publish.new_publish_state(500), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertNotIn('### Plan review findings', body)
        self.assertIn('Keep it.', body)

    def test_findings_are_shed_before_decisions_when_the_body_is_too_big(self):
        """R5: the budget ladder drops the least load-bearing section first."""
        factory_fixtures.pinned_clock()
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(600, 'start', registry=reg, stage='PLAN')
        factory_run.append_event(600, 'decision', registry=reg,
                                 text='F' * 400, finding=True)
        factory_run.append_event(600, 'decision', registry=reg,
                                 text='D' * 400)
        body = factory_publish.render_body(
            factory_run.load_state(600, reg),
            factory_publish.new_publish_state(600), registry=reg,
            now=factory_fixtures.FIXED_NOW, budget=900)
        self.assertIn('D' * 400, body)
        self.assertNotIn('F' * 400, body)
        self.assertIn('1 earlier findings omitted', body)


class RunDashboardRemovalTests(unittest.TestCase):
    """#517 R21 — AC15."""

    def test_no_source_file_emits_the_banned_string(self):
        banned = 'Run ' + 'dashboard'
        for folder in ('tools', 'tests'):
            root = os.path.join(os.path.dirname(__file__), '..', folder)
            for dirpath, _dirs, names in os.walk(root):
                for name in names:
                    if not name.endswith('.py'):
                        continue
                    path = os.path.join(dirpath, name)
                    with open(path, encoding='utf-8') as fh:
                        self.assertNotIn(banned, fh.read(), path)


PR_URL = 'https://github.com/MatthieuGagne/gmb-nuke-raider/pull/579'


class DecisionSurfaceTests(PublishTestCase):
    """#530 R1, R2 — AC1, AC2."""

    def shipped_body(self, publish=None):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        publish = publish or factory_publish.new_publish_state(440)
        return factory_publish.render_body(
            factory_run.load_state(440, reg), publish, registry=reg,
            now=factory_fixtures.FIXED_NOW)

    def with_pr(self):
        publish = factory_publish.new_publish_state(440)
        publish['pr_url'] = PR_URL
        return publish

    def test_a_known_pr_replaces_the_decisions_with_a_link(self):
        """AC1."""
        body = self.shipped_body(self.with_pr())
        self.assertIn(PR_URL, body)
        self.assertNotIn('Journal is the source of truth', body)

    def test_the_recorded_pr_on_the_state_is_enough(self):
        """AC1: publish.json is not the only source."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        factory_run.append_event(440, 'start', registry=reg, pr=PR_URL)
        body = factory_publish.render_body(
            factory_run.load_state(440, reg),
            factory_publish.new_publish_state(440), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertIn(PR_URL, body)
        self.assertNotIn('Journal is the source of truth', body)

    def test_findings_stay_in_the_run_record_even_with_a_pr(self):
        """AC3: only the decisions move."""
        body = self.shipped_body(self.with_pr())
        self.assertIn('### Plan review findings', body)
        self.assertIn('Screenshots become data URIs.', body)

    def test_a_run_whose_rulings_are_all_findings_still_links(self):
        """R2: neither surface may become a dead end."""
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(700, 'start', registry=reg, stage='PLAN',
                                 pr=PR_URL)
        factory_run.append_event(700, 'decision', registry=reg,
                                 text='Only a finding.', finding=True)
        body = factory_publish.render_body(
            factory_run.load_state(700, reg),
            factory_publish.new_publish_state(700), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertIn('### Decisions made', body)
        self.assertIn(PR_URL, body)

    def test_a_run_with_no_rulings_at_all_shows_no_link(self):
        reg = os.path.join(self.tmp, 'reg')
        factory_run.append_event(701, 'start', registry=reg, stage='SHIP',
                                 pr=PR_URL)
        body = factory_publish.render_body(
            factory_run.load_state(701, reg),
            factory_publish.new_publish_state(701), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertNotIn('### Decisions made', body)

    def test_a_failed_run_keeps_its_decisions(self):
        """AC2: no pull request exists, so nothing may be moved."""
        reg = factory_fixtures.build_failed_run(self.tmp)
        body = factory_publish.render_body(
            factory_run.load_state(441, reg),
            factory_publish.new_publish_state(441), registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertIn('Autopsy assembly is best-effort', body)
        self.assertNotIn('pull request', body)

    def test_an_unknown_pr_url_keeps_the_decisions(self):
        """AC2: a degraded --open-pr must not silently drop the record."""
        self.assertIn('Journal is the source of truth', self.shipped_body())

    def test_the_linked_body_matches_its_golden(self):
        """AC1."""
        publish = self.with_pr()
        publish['uploaded'].append('issue-440-attempt-1-BUILD.log')
        self.assertEqual(self.shipped_body(publish),
                         golden('expected_run_issue_body_shipped_pr.md'))

    def test_open_pr_persists_the_url_for_the_run_record(self):
        """AC1: the run record can only link to a URL that outlives SHIP."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        path = os.path.join(self.tmp, 'body.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('body\n')
        url, warnings = factory_publish.open_pr_cli(
            440, 'factory-issue-440', 'feat: x (#440)', path, registry=reg,
            runner=FakeGh({'pr create': (0, PR_URL + '\n', '')}))
        self.assertEqual(url, PR_URL)
        self.assertEqual(warnings, [])
        self.assertEqual(
            factory_publish.load_publish_state(440, reg)['pr_url'], PR_URL)

    def test_a_pr_that_cannot_be_opened_persists_nothing(self):
        """AC7: the terminal step stays terminal and writes no false URL."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        path = os.path.join(self.tmp, 'body.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('body\n')
        url, warnings = factory_publish.open_pr_cli(
            440, 'factory-issue-440', 'feat: x (#440)', path, registry=reg,
            runner=FakeGh({'pr create': (1, '', 'HTTP 500')}))
        self.assertIsNone(url)
        self.assertEqual(len(warnings), 1)
        self.assertIsNone(
            factory_publish.load_publish_state(440, reg).get('pr_url'))

    def test_open_pr_records_the_decision_count_at_that_moment(self):
        """Finding 1: pr_decisions is captured only on a successful open."""
        reg = factory_fixtures.build_shipped_run(self.tmp)  # 2 decisions, 1 finding
        path = os.path.join(self.tmp, 'body.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('body\n')
        url, warnings = factory_publish.open_pr_cli(
            440, 'factory-issue-440', 'feat: x (#440)', path, registry=reg,
            runner=FakeGh({'pr create': (0, PR_URL + '\n', '')}))
        self.assertEqual(url, PR_URL)
        state = factory_run.load_state(440, reg)
        self.assertEqual(
            factory_publish.load_publish_state(440, reg)['pr_decisions'],
            len(state['decisions']))

    def test_a_pr_that_cannot_be_opened_records_no_decision_count(self):
        """Finding 1: a failed open must not leave a stale count behind."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        path = os.path.join(self.tmp, 'body.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('body\n')
        url, warnings = factory_publish.open_pr_cli(
            440, 'factory-issue-440', 'feat: x (#440)', path, registry=reg,
            runner=FakeGh({'pr create': (1, '', 'HTTP 500')}))
        self.assertIsNone(url)
        self.assertIsNone(
            factory_publish.load_publish_state(440, reg).get('pr_decisions'))

    def test_a_decision_recorded_after_the_pr_count_renders_in_full(self):
        """Finding 1: the data-loss path — a late decision must reach the
        run issue, since the PR body was already rendered without it."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        publish = self.with_pr()
        publish['pr_decisions'] = len(state['decisions'])
        factory_run.append_event(
            440, 'decision', registry=reg,
            text='A late decision made after the PR body was rendered.')
        body = factory_publish.render_body(
            factory_run.load_state(440, reg), publish, registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertIn(PR_URL, body)
        self.assertIn(factory_publish.DECISIONS_AFTER_PR, body)
        self.assertIn(
            'A late decision made after the PR body was rendered.', body)

    def test_a_decision_recorded_before_the_pr_count_stays_link_only(self):
        """Finding 1: nothing already reflected on the PR is repeated."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        publish = self.with_pr()
        publish['pr_decisions'] = len(state['decisions'])
        body = factory_publish.render_body(
            factory_run.load_state(440, reg), publish, registry=reg,
            now=factory_fixtures.FIXED_NOW)
        self.assertIn(PR_URL, body)
        self.assertNotIn(factory_publish.DECISIONS_AFTER_PR, body)
        self.assertNotIn('Journal is the source of truth', body)
        self.assertNotIn('The publisher deletes the temporary copy', body)

    def test_pr_decisions_absent_renders_the_link_alone(self):
        """Finding 1: the backward-compatible path for an older publish.json
        or a run whose pr came from state rather than --open-pr."""
        publish = self.with_pr()
        self.assertIsNone(publish['pr_decisions'])
        body = self.shipped_body(publish)
        self.assertIn(PR_URL, body)
        self.assertNotIn(factory_publish.DECISIONS_AFTER_PR, body)
        self.assertNotIn('Journal is the source of truth', body)


class NoStagedDuplicatesTests(PublishTestCase):
    """#530 R4 — AC4."""

    def published_run_dir(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        log = factory_run.log_path(440, 'BUILD', reg)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, 'wb') as fh:
            fh.write(b'make: ok\n' * 200)
        factory_publish.publish_run(440, registry=reg,
                                    stage_completed='BUILD', runner=FakeGh())
        return factory_run.run_dir(440, reg)

    def test_no_file_duplicates_another_file_in_the_run_registry(self):
        """AC4. The autopsy bundle is excluded on purpose: it is a frozen
        snapshot of evidence, not a staged copy. R4 names three staged
        copies and the autopsy is none of them."""
        root = self.published_run_dir()
        seen = {}
        for dirpath, _dirs, names in os.walk(root):
            if 'autopsy' in os.path.relpath(dirpath, root).split(os.sep):
                continue
            for name in names:
                path = os.path.join(dirpath, name)
                digest = factory_run.sha256_file(path)
                self.assertNotIn(
                    digest, seen,
                    '%s duplicates %s' % (path, seen.get(digest)))
                seen[digest] = path

    def test_the_stage_log_is_not_copied_into_the_run_registry(self):
        """AC4: the exact duplicate the spec measured."""
        root = self.published_run_dir()
        self.assertFalse(os.path.exists(
            os.path.join(root, 'publish', 'issue-440-attempt-1-BUILD.log')))

    def test_the_temporary_copy_is_removed_after_the_upload(self):
        """R4: transient, not resident."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        publish = factory_publish.new_publish_state(440)
        log = factory_run.log_path(440, 'BUILD', reg)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, 'wb') as fh:
            fh.write(b'make: ok\n')
        seen = {}

        class PathGh(FakeGh):
            def __call__(self, argv, **kwargs):
                if self.key(argv) == 'release upload':
                    seen['path'] = argv[4]
                return super().__call__(argv, **kwargs)

        self.assertTrue(factory_publish.publish_stage_log(
            state, publish, 'BUILD', [], registry=reg, runner=PathGh()))
        self.assertFalse(os.path.exists(seen['path']))


class PublicationIsOtherwiseUnchangedTests(PlanRunTestCase):
    """#530 R5 — AC6, AC7."""

    def run_publish(self, **overrides):
        fake = self.fake(**overrides)
        result = factory_publish.publish_run(
            440, registry=self.reg, stage_completed='BUILD', runner=fake)
        return result, fake

    def test_the_uploaded_asset_names_are_unchanged(self):
        """AC6 (#530)."""
        result, _fake = self.run_publish()
        self.assertEqual(sorted(result.uploaded),
                         ['issue-440-attempt-1-BUILD.log',
                          'issue-440-plan.md'])

    def test_the_same_gh_verbs_are_called(self):
        """AC6 (#530): same objects, same board writes."""
        _result, fake = self.run_publish(
            **{'release view': (1, '', 'release not found')})
        keys = {fake.key(argv) for argv, _ in fake.calls}
        for expected in ('label create', 'release create', 'release upload',
                         'issue create', 'project item-add',
                         'project field-list'):
            self.assertIn(expected, keys)

    def test_a_clean_publish_reports_nothing_and_exits_zero(self):
        """AC7 (#530)."""
        result, _fake = self.run_publish()
        self.assertEqual(result.warnings, [])
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_OK)

    def test_a_failed_upload_is_reported_and_is_not_a_run_failure(self):
        """AC7 (#530)."""
        result, _fake = self.run_publish(
            **{'release upload': (1, '', 'HTTP 502')})
        self.assertTrue([w for w in result.warnings if 'not uploaded' in w])
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_DEGRADED)

    def test_a_build_log_on_disk_produces_no_missing_log_warning(self):
        """#654 AC2: the exact string the spec names, not a warning count."""
        result, _fake = self.run_publish()
        self.assertEqual(
            [w for w in result.warnings if 'no stage log captured' in w], [])
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_OK)

    def test_removing_the_build_log_brings_the_warning_back(self):
        """#654 AC2, negative control: the assertion above can fail.

        Without this, the pin above would pass on a publisher that could not
        emit the warning at all.
        """
        os.remove(factory_run.log_path(440, 'BUILD', self.reg))
        result, _fake = self.run_publish()
        self.assertTrue(
            [w for w in result.warnings if 'no stage log captured' in w])
        self.assertEqual(factory_publish.exit_code(result),
                         factory_publish.EXIT_DEGRADED)


class TestSlugAgreement(PublishTestCase):
    """#641 R5-R6: one resolver behind both renderers."""

    def test_plan_slug_has_no_second_copy_of_the_recovery(self):
        """R5: the delegation itself, not merely its result.

        Every agreement test below passes against the *current* _plan_slug,
        because the old and new recovery agree on all four inputs. Only this
        test can go red for a re-duplicated copy of the logic.
        """
        with mock.patch.object(factory_run, 'run_slug',
                               return_value='SENTINEL') as patched:
            self.assertEqual(
                factory_publish._plan_slug({'slug': 'x', 'plan': None}),
                'SENTINEL')
        patched.assert_called_once()

    def state(self, **overrides):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        state.update(overrides)
        return state

    def test_plan_slug_delegates_to_the_shared_resolver(self):
        """R6: the title's slug source agrees with the resolver on the PRD-3 shape.

        R5 (no second copy of the recovery logic) is pinned by
        test_plan_slug_has_no_second_copy_of_the_recovery, not here.
        """
        state = self.state(
            slug=None,
            plan='docs/plans/2026-08-18-issue641-factory-pr-slug.md')
        self.assertEqual(factory_publish._plan_slug(state),
                         factory_run.run_slug(state))

    def test_title_and_body_agree_for_one_run(self):
        """AC2 and AC6: the same state renders the same slug on both surfaces."""
        state = self.state(
            issue=641, slug=None,
            plan='docs/plans/2026-08-18-issue641-factory-pr-slug.md')
        self.assertEqual(factory_publish.render_plan_title(state),
                         'plan: factory-pr-slug (#641)')
        self.assertIn('Factory run for issue #641 — factory-pr-slug.',
                      factory_report.render(state))

    def test_they_agree_on_a_non_matching_plan_filename(self):
        """AC5 on both surfaces."""
        state = self.state(issue=641, slug=None, plan='docs/plans/notes.md')
        self.assertEqual(factory_publish.render_plan_title(state),
                         'plan: notes (#641)')
        self.assertIn('Factory run for issue #641 — notes.',
                      factory_report.render(state))

    def test_they_agree_when_the_state_carries_neither_field(self):
        """AC4 on both surfaces — neither renderer raises."""
        state = self.state(issue=641, slug=None, plan=None)
        self.assertEqual(factory_publish.render_plan_title(state),
                         'plan: (no slug) (#641)')
        self.assertIn('Factory run for issue #641 — (no slug).',
                      factory_report.render(state))

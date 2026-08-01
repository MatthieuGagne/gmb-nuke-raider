"""Tests for tools/factory_publish.py"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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
        return factory_publish.summarize_plan(text or big_plan())

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
        preamble, tasks = factory_publish.summarize_plan(text)
        self.assertIn('**Goal:** g', preamble)
        self.assertNotIn('### Smoketest Checkpoint 1 — thing', preamble)
        self.assertEqual(tasks, [])

    def test_a_plan_with_no_tasks_is_all_preamble(self):
        preamble, tasks = factory_publish.summarize_plan('# T\n\nprose\n')
        self.assertEqual(preamble, ['# T', '', 'prose'])
        self.assertEqual(tasks, [])

    def test_an_empty_plan_does_not_raise(self):
        self.assertEqual(factory_publish.summarize_plan(''), ([], []))


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
        self.assertIn('Run dashboard: #481', self.body(publish=publish))

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

    def test_a_tighter_budget_sheds_the_preamble_too(self):
        """R3: the second shed level, which budget=1200 never reaches."""
        body = self.body(budget=750)
        self.assertLessEqual(len(body), 750)
        self.assertIn(factory_publish.PLAN_SHED_PREAMBLE, body)
        self.assertNotIn('## Global Constraints', body)
        self.assertIn('## Task 1: component 1', body)

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
    """Records gh invocations and replays canned results. No network, ever."""

    def __init__(self, results=None, default=(0, '', '')):
        self.calls = []
        self.results = dict(results or {})
        self.default = default

    def key(self, argv):
        """First two non-flag words, e.g. 'issue create' or 'release upload'."""
        words = [a for a in argv[1:] if not a.startswith('-')]
        return ' '.join(words[:2])

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        code, out, err = self.results.get(self.key(argv), self.default)
        return subprocess.CompletedProcess(list(argv), code, out, err)

    def argv_for(self, key):
        return [argv for argv, _ in self.calls if self.key(argv) == key]


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
    {'id': 'F_status', 'name': 'Status'}]})


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

    def test_staged_asset_is_a_byte_exact_copy(self):
        """AC5: the published asset equals the local log, byte for byte."""
        src = self.write_log('BUILD', b'\x00\x01binary\xff\n' * 40)
        fake = FakeGh()
        self.assertTrue(self.publish_log('BUILD', fake))
        staged = fake.argv_for('release upload')[0][-1]
        with open(src, 'rb') as a, open(staged, 'rb') as b:
            self.assertEqual(a.read(), b.read())

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


class TestPublishRun(PublishTestCase):
    def setUp(self):
        super().setUp()
        self.reg = factory_fixtures.build_shipped_run(self.tmp)
        path = factory_run.log_path(440, 'BUILD', self.reg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'make: ok\n')

    def fake(self, **overrides):
        results = {'issue create': (0, ISSUE_URL + '\n', ''),
                   'project item-add': (0, json.dumps({'id': 'PVTI_x'}), ''),
                   'project field-list': (0, FIELD_LIST, '')}
        results.update(overrides)
        return FakeGh(results)

    def run_publish(self, fake, **kw):
        kw.setdefault('registry', self.reg)
        kw.setdefault('now', factory_fixtures.FIXED_NOW)
        return factory_publish.publish_run(440, runner=fake, **kw)

    def test_first_publish_creates_labels_and_types_the_issue(self):
        """AC1."""
        fake = self.fake()
        result = self.run_publish(fake, stage_completed='BUILD')
        self.assertEqual(result.run_issue, 481)
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
        self.assertIn('attempt 2',
                      ' '.join(second.argv_for('issue edit')[0]))
        self.assertTrue(any('attempt-2-BUILD.log' in a
                            for a in second.argv_for('release upload')[0]))

    def test_every_gh_failure_leaves_the_outcome_unchanged(self):
        """AC9: one marked warning each, never an exception."""
        for key in ('issue create', 'issue edit', 'release upload',
                    'issue comment', 'label create', 'release create'):
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


class OpenPrCliTest(unittest.TestCase):
    def test_open_pr_without_branch_is_misuse(self):
        with redirect_stderr(io.StringIO()):
            code = factory_publish.main(
                ['--issue', '461', '--open-pr', '--title', 't',
                 '--body-file', 'x.md'])
        self.assertEqual(code, 2)

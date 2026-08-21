"""Tests for tools/factory_report.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_publish
import factory_report
import factory_run
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_fixtures

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'factory')
SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'factory_report.py')


def golden(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8', newline='') as fh:
        return fh.read()


class ReportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        factory_run.set_clock(None)
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestGoldenBody(ReportTestCase):
    def test_shipped_run_matches_the_golden_byte_for_byte(self):
        """AC2."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertEqual(body, golden('expected_pr_body.md'))

    def test_failed_run_matches_the_failed_golden(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        body = factory_report.render(factory_run.load_state(441, reg))
        self.assertEqual(body, golden('expected_pr_body_failed.md'))

    def test_body_is_stable_across_repeated_renders(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        self.assertEqual(factory_report.render(state),
                         factory_report.render(state))

    def test_body_ends_with_exactly_one_newline(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertTrue(body.endswith('\n'))
        self.assertFalse(body.endswith('\n\n'))


class TestNoAbsolutePaths(ReportTestCase):
    def test_worktree_path_never_reaches_the_body(self):
        """AC2: the worktree path stays in the registry, out of the PR."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        body = factory_report.render(state)
        self.assertNotIn(state['worktree'], body)
        self.assertIsNone(factory_report.ABSOLUTE_PATH.search(body))

    def test_a_decision_carrying_a_path_is_redacted(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        factory_run.append_event(
            441, 'decision', registry=reg,
            text=r'Pinned GBDK_HOME to C:\gbdk for the build.')
        body = factory_report.render(factory_run.load_state(441, reg))
        self.assertNotIn('C:\\gbdk', body)
        self.assertIn('<path>', body)

    def test_posix_home_path_is_redacted(self):
        self.assertEqual(factory_report.redact('see /home/matt/x for detail'),
                         'see <path> for detail')

    def test_relative_paths_survive(self):
        text = 'Plan: docs/plans/2026-07-26-issue436-observability.md'
        self.assertEqual(factory_report.redact(text), text)


class TestPermissionSection(ReportTestCase):
    def test_permission_events_are_reported_when_present(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        factory_run.append_event(440, 'permission', registry=reg,
                                 tool='Bash', outcome='denied',
                                 command='git push --force origin x')
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertIn('## Permission events', body)
        self.assertIn('| Bash | denied | git push --force origin x |', body)

    def test_section_is_absent_when_there_were_none(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertNotIn('## Permission events', body)

    def test_pipe_in_a_command_is_escaped(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        factory_run.append_event(440, 'permission', registry=reg,
                                 tool='Bash', outcome='blocked',
                                 command='ls | wc -l')
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertIn(r'ls \| wc -l', body)


class TestCli(ReportTestCase):
    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT] + list(args),
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def test_prints_the_body_and_exits_zero(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        code, out, _ = self.run_cli('--issue', '440', '--registry', reg)
        self.assertEqual(code, 0)
        self.assertEqual(out.replace('\r\n', '\n'), golden('expected_pr_body.md'))

    def test_writes_to_out_file(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        out_path = os.path.join(self.tmp, 'body.md')
        code, _, _ = self.run_cli('--issue', '440', '--registry', reg,
                                  '--out', out_path)
        self.assertEqual(code, 0)
        with open(out_path, encoding='utf-8', newline='') as fh:
            self.assertEqual(fh.read(), golden('expected_pr_body.md'))

    def test_unknown_run_is_operational_failure_not_one(self):
        code, _, err = self.run_cli('--issue', '12345', '--registry',
                                    os.path.join(self.tmp, 'empty'))
        self.assertEqual(code, 2)
        self.assertIn('no registry entry', err)


class DecisionShapeTests(ReportTestCase):
    """#517 R17 — AC13."""

    def test_uses_the_shared_renderer(self):
        self.assertIs(factory_report.decision_lines,
                      factory_publish.decision_lines)

    def test_a_rationale_renders_as_details_in_the_pr_body(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertIn('<details><summary>Rationale</summary>', body)
        self.assertIn('- **', body)


class PlanReviewFindingsTests(ReportTestCase):
    """#530 R3 — AC3."""

    def test_a_marked_decision_is_a_finding(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        findings, decisions = factory_report.partition_decisions(state)
        self.assertEqual([f['text'] for f in findings],
                         ['Screenshots become data URIs.'])
        self.assertNotIn('Screenshots become data URIs.',
                         [d['text'] for d in decisions])

    def test_an_unmarked_record_counts_as_a_decision(self):
        findings, decisions = factory_report.partition_decisions(
            {'decisions': [{'text': 'Old journal.'}]})
        self.assertEqual(findings, [])
        self.assertEqual([d['text'] for d in decisions], ['Old journal.'])

    def test_findings_never_reach_the_pull_request_body(self):
        """AC3."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertNotIn('Screenshots become data URIs.', body)
        self.assertNotIn('data URI', body)

    def test_the_decisions_section_keeps_the_other_decisions(self):
        """AC1: nothing is lost, only moved."""
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertIn('Journal is the source of truth', body)
        self.assertIn('The publisher deletes the temporary copy after each '
                      'upload.', body)


class TestStageLogsSection(ReportTestCase):
    """#489 AC3: the PR body names the stages that captured no log."""

    def test_unlogged_stages_are_named_in_canonical_order(self):
        state = {'issue': 489, 'unlogged': ['VERIFY', 'GATE', 'BUILD']}
        body = factory_report.render(state)
        self.assertIn('## Stage logs', body)
        self.assertIn('No log was captured for: GATE, BUILD, VERIFY.', body)

    def test_the_section_sits_between_gate_results_and_decisions(self):
        state = {'issue': 489, 'unlogged': ['BUILD']}
        body = factory_report.render(state)
        self.assertLess(body.index('## Gate results'), body.index('## Stage logs'))
        self.assertLess(body.index('## Stage logs'), body.index('## Decisions made'))

    def test_the_failed_fixture_run_names_its_unlogged_stages(self):
        reg = factory_fixtures.build_failed_run(self.tmp)
        state = factory_run.load_state(441, reg)
        self.assertEqual(factory_run.unlogged_stages(state), ['GATE', 'BUILD'])
        self.assertIn('No log was captured for: GATE, BUILD.',
                      factory_report.render(state))

    def test_no_section_when_every_stage_logged(self):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        body = factory_report.render(factory_run.load_state(440, reg))
        self.assertNotIn('## Stage logs', body)

    def test_no_section_for_an_empty_list(self):
        self.assertNotIn('## Stage logs',
                         factory_report.render({'issue': 489, 'unlogged': []}))

    def test_no_section_when_the_key_is_absent(self):
        self.assertNotIn('## Stage logs', factory_report.render({'issue': 489}))

    def test_a_bare_state_dict_does_not_raise(self):
        self.assertIn('Closes #489', factory_report.render({'issue': 489}))

    def test_the_sentence_avoids_the_publish_sentinel_substring(self):
        """tests/test_factory_publish.py asserts this substring is absent."""
        body = factory_report.render({'issue': 489, 'unlogged': ['BUILD']})
        self.assertNotIn('no stage log captured', body)
        self.assertNotIn('no stage log captured',
                         factory_report.UNLOGGED_STAGES_NOTE)

    def test_the_wording_lives_in_a_shared_module_level_constant(self):
        rendered = factory_report.UNLOGGED_STAGES_NOTE % 'BUILD, VERIFY'
        self.assertIn(rendered, factory_report.render(
            {'issue': 489, 'unlogged': ['VERIFY', 'BUILD']}))

    def test_the_note_is_one_unwrapped_line(self):
        """The run issue puts a table under it, and the note stays one line so
        it reads as its own paragraph above that table. GFM parses a table that
        interrupts a paragraph either way — this pins the shape, not a rescue
        from a parser that would drop the table."""
        self.assertNotIn('\n', factory_report.UNLOGGED_STAGES_NOTE)
        body = factory_report.render({'issue': 489, 'unlogged': ['BUILD']})
        self.assertIn(factory_report.UNLOGGED_STAGES_NOTE % 'BUILD',
                      body.splitlines())

    def test_the_sentence_reads_for_a_single_stage(self):
        """'Those commands', not 'Those stages': one stage is the common case."""
        self.assertIn('No log was captured for: BUILD. Those commands ran '
                      'outside `tools/factory_log.py`, so their output is '
                      'not recoverable.',
                      factory_report.render({'issue': 489,
                                             'unlogged': ['BUILD']}))


# A `sys.addaudithook` hook can never be removed once installed, so the hook
# itself is permanent and deliberately inert: it records only while `_AUDITING`
# is on, which exactly one test turns on and turns off again in a `finally`.
# Every other test in the process pays one flag read per audited operation.
_AUDITED = ('open', 'os.stat', 'os.listdir', 'subprocess.Popen')
_AUDIT_EVENTS = []
_AUDITING = False


def _audit_hook(event, _args):
    if _AUDITING and event in _AUDITED:
        _AUDIT_EVENTS.append(event)


class TestRenderReadsNoFilesystem(ReportTestCase):
    """#489: ``render`` is a pure function of state, enforced not asserted.

    The design depends on it — ``unlogged_stages`` takes no registry because
    several callers render a hand-built dict with nothing on disk — but a
    reviewer who inserted an ``open()`` inside ``render`` found every test in
    this file still green. This one traps the syscalls instead of trusting the
    prose.
    """

    def test_render_opens_stats_and_spawns_nothing(self):
        """The audit hook alone would leave one hole: CPython raises no
        ``os.stat`` audit event in practice (verified on 3.13), and stat is
        exactly how a probe like ``factory_run.log_captured`` reads the
        registry — ``os.path.getsize`` resolves ``os.stat`` at call time. So
        the hook covers ``open``, ``os.listdir`` and ``subprocess.Popen``, and
        a recording wrapper covers ``os.stat``.
        """
        global _AUDITING
        state = {'issue': 489, 'unlogged': ['VERIFY', 'GATE']}
        factory_report.render(state)  # warm any lazy import first
        sys.addaudithook(_audit_hook)
        del _AUDIT_EVENTS[:]
        stats = []
        real_stat = os.stat

        def recording_stat(*args, **kwargs):
            stats.append(args)
            return real_stat(*args, **kwargs)

        _AUDITING = True
        try:
            with mock.patch.object(os, 'stat', recording_stat):
                body = factory_report.render(state)
        finally:
            _AUDITING = False
        self.assertEqual(_AUDIT_EVENTS, [])
        self.assertEqual(stats, [])
        self.assertIn('## Stage logs', body)


class TestSummarySlug(ReportTestCase):
    """#641 R4: the Summary line goes through the shared resolver."""

    def body(self, **overrides):
        reg = factory_fixtures.build_shipped_run(self.tmp)
        state = factory_run.load_state(440, reg)
        state.update(overrides)
        return factory_report.render(state)

    def test_slug_is_recovered_from_the_plan_filename(self):
        """AC1."""
        body = self.body(
            slug=None,
            plan='docs/plans/2026-08-18-issue641-factory-pr-slug.md')
        self.assertIn('Factory run for issue #440 — factory-pr-slug.', body)
        self.assertNotIn('(no slug)', body)

    def test_an_explicit_slug_is_preferred(self):
        """AC3."""
        body = self.body(
            slug='observability',
            plan='docs/plans/2026-08-18-issue641-factory-pr-slug.md')
        self.assertIn('Factory run for issue #440 — observability.', body)

    def test_a_state_with_neither_field_renders_without_raising(self):
        """AC4."""
        body = self.body(slug=None, plan=None)
        self.assertIn('Factory run for issue #440 — (no slug).', body)

    def test_a_non_matching_plan_filename_renders_its_stem(self):
        """AC5."""
        body = self.body(slug=None, plan='docs/plans/notes.md')
        self.assertIn('Factory run for issue #440 — notes.', body)

    def test_the_summary_renders_the_spec_example_verbatim(self):
        """AC1's literal sentence, on a bare state dict.

        Asserts the literal rather than ``assertIn(run_slug(state), body)``,
        which compares the resolver to itself through an unanchored substring
        test that any short return value would satisfy.
        """
        state = {'issue': 641, 'slug': None,
                 'plan': 'docs/plans/2026-08-18-issue641-factory-pr-slug.md'}
        self.assertIn('Factory run for issue #641 — factory-pr-slug.',
                      factory_report.render(state))


if __name__ == '__main__':
    unittest.main()

"""Tests for tools/factory_report.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

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

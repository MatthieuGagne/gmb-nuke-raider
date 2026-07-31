"""Tests for tools/factory_report.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
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


if __name__ == '__main__':
    unittest.main()

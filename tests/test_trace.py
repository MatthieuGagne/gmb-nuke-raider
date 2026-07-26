"""Tests for tools/trace.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import trace as trace_tool

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools', 'trace.py')


class TestPlanFilename(unittest.TestCase):
    def test_conventional_name_parses_date_and_issue(self):
        date, issue = trace_tool.parse_plan_name(
            '2026-07-26-issue435-traceability.md')
        self.assertEqual(date, '2026-07-26')
        self.assertEqual(issue, 435)

    def test_legacy_name_parses_date_but_no_issue(self):
        date, issue = trace_tool.parse_plan_name(
            '2026-04-04-turret-fire-and-disappear.md')
        self.assertEqual(date, '2026-04-04')
        self.assertIsNone(issue)

    def test_undated_name_parses_nothing(self):
        date, issue = trace_tool.parse_plan_name('notes.md')
        self.assertIsNone(date)
        self.assertIsNone(issue)

    def test_slug_with_digits_still_parses(self):
        date, issue = trace_tool.parse_plan_name('2026-07-26-issue7-fix-16x16.md')
        self.assertEqual(issue, 7)


class TestPlanHeader(unittest.TestCase):
    def test_header_found(self):
        self.assertEqual(
            trace_tool.plan_header_issue('# Title\n\n**Issue:** #435\n\nbody'),
            435)

    def test_header_absent(self):
        self.assertIsNone(trace_tool.plan_header_issue('# Title\n\nbody'))

    def test_inline_mention_is_not_a_header(self):
        self.assertIsNone(
            trace_tool.plan_header_issue('see **Issue:** #435 inline'))


class TestClosesRefs(unittest.TestCase):
    def test_closes(self):
        self.assertEqual(trace_tool.closes_refs('Closes #424'), [424])

    def test_all_github_keywords(self):
        body = 'Fixed #1\nresolves #2\nclose #3'
        self.assertEqual(trace_tool.closes_refs(body), [1, 2, 3])

    def test_bare_mention_is_not_a_link(self):
        self.assertEqual(trace_tool.closes_refs('related to #424'), [])

    def test_none_body(self):
        self.assertEqual(trace_tool.closes_refs(None), [])


class TestFindPlan(unittest.TestCase):
    def _plan_dir(self, tmp):
        path = os.path.join(tmp, 'docs', 'plans')
        os.makedirs(path)
        return path

    def test_match_by_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = self._plan_dir(tmp)
            with open(os.path.join(plans, '2026-07-26-issue435-trace.md'),
                      'w', encoding='utf-8') as fh:
                fh.write('# Trace\n')
            found = trace_tool.find_plan(435, tmp)
            self.assertEqual(found['path'], 'docs/plans/2026-07-26-issue435-trace.md')
            self.assertFalse(found['removed'])

    def test_match_by_header_when_filename_lacks_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = self._plan_dir(tmp)
            with open(os.path.join(plans, '2026-04-04-legacy.md'),
                      'w', encoding='utf-8') as fh:
                fh.write('# Legacy\n\n**Issue:** #300\n')
            found = trace_tool.find_plan(300, tmp)
            self.assertEqual(found['path'], 'docs/plans/2026-04-04-legacy.md')

    def test_no_match_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._plan_dir(tmp)
            self.assertIsNone(trace_tool.find_plan(999, tmp))


class TestRenderChain(unittest.TestCase):
    _CHAIN = {
        'issue': {'number': 424, 'title': 'LASER primary weapon',
                  'state': 'CLOSED', 'url': 'u'},
        'plan': None,
        'branch': 'worktree-plan-laser-weapon-damage-424',
        'pr': {'number': 428, 'title': 'feat: LASER', 'state': 'MERGED',
               'url': 'u'},
        'merge': {'merged_at': '2026-07-10T01:45:42Z',
                  'commit': 'f18e5ef7358c910f7b6d50e21262bff3744fee86'},
    }

    def test_renders_every_link(self):
        out = trace_tool.render_chain(self._CHAIN)
        self.assertIn('issue  #424  CLOSED  LASER primary weapon', out)
        self.assertIn('plan   (not found)', out)
        self.assertIn('branch worktree-plan-laser-weapon-damage-424', out)
        self.assertIn('PR     #428  MERGED', out)
        self.assertIn('merge  2026-07-10  f18e5ef', out)

    def test_removed_plan_is_annotated(self):
        chain = dict(self._CHAIN)
        chain['plan'] = {'path': 'docs/plans/2026-04-04-old.md',
                         'removed': True, 'commit': 'abc1234def'}
        out = trace_tool.render_chain(chain)
        self.assertIn('(removed from tree; added in abc1234)', out)

    def test_unmerged_pr(self):
        chain = dict(self._CHAIN)
        chain['merge'] = None
        self.assertIn('merge  (not merged)', trace_tool.render_chain(chain))


class TestCli(unittest.TestCase):
    def _run(self, args):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True)

    def test_no_argument_is_usage_error(self):
        self.assertEqual(self._run([]).returncode, 2)


if __name__ == '__main__':
    unittest.main()

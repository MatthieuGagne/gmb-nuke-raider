"""Tests for tools/deny_gate_hook.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'deny_gate_hook.py')


def run(command, tool='Bash', factory=False):
    """Invoke the hook with *command*; return (exit_code, stderr)."""
    env = dict(os.environ)
    env.pop('NUKE_FACTORY_RUN', None)
    if factory:
        # Truthy so the FACTORY_ONLY rules fire, but deliberately non-numeric:
        # factory_run.run_issue() reads this variable as an issue number, and a
        # numeric value here would journal a denial into the real registry on
        # every run of this suite.
        env['NUKE_FACTORY_RUN'] = '1x'
    payload = json.dumps({
        'cwd': os.getcwd(),
        'tool_name': tool,
        'tool_input': {'command': command},
    })
    p = subprocess.run([sys.executable, SCRIPT], input=payload,
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stderr


class UnconditionalDenyTests(unittest.TestCase):
    def test_blocks_long_force_push(self):
        self.assertEqual(run('git push --force origin feat')[0], 2)

    def test_blocks_short_force_push(self):
        self.assertEqual(run('git push -f origin feat')[0], 2)

    def test_blocks_force_with_lease(self):
        self.assertEqual(run('git push --force-with-lease origin feat')[0], 2)

    def test_blocks_trailing_force_flag(self):
        self.assertEqual(run('git push origin feat --force')[0], 2)

    def test_blocks_force_push_wrapped_in_bash_c(self):
        self.assertEqual(run('bash -c "git push --force origin feat"')[0], 2)

    def test_blocks_push_to_master(self):
        self.assertEqual(run('git push origin master')[0], 2)

    def test_blocks_pr_merge(self):
        self.assertEqual(run('gh pr merge 443 --squash')[0], 2)

    def test_blocks_on_powershell_tool_too(self):
        self.assertEqual(run('git push -f origin feat', tool='PowerShell')[0], 2)

    def test_reports_a_reason_on_stderr(self):
        code, err = run('git push --force origin feat')
        self.assertEqual(code, 2)
        self.assertIn('force push', err)


class AllowedTests(unittest.TestCase):
    def test_allows_normal_push(self):
        self.assertEqual(run('git push -u origin feat-x')[0], 0)

    def test_allows_pr_create(self):
        self.assertEqual(run('gh pr create --title x --body y')[0], 0)

    def test_allows_branch_named_like_master(self):
        self.assertEqual(run('git push origin feature-master-fix')[0], 0)

    def test_allows_follow_tags(self):
        self.assertEqual(run('git push --follow-tags origin feat')[0], 0)

    def test_allows_unrelated_tool(self):
        code, _ = run('git push --force origin feat', tool='Read')
        self.assertEqual(code, 0)

    def test_allows_garbage_stdin(self):
        p = subprocess.run([sys.executable, SCRIPT], input='not json',
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


class FactoryGatedTests(unittest.TestCase):
    """Legitimate interactively, forbidden to an unattended run."""

    def test_worktree_remove_allowed_interactively(self):
        self.assertEqual(run('git worktree remove foo')[0], 0)

    def test_worktree_remove_blocked_in_factory(self):
        self.assertEqual(run('git worktree remove foo', factory=True)[0], 2)

    def test_branch_delete_allowed_interactively(self):
        self.assertEqual(run('git branch -D feat-x')[0], 0)

    def test_branch_delete_blocked_in_factory(self):
        self.assertEqual(run('git branch -D feat-x', factory=True)[0], 2)

    def test_hard_reset_blocked_in_factory(self):
        self.assertEqual(run('git reset --hard HEAD~1', factory=True)[0], 2)

    def test_worktree_prune_blocked_in_factory(self):
        self.assertEqual(run('git worktree prune', factory=True)[0], 2)

    def test_branch_list_never_blocked(self):
        self.assertEqual(run('git branch --show-current', factory=True)[0], 0)


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_run


class TestDenialIsRecorded(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reg = os.path.join(self.tmp, 'registry')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def deny(self, command, run='436'):
        env = dict(os.environ)
        env['NUKE_FACTORY_RUN'] = run
        env['NUKE_FACTORY_REGISTRY'] = self.reg
        payload = json.dumps({'cwd': os.getcwd(), 'tool_name': 'Bash',
                              'tool_input': {'command': command}})
        return subprocess.run([sys.executable, SCRIPT], input=payload,
                              capture_output=True, text=True, env=env)

    def test_refusal_still_exits_two(self):
        self.assertEqual(self.deny('git push --force origin x').returncode, 2)

    def test_refusal_is_journalled_with_tool_and_command(self):
        """AC6: a denial is observable after the fact, not only in the terminal."""
        self.deny('git push --force origin x')
        events = factory_run.read_journal(436, self.reg)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['kind'], 'permission')
        self.assertEqual(events[0]['outcome'], 'denied')
        self.assertEqual(events[0]['tool'], 'Bash')
        self.assertEqual(events[0]['command'], 'git push --force origin x')
        self.assertEqual(events[0]['reason'], 'force push')

    def test_allowed_command_records_nothing(self):
        self.assertEqual(self.deny('git status').returncode, 0)
        self.assertEqual(factory_run.read_journal(436, self.reg), [])

    def test_non_numeric_run_marker_still_refuses(self):
        """The legacy truthy value must keep gating FACTORY_ONLY rules."""
        proc = self.deny('git worktree remove x', run='1x')
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(factory_run.read_journal(436, self.reg), [])


if __name__ == '__main__':
    unittest.main()

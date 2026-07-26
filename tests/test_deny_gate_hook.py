"""Tests for tools/deny_gate_hook.py"""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'deny_gate_hook.py')


def run(command, tool='Bash', factory=False):
    """Invoke the hook with *command*; return (exit_code, stderr)."""
    env = dict(os.environ)
    env.pop('NUKE_FACTORY_RUN', None)
    if factory:
        env['NUKE_FACTORY_RUN'] = '1'
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


if __name__ == '__main__':
    unittest.main()

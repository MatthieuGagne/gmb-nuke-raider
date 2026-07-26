"""Tests for tools/skill_overlay_hook.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools', 'skill_overlay_hook.py')

OVERLAY = """---
name: testskill
baseline: superpowers@6.2.0
---

## Project delta

Always do the GB thing.
"""

PLUGINS = {
    "version": 2,
    "plugins": {"superpowers@claude-plugins-official": [{"version": "6.2.0"}]},
}


def run_hook(payload, plugins_path):
    env = dict(os.environ, SKILL_OVERLAY_PLUGINS_JSON=plugins_path)
    return subprocess.run(
        [sys.executable, SCRIPT], input=payload,
        capture_output=True, text=True, env=env)


class HookTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.overlays = os.path.join(self.root, '.claude', 'skill-overlays')
        os.makedirs(self.overlays)
        self.write_overlay('testskill', OVERLAY)
        self.plugins_path = os.path.join(self.root, 'installed_plugins.json')
        with open(self.plugins_path, 'w', encoding='utf-8') as fh:
            json.dump(PLUGINS, fh)

    def tearDown(self):
        self.tmp.cleanup()

    def write_overlay(self, name, content):
        with open(os.path.join(self.overlays, name + '.md'), 'w',
                  encoding='utf-8') as fh:
            fh.write(content)

    def post_tool_use(self, skill, cwd=None):
        return json.dumps({
            'hook_event_name': 'PostToolUse', 'tool_name': 'Skill',
            'cwd': cwd or self.root, 'tool_input': {'skill': skill}})

    def prompt_submit(self, prompt, cwd=None):
        return json.dumps({
            'hook_event_name': 'UserPromptSubmit',
            'cwd': cwd or self.root, 'prompt': prompt})

    def context_of(self, proc):
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        return out['hookSpecificOutput']


class TestInjection(HookTestBase):
    def test_post_tool_use_strips_plugin_prefix(self):
        proc = run_hook(self.post_tool_use('superpowers:testskill'),
                        self.plugins_path)
        hso = self.context_of(proc)
        self.assertEqual(hso['hookEventName'], 'PostToolUse')
        self.assertIn('Always do the GB thing.', hso['additionalContext'])

    def test_post_tool_use_bare_name(self):
        proc = run_hook(self.post_tool_use('testskill'), self.plugins_path)
        self.assertIn('Always do the GB thing.',
                      self.context_of(proc)['additionalContext'])

    def test_frontmatter_not_injected(self):
        proc = run_hook(self.post_tool_use('testskill'), self.plugins_path)
        self.assertNotIn('baseline: superpowers',
                         self.context_of(proc)['additionalContext'])

    def test_user_prompt_slash_command(self):
        proc = run_hook(self.prompt_submit('/testskill some args'),
                        self.plugins_path)
        hso = self.context_of(proc)
        self.assertEqual(hso['hookEventName'], 'UserPromptSubmit')
        self.assertIn('Always do the GB thing.', hso['additionalContext'])

    def test_user_prompt_slash_command_with_plugin_prefix(self):
        proc = run_hook(self.prompt_submit('/superpowers:testskill'),
                        self.plugins_path)
        self.assertIn('Always do the GB thing.',
                      self.context_of(proc)['additionalContext'])

    def test_cwd_subdirectory_walks_up(self):
        sub = os.path.join(self.root, 'src', 'deep')
        os.makedirs(sub)
        proc = run_hook(self.post_tool_use('testskill', cwd=sub),
                        self.plugins_path)
        self.assertIn('Always do the GB thing.',
                      self.context_of(proc)['additionalContext'])


class TestSilence(HookTestBase):
    def assert_silent_ok(self, proc):
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, '')

    def test_plain_prompt_is_silent(self):
        self.assert_silent_ok(run_hook(
            self.prompt_submit('fix the racer bug please'), self.plugins_path))

    def test_unmatched_skill_is_silent(self):
        self.assert_silent_ok(run_hook(
            self.post_tool_use('no-overlay-here'), self.plugins_path))

    def test_other_tool_is_silent(self):
        payload = json.dumps({'hook_event_name': 'PostToolUse',
                              'tool_name': 'Bash', 'cwd': self.root,
                              'tool_input': {'command': 'ls'}})
        self.assert_silent_ok(run_hook(payload, self.plugins_path))

    def test_malformed_stdin_is_silent_exit_zero(self):
        self.assert_silent_ok(run_hook('this is { not json', self.plugins_path))

    def test_empty_stdin_is_silent_exit_zero(self):
        self.assert_silent_ok(run_hook('', self.plugins_path))

    def test_bare_slash_is_silent(self):
        self.assert_silent_ok(run_hook(self.prompt_submit('/'),
                                       self.plugins_path))

    def test_path_traversal_name_is_silent(self):
        self.assert_silent_ok(run_hook(
            self.prompt_submit('/../../etc/passwd'), self.plugins_path))


class TestCanary(HookTestBase):
    def test_version_mismatch_prepends_note(self):
        self.write_overlay('oldskill', OVERLAY.replace(
            'superpowers@6.2.0', 'superpowers@6.1.1'))
        proc = run_hook(self.post_tool_use('oldskill'), self.plugins_path)
        ctx = self.context_of(proc)['additionalContext']
        self.assertIn('baseline has updated', ctx)
        self.assertIn('6.1.1', ctx)
        self.assertIn('6.2.0', ctx)

    def test_version_match_no_note(self):
        proc = run_hook(self.post_tool_use('testskill'), self.plugins_path)
        self.assertNotIn('baseline has updated',
                         self.context_of(proc)['additionalContext'])

    def test_non_superpowers_baseline_no_note(self):
        self.write_overlay('thirdparty', OVERLAY.replace(
            'superpowers@6.2.0', 'grill-with-docs@2026-07-26'))
        proc = run_hook(self.post_tool_use('thirdparty'), self.plugins_path)
        self.assertNotIn('baseline has updated',
                         self.context_of(proc)['additionalContext'])

    def test_missing_plugins_json_still_injects_without_note(self):
        proc = run_hook(self.post_tool_use('testskill'),
                        os.path.join(self.root, 'nope.json'))
        ctx = self.context_of(proc)['additionalContext']
        self.assertIn('Always do the GB thing.', ctx)
        self.assertNotIn('baseline has updated', ctx)


if __name__ == '__main__':
    unittest.main()

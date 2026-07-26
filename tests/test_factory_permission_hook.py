"""Tests for tools/factory_permission_hook.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_permission_hook as hook
import factory_run

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'factory_permission_hook.py')


class TestParseTool(unittest.TestCase):
    def test_extracts_the_tool_from_the_standard_message(self):
        self.assertEqual(
            hook.parse_tool('Claude needs your permission to use Bash'), 'Bash')

    def test_extracts_a_hyphenated_mcp_tool(self):
        self.assertEqual(
            hook.parse_tool('Claude needs your permission to use mcp-gmail'),
            'mcp-gmail')

    def test_unrecognised_message_is_none(self):
        self.assertIsNone(hook.parse_tool('Waiting for your input'))

    def test_empty_message_is_none(self):
        self.assertIsNone(hook.parse_tool(''))


class HookRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reg = os.path.join(self.tmp, 'registry')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_hook(self, payload, run=None):
        env = dict(os.environ)
        env.pop('NUKE_FACTORY_RUN', None)
        if run is not None:
            env['NUKE_FACTORY_RUN'] = run
        env['NUKE_FACTORY_REGISTRY'] = self.reg
        proc = subprocess.run([sys.executable, SCRIPT],
                              input=json.dumps(payload), capture_output=True,
                              text=True, env=env)
        return proc.returncode

    def events(self, issue):
        return factory_run.read_journal(issue, self.reg)


class TestNotificationHook(HookRunner):
    PAYLOAD = {'cwd': '.', 'hook_event_name': 'Notification',
               'message': 'Claude needs your permission to use Bash'}

    def test_records_a_blocked_prompt_against_the_run(self):
        """AC6: a permission prompt round-trips through the journal."""
        self.assertEqual(self.run_hook(self.PAYLOAD, run='436'), 0)
        events = self.events(436)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['kind'], 'permission')
        self.assertEqual(events[0]['tool'], 'Bash')
        self.assertEqual(events[0]['outcome'], 'blocked')
        self.assertEqual(events[0]['issue'], 436)

    def test_records_nothing_outside_a_factory_run(self):
        self.assertEqual(self.run_hook(self.PAYLOAD), 0)
        self.assertFalse(os.path.exists(os.path.join(self.reg, 'runs')))

    def test_non_numeric_run_marker_records_nothing_but_still_exits_zero(self):
        self.assertEqual(self.run_hook(self.PAYLOAD, run='1x'), 0)
        self.assertFalse(os.path.exists(os.path.join(self.reg, 'runs')))

    def test_unparseable_payload_exits_zero(self):
        proc = subprocess.run([sys.executable, SCRIPT], input='not json',
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)

    def test_unrecognised_message_is_recorded_as_unknown_tool(self):
        self.run_hook({'cwd': '.', 'message': 'Something happened'}, run='436')
        self.assertEqual(self.events(436)[0]['tool'], 'unknown')

    def test_hook_never_blocks_even_when_the_registry_is_unusable(self):
        env_reg = os.path.join(self.tmp, 'file')
        with open(env_reg, 'w') as fh:
            fh.write('not a directory')
        env = dict(os.environ)
        env['NUKE_FACTORY_RUN'] = '436'
        env['NUKE_FACTORY_REGISTRY'] = env_reg
        proc = subprocess.run([sys.executable, SCRIPT],
                              input=json.dumps(self.PAYLOAD),
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0)


if __name__ == '__main__':
    unittest.main()

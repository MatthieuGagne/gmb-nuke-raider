"""Tests for tools/bank_check_hook.py — the bank pre-write gate.

Two payload shapes reach this hook. Claude Code's Write/Edit tools send
``file_path``; Pi's ``write``/``edit`` tools send ``path`` (#497). Before the
port the hook read ``file_path`` only, so a Pi write of an unmanifested
src/*.c file read an empty string, returned early, and was allowed — silently.

The probe path below is deliberately absent from bank-manifest.json AND from
disk: bank_check.check_file reports the missing manifest entry either way, so
these tests need no fixture file and write nothing.
"""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'bank_check_hook.py')
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Not in bank-manifest.json and not on disk. Both are required: a manifested
# path would pass the check, and an on-disk path would need cleanup.
UNMANIFESTED = 'src/pi_gate_probe_not_in_manifest.c'


def run(tool_input, tool='write'):
    """Invoke the hook with *tool_input*; return (exit_code, stdout, stderr)."""
    payload = json.dumps({
        'cwd': REPO_ROOT,
        'tool_name': tool,
        'tool_input': tool_input,
    })
    p = subprocess.run([sys.executable, SCRIPT], input=payload,
                       capture_output=True, text=True, cwd=REPO_ROOT)
    return p.returncode, p.stdout, p.stderr


class PiPayloadTests(unittest.TestCase):
    """AC4: a Pi-shaped write of an unmanifested src file is blocked."""

    def test_pi_write_of_unmanifested_src_file_is_blocked(self):
        code, _, err = run({'path': UNMANIFESTED, 'content': 'int x;\n'})
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_pi_edit_of_unmanifested_src_file_is_blocked(self):
        code, _, err = run({'path': UNMANIFESTED, 'old_string': 'a',
                            'new_string': 'b'}, tool='edit')
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_pi_write_outside_src_is_allowed(self):
        self.assertEqual(run({'path': 'tools/scratch.c'})[0], 0)

    def test_pi_write_of_non_c_file_is_allowed(self):
        self.assertEqual(run({'path': 'README.md'})[0], 0)


class ClaudePayloadTests(unittest.TestCase):
    """AC5: the Claude-shaped payload keeps working exactly as before."""

    def test_claude_write_of_unmanifested_src_file_is_blocked(self):
        code, _, err = run({'file_path': UNMANIFESTED}, tool='Write')
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_claude_write_of_a_header_file_is_allowed(self):
        """A .h path needs no manifest entry — the check runs and passes.

        Deliberately not src/main.c: coupling a hook test to a live manifest
        entry breaks it whenever the manifest changes for unrelated reasons.
        """
        code, out, _ = run({'file_path': 'src/pi_gate_probe.h'}, tool='Write')
        self.assertEqual(code, 0)
        self.assertIn('OK', out)

    def test_claude_write_outside_src_is_allowed(self):
        self.assertEqual(run({'file_path': 'tools/scratch.c'}, tool='Write')[0], 0)


class FailOpenTests(unittest.TestCase):
    """Unparseable or empty input must never block — matches the other hooks."""

    def test_garbage_stdin_is_allowed(self):
        p = subprocess.run([sys.executable, SCRIPT], input='not json',
                           capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(p.returncode, 0)

    def test_empty_tool_input_is_allowed(self):
        self.assertEqual(run({})[0], 0)

    def test_neither_path_nor_file_path_is_allowed(self):
        self.assertEqual(run({'content': 'int x;\n'})[0], 0)


if __name__ == '__main__':
    unittest.main()

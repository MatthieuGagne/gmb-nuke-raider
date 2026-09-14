"""Tests for tools/bank_check_hook.py — the bank pre-write gate.

Two payload keys reach this hook. Claude Code's Write/Edit tools send
``file_path``; omp's ``write``/``edit`` tools may send ``path``. Before the
port the hook read ``file_path`` only, so a ``path``-keyed write of an
unmanifested src/*.c file read an empty string, returned early, and was allowed
— silently.

The probe path below is deliberately absent from bank-manifest.json AND from
disk: bank_check.check_file reports the missing manifest entry either way, so
these tests need no fixture file and write nothing.
"""
import json
import os
import subprocess
import sys
import tempfile
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


def run_declared(tool_input, project_dir, tool='Write'):
    """Invoke the hook with CLAUDE_PROJECT_DIR set to *project_dir* (#728).

    The payload cwd stays at REPO_ROOT — the straddle this project actually
    runs in, where the session root and the worktree being written differ."""
    payload = json.dumps({
        'cwd': REPO_ROOT,
        'tool_name': tool,
        'tool_input': tool_input,
    })
    env = dict(os.environ)
    env['CLAUDE_PROJECT_DIR'] = project_dir
    p = subprocess.run([sys.executable, SCRIPT], input=payload,
                       capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return p.returncode, p.stdout, p.stderr


class PathKeyPayloadTests(unittest.TestCase):
    """AC4: a path-keyed write of an unmanifested src file is blocked."""

    def test_path_write_of_unmanifested_src_file_is_blocked(self):
        code, _, err = run({'path': UNMANIFESTED, 'content': 'int x;\n'})
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_path_edit_of_unmanifested_src_file_is_blocked(self):
        code, _, err = run({'path': UNMANIFESTED, 'old_string': 'a',
                            'new_string': 'b'}, tool='edit')
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_path_write_outside_src_is_allowed(self):
        self.assertEqual(run({'path': 'tools/scratch.c'})[0], 0)

    def test_path_write_of_non_c_file_is_allowed(self):
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


class RepoMembershipTests(unittest.TestCase):
    """R5/AC5: only paths resolving inside the project dir are gated."""

    def test_absolute_outside_path_is_allowed(self):
        outside = os.path.join(tempfile.gettempdir(), 'scratch', 'src', 'fixture.c')
        self.assertEqual(run({'file_path': outside}, tool='Write')[0], 0)

    def test_dot_dot_escape_is_allowed(self):
        """#728's reproduction verbatim: a scratch fixture five levels out."""
        escape = '../../../../../scratchpad/ac4/src/fixture.c'
        self.assertEqual(run({'file_path': escape}, tool='Write')[0], 0)

    def test_absolute_in_repo_path_is_still_blocked(self):
        inside = os.path.join(REPO_ROOT, UNMANIFESTED.replace('/', os.sep))
        code, _, err = run({'file_path': inside}, tool='Write')
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_worktree_write_is_gated_when_project_dir_is_another_repo(self):
        """The straddle this project mandates: the session is rooted at the main
        repo (C:\\Code\\nuke-raider) while every write lands in an Orca worktree.

        The declared project dir then contains none of the worktree's files. If
        membership were judged against CLAUDE_PROJECT_DIR alone the hard bank
        gate would exit 0 on an unmanifested src/*.c — a check that cannot run
        reading as a pass, which is the defect #728 exists to eliminate. The
        payload's repo root is an equally valid base, so the path is gated."""
        with tempfile.TemporaryDirectory() as elsewhere:
            code, _, err = run_declared({'file_path': UNMANIFESTED}, elsewhere)
        self.assertEqual(code, 2)
        self.assertIn('not in bank-manifest.json', err)

    def test_scratch_fixture_stays_ignored_under_a_foreign_project_dir(self):
        """R5/AC5 must not regress: a fixture outside BOTH bases is ignored."""
        with tempfile.TemporaryDirectory() as elsewhere:
            outside = os.path.join(tempfile.gettempdir(), 'scratch', 'src', 'fixture.c')
            self.assertEqual(run_declared({'file_path': outside}, elsewhere)[0], 0)

    def test_project_dir_above_the_repo_reports_the_repo_relative_path(self):
        """An ancestor CLAUDE_PROJECT_DIR keeps the path nominally 'inside' it,
        so relativising against it leaves a leading worktree-name component and
        bank_check looks up a manifest key that cannot exist. The path handed to
        bank_check must be relative to the directory it actually runs in."""
        parent = os.path.dirname(REPO_ROOT)
        code, _, err = run_declared({'file_path': UNMANIFESTED}, parent)
        self.assertEqual(code, 2)
        self.assertIn('ERROR: %s is not in bank-manifest.json' % UNMANIFESTED, err)
        self.assertNotIn(os.path.basename(REPO_ROOT) + '/', err)

    def test_reported_path_keeps_the_spelling_the_developer_typed(self):
        """normcase belongs to the containment comparison only. Folding it into
        the returned path makes the manifest key — and the message a developer
        reads — a lowercased impostor of what they wrote."""
        mixed = 'src/PiGateProbe_NotInManifest.c'
        code, _, err = run({'file_path': mixed}, tool='Write')
        self.assertEqual(code, 2)
        self.assertIn(mixed, err)

    def test_case_differing_project_dir_still_gates(self):
        """Path comparison is normcase/realpath, not lexical: a drive-letter or
        case difference must not silently disable the gate (a gate that cannot
        run reading as a pass is the #728 defect class itself)."""
        payload = json.dumps({'cwd': REPO_ROOT, 'tool_name': 'Write',
                              'tool_input': {'file_path': UNMANIFESTED}})
        env = dict(os.environ)
        env['CLAUDE_PROJECT_DIR'] = REPO_ROOT.upper()
        p = subprocess.run([sys.executable, SCRIPT], input=payload,
                           capture_output=True, text=True, cwd=REPO_ROOT, env=env)
        if os.name != 'nt':
            self.skipTest('case-insensitive path comparison is a Windows behaviour')
        self.assertEqual(p.returncode, 2)
        self.assertIn('not in bank-manifest.json', p.stderr)


if __name__ == '__main__':
    unittest.main()

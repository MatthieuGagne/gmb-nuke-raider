"""Tests for tools/factory_log.py"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_log
import factory_run

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_fixtures

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'factory_log.py')


def child(code, *argv):
    """A cross-platform child: [sys.executable, -c, code, *argv] (AC7)."""
    return [sys.executable, '-c', code] + list(argv)


class LogTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, 'BUILD.log')
        self.reset = factory_fixtures.pinned_clock()

    def tearDown(self):
        self.reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_logged(self, cmd, **kw):
        """In-process run; returns (exit_code, console bytes, stderr text)."""
        kw.setdefault('stage', 'BUILD')
        kw.setdefault('log_path', self.log)
        console = io.BytesIO()
        err = io.StringIO()
        with redirect_stderr(err):
            code = factory_log.run_logged(cmd, console=console, **kw)
        return code, console.getvalue(), err.getvalue()

    def log_bytes(self):
        with open(self.log, 'rb') as fh:
            return fh.read()

    def assert_one_warning(self, err):
        self.assertEqual(err.count('factory-log: WARNING:'), 1, err)


class TestTee(LogTestCase):
    def test_exit_code_and_interleaved_streams(self):
        """AC1: non-zero exit passes through; stdout+stderr in emission order."""
        code, console, err = self.run_logged(child(
            "import sys;"
            "sys.stdout.write('out1\\n'); sys.stdout.flush();"
            "sys.stderr.write('err1\\n'); sys.stderr.flush();"
            "sys.stdout.write('out2\\n'); sys.stdout.flush();"
            "sys.exit(3)"))
        self.assertEqual(code, 3)
        body = self.log_bytes()
        self.assertLess(body.index(b'out1'), body.index(b'err1'))
        self.assertLess(body.index(b'err1'), body.index(b'out2'))

    def test_second_invocation_appends_with_its_own_header(self):
        """AC2: retries accumulate; each header has cmd, cwd, time, attempt."""
        self.run_logged(child("print('first')"))
        self.run_logged(child("print('second')"), attempt=2)
        text = self.log_bytes().decode('utf-8', 'replace')
        self.assertIn('first', text)
        self.assertIn('second', text)
        headers = [line for line in text.splitlines()
                   if line.startswith('===== factory-log') and 'started=' in line]
        self.assertEqual(len(headers), 2)
        self.assertNotIn('attempt=', headers[0])
        self.assertIn('attempt=2', headers[1])
        self.assertEqual(text.count('cmd: '), 2)
        self.assertEqual(text.count('cwd: '), 2)

    def test_console_and_log_bytes_identical(self):
        """AC4 (#450) under --stream: console bytes and log bytes are one stream."""
        code, console, err = self.run_logged(child(
            "import sys; sys.stdout.buffer.write(b'A\\rB\\nC');"
            "sys.stdout.buffer.flush()"), stream=True)
        self.assertEqual(code, 0)
        self.assertEqual(console, b'A\rB\nC')
        body = self.log_bytes()
        marker = b'----- output -----\n'
        start = body.index(marker) + len(marker)
        end = body.rindex(b'===== factory-log stage=BUILD exit=')
        self.assertEqual(body[start:end], console)

    def test_non_utf8_and_bare_cr_logged_verbatim(self):
        """AC8: no CRLF translation, no replacement characters."""
        code, console, err = self.run_logged(child(
            "import sys; sys.stdout.buffer.write(b'\\xff\\xfe\\rraw');"
            "sys.stdout.buffer.flush()"), stream=True)
        self.assertEqual(code, 0)
        self.assertEqual(console, b'\xff\xfe\rraw')
        self.assertIn(b'\xff\xfe\rraw', self.log_bytes())

    def test_trailer_records_exit_code(self):
        """AC5 positive: a completed invocation ends with an exit trailer."""
        code, _, _ = self.run_logged(child("import sys; sys.exit(5)"))
        self.assertEqual(code, 5)
        last = self.log_bytes().decode('utf-8', 'replace').splitlines()[-1]
        self.assertTrue(
            last.startswith('===== factory-log stage=BUILD exit=5 ended='), last)
        self.assertTrue(last.endswith('====='), last)

    def test_unknown_stage_is_rejected_before_running(self):
        """Grill: stage validated against factory_run.STAGES; nothing runs."""
        with self.assertRaises(ValueError):
            factory_log.run_logged(['x'], stage='NOPE', log_path=self.log)
        self.assertFalse(os.path.exists(self.log))

    def test_output_visible_in_log_before_child_exits(self):
        """AC7: streaming, not capture_output. Sentinel-file handshake."""
        sentinel = os.path.join(self.tmp, 'go')
        code_str = (
            "import os, sys, time\n"
            "sys.stdout.write('EARLY\\n'); sys.stdout.flush()\n"
            "deadline = time.time() + 10\n"
            "while time.time() < deadline and not os.path.exists(sys.argv[1]):\n"
            "    time.sleep(0.05)\n")
        result = {}

        def run():
            result['code'], _, _ = self.run_logged(
                [sys.executable, '-c', code_str, sentinel])

        worker = threading.Thread(target=run)
        worker.start()
        try:
            deadline = time.time() + 10
            seen = b''
            while time.time() < deadline and b'EARLY' not in seen:
                if os.path.exists(self.log):
                    with open(self.log, 'rb') as fh:
                        seen = fh.read()
                time.sleep(0.05)
            self.assertIn(b'EARLY', seen)
            self.assertNotIn(b'exit=', seen)  # child still running: no trailer
        finally:
            open(sentinel, 'w').close()
            worker.join(timeout=15)
        self.assertEqual(result.get('code'), 0)


class TestQuietOnSuccess(LogTestCase):
    """#529: the console copy is redundant when the command passed."""

    MARKER = 'MARKER529'
    # The child splits the marker so it never appears intact in argv — the
    # summary echoes the command, and an intact marker would make every
    # "output is absent" assertion below vacuous.
    NOISY = ("import sys;"
             "m = 'MARK' + 'ER529';"
             "sys.stdout.buffer.write((m + ' one\\n' + m + ' two\\n').encode());"
             "sys.stdout.buffer.flush();"
             "sys.stderr.buffer.write(b'err\\n');"
             "sys.stderr.buffer.flush()")
    NOISY_BYTES = 32   # 14 + 14 + 4, identical on Windows and Linux
    NOISY_LINES = 3

    def test_success_prints_one_summary_line_not_the_output(self):
        """AC1: compact console output on success."""
        code, console, err = self.run_logged(child(self.NOISY))
        self.assertEqual(code, 0)
        text = console.decode('utf-8')
        self.assertNotIn(self.MARKER, text)
        self.assertEqual(len(text.splitlines()), 1, text)
        self.assertTrue(text.startswith(factory_log.SUMMARY_PREFIX), text)

    def test_success_summary_names_stage_exit_size_log_and_command(self):
        """AC1: 'enough to confirm what ran and that it passed'."""
        code, console, err = self.run_logged(child(self.NOISY))
        self.assertEqual(code, 0)
        text = console.decode('utf-8')
        self.assertIn('stage=BUILD', text)
        self.assertIn('exit=0', text)
        self.assertIn('bytes=%d' % self.NOISY_BYTES, text)
        self.assertIn('lines=%d' % self.NOISY_LINES, text)
        self.assertIn('log=%s' % self.log, text)
        self.assertIn('cmd: ', text)
        self.assertIn(sys.executable, text)

    def test_success_log_file_still_holds_the_whole_output(self):
        """AC1 second half: quiet console, complete file.

        Asserts on the output slice, not the whole file — the header's
        ``cmd:`` line would satisfy a naive substring search on its own.
        """
        self.run_logged(child(self.NOISY))
        body = self.log_bytes()
        marker = b'----- output -----\n'
        start = body.index(marker) + len(marker)
        end = body.rindex(b'===== factory-log stage=BUILD exit=')
        # sorted(): stdout is block-buffered on the merged pipe, stderr is not,
        # so arrival order is buffering-dependent.
        self.assertEqual(sorted(body[start:end].split(b'\n')),
                         sorted([b'MARKER529 one', b'MARKER529 two',
                                 b'err', b'']))

    def test_failure_prints_the_full_output(self):
        """AC2: a failing command is unchanged — every byte reaches the console."""
        code, console, err = self.run_logged(
            child(self.NOISY + "; sys.exit(3)"))
        self.assertEqual(code, 3)
        self.assertIn(b'MARKER529 one', console)
        self.assertIn(b'MARKER529 two', console)
        self.assertIn(b'err', console)
        self.assertNotIn(factory_log.SUMMARY_PREFIX.encode(), console)

    def test_failure_console_matches_the_logged_body_byte_for_byte(self):
        """AC2: 'exactly as it is today' — no reordering, no re-encoding."""
        code, console, err = self.run_logged(child(
            "import sys; sys.stdout.buffer.write(b'A\\rB\\n\\xff');"
            "sys.stdout.buffer.flush(); sys.exit(1)"))
        self.assertEqual(code, 1)
        body = self.log_bytes()
        marker = b'----- output -----\n'
        start = body.index(marker) + len(marker)
        end = body.rindex(b'===== factory-log stage=BUILD exit=')
        self.assertEqual(console, body[start:end])

    def test_log_body_is_exactly_header_output_trailer_on_success(self):
        """AC3: the file the autopsy reads is spelled out, not inferred.

        ``factory_fixtures.pinned_clock()`` auto-advances by ``STEP`` per call,
        so the header and trailer carry consecutive stamps. Do NOT call
        ``factory_run.timestamp()`` here — every call burns a tick.
        """
        started = factory_fixtures.START.isoformat(timespec='seconds')
        ended = (factory_fixtures.START
                 + factory_fixtures.STEP).isoformat(timespec='seconds')
        self.run_logged(child(
            "import sys; sys.stdout.buffer.write(b'payload\\n')"))
        body = self.log_bytes()
        self.assertTrue(body.startswith(
            b'===== factory-log stage=BUILD started=' + started.encode()), body)
        self.assertIn(b'\n----- output -----\npayload\n'
                      b'===== factory-log stage=BUILD exit=0 ended='
                      + ended.encode(), body)

    def test_spawn_failure_still_returns_127_and_says_so(self):
        """AC4: distinct codes survive buffering.

        The console is asserted empty, not merely summary-free: ``popen`` is the
        first thing ``run_logged`` attempts, so no chunk has been read and the
        buffer is provably empty on this path (#570).
        """
        code, console, err = self.run_logged(['definitely-not-a-real-command-529'])
        self.assertEqual(code, 127)
        self.assertIn('factory-log: cannot spawn', err)
        self.assertIn(b'exit=127', self.log_bytes())
        self.assertEqual(console, b'')

    def test_success_with_a_dead_log_sink_falls_back_to_full_output(self):
        """AC4 fail-open: never point at a log that was never written.

        The child splits its payload the same way ``TestQuietOnSuccess.NOISY``
        does: the summary line ends with ``cmd: <argv joined>``, so an intact
        ``kept`` in the child's source would satisfy the assertion below on its
        own (#570).
        """
        blocker = os.path.join(self.tmp, 'blocker')
        open(blocker, 'w').close()
        bad = os.path.join(blocker, 'sub', 'BUILD.log')
        code, console, err = self.run_logged(
            child("import sys; m = 'ke' + 'pt';"
                  " sys.stdout.buffer.write((m + '\\n').encode())"),
            log_path=bad)
        self.assertEqual(code, 0)
        self.assertIn(b'kept', console)
        self.assertNotIn(factory_log.SUMMARY_PREFIX.encode(), console)
        self.assert_one_warning(err)


class TestStreamEscapeHatch(LogTestCase):
    """AC5: one invocation opts back into the live tee."""

    VERBATIM = "import sys; sys.stdout.buffer.write(b'verbatim\\n')"

    def test_stream_true_restores_full_output_on_success(self):
        code, console, err = self.run_logged(child(self.VERBATIM), stream=True)
        self.assertEqual(code, 0)
        self.assertEqual(console, b'verbatim\n')
        self.assertNotIn(factory_log.SUMMARY_PREFIX.encode(), console)

    def test_stream_true_still_writes_the_same_log(self):
        self.run_logged(child(self.VERBATIM), stream=True)
        self.assertIn(b'verbatim\n', self.log_bytes())


class TestAutopsySourceIntact(LogTestCase):
    """AC6: the failing-stage log the autopsy and publisher read is complete."""

    def test_registry_log_holds_every_line_after_a_failure(self):
        reg = os.path.join(self.tmp, 'registry')
        payload = b''.join(b'row %d\n' % i for i in range(200))
        with mock.patch.dict(os.environ, {'NUKE_FACTORY_REGISTRY': reg}):
            code, console, err = self.run_logged(
                child("import sys; sys.stdout.buffer.write(%r); sys.exit(4)"
                      % payload),
                issue=529, log_path=None)
            path = factory_run.log_path(529, 'BUILD')
        self.assertEqual(code, 4)
        with open(path, 'rb') as fh:
            body = fh.read()
        for i in (0, 99, 199):
            self.assertIn(b'row %d\n' % i, body)
        self.assertIn(b'exit=4', body)


class ExplodingChild:
    """Streams one chunk, then dies mid-read — an incomplete invocation (AC5)."""

    def __init__(self):
        self.stdout = self
        self._sent = False

    def read1(self, size):
        if not self._sent:
            self._sent = True
            return b'partial output'
        raise RuntimeError('runner died mid-stream')

    def wait(self, timeout=None):
        return 0


class InterruptedChild:
    """Raises KeyboardInterrupt mid-read; reports 130 like a Ctrl-C'd child."""

    def __init__(self):
        self.stdout = self

    def read1(self, size):
        raise KeyboardInterrupt

    def wait(self, timeout=None):
        return 130


class TestFailOpen(LogTestCase):
    EXIT7 = "import sys; sys.exit(7)"

    def test_unwritable_destination_still_runs_and_warns_once(self):
        """AC3: mkdir failure — a file blocks the log's parent directory."""
        blocker = os.path.join(self.tmp, 'blocker')
        open(blocker, 'w').close()
        bad = os.path.join(blocker, 'sub', 'BUILD.log')
        code, console, err = self.run_logged(child(self.EXIT7), log_path=bad)
        self.assertEqual(code, 7)
        self.assert_one_warning(err)

    def test_unresolvable_registry_root_still_runs_and_warns_once(self):
        """AC3: repo_root raising must not take the command down with it."""
        with mock.patch.dict(os.environ):
            os.environ.pop('NUKE_FACTORY_REGISTRY', None)
            with mock.patch.object(factory_run, 'repo_root',
                                   side_effect=RuntimeError('no repo')):
                code, console, err = self.run_logged(
                    child(self.EXIT7), issue=450, log_path=None)
        self.assertEqual(code, 7)
        self.assert_one_warning(err)

    def test_missing_issue_number_still_runs_and_warns_once(self):
        """AC3: outside a factory run the helper degrades to a plain runner."""
        with mock.patch.dict(os.environ):
            os.environ.pop('NUKE_FACTORY_RUN', None)
            code, console, err = self.run_logged(
                child(self.EXIT7), issue=None, log_path=None)
        self.assertEqual(code, 7)
        self.assert_one_warning(err)

    def test_unspawnable_command_returns_127(self):
        """AC6: spawn failure is not swallowed and never reports success."""
        code, console, err = self.run_logged(
            ['definitely-not-a-real-command-450'])
        self.assertEqual(code, 127)
        self.assertIn('factory-log: cannot spawn', err)
        self.assertIn(b'exit=127', self.log_bytes())

    def test_incomplete_invocation_leaves_no_trailer(self):
        """AC5 negative: header and partial bytes on disk, no trailer."""
        console = io.BytesIO()
        with self.assertRaises(RuntimeError):
            factory_log.run_logged(
                ['whatever'], stage='BUILD', log_path=self.log,
                console=console, popen=lambda *a, **k: ExplodingChild())
        body = self.log_bytes()
        self.assertIn(b'===== factory-log stage=BUILD', body)
        self.assertIn(b'partial output', body)
        self.assertNotIn(b'exit=', body)

    def test_exception_mid_read_still_flushes_buffered_bytes(self):
        """#529: buffering must not swallow output an exception interrupts."""
        console = io.BytesIO()
        with self.assertRaises(RuntimeError):
            factory_log.run_logged(
                ['whatever'], stage='BUILD', log_path=self.log,
                console=console, popen=lambda *a, **k: ExplodingChild())
        self.assertEqual(console.getvalue(), b'partial output')

    def test_keyboard_interrupt_records_the_childs_exit(self):
        """Grill: Ctrl-C — wait briefly, write the trailer, return."""
        console = io.BytesIO()
        code = factory_log.run_logged(
            ['whatever'], stage='BUILD', log_path=self.log,
            console=console, popen=lambda *a, **k: InterruptedChild())
        self.assertEqual(code, 130)
        self.assertIn(b'exit=130', self.log_bytes())


class TestCli(unittest.TestCase):
    """CLI per tools/ convention, exercised as a subprocess like test_factory_report."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, 'BUILD.log')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT] + list(args),
                              capture_output=True)
        return proc.returncode, proc.stdout, proc.stderr

    MARK = "import sys; sys.stdout.buffer.write(b'MARK' + b'ER529\\n')"

    def test_happy_path_streams_logs_and_pins_the_clock(self):
        code, out, err = self.run_cli(
            '--stage', 'BUILD', '--log-path', self.log, '--attempt', '2',
            '--stream', '--now', '2026-07-27T12:00:00+00:00',
            '--', sys.executable, '-c', self.MARK)
        self.assertEqual(code, 0)
        self.assertEqual(out, b'MARKER529\n')
        with open(self.log, 'rb') as fh:
            body = fh.read()
        self.assertIn(b'attempt=2 started=2026-07-27T12:00:00+00:00', body)
        self.assertIn(b'exit=0 ended=2026-07-27T12:00:00+00:00', body)

    def test_cli_is_quiet_on_success_without_stream(self):
        """AC1 + AC5 through the CLI: the flag is what makes the difference."""
        code, out, err = self.run_cli(
            '--stage', 'BUILD', '--log-path', self.log,
            '--', sys.executable, '-c', self.MARK)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(factory_log.SUMMARY_PREFIX.encode()), out)
        self.assertNotIn(b'MARKER529', out)
        with open(self.log, 'rb') as fh:
            self.assertIn(b'MARKER529\n', fh.read())

    def test_child_exit_code_passes_through(self):
        code, out, err = self.run_cli(
            '--stage', 'BUILD', '--log-path', self.log,
            '--', sys.executable, '-c', 'import sys; sys.exit(9)')
        self.assertEqual(code, 9)

    def test_unknown_stage_exits_2_and_runs_nothing(self):
        """AC6: invalid --stage returns 2 and the command never runs."""
        marker = os.path.join(self.tmp, 'ran')
        code, out, err = self.run_cli(
            '--stage', 'NOPE', '--log-path', self.log,
            '--', sys.executable, '-c',
            "import sys; open(sys.argv[1], 'w').close()", marker)
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(marker))
        self.assertIn(b'factory_log', err)

    def test_no_command_after_dashes_exits_2(self):
        code, out, err = self.run_cli('--stage', 'BUILD', '--log-path', self.log)
        self.assertEqual(code, 2)
        self.assertIn(b'no command', err)

    def test_bad_now_exits_2(self):
        code, out, err = self.run_cli(
            '--stage', 'BUILD', '--log-path', self.log, '--now', 'not-a-time',
            '--', sys.executable, '-c', 'pass')
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()

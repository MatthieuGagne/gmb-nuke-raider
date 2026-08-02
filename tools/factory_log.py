"""Stage log capture: tee a factory stage command's output into the run registry.

Runs a command, appends its output to
``<registry>/runs/issue-<N>/logs/<STAGE>.log``, and reports on the console.
stderr is merged into stdout on a single pipe, so the log preserves real
interleaving. Binary end-to-end: the log receives the child's bytes verbatim.

The console copy is asymmetric (#529). A command that **fails** prints its full
output, byte-identical to the logged body — a failing gate is where every line
matters. A command that **succeeds** prints one ``factory-log: ok`` summary line
naming the stage, exit code, output size and log path: the bytes are already on
disk, and reproducing them costs thousands of tokens to convey one bit. Pass
``--stream`` (``stream=True``) to restore the live tee for one invocation. The
summary is suppressed whenever the log sink failed — output is never quieted in
favour of a file that was not written.

One consequence of buffering: while a command is still running the console is
silent, so a wrapped command that hangs or is killed by a harness timeout prints
nothing at all. The bytes are still in the stage log — tail
``<registry>/runs/issue-<N>/logs/<STAGE>.log``, whose path is fixed by the
``--stage`` and ``--issue`` that were passed in.

Each invocation appends a single-line, fixed-prefix header and trailer, so
``grep '^===== factory-log'`` reconstructs the invocation list with no parser:

    ===== factory-log stage=BUILD attempt=2 started=2026-07-27T12:00:00+00:00 =====
    cwd: C:/Code/nuke-raider/.claude/worktrees/factory-log-450
    cmd: make clean
    ----- output -----
    <child bytes, verbatim>
    ===== factory-log stage=BUILD exit=0 ended=2026-07-27T12:01:03+00:00 =====

The trailer is the completion signal: its absence means the invocation did not
complete. Logging is fail-open — the child's exit code is always returned, and
each logging failure emits exactly one ``factory-log: WARNING:`` line on
stderr. The child failing to spawn is NOT a logging failure: it returns 127.

The child's stdout is a pipe, not a pty, so ``isatty()`` is false and
TTY-conditional color/progress rendering is suppressed. That is the documented
cost of capture; nothing forces color back on.

Commands are argv lists — never ``shell=True``. A compound command names its
shell explicitly; callers (#437, #438) copy this pattern:

    run_logged(["pwsh", "-NoProfile", "-Command", "make clean; make"],
               stage="BUILD", issue=450)

Usage:
    python tools/factory_log.py --stage BUILD --issue 450 -- make clean
    python tools/factory_log.py --stage BUILD --attempt 2 -- pwsh -NoProfile -Command "make clean; make"
    python tools/factory_log.py --stage GATE --issue 529 --stream -- python tools/spec_lint.py --issue 529 --json
    or imported:  factory_log.run_logged(cmd, stage="BUILD", issue=450) -> int

Exit codes:
    k    the child's own exit code, verbatim — including 0, 1, 2, 130
    127  the child could not be spawned (nonexistent command, bad cwd)
    2    helper misuse (unknown --stage, bad --now, no command after --)
    130  interrupted by Ctrl-C and the child did not report its own code
"""
import argparse
import os
import subprocess
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import factory_run
sys.path.remove(_TOOLS_DIR)

CHUNK_SIZE = 65536
INTERRUPT_GRACE_SECONDS = 5   # Ctrl-C: how long to wait for the child's own exit
WARNING_PREFIX = "factory-log: WARNING: "
SUMMARY_PREFIX = "factory-log: ok "


def _warn(message):
    print(WARNING_PREFIX + message, file=sys.stderr)


class _LogSink:
    """Append-only log that fails open: first write error warns, then mutes."""

    def __init__(self, handle):
        self._handle = handle
        self.ok = handle is not None

    def write(self, data):
        if self._handle is None:
            return
        try:
            self._handle.write(data)
            self._handle.flush()
        except OSError as exc:
            self._handle = None
            self.ok = False
            _warn("log write failed, further output not logged: %s" % exc)

    def close(self):
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass


def _resolve_log_path(stage, issue, explicit_path):
    """The log destination, or None (after one warning) when unresolvable."""
    if explicit_path is not None:
        return explicit_path
    if issue is None:
        issue = factory_run.run_issue()
    if issue is None:
        _warn("no issue number (pass issue=/--issue or set NUKE_FACTORY_RUN); "
              "output not logged")
        return None
    try:
        return factory_run.log_path(issue, stage)
    except (RuntimeError, OSError) as exc:
        _warn("cannot resolve registry root, output not logged: %s" % exc)
        return None


def _open_log(path):
    """Open *path* for binary append, or None (after one warning) on failure."""
    if path is None:
        return None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError as exc:
        _warn("cannot create log directory, output not logged: %s" % exc)
        return None
    try:
        return open(path, "ab")
    except OSError as exc:
        _warn("cannot open log, output not logged: %s" % exc)
        return None


def _header(stage, attempt, cmd, cwd):
    attempt_part = "" if attempt is None else " attempt=%d" % attempt
    lines = (
        "===== factory-log stage=%s%s started=%s ====="
        % (stage, attempt_part, factory_run.timestamp()),
        "cwd: %s" % os.path.abspath(cwd or os.getcwd()),
        "cmd: %s" % " ".join(cmd),
        "----- output -----",
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _trailer(stage, exit_code):
    return ("===== factory-log stage=%s exit=%d ended=%s =====\n"
            % (stage, exit_code, factory_run.timestamp())).encode("utf-8")


def _summary(stage, cmd, path, total_bytes, total_lines):
    """One line standing in for a passing command's output (#529).

    ``total_lines`` counts newline bytes, so output whose last line has no
    trailing newline reads one low. It is a size hint, not a tally.
    """
    return ((SUMMARY_PREFIX + "stage=%s exit=0 bytes=%d lines=%d log=%s cmd: %s\n")
            % (stage, total_bytes, total_lines, path, " ".join(cmd))).encode("utf-8")


def run_logged(cmd, *, stage, issue=None, attempt=None, cwd=None,
               log_path=None, env=None, console=None, popen=subprocess.Popen,
               stream=False):
    """Run *cmd*, logging its merged stdout+stderr and reporting on the console.

    The stage log always receives every byte as it arrives. The console gets
    the full output when the command fails, and a single ``factory-log: ok``
    summary line when it succeeds (#529) — the bytes are on disk, and a passing
    gate carries one bit of information. Pass ``stream=True`` (``--stream``) to
    restore the live tee for one invocation.

    Returns the child's exit code verbatim, or 127 when it cannot be spawned.
    *console* and *popen* are test seams (the ``runner=`` idiom from
    prepush_build.py); production callers leave them defaulted.
    """
    if stage not in factory_run.STAGES:
        raise ValueError("unknown stage %r; the vocabulary is owned by "
                         "factory_run.STAGES (#436): %s"
                         % (stage, ", ".join(factory_run.STAGES)))
    out = sys.stdout.buffer if console is None else console
    resolved = _resolve_log_path(stage, issue, log_path)
    log = _LogSink(_open_log(resolved))
    held = None if stream else []
    total_bytes = 0
    total_lines = 0
    reported = False
    try:
        log.write(_header(stage, attempt, cmd, cwd))
        try:
            child = popen(cmd, cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as exc:
            # Not a logging failure: must not masquerade as success (R4).
            print("factory-log: cannot spawn %r: %s" % (cmd[0], exc),
                  file=sys.stderr)
            log.write(_trailer(stage, 127))
            reported = True
            return 127
        try:
            while True:
                chunk = child.stdout.read1(CHUNK_SIZE)
                if not chunk:
                    break
                if held is None:
                    out.write(chunk)
                    out.flush()
                else:
                    # Unbounded on purpose: the log file (written below) is the
                    # durable copy, so this buffer only has to survive one command.
                    held.append(chunk)
                    total_bytes += len(chunk)
                    total_lines += chunk.count(b"\n")
                log.write(chunk)
            exit_code = child.wait()
        except KeyboardInterrupt:
            # Ctrl-C already reached the child via the process group; it dies
            # natively. Record whatever exit it reports, 130 if it will not.
            try:
                exit_code = child.wait(timeout=INTERRUPT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                exit_code = 130
        log.write(_trailer(stage, exit_code))
        if held is not None:
            # log.ok guards the one claim the summary makes that could be
            # false: that the output is retrievable from `resolved`.
            if exit_code == 0 and log.ok:
                out.write(_summary(stage, cmd, resolved, total_bytes,
                                   total_lines))
            else:
                for chunk in held:
                    out.write(chunk)
            out.flush()
            reported = True
        return exit_code
    finally:
        # An exception between the first chunk and the report would otherwise
        # swallow buffered bytes the streaming version had already printed.
        if held is not None and not reported:
            for chunk in held:
                out.write(chunk)
            out.flush()
        log.close()


def split_command(argv):
    """Split helper options from the child command at the first ``--``."""
    if "--" in argv:
        cut = argv.index("--")
        return argv[:cut], argv[cut + 1:]
    return argv, []


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", required=True,
                        help="stage name, one of: %s"
                             % ", ".join(factory_run.STAGES))
    parser.add_argument("--issue", type=int, default=None,
                        help="issue number (default: NUKE_FACTORY_RUN)")
    parser.add_argument("--attempt", type=int, default=None,
                        help="attempt number recorded in the log header")
    parser.add_argument("--cwd", default=None,
                        help="working directory for the command")
    parser.add_argument("--log-path", default=None,
                        help="write the log here instead of the registry")
    parser.add_argument("--stream", action="store_true",
                        help="stream full output even on success (escape hatch)")
    parser.add_argument("--now", default=None,
                        help="pin the clock, UTC ISO-8601 (determinism seam)")
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    own, cmd = split_command(argv)
    args = build_parser().parse_args(own)
    if args.stage not in factory_run.STAGES:
        print("factory_log: unknown --stage %r (one of: %s)"
              % (args.stage, ", ".join(factory_run.STAGES)), file=sys.stderr)
        return 2
    if not cmd:
        print("factory_log: no command after --", file=sys.stderr)
        return 2
    if args.now:
        try:
            pinned = factory_run.parse_now(args.now)
        except ValueError as exc:
            print("factory_log: bad --now: %s" % exc, file=sys.stderr)
            return 2
        factory_run.set_clock(lambda: pinned)
    return run_logged(cmd, stage=args.stage, issue=args.issue,
                      attempt=args.attempt, cwd=args.cwd,
                      log_path=args.log_path, stream=args.stream)


if __name__ == "__main__":
    sys.exit(main())

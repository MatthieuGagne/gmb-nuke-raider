"""Stage log capture: tee a factory stage command's output into the run registry.

Runs a command, streams its output to the console unchanged, and appends the
same bytes to ``<registry>/runs/issue-<N>/logs/<STAGE>.log``. stderr is merged
into stdout on a single pipe, so the log preserves real interleaving. Binary
end-to-end: the log's bytes and the console's bytes are the same stream.

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


def _warn(message):
    print(WARNING_PREFIX + message, file=sys.stderr)


class _LogSink:
    """Append-only log that fails open: first write error warns, then mutes."""

    def __init__(self, handle):
        self._handle = handle

    def write(self, data):
        if self._handle is None:
            return
        try:
            self._handle.write(data)
            self._handle.flush()
        except OSError as exc:
            self._handle = None
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


def run_logged(cmd, *, stage, issue=None, attempt=None, cwd=None,
               log_path=None, env=None, console=None, popen=subprocess.Popen):
    """Run *cmd*, teeing its merged stdout+stderr to console and stage log.

    Returns the child's exit code verbatim, or 127 when it cannot be spawned.
    *console* and *popen* are test seams (the ``runner=`` idiom from
    prepush_build.py); production callers leave them defaulted.
    """
    if stage not in factory_run.STAGES:
        raise ValueError("unknown stage %r; the vocabulary is owned by "
                         "factory_run.STAGES (#436): %s"
                         % (stage, ", ".join(factory_run.STAGES)))
    out = sys.stdout.buffer if console is None else console
    log = _LogSink(_open_log(_resolve_log_path(stage, issue, log_path)))
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
            return 127
        try:
            while True:
                chunk = child.stdout.read1(CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                out.flush()
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
        return exit_code
    finally:
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
                      log_path=args.log_path)


if __name__ == "__main__":
    sys.exit(main())

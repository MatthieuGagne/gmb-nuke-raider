#!/usr/bin/env python3
"""Factory run dashboard: one row per run in the registry.

Read-only, and now it writes nothing at all. The durable, shareable rendering
of a run is its GitHub run issue — ADR 472; this is the zero-latency
offline check beside it — a terminal table and ``--json``, costing no network
round trip. Two renderings of one state drift, so there is only one.

Two unhealthy conditions are deliberately distinct: a **stale** run is one
whose recorded worktree is gone, and an **idle** run is one whose worktree is
intact but which has emitted nothing recently. They call for different actions,
so they are never collapsed into one word.

Terminal runs (complete, failed) outrank both: a finished run legitimately
outlives its worktree and must not be reported as stale.

Missing logs are reported separately from the conditions (#489): a stage that
ran without a captured log says nothing about whether the run is healthy, only
that the evidence for what it did was never written down. It is named in a
trailing summary line, never in a column.

Usage:
    python3 tools/factory_status.py
    python3 tools/factory_status.py --json
    python3 tools/factory_status.py --registry PATH --now 2026-07-26T12:00:00+00:00

Exit codes:
    0  rendered, whatever the health of the runs it found
    2  operational error (registry unreadable, bad --now)
"""
import argparse
import json
import os
import sys
from datetime import datetime

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import factory_run
sys.path.remove(_TOOLS_DIR)

EXIT_OK = 0
EXIT_OPERATIONAL = 2

IDLE_SECONDS = 900          # 15 minutes of silence from a live worktree
CONDITIONS = ("failed", "complete", "stale", "idle", "active")


def elapsed_seconds(state, now):
    """Seconds since the run's last event, or None. Public: factory_publish
    needs it to reuse condition() verbatim for one run (#472 R3)."""
    ts = state.get("updated")
    if not ts:
        return None
    try:
        then = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    return max(0, int((now - then).total_seconds()))


def _elapsed_text(seconds):
    """Fixed-shape elapsed string. Deterministic for a pinned clock."""
    if seconds is None:
        return "-"
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % divmod(seconds, 60)
    if seconds < 86400:
        return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "%dd %02dh" % (seconds // 86400, (seconds % 86400) // 3600)


def condition(state, elapsed, worktree_exists):
    """One of CONDITIONS, in precedence order (see the module docstring)."""
    if state.get("failure"):
        return "failed"
    if state.get("finished"):
        return "complete"
    if state.get("worktree") and not worktree_exists:
        return "stale"
    if elapsed is not None and elapsed >= IDLE_SECONDS:
        return "idle"
    return "active"


def _column_slug(state):
    """The run's slug for the fixed-width SLUG column (#650 R1, R2).

    Shares the resolver with the PR body and the plan issue title, so a run
    whose slug is recoverable from its plan filename stops showing as '-'.
    The fallback stays the one-character placeholder rather than
    ``factory_run.FALLBACK_SLUG``: this is a table column, and '(no slug)'
    would widen it by eight characters for a run that has nothing to show.

    A state carrying the fallback string as an explicit slug collapses to the
    placeholder too. That is only reachable through hand-written state, and
    both spellings mean the same thing, so the collision is left alone.
    """
    slug = factory_run.run_slug(state)
    return "-" if slug == factory_run.FALLBACK_SLUG else slug


def _row(state, now):
    worktree = state.get("worktree")
    exists = bool(worktree) and os.path.isdir(worktree)
    elapsed = elapsed_seconds(state, now)
    gates = factory_run.ordered_gates(state)
    return {
        "issue": state["issue"],
        # #698: `or DEFAULT_LANE`, not a bare .get -- SCHEMA_VERSION stays 1,
        # so every state.json written before this field existed loads without
        # it, and several landed tests call _row with a hand-built dict.
        "lane": state.get("lane") or factory_run.DEFAULT_LANE,
        "slug": _column_slug(state),
        "branch": state.get("branch") or "-",
        "plan": state.get("plan"),
        "attempt": int(state.get("attempt") or 1),
        "stage": state.get("stage") or "-",
        "worktree": worktree,
        "worktree_exists": exists,
        "elapsed": elapsed,
        "elapsed_text": _elapsed_text(elapsed),
        "condition": condition(state, elapsed, exists),
        "gates": gates,
        "unlogged_stages": factory_run.unlogged_stages(state),
        "gates_pass": sum(1 for g in gates if g.get("result") == "pass"),
        "gates_fail": sum(1 for g in gates if g.get("result") == "fail"),
        "decisions": state.get("decisions") or [],
        "scenarios": state.get("scenarios") or [],
        "permissions": state.get("permissions") or [],
        "failure": state.get("failure"),
        "updated": state.get("updated"),
    }


def collect(registry=None, now=None):
    """Every run in *registry*, sorted by issue. Never writes."""
    registry = registry or factory_run.registry_root()
    now = now or factory_run.clock()
    runs = os.path.join(registry, "runs")
    rows = []
    if not os.path.isdir(runs):
        return rows
    for name in sorted(os.listdir(runs)):
        if not name.startswith("issue-"):
            continue
        try:
            issue = int(name[len("issue-"):])
        except ValueError:
            continue
        state = factory_run.load_state(issue, registry)
        if state is None:
            continue
        rows.append(_row(state, now))
    rows.sort(key=lambda r: r["issue"])
    return rows


# ── Terminal ─────────────────────────────────────────────────────────────────

_COLUMNS = (("ISSUE", "issue"), ("LANE", "lane"), ("STAGE", "stage"),
            ("CONDITION", "condition"), ("ATT", "attempt"), ("GATES", "_gates"),
            ("PERM", "_perm"), ("ELAPSED", "elapsed_text"), ("SLUG", "slug"))


def render_table(rows, registry):
    """Fixed-width table plus a one-line summary."""
    if not rows:
        return "No factory runs recorded in %s\n" % registry

    cells = []
    for row in rows:
        view = dict(row)
        view["_gates"] = "%d ok / %d fail" % (row["gates_pass"], row["gates_fail"])
        view["_perm"] = str(len(row["permissions"]))
        cells.append([str(view[key]) for _, key in _COLUMNS])

    widths = [max(len(header), max(len(c[i]) for c in cells))
              for i, (header, _) in enumerate(_COLUMNS)]
    out = ["  ".join(h.ljust(widths[i]) for i, (h, _) in enumerate(_COLUMNS))]
    out += ["  ".join(c[i].ljust(widths[i]) for i in range(len(_COLUMNS))).rstrip()
            for c in cells]

    counts = {c: sum(1 for r in rows if r["condition"] == c) for c in CONDITIONS}
    summary = ", ".join("%d %s" % (counts[c], c) for c in CONDITIONS if counts[c])
    out += ["", "%d runs: %s" % (len(rows), summary)]

    stale = [r for r in rows if r["condition"] == "stale"]
    if stale:
        out.append("stale worktrees: %s"
                   % ", ".join("#%d" % r["issue"] for r in stale))

    # A run whose stage produced no log is not unhealthy enough to change its
    # condition -- it shipped or it did not -- but the evidence for what it did
    # is gone, so the table names it rather than leaving the gap invisible
    # (#489). No fixed-width column: on a healthy run the list is empty, and a
    # column would widen every row to render nothing.
    unlogged = [r for r in rows if r.get("unlogged_stages")]
    if unlogged:
        out.append("unlogged stages: %s"
                   % ", ".join("#%d %s" % (r["issue"],
                                           " ".join(r["unlogged_stages"]))
                               for r in unlogged))
    return "\n".join(out) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", default=None,
                        help="registry root (default: <main repo root>/.factory)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the rows as JSON")
    parser.add_argument("--now", default=None,
                        help="pin the clock, UTC ISO-8601 (determinism seam)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    now = None
    if args.now:
        try:
            now = factory_run.parse_now(args.now)
        except ValueError as exc:
            print("factory_status: bad --now: %s" % exc, file=sys.stderr)
            return EXIT_OPERATIONAL
        factory_run.set_clock(lambda: now)

    try:
        registry = args.registry or factory_run.registry_root()
        rows = collect(registry, now=now)
    except (RuntimeError, OSError) as exc:
        print("factory_status: %s" % exc, file=sys.stderr)
        return EXIT_OPERATIONAL

    if args.as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_table(rows, registry))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Factory run dashboard: one row per run in the registry.

Read-only. This tool never writes state or the journal — the only thing it
writes is the rendered page (``--html``), which ``factory_run.append_event()``
also regenerates on every event. That is what makes the page's meta-refresh
honest with no watcher process and no server.

Two unhealthy conditions are deliberately distinct: a **stale** run is one
whose recorded worktree is gone, and an **idle** run is one whose worktree is
intact but which has emitted nothing recently. They call for different actions,
so they are never collapsed into one word.

Terminal runs (complete, failed) outrank both: a finished run legitimately
outlives its worktree and must not be reported as stale.

Usage:
    python3 tools/factory_status.py
    python3 tools/factory_status.py --json
    python3 tools/factory_status.py --html [--out .factory/status.html]
    python3 tools/factory_status.py --registry PATH --now 2026-07-26T12:00:00+00:00

Exit codes:
    0  rendered, whatever the health of the runs it found
    2  operational error (registry unreadable, output unwritable, bad --now)
"""
import argparse
import base64
import json
import os
import sys
from datetime import datetime
from html import escape

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import factory_run
sys.path.remove(_TOOLS_DIR)

EXIT_OK = 0
EXIT_OPERATIONAL = 2

IDLE_SECONDS = 900          # 15 minutes of silence from a live worktree
CONDITIONS = ("failed", "complete", "stale", "idle", "active")


def _elapsed_seconds(state, now):
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


def _row(state, now):
    worktree = state.get("worktree")
    exists = bool(worktree) and os.path.isdir(worktree)
    elapsed = _elapsed_seconds(state, now)
    gates = factory_run.ordered_gates(state)
    return {
        "issue": state["issue"],
        "slug": state.get("slug") or "-",
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

_COLUMNS = (("ISSUE", "issue"), ("STAGE", "stage"), ("CONDITION", "condition"),
            ("ATT", "attempt"), ("GATES", "_gates"), ("PERM", "_perm"),
            ("ELAPSED", "elapsed_text"), ("SLUG", "slug"))


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
    return "\n".join(out) + "\n"


# ── HTML ─────────────────────────────────────────────────────────────────────

MAX_SCREENSHOTS = 3
MAX_IMAGE_BYTES = 512 * 1024
REFRESH_SECONDS = 30

_CSS = """\
body{font-family:ui-monospace,Consolas,monospace;background:#14171a;
color:#dfe4e8;margin:0;padding:24px;line-height:1.5}
h1{font-size:18px;margin:0 0 4px}
.meta{color:#7d8891;font-size:12px;margin-bottom:20px}
.run{border:1px solid #2b3238;border-radius:6px;padding:16px;margin-bottom:18px;
background:#1b1f23}
.run h2{font-size:15px;margin:0 0 6px;font-weight:normal}
.sub{color:#7d8891;font-size:11px;margin-bottom:10px}
.badge{font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px}
.b-active{background:#1f6feb;color:#fff}
.b-idle{background:#7d5b00;color:#fff}
.b-stale{background:#4b4b4b;color:#fff}
.b-failed{background:#8b1d1d;color:#fff}
.b-complete{background:#1a7f37;color:#fff}
.strip{display:flex;gap:6px;margin:10px 0}
.stg{flex:1;text-align:center;font-size:11px;padding:6px 0;border-radius:4px;
background:#23292e;color:#7d8891}
.stg.done{background:#173d24;color:#7fd18f}
.stg.current{background:#1f6feb;color:#fff}
.stg.failed{background:#5b1717;color:#ffb3b3}
h3{font-size:12px;color:#7d8891;font-weight:normal;margin:14px 0 4px}
table{border-collapse:collapse;width:100%;font-size:12px}
th,td{border:1px solid #2b3238;padding:4px 8px;text-align:left}
th{color:#7d8891;font-weight:normal}
.pass{color:#7fd18f}
.fail{color:#ff8080}
ul{margin:4px 0;padding-left:20px;font-size:12px}
.shots{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
.shots figure{margin:0}
.shots img{image-rendering:pixelated;width:320px;border:1px solid #2b3238;
display:block}
.shots figcaption{font-size:11px;color:#7d8891;margin-top:3px}
.note{font-size:11px;color:#c9a227;margin:6px 0 0}
.empty{color:#7d8891;font-size:12px}
"""


def _latest_autopsy(registry, issue):
    """Newest ``autopsy/attempt-<k>/smoketest`` directory, by attempt number."""
    base = os.path.join(factory_run.run_dir(issue, registry), "autopsy")
    if not os.path.isdir(base):
        return None
    attempts = []
    for name in os.listdir(base):
        if name.startswith("attempt-"):
            try:
                attempts.append((int(name[len("attempt-"):]), name))
            except ValueError:
                continue
    for _, name in sorted(attempts, reverse=True):
        smoke = os.path.join(base, name, "smoketest")
        if os.path.isdir(smoke):
            return smoke
    return None


def screenshot_paths(row, registry):
    """(paths, source) for one run.

    A live run's PNGs are read straight from its worktree; once the worktree is
    gone the autopsy bundle is the fallback, which is what lets a stale run's
    page still show what it looked like when it died.
    """
    worktree = row.get("worktree")
    base, source = None, "none"
    if worktree:
        candidate = os.path.join(worktree, "build", "smoketest")
        if os.path.isdir(candidate):
            base, source = candidate, "worktree"
    if base is None:
        base = _latest_autopsy(registry, row["issue"])
        source = "autopsy" if base else "none"
    if base is None:
        return [], "none"
    paths = []
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if name.lower().endswith(".png"):
                paths.append(os.path.join(dirpath, name))
    paths.sort()
    return paths, source


def select_screenshots(paths, limit=MAX_SCREENSHOTS):
    """(kept, dropped). Failure frames are never dropped.

    Ordering is by filename, not mtime: the page is part of a determinism
    contract and mtime is not reproducible across machines or checkouts.
    """
    failures = [p for p in paths if os.path.basename(p).startswith("failure")]
    rest = [p for p in paths if p not in failures]
    kept = failures + (rest[-limit:] if limit >= 0 else rest)
    return kept, len(paths) - len(kept)


def _embed(path):
    """(data-uri, None) or (None, reason)."""
    try:
        size = os.path.getsize(path)
        if size > MAX_IMAGE_BYTES:
            return None, "too large (%d bytes)" % size
        with open(path, "rb") as fh:
            return ("data:image/png;base64,"
                    + base64.b64encode(fh.read()).decode("ascii")), None
    except OSError as exc:
        return None, str(exc)


def _stage_strip(row):
    stages = list(factory_run.STAGES)
    current = row["stage"] if row["stage"] in stages else None
    index = stages.index(current) if current else -1
    out = ['<div class="strip">']
    for i, stage in enumerate(stages):
        if index >= 0 and i < index:
            css = "stg done"
        elif index >= 0 and i == index:
            css = "stg failed" if row["condition"] == "failed" else "stg current"
        elif row["condition"] == "complete":
            css = "stg done"
        else:
            css = "stg"
        out.append('<div class="%s">%s</div>' % (css, escape(stage)))
    out.append("</div>")
    return "".join(out)


def _run_html(row, registry, limit):
    out = ['<section class="run">']
    out.append('<h2>#%d %s<span class="badge b-%s">%s</span></h2>'
               % (row["issue"], escape(row["slug"]), row["condition"],
                  row["condition"]))
    out.append('<div class="sub">branch %s &middot; attempt %d &middot; '
               'last event %s ago%s</div>'
               % (escape(row["branch"]), row["attempt"],
                  escape(row["elapsed_text"]),
                  " &middot; worktree missing" if not row["worktree_exists"]
                  and row["worktree"] else ""))
    out.append(_stage_strip(row))

    if row["failure"]:
        out.append('<h3>Failure</h3><p class="fail">%s</p>'
                   % escape(str(row["failure"].get("message") or "")))

    out.append("<h3>Gate results</h3>")
    if row["gates"]:
        out.append("<table><tr><th>Stage</th><th>Gate</th><th>Result</th></tr>")
        for gate in row["gates"]:
            result = gate.get("result") or "-"
            css = "pass" if result == "pass" else (
                "fail" if result == "fail" else "")
            out.append('<tr><td>%s</td><td>%s</td><td class="%s">%s</td></tr>'
                       % (escape(str(gate.get("stage") or "-")),
                          escape(str(gate.get("gate") or "-")), css,
                          escape(result)))
        out.append("</table>")
    else:
        out.append('<p class="empty">No gates recorded.</p>')

    out.append("<h3>Decisions</h3>")
    if row["decisions"]:
        out.append("<ul>" + "".join(
            "<li>%s</li>" % escape(str(d.get("text") or ""))
            for d in row["decisions"]) + "</ul>")
    else:
        out.append('<p class="empty">None recorded.</p>')

    if row["permissions"]:
        out.append("<h3>Permission events</h3>")
        out.append("<table><tr><th>Tool</th><th>Outcome</th><th>Command</th></tr>")
        for perm in row["permissions"]:
            out.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                       % (escape(str(perm.get("tool") or "-")),
                          escape(str(perm.get("outcome") or "-")),
                          escape(str(perm.get("command") or "-"))))
        out.append("</table>")

    out.append("<h3>Screenshots</h3>")
    paths, source = screenshot_paths(row, registry)
    kept, dropped = select_screenshots(paths, limit)
    figures, failed = [], []
    for path in kept:
        uri, reason = _embed(path)
        if uri is None:
            failed.append("%s (%s)" % (os.path.basename(path), reason))
            continue
        figures.append('<figure><img src="%s" alt="%s"><figcaption>%s</figcaption>'
                       '</figure>' % (uri, escape(os.path.basename(path)),
                                      escape(os.path.basename(path))))
    if figures:
        out.append('<div class="shots">' + "".join(figures) + "</div>")
    else:
        out.append('<p class="empty">No screenshots available for this run.</p>')
    if dropped:
        out.append('<p class="note">Showing %d of %d screenshots (capped at %d '
                   'plus every failure frame), read from the %s.</p>'
                   % (len(kept), len(paths), limit, source))
    if failed:
        out.append('<p class="note">Not embedded: %s</p>'
                   % escape(", ".join(failed)))

    out.append("</section>")
    return "".join(out)


def render_html(rows, registry, now, limit=MAX_SCREENSHOTS):
    """The whole dashboard as one self-contained document.

    Everything is inline — CSS and images alike — so the page opens from disk
    with no server and keeps working after the worktrees it describes are gone.
    """
    body = ("".join(_run_html(r, registry, limit) for r in rows)
            if rows else
            '<p class="empty">No factory runs recorded in %s</p>'
            % escape(str(registry)))
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        '<meta http-equiv="refresh" content="%d">\n'
        "<title>Factory runs</title>\n"
        "<style>%s</style></head><body>\n"
        "<h1>Factory runs</h1>\n"
        '<div class="meta">%s &middot; rendered %s &middot; refreshes every %ds'
        "</div>\n"
        "%s\n</body></html>\n"
        % (REFRESH_SECONDS, _CSS, escape(str(registry)),
           escape(now.astimezone().isoformat(timespec="seconds")),
           REFRESH_SECONDS, body))


def write_html(registry=None, out=None, now=None, limit=MAX_SCREENSHOTS):
    """Render and atomically replace the page. Returns its path."""
    registry = registry or factory_run.registry_root()
    out = out or os.path.join(registry, "status.html")
    now = now or factory_run.clock()
    page = render_html(collect(registry, now=now), registry, now, limit)
    directory = os.path.dirname(os.path.abspath(out))
    os.makedirs(directory, exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    os.replace(tmp, out)
    return out


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", default=None,
                        help="registry root (default: <main repo root>/.factory)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the rows as JSON")
    parser.add_argument("--html", action="store_true",
                        help="write the HTML dashboard instead of a table")
    parser.add_argument("--out", default=None,
                        help="HTML output path (default: <registry>/status.html)")
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

    if args.html:
        try:
            path = write_html(registry=registry, out=args.out, now=now)
        except OSError as exc:
            print("factory_status: cannot write the page: %s" % exc,
                  file=sys.stderr)
            return EXIT_OPERATIONAL
        print(path)
    elif args.as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_table(rows, registry))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

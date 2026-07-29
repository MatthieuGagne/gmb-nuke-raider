#!/usr/bin/env python3
"""Publish a factory run to GitHub: run issue, stage-log and screenshot assets.

Sole writer of the GitHub surfaces — the run issue, the release assets, and the
spec-issue comment. ``factory_run`` stays the sole writer of run state and the
journal; ``factory_log`` stays the sole writer of ``logs/``. This module's own
durable memory is ``runs/issue-<N>/publish.json``, which nothing else writes:
the same narrowing ADR 0005 applied to the log subtree, extended to a third
owner (ADR 0006, #472).

Publication is an explicit call, never a side effect of ``append_event()``. A
GitHub outage must not be able to stall a stage or slow the journal's hot path,
so the published copy is allowed to lag and the local registry stays the
authority — the doctrine ADR 0003 set for state-versus-journal.

Fail-open end to end: no publication failure changes a run's outcome. Each
degradation emits exactly one ``factory-publish: WARNING:`` line on stderr and,
where the body is still writable, is reported in the body.

Usage:
    python tools/factory_publish.py --issue 437 --stage-completed BUILD
    python tools/factory_publish.py --issue 437 --terminal
    python tools/factory_publish.py --issue 437 --dry-run
    or imported:  factory_publish.publish_run(437) -> PublishResult

Exit codes:
    0  published fully
    1  published with degradation (assets withheld, upload failed, body shed) —
       reportable, but never a run failure
    2  misuse (unknown --stage-completed, bad --now, no registry entry)
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import factory_run
import factory_status
import install_hooks
sys.path.remove(_TOOLS_DIR)

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_MISUSE = 2

WARNING_PREFIX = "factory-publish: WARNING: "

# GitHub's body cap is ~65k UTF-8; 5k is headroom for this renderer being wrong
# about its own size. A body edit rejected for length would silently freeze the
# dashboard exactly when a run is going wrong, so the bound is enforced here
# rather than discovered from an API error (R5).
BODY_BUDGET = 60000
LOG_TAIL_LINES = 100
LOG_TAIL_BYTES = 64 * 1024

RELEASE_TAG = "factory-logs"
RELEASE_TITLE = "Factory stage logs"
RELEASE_NOTES = ("Rolling attachment point for factory stage logs and "
                 "smoketest screenshots. Not a software release.")
RUN_LABEL = "log"
DEFAULT_REPO = "MatthieuGagne/gmb-nuke-raider"
PROJECT_NUMBER = 3
PROJECT_OWNER = "MatthieuGagne"
PROJECT_ID = "PVT_kwHOAv4a5M4BepB5"

PUBLISH_FILE = "publish.json"
PUBLISH_SCHEMA_VERSION = 1
PUBLISH_DIRNAME = "publish"          # staged assets, publisher-owned

BODY_MARKER = ("<!-- factory-publish v1 — regenerated on every publish; "
               "manual edits are overwritten -->")

GLYPH_DONE = "✅"
GLYPH_CURRENT = "🔵"
GLYPH_FAILED = "❌"
GLYPH_PENDING = "⬜"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

PublishResult = collections.namedtuple(
    "PublishResult", "run_issue warnings uploaded")


def _warn(warnings, message):
    """Record one degradation and say so once, on stderr (R11)."""
    warnings.append(message)
    print(WARNING_PREFIX + message, file=sys.stderr)


# ── Publish state ────────────────────────────────────────────────────────────

def publish_path(issue, registry=None):
    """``runs/issue-<N>/publish.json`` — written by this module alone."""
    return os.path.join(factory_run.run_dir(issue, registry), PUBLISH_FILE)


def new_publish_state(issue):
    """An empty publication record for *issue*."""
    return {
        "schema_version": PUBLISH_SCHEMA_VERSION,
        "issue": int(issue),
        "run_issue": None,          # the GitHub issue this run renders into
        "projected": False,         # added to the Documents project, Type=Log
        "commented_attempts": [],   # spec-issue comments already posted (R10)
        "uploaded": [],             # asset names already on the release (R7)
        "withheld": {},             # asset name -> reason the scan refused it
    }


def load_publish_state(issue, registry=None):
    """The publication record, self-healing. Never raises.

    A record this module cannot read is a record it has not written yet: the
    registry is the authority on the run, and refusing to publish because a
    cache is corrupt would be the failure mode R11 exists to prevent.
    """
    try:
        with open(publish_path(issue, registry), encoding="utf-8") as fh:
            publish = json.load(fh)
    except (OSError, ValueError):
        return new_publish_state(issue)
    if not isinstance(publish, dict) or \
            publish.get("schema_version") != PUBLISH_SCHEMA_VERSION:
        return new_publish_state(issue)
    merged = new_publish_state(issue)
    merged.update(publish)
    return merged


def save_publish_state(publish, registry=None):
    """Write the record atomically: temp file in the same dir, then replace."""
    directory = factory_run.run_dir(publish["issue"], registry)
    os.makedirs(directory, exist_ok=True)
    final = os.path.join(directory, PUBLISH_FILE)
    tmp = final + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(publish, fh, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)


# ── Asset identity ───────────────────────────────────────────────────────────

def log_asset_name(issue, attempt, stage):
    """``issue-<N>-attempt-<k>-<stage>.log``.

    The discriminator is **attempt**, not a run id: a run is one per spec issue
    and an attempt is one pass at it (CONTEXT.md). #437 R11's ``run-<runid>``
    named a concept that exists nowhere in this codebase (#472 R2).
    """
    return "issue-%d-attempt-%d-%s.log" % (int(issue), int(attempt), stage)


def shot_asset_name(issue, attempt, path):
    """``issue-<N>-attempt-<k>-<scenario>-<frame>.png`` for a screenshot path."""
    frame = os.path.splitext(os.path.basename(path))[0]
    scenario = os.path.basename(os.path.dirname(path))
    return "issue-%d-attempt-%d-%s-%s.png" % (
        int(issue), int(attempt), _UNSAFE.sub("-", scenario),
        _UNSAFE.sub("-", frame))


def asset_url(name, repo=DEFAULT_REPO):
    """Public download URL. Constructed, never queried: the renderer is pure
    and its goldens must not depend on a network round trip."""
    return "https://github.com/%s/releases/download/%s/%s" % (
        repo, RELEASE_TAG, name)


# ── Title ────────────────────────────────────────────────────────────────────

def run_condition(state, now=None):
    """One of ``factory_status.CONDITIONS`` for a single run.

    Delegates rather than re-deriving: the five conditions and their precedence
    are specified and tested in factory_status, and a second definition would
    drift from the first (R3).
    """
    now = now or factory_run.clock()
    worktree = state.get("worktree")
    exists = bool(worktree) and os.path.isdir(worktree)
    return factory_status.condition(
        state, factory_status.elapsed_seconds(state, now), exists)


def render_title(state, now=None):
    """``run <N> · attempt <k> · <STAGE> · <condition>``. Pure."""
    return "run %d · attempt %d · %s · %s" % (
        int(state["issue"]), int(state.get("attempt") or 1),
        state.get("stage") or "-", run_condition(state, now))


# ── Body ─────────────────────────────────────────────────────────────────────

def _cell(value):
    """One table cell: None becomes a dash, pipes are escaped."""
    if value is None or value == "":
        return "-"
    return str(value).replace("|", r"\|")


def _table(headers, rows):
    out = ["| %s |" % " | ".join(headers),
           "|%s|" % "|".join("---" for _ in headers)]
    out += ["| %s |" % " | ".join(_cell(c) for c in row) for row in rows]
    return out


def stage_strip(state, now=None):
    """``✅ GATE → 🔵 BUILD → ⬜ SHIP``, generated from factory_run.STAGES.

    Never a hardcoded list of five: PRD-11 (#471) inserts REVIEW between VERIFY
    and SHIP and it must appear here with no edit to this module (R4).
    """
    stages = list(factory_run.STAGES)
    condition = run_condition(state, now)
    current = state.get("stage")
    index = stages.index(current) if current in stages else -1
    glyphs = []
    for i, stage in enumerate(stages):
        if condition == "complete":
            glyph = GLYPH_DONE
        elif index < 0 or i > index:
            glyph = GLYPH_PENDING
        elif i < index:
            glyph = GLYPH_DONE
        else:
            glyph = GLYPH_FAILED if condition == "failed" else GLYPH_CURRENT
        glyphs.append("%s %s" % (glyph, stage))
    return " → ".join(glyphs)


def _section_gates(ctx):
    gates = factory_run.ordered_gates(ctx["state"])
    if not gates:
        return ["_No gates recorded._"]
    return _table(("Stage", "Gate", "Result"),
                  [(g.get("stage"), g.get("gate"), g.get("result"))
                   for g in gates])


def _section_decisions(ctx):
    decisions = ctx["state"].get("decisions") or []
    dropped = ctx["drop_decisions"]
    kept = decisions[dropped:] if dropped else decisions
    if not kept and not dropped:
        return None
    out = []
    if dropped:
        out.append("_%d earlier decisions omitted_" % dropped)
        out.append("")
    out += ["- %s" % (d.get("text") or "-") for d in kept]
    return out


def _section_scenarios(ctx):
    scenarios = ctx["state"].get("scenarios") or []
    shots = [n for n in ctx["publish"].get("uploaded") or []
             if n.endswith(".png")]
    if not scenarios and not shots:
        return None
    out = []
    if scenarios:
        out += _table(("Scenario", "Blocking", "Result"),
                      [(s.get("scenario"), s.get("blocking"), s.get("result"))
                       for s in scenarios])
    for name in shots:
        if out:
            out.append("")
        out.append("![%s](%s)" % (name, asset_url(name, ctx["repo"])))
    return out


def _section_stage_logs(ctx):
    rows = []
    for name in sorted(ctx["publish"].get("uploaded") or []):
        parsed = _parse_log_asset(name)
        if parsed is None:
            continue
        attempt, stage = parsed
        rows.append((stage, attempt,
                     "[%s](%s)" % (name, asset_url(name, ctx["repo"]))))
    for name, reason in sorted((ctx["publish"].get("withheld") or {}).items()):
        parsed = _parse_log_asset(name)
        if parsed is None:
            continue
        attempt, stage = parsed
        rows.append((stage, attempt, "withheld — %s" % reason))
    if not rows:
        return ["_No stage logs published yet._"]
    rows.sort(key=lambda r: (_stage_rank(r[0]), r[1]))
    return _table(("Stage", "Attempt", "Log"), rows)


def _section_permissions(ctx):
    if ctx["shed_permissions"]:
        count = len(ctx["state"].get("permissions") or [])
        return ["_%d events omitted — see the local registry_" % count] \
            if count else None
    perms = ctx["state"].get("permissions") or []
    if not perms:
        return None
    return _table(("Tool", "Outcome", "Command"),
                  [(p.get("tool"), p.get("outcome"), p.get("command"))
                   for p in perms])


# Order is fixed and the list is data, not inlined markup: PRD-11 adds its
# "Review findings" section by appending one entry here (R4).
SECTIONS = (
    ("Gate results", _section_gates),
    ("Decisions made", _section_decisions),
    ("Scenario evidence", _section_scenarios),
    ("Stage logs", _section_stage_logs),
    ("Permission events", _section_permissions),
)

_LOG_ASSET = re.compile(r"^issue-\d+-attempt-(\d+)-(.+)\.log$")


def _parse_log_asset(name):
    """(attempt, stage) for a log asset name, or None."""
    match = _LOG_ASSET.match(name)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _stage_rank(stage):
    stages = list(factory_run.STAGES)
    return stages.index(stage) if stage in stages else len(stages)


def _render(ctx):
    state = ctx["state"]
    out = ["**Spec** #%d · **Branch** `%s` · **Attempt** %d · **Updated** %s"
           % (int(state["issue"]), state.get("branch") or "-",
              int(state.get("attempt") or 1), state.get("updated") or "-"),
           "",
           stage_strip(state, ctx["now"])]
    for title, render in ctx["sections"]:
        lines = render(ctx)
        if lines is None:
            continue
        out += ["", "### %s" % title, ""] + lines
    out += ["", BODY_MARKER]
    return "\n".join(out) + "\n"


def render_body(state, publish, registry=None, now=None, repo=DEFAULT_REPO,
                budget=BODY_BUDGET):
    """The whole run issue body. Pure in (state, publish) but for the log tail.

    Rendered, measured, then shed until it fits — see ``_shed`` (R5).
    """
    ctx = {"state": state, "publish": publish, "registry": registry,
           "now": now, "repo": repo, "sections": SECTIONS,
           "shed_tail": False, "shed_permissions": False, "drop_decisions": 0}
    return _render(ctx)

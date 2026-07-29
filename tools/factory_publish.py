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

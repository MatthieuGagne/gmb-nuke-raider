#!/usr/bin/env python3
"""Factory run registry: run state, event journal, and autopsy bundles.

The registry lives at ``<main repo root>/.factory/runs/issue-<N>/`` — outside
every worktree, so a run stays explainable after its worktree is gone.

The journal (``journal.jsonl``) is the source of truth and ``state.json`` is a
cached projection of it; see
``docs/adr/0003-factory-run-journal-as-source-of-truth.md``. ``append_event()``
writes the journal line first, then re-saves state atomically, so state can lag
the journal by one event and can never lead it.

This module is the only writer of the registry. Every other factory tool reads.
It is a library, not a CLI: ``factory_status.py`` and ``factory_report.py`` are
the command-line surfaces.

Usage (imported):
    import factory_run
    factory_run.append_event(436, "gate", stage="BUILD", gate="make test",
                             result="pass")
    state = factory_run.load_state(436)

Exit codes:
    n/a — library module, raises on programmer error, never calls sys.exit().
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = 1

# Canonical stage order. Every renderer sorts gates by this, never by dict
# order — see the determinism contract in issue #436 R6.
STAGES = ("GATE", "PLAN", "BUILD", "VERIFY", "SHIP")

EVENT_KINDS = ("start", "stage", "gate", "decision", "retry", "scenario",
               "permission", "failure", "finish")

REGISTRY_DIRNAME = ".factory"
STATE_FILE = "state.json"
JOURNAL_FILE = "journal.jsonl"

_clock = None


# ── Time: the single seam ────────────────────────────────────────────────────

def set_clock(fn):
    """Install a zero-arg callable returning an aware datetime. None resets."""
    global _clock
    _clock = fn


def clock():
    """The one source of time. Always an aware UTC datetime."""
    if _clock is not None:
        return _clock()
    return datetime.now(timezone.utc)


def timestamp():
    """UTC ISO-8601 with an explicit offset, second resolution."""
    return clock().astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_now(text):
    """Parse a ``--now`` argument. A naive value is read as UTC."""
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── Registry location ────────────────────────────────────────────────────────

def repo_root(cwd=None):
    """Absolute path of the MAIN repository root, from anywhere in the tree.

    ``git rev-parse --git-common-dir`` returns a path relative to *cwd* in the
    main tree and an absolute one inside a linked worktree, so it is joined
    with *cwd* before use. ``--show-toplevel`` is the trap: inside a worktree
    it returns the worktree root, which is not where the registry lives.
    """
    cwd = os.path.abspath(cwd or os.getcwd())
    proc = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                          cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("not a git repository: %s" % cwd)
    common = os.path.abspath(os.path.join(cwd, proc.stdout.strip()))
    return os.path.dirname(common)


def registry_root(cwd=None):
    """``<main repo root>/.factory``.

    ``NUKE_FACTORY_REGISTRY`` overrides it, which is how the hooks are tested
    outside a git tree and how a run can be pointed at a scratch registry.
    """
    override = os.environ.get("NUKE_FACTORY_REGISTRY")
    if override:
        return os.path.abspath(override)
    return os.path.join(repo_root(cwd), REGISTRY_DIRNAME)


def run_dir(issue, registry=None):
    return os.path.join(registry or registry_root(), "runs",
                        "issue-%d" % int(issue))


def state_path(issue, registry=None):
    return os.path.join(run_dir(issue, registry), STATE_FILE)


def journal_path(issue, registry=None):
    return os.path.join(run_dir(issue, registry), JOURNAL_FILE)


def run_issue(env=None):
    """Issue number from ``NUKE_FACTORY_RUN``, or None when not a factory run.

    The variable stays truthy for ``deny_gate_hook``'s boolean check; only this
    parser cares that it now carries a number. A non-numeric legacy value means
    "factory run, unattributable" — truthy there, None here.
    """
    raw = (env if env is not None else os.environ).get(
        "NUKE_FACTORY_RUN", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return None


# ── State ────────────────────────────────────────────────────────────────────

def new_state(issue):
    """An empty projection for *issue*."""
    return {
        "schema_version": SCHEMA_VERSION,
        "issue": int(issue),
        "slug": None,
        "branch": None,
        "worktree": None,
        "plan": None,
        "attempt": 1,
        "stage": None,
        "gates": [],
        "decisions": [],
        "scenarios": [],
        "permissions": [],
        "failure": None,
        "finished": None,
        "updated": None,
        "event_count": 0,
    }


def save_state(state, registry=None):
    """Write *state* atomically: temp file in the same dir, then os.replace."""
    directory = run_dir(state["issue"], registry)
    os.makedirs(directory, exist_ok=True)
    final = os.path.join(directory, STATE_FILE)
    tmp = final + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)

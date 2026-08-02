#!/usr/bin/env python3
"""Publish a factory run to GitHub: run issue, stage-log and screenshot assets.

Sole writer of the GitHub surfaces — the run issue, the release assets, and the
spec-issue comment. ``factory_run`` stays the sole writer of run state and the
journal; ``factory_log`` stays the sole writer of ``logs/``. This module's own
durable memory is ``runs/issue-<N>/publish.json``, which nothing else writes:
the same narrowing ADR 450 applied to the log subtree, extended to a
third owner — ADR 472.

Publication is an explicit call, never a side effect of ``append_event()``. A
GitHub outage must not be able to stall a stage or slow the journal's hot path,
so the published copy is allowed to lag and the local registry stays the
authority — the doctrine ADR 436 set for state-versus-journal.

Fail-open end to end: no publication failure changes a run's outcome. Each
degradation emits exactly one ``factory-publish: WARNING:`` line on stderr and,
where the body is still writable, is reported in the body.

Usage:
    python tools/factory_publish.py --issue 437 --stage-completed BUILD
    python tools/factory_publish.py --issue 437 --terminal
    python tools/factory_publish.py --issue 437 --run-start
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
import factory_report
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
TRUNCATION_MARKER = "\n\n_… truncated at the %d-character budget …_\n" % BODY_BUDGET
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
# Single-select field and option names on the Documents board, for both Type
# and Status. Names only: the field id and the option ids are resolved at
# call time, because GitHub regenerates option ids whenever a field's option
# set is edited (#513 R5).
TYPE_FIELD = "Type"
TYPE_LOG = "Log"
STATUS_FIELD = "Status"
STATUS_TODO = "Todo"
STATUS_IN_PROGRESS = "In Progress"
STATUS_DONE = "Done"

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
        "spec_item_id": None,       # Documents-project item for the spec issue
        "run_item_id": None,        # Documents-project item for the run issue
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


def display_worktree(worktree, registry=None):
    """The worktree path as it is safe to publish (Q1b).

    The run issue is public, so an absolute path would put a developer's home
    directory into a search index — the same reason factory_report keeps them
    out of a PR body. Repo-relative is still enough to ``cd`` into and leaks
    nothing; anything outside the repository falls back to that module's
    placeholder rather than inventing a second convention.

    The root is ``dirname(registry)`` — the registry is ``<repo root>/.factory``
    by construction — so this needs no ``git`` subprocess and stays pure and
    deterministic under a fixture registry.
    """
    if not worktree:
        return "-"
    try:
        root = os.path.dirname(registry or factory_run.registry_root())
        relative = os.path.relpath(os.path.abspath(worktree), root)
    except (RuntimeError, OSError, ValueError):
        # ValueError: os.path.relpath across Windows drive letters.
        return factory_report.redact(worktree)
    if relative.startswith(os.pardir) or os.path.isabs(relative):
        return factory_report.redact(worktree)
    return relative.replace(os.sep, "/")


def log_tail(issue, stage, registry=None, lines=LOG_TAIL_LINES):
    """The last *lines* lines of a stage log, or None when there is none.

    Decoded with ``errors='replace'`` and labelled a lossy excerpt: a stage log
    is binary end-to-end (#450) and a run issue must never be the reason a
    failure cannot be read. Only the tail is read off disk — a build log can be
    megabytes and the body budget is 60k.
    """
    if not stage:
        return None
    try:
        path = factory_run.log_path(issue, stage, registry)
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > LOG_TAIL_BYTES:
                fh.seek(size - LOG_TAIL_BYTES)
            raw = fh.read()
    except OSError:
        return None
    text = raw.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _section_failure(ctx):
    state = ctx["state"]
    failure = state.get("failure")
    if not failure:
        return None
    stage = state.get("stage")
    out = ["- **Stage** %s" % (stage or "-"),
           "- **Reason** %s" % (failure.get("message") or "-"),
           "- **Worktree** `%s`" % display_worktree(state.get("worktree"),
                                                    ctx["registry"])]
    if ctx["shed_tail"]:
        name = log_asset_name(state["issue"],
                              int(state.get("attempt") or 1), stage) \
            if stage else None
        out += ["", "tail omitted — full log: %s"
                % (asset_url(name, ctx["repo"]) if name else "not published")]
        return out
    tail = log_tail(state["issue"], stage, ctx["registry"])
    if tail is None:
        out += ["", "no stage log captured"]
        return out
    out += ["",
            "<details><summary>%s log tail — last %d lines, lossy excerpt"
            "</summary>" % (stage, LOG_TAIL_LINES),
            "",
            "````",
            tail,
            "````",
            "",
            "</details>"]
    return out


# Order is fixed and the list is data, not inlined markup: PRD-11 adds its
# "Review findings" section by appending one entry here (R4).
SECTIONS = (
    ("Failure", _section_failure),
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
    """The whole run issue body, bounded at *budget* characters.

    Render, measure, then shed in a fixed order until it fits, each cut leaving
    an explicit marker rather than vanishing: the inline log tail, then
    permission events, then decisions oldest-first. Never shed: the status
    header, the stage strip, the failure fields, the gate table, the stage-log
    asset table. A hard truncation is the backstop (R5).
    """
    ctx = {"state": state, "publish": publish, "registry": registry,
           "now": now, "repo": repo, "sections": SECTIONS,
           "shed_tail": False, "shed_permissions": False, "drop_decisions": 0}

    def attempt():
        body = _render(ctx)
        return body if len(body) <= budget else None

    body = attempt()
    if body is not None:
        return body

    ctx["shed_tail"] = True
    body = attempt()
    if body is not None:
        return body

    ctx["shed_permissions"] = True
    body = attempt()
    if body is not None:
        return body

    # Oldest first: the most recent decisions are the ones that explain where
    # the run is now. Linear because decisions are human-authored and few.
    for drop in range(1, len(state.get("decisions") or []) + 1):
        ctx["drop_decisions"] = drop
        body = attempt()
        if body is not None:
            return body

    return _render(ctx)[:budget - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


# ── Secret scan ──────────────────────────────────────────────────────────────

SCAN_CHUNK = 1 << 20
_SCAN_OVERLAP = 512          # longest credential shape, with room to spare

# Refuse, never redact. Everything that is published stays byte-exact (AC5);
# redaction would make that invariant conditional, and one false positive would
# silently corrupt a log. A hit blocks exactly one asset and says so in the
# body — the run's outcome is unchanged (R8).
SECRET_PATTERNS = (
    ("gh[pousr]_", re.compile(rb"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("github_pat_", re.compile(rb"github_pat_[A-Za-z0-9_]{20,}")),
    ("xox[baprs]-", re.compile(rb"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("AKIA", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("Bearer", re.compile(rb"[Bb]earer\s+[A-Za-z0-9._~+/=-]{20,}")),
)


def scan_secrets(path):
    """The shape that matched, or None when the file is clean.

    Reads in chunks with an overlap so a credential straddling a chunk
    boundary is still caught. A file that cannot be read is reported as unsafe:
    the scan is the only thing standing between a stage log and a public
    release asset, and "could not check" is not "clean".
    """
    try:
        with open(path, "rb") as fh:
            carry = b""
            while True:
                chunk = fh.read(SCAN_CHUNK)
                if not chunk:
                    return None
                window = carry + chunk
                for label, pattern in SECRET_PATTERNS:
                    if pattern.search(window):
                        return "credential-shaped string (%s)" % label
                carry = window[-_SCAN_OVERLAP:]
    except OSError as exc:
        return "unreadable, not scanned: %s" % exc


# ── Screenshot sourcing ──────────────────────────────────────────────────────

def latest_autopsy(issue, registry=None):
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


def screenshot_paths(state, registry=None):
    """(paths, source) for one run.

    A live run's PNGs are read straight from its worktree; once the worktree is
    gone the autopsy bundle is the fallback, which is what lets a dead run's
    issue still show what it looked like when it died (AC7).
    """
    worktree = state.get("worktree")
    base, source = None, "none"
    if worktree:
        candidate = os.path.join(worktree, "build", "smoketest")
        if os.path.isdir(candidate):
            base, source = candidate, "worktree"
    if base is None:
        base = latest_autopsy(state["issue"], registry)
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


def select_screenshots(paths):
    """Every screenshot, failure frames first.

    Uncapped: a run produces four to eight PNGs and GitHub stores them for
    free, so the HTML page's three-image cap retires with the page (R9).
    Ordering is by filename, not mtime — the body is under a determinism
    contract and mtime is not reproducible across machines.
    """
    failures = [p for p in paths if os.path.basename(p).startswith("failure")]
    return failures + [p for p in paths if p not in failures]


# ── The gh layer ─────────────────────────────────────────────────────────────

def _tail(text, limit=200):
    """One line of stderr, short enough for a warning."""
    text = " ".join((text or "").split())
    return text[-limit:] if text else "(no stderr)"


def gh(argv, runner=subprocess.run):
    """Run one ``gh`` command. Never raises; the caller decides what a failure
    means. *runner* is the injected seam that keeps every test off the network
    (the idiom from prepush_build.py:43).

    The environment is scrubbed with ``install_hooks.clean_env``: git exports
    ``GIT_DIR`` into every hook's environment and it overrides *cwd*, which hit
    real factory code before (#462). Output is decoded as UTF-8 with
    replacement so a Windows console codepage cannot turn a parse into a crash.
    """
    command = ["gh"] + list(argv)
    try:
        return runner(command, capture_output=True, encoding="utf-8",
                      errors="replace", env=install_hooks.clean_env())
    except OSError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))


def _already(proc, *needles):
    """True when gh refused because the thing already exists."""
    text = ((proc.stdout or "") + (proc.stderr or "")).lower()
    return any(n in text for n in needles)


def ensure_label(warnings, runner=subprocess.run):
    """Create the ``log`` label if it is missing. Idempotent, fail-open."""
    proc = gh(["label", "create", RUN_LABEL, "--color", "5319E7",
               "--description", "Factory run dashboard issue"], runner=runner)
    if proc.returncode == 0 or _already(proc, "already exists"):
        return True
    _warn(warnings, "label %r not ensured: %s" % (RUN_LABEL, _tail(proc.stderr)))
    return False


def ensure_release(warnings, runner=subprocess.run):
    """Create the rolling ``factory-logs`` release if it is missing.

    Marked not-latest so the repo's tag list stays about the game (R13). Doing
    this on demand rather than as a one-time manual step keeps a walk-away run
    from failing on setup nobody remembered to do.
    """
    if gh(["release", "view", RELEASE_TAG], runner=runner).returncode == 0:
        return True
    proc = gh(["release", "create", RELEASE_TAG, "--title", RELEASE_TITLE,
               "--notes", RELEASE_NOTES, "--latest=false"], runner=runner)
    if proc.returncode == 0 or _already(proc, "already exists"):
        return True
    _warn(warnings, "release %r not ensured: %s"
          % (RELEASE_TAG, _tail(proc.stderr)))
    return False


def issue_url(number, repo=DEFAULT_REPO):
    """The canonical URL of an issue. Constructed, never queried."""
    return "https://github.com/%s/issues/%d" % (repo, int(number))


def project_item_add(url, warnings, runner=subprocess.run):
    """The Documents-project item id for *url*, or None.

    ``gh project item-add`` is idempotent — an issue already on the board comes
    back with its existing item id — so this is also the resolver, not just the
    adder (#513 R2).
    """
    add = gh(["project", "item-add", str(PROJECT_NUMBER), "--owner",
              PROJECT_OWNER, "--url", url, "--format", "json"], runner=runner)
    if add.returncode != 0:
        _warn(warnings, "%s not added to the Documents project: %s"
              % (url, _tail(add.stderr)))
        return None
    try:
        return json.loads(add.stdout)["id"]
    except (ValueError, KeyError, TypeError):
        _warn(warnings, "project item id not parseable from item-add output")
        return None


def resolve_single_select(field_name, option_name, warnings,
                          runner=subprocess.run):
    """(field id, option id) for one single-select option, resolved by name.

    Never a hardcoded id: option ids are regenerated whenever the field's
    option set is edited, so a constant would silently write to a stale option
    or fail outright (#513 R5). One ``field-list`` per write is the price — a run
    makes at most four of these calls, against 15-25 body edits, and a cache
    would have to be invalidated by exactly the board edit this defends
    against.
    """
    fields = gh(["project", "field-list", str(PROJECT_NUMBER), "--owner",
                 PROJECT_OWNER, "--format", "json"], runner=runner)
    field_id = option_id = None
    try:
        for field in json.loads(fields.stdout).get("fields") or []:
            if field.get("name") != field_name:
                continue
            field_id = field.get("id")
            for option in field.get("options") or []:
                if option.get("name") == option_name:
                    option_id = option.get("id")
    except (ValueError, AttributeError):
        pass
    if not field_id or not option_id:
        _warn(warnings, "project %s=%s not set: no %s field with a %s option "
                        "in project %d"
              % (field_name, option_name, field_name, option_name,
                 PROJECT_NUMBER))
        return None, None
    return field_id, option_id


def set_single_select(item_id, field_name, option_name, warnings,
                      runner=subprocess.run):
    """Set one single-select field on one project item. Fail-open (#513 R6)."""
    field_id, option_id = resolve_single_select(field_name, option_name,
                                                warnings, runner=runner)
    if not field_id or not option_id:
        return False
    edit = gh(["project", "item-edit", "--id", item_id, "--project-id",
               PROJECT_ID, "--field-id", field_id,
               "--single-select-option-id", option_id], runner=runner)
    if edit.returncode != 0:
        _warn(warnings, "project %s=%s not set: %s"
              % (field_name, option_name, _tail(edit.stderr)))
        return False
    return True


_ISSUE_NUMBER = re.compile(r"/issues/(\d+)\s*$")


def write_body_file(issue, text, registry=None, name="publish-body.md"):
    """Stage a body for ``--body-file`` and keep it as the offline copy.

    Never argv: the body carries emoji and a Windows console codepage is not
    UTF-8. The file lives under the run directory, which this module owns.
    """
    directory = os.path.join(factory_run.run_dir(issue, registry),
                             PUBLISH_DIRNAME)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def ensure_run_issue(state, publish, title, body, warnings, registry=None,
                     runner=subprocess.run):
    """Create the run issue, or edit the one this run already owns.

    One run issue per **spec** issue, created on the first publish and reused
    forever after — its number lives in publish.json so it is never recreated
    (R2). Returns the number, or None when creation failed.
    """
    issue = int(state["issue"])
    path = write_body_file(issue, body, registry)
    number = publish.get("run_issue")
    if number:
        proc = gh(["issue", "edit", str(number), "--title", title,
                   "--body-file", path], runner=runner)
        if proc.returncode != 0:
            _warn(warnings, "run issue #%d not updated: %s"
                  % (number, _tail(proc.stderr)))
        return number

    proc = gh(["issue", "create", "--title", title, "--body-file", path,
               "--label", RUN_LABEL], runner=runner)
    if proc.returncode != 0:
        _warn(warnings, "run issue not created: %s" % _tail(proc.stderr))
        return None
    match = _ISSUE_NUMBER.search((proc.stdout or "").strip())
    if not match:
        _warn(warnings, "run issue number not parseable from: %s"
              % _tail(proc.stdout))
        return None
    publish["run_issue"] = int(match.group(1))
    publish["run_issue_url"] = (proc.stdout or "").strip().splitlines()[-1]
    return publish["run_issue"]


_STATE_VERB = {True: ("reopen", "reopened"), False: ("close", "closed")}


def set_issue_state(number, want_open, warnings, runner=subprocess.run):
    """Reopen the run issue for a new attempt, close it at terminal (R2)."""
    verb, past = _STATE_VERB[bool(want_open)]
    proc = gh(["issue", verb, str(number)], runner=runner)
    if proc.returncode == 0 or _already(proc, "already open", "already closed"):
        return True
    _warn(warnings, "run issue #%d not %s: %s"
          % (number, past, _tail(proc.stderr)))
    return False


def ensure_project_type_log(publish, issue_url, warnings,
                            runner=subprocess.run):
    """Add the run issue to "Nuke Raider — Documents", Type = Log,
    Status = In Progress.

    Once per run, not once per publish: the Logs view only needs the item to
    exist, and a run that has just joined the board is by definition running
    (#513 R3). Projects views have no API, so the view itself was built by
    hand (R13) and this only feeds it.

    The ``projected`` guard covers board **membership** and the one-time
    ``Type`` write. It deliberately does not cover the terminal ``Status``
    writes — see ``finish_project_status()``.
    """
    if publish.get("projected"):
        return True
    item_id = publish.get("run_item_id") or \
        project_item_add(issue_url, warnings, runner=runner)
    if not item_id:
        return False
    publish["run_item_id"] = item_id
    if not set_single_select(item_id, TYPE_FIELD, TYPE_LOG, warnings,
                             runner=runner):
        return False
    # A failed Status write is a degradation, not a reason to re-join the
    # board on the next publish: membership and Type are already correct.
    set_single_select(item_id, STATUS_FIELD, STATUS_IN_PROGRESS, warnings,
                      runner=runner)
    publish["projected"] = True
    return True


def finish_project_status(state, publish, run_url, warnings,
                          runner=subprocess.run):
    """The terminal board writes (#513 R4).

    The run issue is Done either way. The spec goes back to Todo only when the
    run failed: a successful run leaves it In Progress, because the PR is open
    and it is the merge — which this module never observes — that finishes the
    spec.

    Outside the ``projected`` guard on purpose. Behind it, these writes would
    no-op on every run after the first publish (#513, Notes). The spec half is
    also outside ``run_url``: a failed run whose dashboard issue could not be
    created is exactly when a spec pinned at In Progress would mislead longest.

    ``run_url`` is the caller's to resolve, not this function's: ``publish_run``
    passes it when the run item is cached (``project_item_add`` below then
    makes no network call at all — it only needs the URL to pass to
    ``project_item_add`` if the cache is empty) or when the record was
    already ``projected`` before this publish with no cached id (the add
    below is then the *first* attempt this publish, not a retry). It passes
    ``None`` exactly when neither is true: the run issue has no resolvable
    board item this publish, because the only add attempt made for it this
    publish — inside ``ensure_project_type_log`` — failed. Retrying that
    same failed add here would just repeat the call and double the warning
    for it; gating on ``ensure_project_type_log``'s overall return value
    instead of on this narrower condition would also (wrongly) skip the
    Done write whenever the add succeeds but a later step in that function,
    such as the ``Type`` write, fails — the id is still perfectly usable.
    """
    if run_url:
        run_item = publish.get("run_item_id") or project_item_add(
            run_url, warnings, runner=runner)
        if run_item:
            publish["run_item_id"] = run_item
            set_single_select(run_item, STATUS_FIELD, STATUS_DONE, warnings,
                              runner=runner)
    if not state.get("failure"):
        return
    spec_item = publish.get("spec_item_id") or project_item_add(
        issue_url(state["issue"]), warnings, runner=runner)
    if spec_item:
        publish["spec_item_id"] = spec_item
        set_single_select(spec_item, STATUS_FIELD, STATUS_TODO, warnings,
                          runner=runner)


# ── Assets ───────────────────────────────────────────────────────────────────

def stage_dir(issue, registry=None):
    """Where assets are staged under their published names, publisher-owned.

    ``gh release upload`` names the asset after the file's basename, so the
    copy is what carries ``issue-<N>-attempt-<k>-<stage>.log``. The copy is
    also what makes AC5 provable: bytes in, bytes out, no read of the content.
    """
    path = os.path.join(factory_run.run_dir(issue, registry), PUBLISH_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def upload_asset(path, name, publish, warnings, runner=subprocess.run):
    """Upload one staged asset. Never clobbers an existing one (R7)."""
    if name in (publish.get("uploaded") or []):
        return True
    proc = gh(["release", "upload", RELEASE_TAG, path], runner=runner)
    if proc.returncode != 0:
        _warn(warnings, "asset %s not uploaded: %s" % (name, _tail(proc.stderr)))
        return False
    publish.setdefault("uploaded", []).append(name)
    return True


def publish_stage_log(state, publish, stage, warnings, registry=None,
                      runner=subprocess.run):
    """Publish one stage's log as a per-attempt asset.

    A verbatim whole-file copy of ``logs/<stage>.log`` as it stood at upload
    time — the publisher copies bytes and never reads log content, so #450's
    no-parsing boundary is untouched. Local logs are append-only across
    attempts, so attempt *k*'s asset is a superset of attempt *k-1*'s; that
    redundancy is the accepted cost of an immutable per-attempt history (R7).
    """
    issue = int(state["issue"])
    attempt = int(state.get("attempt") or 1)
    name = log_asset_name(issue, attempt, stage)
    if name in (publish.get("uploaded") or []):
        return True

    src = factory_run.log_path(issue, stage, registry)
    if not os.path.isfile(src):
        _warn(warnings, "no stage log captured for %s (%s)" % (stage, src))
        return False

    reason = scan_secrets(src)
    if reason:
        publish.setdefault("withheld", {})[name] = "%s — local copy: %s" % (
            reason, os.path.join("logs", "%s.log" % stage))
        _warn(warnings, "asset withheld for %s: %s (the run is unaffected)"
              % (stage, reason))
        return False

    dest = os.path.join(stage_dir(issue, registry), name)
    try:
        shutil.copyfile(src, dest)
    except OSError as exc:
        _warn(warnings, "asset %s not staged: %s" % (name, exc))
        return False
    return upload_asset(dest, name, publish, warnings, runner=runner)


def publish_screenshots(state, publish, warnings, registry=None,
                        runner=subprocess.run):
    """Publish this attempt's screenshots. Returns the names now published.

    Uncapped and never scanned: a PNG has no credential shape to find, and the
    scan must not become a reason evidence goes missing. Failure frames first,
    so the one that matters is uploaded even if a later one fails (R9).
    """
    issue = int(state["issue"])
    attempt = int(state.get("attempt") or 1)
    paths, _source = screenshot_paths(state, registry)
    published = []
    for path in select_screenshots(paths):
        name = shot_asset_name(issue, attempt, path)
        if name in (publish.get("uploaded") or []):
            published.append(name)
            continue
        dest = os.path.join(stage_dir(issue, registry), name)
        try:
            shutil.copyfile(path, dest)
        except OSError as exc:
            _warn(warnings, "screenshot %s not staged: %s" % (name, exc))
            continue
        if upload_asset(dest, name, publish, warnings, runner=runner):
            published.append(name)
    return published


# ── Orchestration ────────────────────────────────────────────────────────────

def _outcome(state):
    if state.get("failure"):
        return "failed"
    if state.get("finished"):
        return str((state["finished"] or {}).get("result") or "finished")
    return "ended"


def comment_once(state, publish, run_issue, warnings, registry=None,
                 runner=subprocess.run):
    """Exactly one spec-issue comment per attempt, at terminal (R10).

    Editing a body notifies nobody, so a comment is the only completion signal;
    one per attempt is the whole notification budget. The first publish
    mentioning ``#<N>`` cross-references the spec's timeline for free, so there
    is no start-of-run comment.
    """
    issue = int(state["issue"])
    attempt = int(state.get("attempt") or 1)
    if attempt in (publish.get("commented_attempts") or []):
        return False

    lines = ["Factory attempt %d **%s**." % (attempt, _outcome(state))]
    if run_issue:
        lines.append("")
        lines.append("Run dashboard: #%d" % run_issue)
    if state.get("pr"):
        lines.append("Pull request: %s" % state["pr"])
    if state.get("failure"):
        lines.append("")
        lines.append("Failed in %s: %s" % (
            state.get("stage") or "-",
            (state["failure"] or {}).get("message") or "-"))
    body = "\n".join(lines) + "\n"

    path = write_body_file(issue, body, registry, name="publish-comment.md")
    proc = gh(["issue", "comment", str(issue), "--body-file", path],
              runner=runner)
    if proc.returncode != 0:
        _warn(warnings, "spec issue comment not posted: %s"
              % _tail(proc.stderr))
        return False
    publish.setdefault("commented_attempts", []).append(attempt)
    return True


def open_pr(issue, branch, title, body_path, publish=None, warnings=None,
            runner=subprocess.run):
    """Open the run's pull request. Returns (url, created).

    SHIP used to call ``gh pr create`` itself. That is the run's entire
    deliverable, and a raw outward-facing gh write is exactly what a harness
    permission gate stops — so a run could do all its work and then fail to
    hand it over (#481). Every other GitHub write already goes through this
    module; this closes the last hole.

    Fail-open like the rest of this file: a PR that cannot be opened is
    reported through *warnings* and never raises. The caller decides what that
    means — and for SHIP it means a run failure, not a publish degradation,
    because there is nothing to review without it.
    """
    warnings = warnings if warnings is not None else []
    if not os.path.exists(body_path):
        _warn(warnings, "PR not opened: body file missing (%s)" % body_path)
        return None, False

    proc = gh(["pr", "create", "--head", branch, "--title", title,
               "--body-file", body_path], runner=runner)
    if proc.returncode != 0:
        if _already(proc, "already exists"):
            # Idempotent by design: --resume must not fail on a second SHIP.
            return None, False
        _warn(warnings, "PR not opened: %s" % _tail(proc.stderr))
        return None, False

    url = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else None
    if publish is not None and url:
        publish["pr_url"] = url
    return url, True


def run_start(issue, registry=None, runner=subprocess.run):
    """Mark the spec issue In Progress on the Documents board (#513 R1).

    Exactly two things: ensure board membership, then set Status. No run issue,
    no rendered body, no asset — and never ``Type``, which stays with the human
    and with ``/prd`` (#513 R2).

    Idempotent in the sense that matters: a ``--resume`` or a second attempt
    adds no duplicate item, because the item id is cached in publish.json
    (#513 R7).
    The Status write itself is re-issued, and that is deliberate — it is what
    puts a retried run back to In Progress after a failed attempt pushed the
    spec to Todo.

    Called before GATE, so it does not require — and does not check for — a
    registry entry: the run directory it writes into is the one the ``start``
    event has just created.
    """
    registry = registry or factory_run.registry_root()
    publish = load_publish_state(issue, registry)
    warnings = []
    item_id = publish.get("spec_item_id") or \
        project_item_add(issue_url(issue), warnings, runner=runner)
    if item_id:
        publish["spec_item_id"] = item_id
        set_single_select(item_id, STATUS_FIELD, STATUS_IN_PROGRESS, warnings,
                          runner=runner)
    try:
        save_publish_state(publish, registry)
    except OSError as exc:
        _warn(warnings, "publish state not saved: %s" % exc)
    return PublishResult(publish.get("run_issue"), warnings,
                         list(publish.get("uploaded") or []))


def publish_run(issue, registry=None, stage_completed=None, terminal=False,
                runner=subprocess.run, now=None):
    """Re-render this run's GitHub surfaces. Never raises (R11).

    Called explicitly by the orchestrator at stage transitions, gate results
    and terminal events — roughly 15-25 edits per run. The local registry stays
    the authority and the published copy is allowed to lag (R6).
    """
    registry = registry or factory_run.registry_root()
    state = factory_run.load_state(issue, registry)
    if state is None:
        raise LookupError("no registry entry for issue #%d under %s"
                          % (int(issue), registry))
    publish = load_publish_state(issue, registry)
    warnings = []

    ensure_label(warnings, runner=runner)
    ensure_release(warnings, runner=runner)

    if stage_completed:
        publish_stage_log(state, publish, stage_completed, warnings,
                          registry=registry, runner=runner)
    if terminal and state.get("stage"):
        publish_stage_log(state, publish, state["stage"], warnings,
                          registry=registry, runner=runner)
    publish_screenshots(state, publish, warnings, registry=registry,
                        runner=runner)

    known = publish.get("run_issue")
    if known and not terminal:
        set_issue_state(known, True, warnings, runner=runner)

    title = render_title(state, now)
    body = render_body(state, publish, registry=registry, now=now)
    number = ensure_run_issue(state, publish, title, body, warnings,
                              registry=registry, runner=runner)

    was_projected = bool(publish.get("projected"))
    run_url = None
    if number:
        run_url = publish.get("run_issue_url") or issue_url(number)
        ensure_project_type_log(publish, run_url, warnings, runner=runner)
    if terminal:
        if number:
            set_issue_state(number, False, warnings, runner=runner)
        # A resolvable board item is one already cached (the add succeeded,
        # even if the later Type write did not) or one never attempted this
        # publish at all (an already-projected record with no cached id).
        # Neither case should retry a failed add — see
        # finish_project_status()'s docstring.
        resolved = bool(publish.get("run_item_id")) or was_projected
        finish_project_status(state, publish, run_url if resolved else None,
                              warnings, runner=runner)
        comment_once(state, publish, number, warnings, registry=registry,
                     runner=runner)

    try:
        save_publish_state(publish, registry)
    except OSError as exc:
        _warn(warnings, "publish state not saved: %s" % exc)
    return PublishResult(number, warnings, list(publish.get("uploaded") or []))


def exit_code(result):
    """0 when clean, 1 when degraded. The orchestrator must not treat 1 as a
    run failure (R11)."""
    return EXIT_DEGRADED if result.warnings else EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issue", type=int, required=True,
                        help="spec issue number of the run to publish")
    parser.add_argument("--registry", default=None,
                        help="registry root (default: <main repo root>/.factory)")
    parser.add_argument("--stage-completed", default=None,
                        help="stage whose log just completed, one of: %s"
                             % ", ".join(factory_run.STAGES))
    parser.add_argument("--terminal", action="store_true",
                        help="the run has ended: close the issue and comment")
    parser.add_argument("--run-start", action="store_true", dest="run_start",
                        help="mark the spec issue In Progress on the "
                             "Documents board; makes no other write")
    parser.add_argument("--dry-run", action="store_true",
                        help="render the body to stdout, touch no network")
    parser.add_argument("--now", default=None,
                        help="pin the clock, UTC ISO-8601 (determinism seam)")
    parser.add_argument("--open-pr", action="store_true", dest="open_pr",
                        help="open the run's pull request")
    parser.add_argument("--branch", default=None,
                        help="head branch for --open-pr")
    parser.add_argument("--title", default=None,
                        help="PR title for --open-pr")
    parser.add_argument("--body-file", default=None, dest="body_file",
                        help="PR body file for --open-pr")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    now = None
    if args.now:
        try:
            now = factory_run.parse_now(args.now)
        except ValueError as exc:
            print("factory_publish: bad --now: %s" % exc, file=sys.stderr)
            return EXIT_MISUSE
        factory_run.set_clock(lambda: now)
    if args.stage_completed and args.stage_completed not in factory_run.STAGES:
        print("factory_publish: unknown --stage-completed %r (one of: %s)"
              % (args.stage_completed, ", ".join(factory_run.STAGES)),
              file=sys.stderr)
        return EXIT_MISUSE

    if args.run_start:
        # --run-start makes exactly one write and no other, so it cannot be
        # combined with any flag that requests a different write or a
        # different contract. This check must not depend on registry_root()
        # succeeding — it has to fire even outside a git repo — and it has to
        # sit ahead of the --open-pr branch below, which would otherwise run
        # to completion instead of ever inspecting --run-start.
        conflicts = [flag for flag, present in (
            ("--dry-run", args.dry_run),
            ("--open-pr", args.open_pr),
            ("--stage-completed", args.stage_completed),
            ("--terminal", args.terminal)) if present]
        if conflicts:
            print("factory_publish: --run-start cannot be combined with %s"
                  % ", ".join(conflicts), file=sys.stderr)
            return EXIT_MISUSE

    if args.open_pr:
        missing = [n for n, v in (("--branch", args.branch),
                                  ("--title", args.title),
                                  ("--body-file", args.body_file))
                   if not v]
        if missing:
            sys.stderr.write("factory-publish: --open-pr requires %s\n"
                             % ", ".join(missing))
            return EXIT_MISUSE
        warnings = []
        url, _ = open_pr(args.issue, args.branch, args.title, args.body_file,
                         warnings=warnings)
        for message in warnings:
            sys.stderr.write("factory-publish: WARNING: %s\n" % message)
        if url:
            sys.stdout.write(url + "\n")
            return 0
        # The PR is the deliverable: unlike every other call in this tool,
        # exit 1 here is a real failure, not a publication degradation.
        return 1

    try:
        registry = args.registry or factory_run.registry_root()
        if args.run_start:
            return exit_code(run_start(args.issue, registry=registry))
        if args.dry_run:
            state = factory_run.load_state(args.issue, registry)
            if state is None:
                raise LookupError("no registry entry for issue #%d under %s"
                                  % (args.issue, registry))
            body = render_body(state, load_publish_state(args.issue, registry),
                               registry=registry, now=now)
            sys.stdout.buffer.write(body.encode("utf-8"))
            return EXIT_OK
        result = publish_run(args.issue, registry=registry,
                             stage_completed=args.stage_completed,
                             terminal=args.terminal, now=now)
    except (LookupError, RuntimeError, OSError) as exc:
        print("factory_publish: %s" % exc, file=sys.stderr)
        return EXIT_MISUSE
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())

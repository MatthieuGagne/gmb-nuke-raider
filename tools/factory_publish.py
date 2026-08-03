#!/usr/bin/env python3
"""Publish a factory run to GitHub: run issue, plan issue, stage-log and
screenshot assets, spec-issue comment, and pull request.

Sole writer of the GitHub surfaces — the run issue, the plan issue, the
release assets, the spec-issue comment, the Documents-board item fields on
both the spec and run issues, and the pull request. ``factory_run`` stays
the sole writer of run state and the journal; ``factory_log`` stays the sole
writer of ``logs/``. This module's own
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
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import factory_report
import factory_run
import factory_status
import install_hooks
sys.path.remove(_TOOLS_DIR)

# One renderer for both bodies (#517 R17).
decision_lines = factory_report.decision_lines

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
TYPE_PLAN = "Plan"
STATUS_FIELD = "Status"
STATUS_TODO = "Todo"
STATUS_IN_PROGRESS = "In Progress"
STATUS_DONE = "Done"

PUBLISH_FILE = "publish.json"
PUBLISH_SCHEMA_VERSION = 1
PUBLISH_DIRNAME = "publish"          # rendered bodies, publisher-owned

BODY_MARKER = ("<!-- factory-publish v1 — regenerated on every publish; "
               "manual edits are overwritten -->")

# One surface per run (#530 R1). The other one links here, so neither is a
# dead end (R2).
DECISIONS_IN_PR = "_The decisions are in the [pull request](%s)._"

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
        "plan_issue": None,         # the plan issue this run renders into
        "plan_projected": False,    # added to the project, Type=Plan (#514)
        "plan_item_id": None,       # Documents-project item for the plan issue
        "plan_sha256": None,        # digest of the plan as last uploaded
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
    findings, decisions = factory_report.partition_decisions(ctx["state"])
    if ctx["pr"]:
        # A shipped run puts the record where the human reviews the code, and
        # this section becomes the link to it (#530 R1, R2). The link shows
        # for a finding too: a run whose rulings are all findings would
        # otherwise leave both surfaces pointing nowhere.
        return [DECISIONS_IN_PR % ctx["pr"]] if (decisions or findings) \
            else None
    dropped = ctx["drop_decisions"]
    kept = decisions[dropped:] if dropped else decisions
    if not kept and not dropped:
        return None
    out = []
    if dropped:
        out.append("_%d earlier decisions omitted_" % dropped)
        out.append("")
    for decision in kept:
        out += decision_lines(decision)
    return out


def _section_findings(ctx):
    """Plan-review findings, this record's alone (#530 R3).

    A finding names a defect in a draft plan that was corrected before any
    code was written. It shows that plan review works, so it belongs here. It
    is not a fact about the code in the pull request, so it stays out of the
    pull request body.
    """
    findings, _decisions = factory_report.partition_decisions(ctx["state"])
    dropped = ctx["drop_findings"]
    kept = findings[dropped:] if dropped else findings
    if not kept and not dropped:
        return None
    out = []
    if dropped:
        out.append("_%d earlier findings omitted_" % dropped)
        out.append("")
    for finding in kept:
        out += decision_lines(finding)
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
    ("Plan review findings", _section_findings),
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


# ── Plan publication (#514) ──────────────────────────────────────────────────
#
# A factory run's plan is 1800-3200 lines of markdown with inline code, and it
# never reaches the branch: docs/plans/ is gitignored, so the worktree working
# copy is the only copy that exists. The issue body is therefore a structural
# summary and the release asset is the normal read path (R3/R4), not an
# overflow fallback.

PLAN_LABEL = "plan"
PLAN_LABEL_COLOR = "1D76DB"
PLAN_LABEL_DESC = "Factory execution plan for one run"

PLAN_BODY_MARKER = ("<!-- factory-publish plan v1 — regenerated on every "
                    "publish; manual edits are overwritten -->")
PLAN_SUMMARY_LINK = ("_Structural summary — fenced code and task steps "
                     "omitted. Full plan: %s_")
PLAN_SUMMARY_WITHHELD = ("_Structural summary — fenced code and task steps "
                         "omitted. Full plan withheld: %s_")
PLAN_SHED_FILES = "_Task file lists omitted — see the full plan._"
PLAN_SHED_PREAMBLE = "_Preamble omitted — see the full plan._"
PLAN_UNTERMINATED = ("_The plan ends inside an unclosed code fence — the "
                     "summary above stops there and may be incomplete. Read "
                     "the full plan._")

# A fence opens with three or more backticks or tildes, indented at most three
# spaces (CommonMark). The closer must use the same character and be at least
# as long, which is exactly how a ```` block holds a ``` one — and plans do
# that constantly, because they quote markdown documents verbatim.
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_TASK_HEADING = re.compile(r"^#{2,4}\s+Task\s+\d+\b")
_BATCH_HEADING = re.compile(
    r"^#{2,4}\s+(Batch\b|Parallel Execution Groups\b|Smoketest Checkpoint\b)")
_ANY_HEADING = re.compile(r"^#{1,6}\s")
_FILES_LINE = re.compile(r"^\*\*Files:\*\*")
_DEPENDS_LINE = re.compile(r"^\*\*Depends on:\*\*")

# The plan asset carries no attempt number, unlike every other asset here. R5
# makes it a living mirror re-uploaded whenever the plan changes, so a
# per-attempt immutable copy would contradict the re-sync it exists for.
PLAN_ASSET_TEMPLATE = "issue-%d-plan.md"


def plan_asset_name(issue):
    """``issue-<N>-plan.md`` — one per spec issue, updated in place."""
    return PLAN_ASSET_TEMPLATE % int(issue)


def _fenced(lines):
    """``(pairs, unterminated)`` — every line tagged with whether it sits
    inside a fenced block, and whether the document ended still inside one.

    Both the opening and the closing fence report True: they are part of the
    block, not of the prose around it. An unterminated fence is reported
    rather than swallowed — it makes every later line read as code, and the
    tail of a 3000-line plan would otherwise disappear from the summary with
    nothing to say it had.
    """
    out = []
    fence = None
    for line in lines:
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                out.append((line, True))
            else:
                out.append((line, False))
        else:
            closes = (match and match.group(1)[0] == fence[0]
                      and len(match.group(1)) >= len(fence))
            if closes:
                fence = None
            out.append((line, True))
    return out, fence is not None


def _collapse(lines):
    """Trim trailing space, drop edge blanks, collapse blank runs to one.

    Deleting a fenced block leaves the blank lines that surrounded it, and a
    summary made mostly of vertical whitespace is what a reader has to scroll
    past to reach the tasks.
    """
    out = []
    for line in lines:
        if line.strip():
            out.append(line.rstrip())
        elif out and out[-1] != "":
            out.append("")
    while out and out[-1] == "":
        out.pop()
    return out


def summarize_plan(text):
    """``(preamble_lines, task_blocks, unterminated)`` — R3's structural
    summary, plus whether the document ended inside an unclosed fence.

    The preamble is everything above the first task or batch heading, with
    fenced blocks removed. Each task block is its ``## Task N:`` heading plus
    its ``**Depends on:**`` line and its ``**Files:**`` line with the bullet
    list that follows; the steps, and every fenced block, are dropped.

    Fence tracking is load-bearing rather than defensive: real plans quote
    whole markdown documents inside ```` blocks, so a line-oriented scan for
    ``## Task`` finds headings that belong to a code sample.
    """
    marked, unterminated = _fenced(text.splitlines())
    first = None
    for index, (line, fence) in enumerate(marked):
        if fence:
            continue
        if _TASK_HEADING.match(line) or _BATCH_HEADING.match(line):
            first = index
            break

    head = marked if first is None else marked[:first]
    preamble = _collapse([line for line, fence in head if not fence])
    tasks = []
    if first is None:
        return preamble, tasks, unterminated

    index = first
    while index < len(marked):
        line, fence = marked[index]
        index += 1
        if fence or not _TASK_HEADING.match(line):
            continue
        block = [line.rstrip()]
        while index < len(marked):
            line, fence = marked[index]
            if not fence and _ANY_HEADING.match(line):
                break
            if fence:
                index += 1
                continue
            if _DEPENDS_LINE.match(line):
                block.append(line.rstrip())
            elif _FILES_LINE.match(line):
                block.append(line.rstrip())
                index += 1
                while index < len(marked):
                    bullet, bullet_fence = marked[index]
                    if bullet_fence or not bullet.lstrip().startswith("- "):
                        break
                    block.append(bullet.rstrip())
                    index += 1
                continue
            index += 1
        tasks.append(block)
    return preamble, tasks, unterminated


def plan_path(state):
    """Absolute path to the run's plan file, or None when there is none.

    Resolved against the worktree, never against git: ``docs/plans/`` is
    gitignored, so the branch never carries the file and the working copy is
    the only place it exists (R5).

    Normalised, because ``state["plan"]`` is recorded with forward slashes
    and ``os.path.join`` does not translate them on Windows — the mixed
    separator opens fine but is not comparable, and this path is compared.
    """
    plan = state.get("plan")
    if not plan:
        return None
    if os.path.isabs(plan):
        return plan
    worktree = state.get("worktree")
    if not worktree:
        return None
    return os.path.normpath(os.path.join(worktree, plan))


def read_plan(state):
    """The plan's text, or None when it cannot be read.

    ``errors="replace"`` for the same reason ``log_tail`` uses it: a plan a
    publisher cannot decode must still publish, badly, rather than not at all.
    """
    path = plan_path(state)
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _plan_slug(state):
    """The run's slug for the plan issue title.

    ``state["slug"]`` is the intended source but nothing in the factory
    currently emits it — ``stages.md`` step 3 records only worktree and
    branch — so the plan filename is the fallback. PRD-3 fixes the filename
    as ``YYYY-MM-DD-issue<N>-<slug>.md``, which makes the slug recoverable
    without inventing a second naming convention.
    """
    slug = state.get("slug")
    if slug:
        return slug
    plan = state.get("plan")
    if plan:
        stem = os.path.splitext(os.path.basename(plan))[0]
        match = re.match(r"^\d{4}-\d{2}-\d{2}-issue\d+-(.+)$", stem)
        if match:
            return match.group(1)
        if stem:
            return stem
    return "(no slug)"


def render_plan_title(state):
    """``plan: <slug> (#<N>)`` (R1). Pure."""
    return "plan: %s (#%d)" % (_plan_slug(state), int(state["issue"]))


# factory_report.ABSOLUTE_PATH with one change: a left boundary on the
# drive-letter alternative. Without it the pattern matches the "s:/" inside
# "https:/" and turns every citation into "http<path>" -- and plans cite
# issue and PR URLs constantly. Anchoring beats holding URLs out of the
# redaction: an exemption is unreachable by the redactor, so a path glued to
# a URL (".../build?out=C:\Users\alice\log.txt") rode straight through it.
# factory_report is out of scope for #514, so the variant lives here.
_PROSE_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s`|]*"
    r"|\\\\[^\s`|]+"
    r"|(?<![\w.~-])/(?:home|Users|opt|mnt|srv|var|tmp)/[^\s`|]*")


def _redact_prose(text):
    """``factory_report.redact`` for free-form plan prose.

    Same substitution, same placeholder; only the drive-letter alternative
    differs, and only by requiring that it not follow an alphanumeric. A
    plain ``https://host/path`` is therefore untouched while
    ``C:\\Users\\...`` still goes, wherever it appears -- including inside a
    URL's query string.
    """
    return _PROSE_PATH.sub(factory_report.REDACTION, text)


def render_plan_body(state, publish, plan_text, repo=DEFAULT_REPO,
                     budget=BODY_BUDGET):
    """The plan issue body, bounded at *budget* characters (R3).

    Render, measure, then shed in a fixed order until it fits: the task file
    lists first, then the preamble, each cut leaving an explicit marker.
    Never shed: the header, the task headings, and the link to the full plan —
    a summary that has lost its task list is not a summary of a plan. A hard
    truncation is the backstop, exactly as in ``render_body``.

    An empty *plan_text* is meaningful, not an error: it is what
    ``publish_plan`` passes when ``scan_secrets`` refused the file, and it
    renders a body with a header and a withheld marker and no plan text at
    all. The scan guards the issue body as well as the asset — the body is
    the more exposed of the two, because it is indexed.
    """
    issue = int(state["issue"])
    name = plan_asset_name(issue)
    withheld = (publish.get("withheld") or {}).get(name)
    link = PLAN_SUMMARY_WITHHELD % withheld if withheld else \
        PLAN_SUMMARY_LINK % asset_url(name, repo)

    # redact() for the same reason display_worktree() uses it: state["plan"]
    # may be absolute, and this body is a public issue.
    header = ["**Spec** #%d · **Plan** `%s` · **Branch** `%s`"
              % (issue, factory_report.redact(state.get("plan") or "-"),
                 state.get("branch") or "-")]
    run_issue = publish.get("run_issue")
    if run_issue:
        header += ["", "Run issue: #%d" % run_issue]

    preamble, tasks, unterminated = summarize_plan(plan_text)
    # Every line below is lifted verbatim from a local file and published to
    # a public, indexed issue. Plans routinely name machine-specific
    # toolchain paths in their preamble and absolute paths in a Files
    # bullet, and this text needs exactly the redaction display_worktree()
    # already gives a worktree path.
    preamble = [_redact_prose(line) for line in preamble]
    tasks = [[_redact_prose(line) for line in block] for block in tasks]

    def build(drop_files, drop_preamble):
        out = list(header)
        if drop_preamble:
            out += ["", PLAN_SHED_PREAMBLE]
        elif preamble:
            out += [""] + preamble
        for block in tasks:
            out += [""] + ([block[0]] if drop_files else block)
        if drop_files and tasks:
            out += ["", PLAN_SHED_FILES]
        if unterminated:
            out += ["", PLAN_UNTERMINATED]
        out += ["", link, "", PLAN_BODY_MARKER]
        return "\n".join(out) + "\n"

    for shed in ((False, False), (True, False), (True, True)):
        body = build(*shed)
        if len(body) <= budget:
            return body
    return body[:budget - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def _render(ctx):
    state = ctx["state"]
    header = ("**Spec** #%d · **Branch** `%s` · **Attempt** %d · **Updated** %s"
              % (int(state["issue"]), state.get("branch") or "-",
                 int(state.get("attempt") or 1), state.get("updated") or "-"))
    plan_issue = (ctx["publish"] or {}).get("plan_issue")
    if plan_issue:
        header += " · **Plan** #%d" % plan_issue
    out = [header, "", stage_strip(state, ctx["now"])]
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
    permission events, then plan-review findings oldest-first, then decisions
    oldest-first. Never shed: the status header, the stage strip, the failure
    fields, the gate table, the stage-log asset table. A hard truncation is
    the backstop (R5).
    """
    ctx = {"state": state, "publish": publish, "registry": registry,
           "now": now, "repo": repo, "sections": SECTIONS,
           "pr": state.get("pr") or (publish or {}).get("pr_url"),
           "shed_tail": False, "shed_permissions": False,
           "drop_findings": 0, "drop_decisions": 0}

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

    findings, decisions = factory_report.partition_decisions(state)

    # Findings before decisions: a finding describes a draft that no longer
    # exists, while a decision explains the code that shipped.
    for drop in range(1, len(findings) + 1):
        ctx["drop_findings"] = drop
        body = attempt()
        if body is not None:
            return body

    if not ctx["pr"]:
        # Oldest first: the most recent decisions are the ones that explain
        # where the run is now. Linear because decisions are human-authored
        # and few. Skipped when the section is already just a link.
        for drop in range(1, len(decisions) + 1):
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


def ensure_label(warnings, runner=subprocess.run, label=RUN_LABEL,
                 color="5319E7", description="Factory run dashboard issue"):
    """Create *label* if it is missing. Idempotent, fail-open."""
    proc = gh(["label", "create", label, "--color", color,
               "--description", description], runner=runner)
    if proc.returncode == 0 or _already(proc, "already exists"):
        return True
    _warn(warnings, "label %r not ensured: %s" % (label, _tail(proc.stderr)))
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
    if fields.returncode != 0:
        _warn(warnings, "project field-list failed, %s=%s not set: %s"
              % (field_name, option_name, _tail(fields.stderr)))
        return None, None
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
        _warn(warnings, "project %s=%s not set: no %s field with option %r "
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


def ensure_project_type_plan(publish, issue_url, warnings,
                             runner=subprocess.run):
    """Add the plan issue to "Nuke Raider — Documents", ``Type = Plan``.

    Mirrors ``ensure_project_type_log`` and deliberately writes no ``Status``:
    a plan is a document, not a run. It has no lifecycle on the board — it is
    created once and closed by the merge of the run's PR (#514 R9), so there
    is no state for a Status column to track.

    ``Plan`` must exist as an option on the board's ``Type`` field before this
    can succeed; it is a one-time manual prerequisite. Until it does, the plan
    issue is still created and labelled and the run is unaffected — one
    warning per publish.
    """
    if publish.get("plan_projected"):
        return True
    item_id = publish.get("plan_item_id") or \
        project_item_add(issue_url, warnings, runner=runner)
    if not item_id:
        return False
    publish["plan_item_id"] = item_id
    if not set_single_select(item_id, TYPE_FIELD, TYPE_PLAN, warnings,
                             runner=runner):
        return False
    publish["plan_projected"] = True
    return True


def finish_project_status(state, publish, run_url, warnings,
                          runner=subprocess.run):
    """The terminal board writes (#513 R4).

    The run issue is Done either way. The spec goes back to Todo only when the
    run failed: a successful run leaves it In Progress, because the PR is open
    and it is the merge — which this module never observes — that finishes the
    spec.

    Outside the ``projected`` guard on purpose: behind it, these writes would
    no-op on every run after the first publish. The spec half is also outside
    ``run_url``: a failed run whose dashboard issue could not be created is
    exactly when a spec pinned at In Progress would mislead longest.

    ``run_url`` is ``None`` exactly when this publish's only add attempt for
    the run issue already failed (inside ``ensure_project_type_log``) —
    retrying it here would just repeat the call and double the warning for it.
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

@contextlib.contextmanager
def staged(path, name):
    """A short-lived copy of *path* under its published name (#530 R4).

    ``gh release upload`` names an asset after the file's basename, so the
    rename is what carries ``issue-<N>-attempt-<k>-<stage>.log``. The copy is
    also what keeps the upload byte-exact: bytes in, bytes out, no read of the
    content.

    It lives in a temporary directory and is removed when the upload returns.
    A byte-identical second copy inside the run registry costs disk for the
    life of the run and proves nothing that the upload does not prove already.
    """
    directory = tempfile.mkdtemp(prefix="factory-publish-")
    try:
        dest = os.path.join(directory, name)
        shutil.copyfile(path, dest)
        yield dest
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def upload_asset(path, name, publish, warnings, runner=subprocess.run,
                 clobber=False):
    """Upload one staged asset. Never clobbers an existing one (R7).

    The single exception is the plan asset, which R5 (#514) makes a living
    mirror of the plan file: it is re-uploaded with ``--clobber`` whenever the
    plan's sha256 moves, and its ledger entry stays one name.
    """
    uploaded = publish.setdefault("uploaded", [])
    if name in uploaded and not clobber:
        return True
    argv = ["release", "upload", RELEASE_TAG, path]
    if clobber:
        argv.append("--clobber")
    proc = gh(argv, runner=runner)
    if proc.returncode != 0:
        _warn(warnings, "asset %s not uploaded: %s" % (name, _tail(proc.stderr)))
        return False
    if name not in uploaded:
        uploaded.append(name)
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

    try:
        with staged(src, name) as dest:
            return upload_asset(dest, name, publish, warnings, runner=runner)
    except OSError as exc:
        _warn(warnings, "asset %s not staged: %s" % (name, exc))
        return False


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
        try:
            with staged(path, name) as dest:
                sent = upload_asset(dest, name, publish, warnings,
                                    runner=runner)
        except OSError as exc:
            _warn(warnings, "screenshot %s not staged: %s" % (name, exc))
            continue
        if sent:
            published.append(name)
    return published


def publish_plan_asset(state, publish, path, reason, warnings, registry=None,
                       runner=subprocess.run):
    """Upload the byte-exact plan, re-uploading only when it changed (R4/R5).

    The plan is the one asset that is a mirror rather than a record: real
    plans are 1800-3200 lines and the issue body is only a summary, so this
    file is the normal read path and it has to track edits made during BUILD.

    *reason* is ``scan_secrets(path)``, computed once by the caller because
    the same verdict also decides whether the issue **body** may carry the
    plan text. Scanning here and rendering there independently is how a
    credential ends up withheld from the asset and published in the issue.
    """
    issue = int(state["issue"])
    name = plan_asset_name(issue)
    if reason:
        # redact BOTH halves: scan_secrets' "unreadable, not scanned: <exc>"
        # variant carries str(OSError), which embeds the absolute path it
        # failed to open. Redacting only the neighbouring value on this line
        # is the mistake 81808b7 and c901676 already fixed twice.
        safe = factory_report.redact(reason)
        publish.setdefault("withheld", {})[name] = "%s — local copy: %s" % (
            safe,
            factory_report.redact(state.get("plan") or "the run's worktree"))
        _warn(warnings, "plan asset withheld: %s (the run is unaffected)"
              % safe)
        return False
    # A mirror clears as well as sets: once the author removes the offending
    # string, a stale entry here would keep the body rendering the withheld
    # marker forever and make R5's re-sync one-way.
    publish.setdefault("withheld", {}).pop(name, None)

    try:
        digest = factory_run.sha256_file(path)
    except OSError as exc:
        _warn(warnings, "plan asset %s not hashed: %s" % (name, exc))
        return False
    if digest == publish.get("plan_sha256"):
        return True

    try:
        with staged(path, name) as dest:
            if not upload_asset(dest, name, publish, warnings, runner=runner,
                                clobber=True):
                return False
    except OSError as exc:
        _warn(warnings, "plan asset %s not staged: %s" % (name, exc))
        return False
    publish["plan_sha256"] = digest
    return True


def ensure_plan_issue(state, publish, title, body, warnings, registry=None,
                      runner=subprocess.run):
    """Create the plan issue, or edit the one this run already owns (R6).

    Never closed by this module: a plan issue is closed by the merge of the PR
    that carries ``Closes #<plan issue>`` (R7), and a run that never ships
    leaves it open on purpose, as standing evidence (R9).
    """
    issue = int(state["issue"])
    path = write_body_file(issue, body, registry, name="publish-plan-body.md")
    number = publish.get("plan_issue")
    if number:
        proc = gh(["issue", "edit", str(number), "--title", title,
                   "--body-file", path], runner=runner)
        if proc.returncode != 0:
            _warn(warnings, "plan issue #%d not updated: %s"
                  % (number, _tail(proc.stderr)))
        return number

    ensure_label(warnings, runner=runner, label=PLAN_LABEL,
                 color=PLAN_LABEL_COLOR, description=PLAN_LABEL_DESC)
    proc = gh(["issue", "create", "--title", title, "--body-file", path,
               "--label", PLAN_LABEL], runner=runner)
    if proc.returncode != 0:
        _warn(warnings, "plan issue not created: %s" % _tail(proc.stderr))
        return None
    match = _ISSUE_NUMBER.search((proc.stdout or "").strip())
    if not match:
        _warn(warnings, "plan issue number not parseable from: %s"
              % _tail(proc.stdout))
        return None
    publish["plan_issue"] = int(match.group(1))
    publish["plan_issue_url"] = (proc.stdout or "").strip().splitlines()[-1]
    return publish["plan_issue"]


def publish_plan(state, publish, warnings, registry=None,
                 runner=subprocess.run, repo=DEFAULT_REPO):
    """Create or re-sync this run's plan issue and its release asset (#514).

    Fail-open in exactly one place: the plan is read once, and a plan that
    cannot be read costs one warning and skips both surfaces (R10). A run with
    no plan recorded — every publish before PLAN step 4 — is silent rather
    than degraded, because there is nothing wrong with it yet.
    """
    if not state.get("plan"):
        return None
    text = read_plan(state)
    if text is None:
        _warn(warnings, "plan not published: cannot read %s"
              % factory_report.redact(state.get("plan")
                                      or "the recorded path"))
        return publish.get("plan_issue")

    # One scan, two surfaces. A credential-shaped string withholds the asset
    # *and* empties the summary: the issue body is the more exposed of the
    # two, because GitHub indexes it and a release asset is a download.
    path = plan_path(state)
    reason = scan_secrets(path)
    publish_plan_asset(state, publish, path, reason, warnings,
                       registry=registry, runner=runner)
    number = ensure_plan_issue(
        state, publish, render_plan_title(state),
        render_plan_body(state, publish, "" if reason else text, repo=repo),
        warnings, registry=registry, runner=runner)
    if number:
        url = publish.get("plan_issue_url") or \
            "https://github.com/%s/issues/%d" % (repo, number)
        ensure_project_type_plan(publish, url, warnings, runner=runner)
    return number


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
        lines.append("Run issue: #%d" % run_issue)
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


CLOSES_LINE = "Closes #%d"


def pr_body_with_plan(issue, body_path, registry=None, warnings=None):
    """The PR body path, with ``Closes #<plan issue>`` appended (R7).

    Returns the original path when there is no plan issue or the body already
    closes it, and a staged copy otherwise — the file handed in is never
    rewritten, because it is ``factory_report``'s deterministic output and the
    SHIP stage may re-render it.

    ``factory_report`` is deliberately not taught about this: the plan issue
    number lives in ``publish.json``, which only this module owns, and
    widening that boundary is what ADR 0006 (#475) exists to prevent.

    Fail-open like the rest of this file, and specifically *not* covered by
    the ``--open-pr`` exception: a PR that ships without the plan link is a
    degradation, while a PR that does not ship at all is a run failure (R10).

    ``TypeError`` is in the caught set because ``plan_issue`` is read back
    from a JSON file: a non-numeric value survives the ``if not number``
    guard and reaches ``int()``, and this is the one call site with no
    enclosing handler.
    """
    warnings = warnings if warnings is not None else []
    try:
        number = load_publish_state(issue, registry).get("plan_issue")
        if not number:
            return body_path
        with open(body_path, encoding="utf-8") as fh:
            body = fh.read()
        line = CLOSES_LINE % int(number)
        if re.search(r"(?m)^%s\s*$" % re.escape(line), body):
            return body_path
        if body and not body.endswith("\n"):
            body += "\n"
        return write_body_file(issue, body + line + "\n", registry,
                               name="publish-pr-body.md")
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _warn(warnings, "plan issue not linked from the PR body: %s" % exc)
        return body_path


def open_pr_cli(issue, branch, title, body_file, registry=None,
                runner=subprocess.run):
    """The ``--open-pr`` command. Returns ``(url_or_None, warnings)``.

    Persists ``pr_url`` in publish.json, which is what lets the run issue link
    to the pull request instead of repeating the decision record (#530 R1).
    The URL has to outlive this process for that to work, and the ``finish``
    event does not carry it into the projection.

    Nothing is saved when no URL comes back: a failed ``gh pr create`` must
    not leave a URL behind for the next publish to link to.
    """
    warnings = []
    publish = load_publish_state(issue, registry)
    body_file = pr_body_with_plan(issue, body_file, registry=registry,
                                  warnings=warnings)
    url, _created = open_pr(issue, branch, title, body_file, publish=publish,
                            warnings=warnings, runner=runner)
    if url:
        try:
            save_publish_state(publish, registry)
        except OSError as exc:
            _warn(warnings, "publish state not saved: %s" % exc)
    return url, warnings


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
    registry entry: the run directory may not exist yet — ``save_publish_state``
    creates it, and the later ``start`` event reuses it.
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
    # Before the run issue renders, so its header can cross-link a plan issue
    # number that is already known (R11). By PLAN the run issue exists — GATE
    # published first — so the plan body's own back-link is never empty.
    publish_plan(state, publish, warnings, registry=registry, runner=runner)

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
        # Resolvable: the add already succeeded, or was never attempted this
        # publish (see finish_project_status()'s docstring re run_url=None).
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
        url, _warnings = open_pr_cli(args.issue, args.branch, args.title,
                                     args.body_file, registry=args.registry)
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

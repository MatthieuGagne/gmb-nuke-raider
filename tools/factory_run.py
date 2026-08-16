#!/usr/bin/env python3
"""Factory run registry: run state, event journal, and autopsy bundles.

The registry lives at ``<main repo root>/.factory/runs/issue-<N>/`` — outside
every worktree, so a run stays explainable after its worktree is gone.

The journal (``journal.jsonl``) is the source of truth and ``state.json`` is a
cached projection of it; see ADR 436. ``append_event()``
writes the journal line first, then re-saves state atomically, so state can lag
the journal by one event and can never lead it.

This module is the sole writer of run state and the journal; ``factory_log.py``
is the sole writer of the ``logs/`` subtree (ADR 450). Every other
factory tool reads. It is a library, not a CLI: ``factory_status.py`` and
``factory_report.py`` are the command-line surfaces.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install_hooks

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

    The environment is scrubbed with ``install_hooks.clean_env``: git exports
    ``GIT_DIR`` and friends into every hook's environment and they override
    *cwd*, so an unscrubbed call made from a hook resolves to whichever
    repository invoked the hook rather than to *cwd* (#441).
    """
    cwd = os.path.abspath(cwd or os.getcwd())
    proc = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                          cwd=cwd, capture_output=True, text=True,
                          env=install_hooks.clean_env())
    if proc.returncode != 0:
        raise RuntimeError("not a git repository: %s" % cwd)
    common = os.path.abspath(os.path.join(cwd, proc.stdout.strip()))
    return os.path.dirname(common)


def smoketest_dir(worktree, main_root=None):
    """Where ONE run's smoketest artifacts are, or None.

    Before #588 the harness wrote into the worktree; since R14 it writes into
    the main tree, under a directory named for the checkout that produced them.
    Both places are checked, worktree first, so a run made before the change
    still publishes its evidence.

    The name-for-the-checkout part is what keeps this exact. A bare
    ``<main>/build/smoketest`` would match ANY run's output, so a stale run
    whose worktree is gone would be handed a live run's screenshots.

    main_root defaults to this repository's main tree. A caller holding a
    registry path passes that path's parent instead, which keeps the lookup
    inside whatever tree the registry belongs to — that is what makes this
    hermetic under a temporary registry in the tests.
    """
    candidates = []
    if worktree:
        candidates.append(os.path.join(worktree, "build", "smoketest"))
    if main_root is None:
        try:
            main_root = repo_root()
        except RuntimeError:
            main_root = None
    if main_root and worktree:
        leaf = os.path.basename(os.path.normpath(worktree))
        candidates.append(os.path.join(main_root, "build", "smoketest", leaf))
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


def main_root_of(registry):
    """The tree a registry path belongs to: ``<root>/.factory`` -> ``<root>``."""
    return os.path.dirname(os.path.normpath(registry)) if registry else None


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


def log_path(issue, stage, registry=None):
    """``runs/issue-<N>/logs/<STAGE>.log`` — written by factory_log.py (#450)."""
    return os.path.join(run_dir(issue, registry), "logs", "%s.log" % stage)


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
        "pr": None,
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


def apply_event(state, event):
    """Fold one event into *state*. Mutates and returns it.

    This is the whole projection. ``rebuild_state`` and ``append_event`` share
    it, which is what makes replay and incremental writing agree by
    construction rather than by discipline.
    """
    kind = event.get("kind")
    ts = event.get("ts")
    if event.get("attempt") is not None:
        state["attempt"] = event["attempt"]

    if kind == "start":
        for field in ("slug", "branch", "worktree", "plan", "pr"):
            if event.get(field) is not None:
                state[field] = event[field]
        if event.get("stage"):
            state["stage"] = event["stage"]
    elif kind == "stage":
        state["stage"] = event.get("stage")
    elif kind == "gate":
        state["gates"].append({"stage": event.get("stage"),
                               "gate": event.get("gate"),
                               "result": event.get("result"), "ts": ts})
    elif kind == "decision":
        # `text` is the one-sentence ruling, `rationale` the reasoning behind
        # it (#517 R15). `rationale` is optional and the key is left out when
        # it is absent, so a journal written before this field replays to the
        # same bytes and SCHEMA_VERSION stays at 1 (R16).
        record = {"text": event.get("text"), "ts": ts}
        if event.get("rationale") is not None:
            record["rationale"] = event["rationale"]
        # A plan-review finding names a defect in a draft plan that was
        # corrected before any code was written (#530 R3). The marker is
        # explicit, never inferred from the stage: an unmarked ruling stays a
        # decision, so a run that forgets the field keeps the ruling on the
        # reviewer's surface instead of hiding it there.
        if event.get("finding"):
            record["finding"] = True
        state["decisions"].append(record)
    elif kind == "scenario":
        state["scenarios"].append({"scenario": event.get("scenario"),
                                   "result": event.get("result"),
                                   "blocking": event.get("blocking"), "ts": ts})
    elif kind == "permission":
        state["permissions"].append({"tool": event.get("tool"),
                                     "command": event.get("command"),
                                     "outcome": event.get("outcome"),
                                     "reason": event.get("reason"), "ts": ts})
    elif kind == "retry":
        # A new attempt re-runs the gates and scenarios, so this attempt's
        # results start empty. Decisions and permissions accumulate across the
        # whole run: both are evidence about the run, not about one pass.
        state["gates"] = []
        state["scenarios"] = []
        state["failure"] = None
        state["finished"] = None
        state["stage"] = event.get("stage") or state["stage"]
    elif kind == "failure":
        state["failure"] = {"message": event.get("message"), "ts": ts}
    elif kind == "finish":
        state["finished"] = {"result": event.get("result"), "ts": ts}

    state["updated"] = ts
    state["event_count"] += 1
    return state


def rebuild_state(issue, events):
    """Replay *events* into a fresh projection."""
    state = new_state(issue)
    for event in events:
        apply_event(state, event)
    return state


def read_journal(issue, registry=None):
    """Parsed events, oldest first. Unparseable lines are skipped, not fatal.

    A truncated final line is the expected corruption for an append-only file
    written by a process that was killed; a corrupt middle line is rarer but
    equally survivable, and a forensic tool that refuses to open the file is
    useless at exactly the moment it is needed.
    """
    try:
        with open(journal_path(issue, registry), encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return []
    events = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def _load_state_raw(issue, registry=None):
    """state.json as written, or None when it is unusable."""
    try:
        with open(state_path(issue, registry), encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or \
            state.get("schema_version") != SCHEMA_VERSION:
        return None
    return state


def load_state(issue, registry=None):
    """Current state, self-healing. Never writes.

    Rebuilds from the journal when state.json is missing, unparseable, of a
    foreign schema version, or behind the journal. Returns None when the run
    has no registry entry at all.
    """
    events = read_journal(issue, registry)
    state = _load_state_raw(issue, registry)
    if state is not None and state.get("event_count") == len(events):
        return state
    if not events:
        return state
    return rebuild_state(issue, events)


def ordered_gates(state):
    """Gates in canonical stage order, journal order within a stage.

    Stages the schema does not know sort last rather than being dropped — an
    unrecognised stage is a reporting problem, not a reason to hide evidence.
    """
    rank = {stage: i for i, stage in enumerate(STAGES)}
    gates = state.get("gates") or []
    return [gate for _, gate in sorted(
        enumerate(gates),
        key=lambda pair: (rank.get(pair[1].get("stage"), len(rank)), pair[0]))]


def append_event(issue, kind, registry=None, **fields):
    """Append one event, then re-save the projection. Returns the event.

    Journal first, state second — see ADR 436. Fields whose value is None are
    dropped so the journal stays readable. This function performs no rendering
    and no network I/O: publication to GitHub is an explicit call into
    factory_publish, never a side effect of the writer (#472 R6).
    """
    if "render" in fields:
        # Explicit, because **fields would otherwise swallow a stale render=
        # and write it into the journal as if it were run data.
        raise TypeError("append_event() got an unexpected keyword argument "
                        "'render' (#472 R14)")
    if kind not in EVENT_KINDS:
        raise ValueError("unknown event kind: %r (expected one of %s)"
                         % (kind, ", ".join(EVENT_KINDS)))
    registry = registry or registry_root()
    directory = run_dir(issue, registry)
    os.makedirs(directory, exist_ok=True)

    state = _load_state_raw(issue, registry)
    journal = read_journal(issue, registry)
    if state is None or state.get("event_count") != len(journal):
        state = rebuild_state(issue, journal)

    attempt = fields.pop("attempt", None)
    event = {"ts": timestamp(), "issue": int(issue), "kind": kind,
             "attempt": int(attempt) if attempt is not None
                        else state["attempt"]}
    event.update({k: v for k, v in fields.items() if v is not None})

    with open(os.path.join(directory, JOURNAL_FILE), "a",
              encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())

    apply_event(state, event)
    save_state(state, registry)
    return event


# ── Autopsy ──────────────────────────────────────────────────────────────────

def sha256_file(path):
    """Hex sha256 of *path*, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_autopsy(issue, registry=None, worktree=None, scenario=None,
                  rom=None, ref_rom=None):
    """Copy this attempt's evidence into ``autopsy/attempt-<k>/``.

    Everything worktree-resident is copied in, never referenced, so the bundle
    outlives the worktree. Stage logs are excluded on purpose: they are written
    straight into the registry (#450) and already survive.

    Best-effort by contract. Every expected artifact is listed in
    ``manifest.json`` as present or absent-with-reason, a missing artifact is
    never an error, and this function never raises — an autopsy that dies
    during a failure destroys the evidence it exists to preserve. Returns the
    bundle directory, or None when the registry itself is unusable.
    """
    registry = registry or registry_root()
    try:
        state = load_state(issue, registry) or new_state(issue)
        attempt = int(state.get("attempt") or 1)
        dest = os.path.join(run_dir(issue, registry), "autopsy",
                            "attempt-%d" % attempt)
        os.makedirs(dest, exist_ok=True)
    except Exception:
        return None

    entries = []

    def record(name, src, rel=None):
        if not src or not os.path.isfile(src):
            entries.append({"name": name, "present": False,
                            "reason": "not found: %s" % (src or "<unset>")})
            return
        rel = rel or os.path.basename(src)
        try:
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)
            entries.append({"name": name, "present": True, "source": src,
                            "dest": rel.replace(os.sep, "/")})
        except OSError as exc:
            entries.append({"name": name, "present": False,
                            "reason": "copy failed: %s" % exc})

    try:
        record("state", os.path.join(run_dir(issue, registry), STATE_FILE))
        record("journal", os.path.join(run_dir(issue, registry), JOURNAL_FILE))
        record("scenario", scenario)

        smoke = smoketest_dir(worktree, main_root=main_root_of(registry))
        if not smoke:
            entries.append({"name": "smoketest", "present": False,
                            "reason": "no smoketest directory in the worktree "
                                      "or the main tree"})
        else:
            copied = 0
            for name in sorted(os.listdir(smoke)):
                sub = os.path.join(smoke, name)
                if not os.path.isdir(sub):
                    continue
                for fname in sorted(os.listdir(sub)):
                    if fname.endswith((".png", ".jsonl")) or \
                            fname == "results.json":
                        record("smoketest/%s/%s" % (name, fname),
                               os.path.join(sub, fname),
                               os.path.join("smoketest", name, fname))
                        copied += 1
            entries.append({"name": "smoketest", "present": copied > 0,
                            "reason": None if copied else
                                      "no artifacts under %s" % smoke,
                            "count": copied})

        checks = {}
        for label, path in (("rom", rom), ("ref_rom", ref_rom)):
            if path and os.path.isfile(path):
                try:
                    checks[label] = {"path": path, "sha256": sha256_file(path)}
                    continue
                except OSError as exc:
                    reason = "hash failed: %s" % exc
            else:
                reason = "not found: %s" % (path or "<unset>")
            checks[label] = {"path": path, "sha256": None, "reason": reason}
            entries.append({"name": "checksum:%s" % label, "present": False,
                            "reason": reason})
        with open(os.path.join(dest, "checksums.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(checks, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except Exception as exc:
        entries.append({"name": "assembly", "present": False,
                        "reason": "aborted: %s" % exc})

    try:
        with open(os.path.join(dest, "manifest.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"schema_version": SCHEMA_VERSION, "issue": int(issue),
                       "attempt": attempt, "created": timestamp(),
                       "artifacts": entries}, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except Exception:
        pass
    return dest


# ── Workspace preservation ───────────────────────────────────────────────────

def sdd_workspace_dir(worktree, plan):
    """The subagent-driven-development workspace for one plan, or None.

    The baseline's ``scripts/sdd-workspace`` resolves this as
    ``<git rev-parse --show-toplevel>/.superpowers/sdd/<plan basename minus
    .md>/``. Note the asymmetry with ``registry_root``: the registry hangs off
    ``--git-common-dir``, the MAIN repo root, while this hangs off the
    WORKTREE root. Both are computed here from the paths the run already
    recorded rather than by shelling out to git, which keeps this hermetic
    under a temporary registry in the tests.

    The legacy flat path ``.superpowers/sdd/progress.md`` — a ledger written
    before the baseline scoped workspaces per plan — is deliberately not
    matched: an unscoped ledger may belong to another plan entirely.
    """
    if not worktree or not plan:
        return None
    slug = os.path.basename(str(plan).replace("/", os.sep))
    if slug.endswith(".md"):
        slug = slug[:-3]
    if not slug or slug in (".", ".."):
        return None
    candidate = os.path.join(worktree, ".superpowers", "sdd", slug)
    return candidate if os.path.isdir(candidate) else None


def preserve_workspace(issue, registry=None, worktree=None, plan=None):
    """Copy a run's own working notes into ``sdd-workspace/``.

    The plan, the subagent-driven-development ledger and every task brief and
    report live in the worktree and are gitignored (``docs/plans/`` and
    ``.superpowers/``), so ordinary worktree cleanup destroys the record of why
    the run made the choices it made (#633 R6). Everything is copied, never
    referenced, so the notes outlive the worktree — the same contract
    ``write_autopsy`` keeps for failure evidence.

    Unlike the autopsy this is NOT attempt-scoped: a later attempt's notes
    replace an earlier attempt's, matching how the publisher treats the plan
    asset. The journal is the per-attempt record.

    ``worktree`` and ``plan`` default to the run state's values. ``plan`` is
    repo-relative, resolved against the worktree — the only tree it exists in.

    Best-effort by contract (#633 R7). Every expected artifact is listed in
    ``manifest.json`` as present or absent-with-reason, a missing artifact is
    never an error, and this function never raises: preservation that can fail
    a run is worse than no preservation. Returns the directory, or None when
    the registry itself is unusable.
    """
    registry = registry or registry_root()
    try:
        state = load_state(issue, registry) or new_state(issue)
        worktree = worktree or state.get("worktree")
        plan = plan or state.get("plan")
        dest = os.path.join(run_dir(issue, registry), "sdd-workspace")
        os.makedirs(dest, exist_ok=True)
    except Exception:
        return None

    entries = []

    def record(name, src, rel=None):
        if not src or not os.path.isfile(src):
            entries.append({"name": name, "present": False,
                            "reason": "not found: %s" % (src or "<unset>")})
            return False
        rel = rel or os.path.basename(src)
        try:
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)
            entries.append({"name": name, "present": True, "source": src,
                            "dest": rel.replace(os.sep, "/")})
            return True
        except OSError as exc:
            entries.append({"name": name, "present": False,
                            "reason": "copy failed: %s" % exc})
            return False

    try:
        plan_src = None
        if worktree and plan:
            plan_src = os.path.join(worktree, str(plan).replace("/", os.sep))
        record("plan", plan_src)

        sdd = sdd_workspace_dir(worktree, plan)
        if not sdd:
            entries.append({"name": "workspace", "present": False,
                            "reason": "no SDD workspace for plan %s under %s"
                                      % (plan or "<unset>",
                                         worktree or "<unset>")})
            entries.append({"name": "ledger", "present": False,
                            "reason": "no SDD workspace to read it from"})
        else:
            copied = 0
            ledger = False
            for fname in sorted(os.listdir(sdd)):
                src = os.path.join(sdd, fname)
                if not os.path.isfile(src):
                    continue
                if record("workspace/%s" % fname, src,
                          os.path.join("workspace", fname)):
                    copied += 1
                    if fname == "progress.md":
                        ledger = True
            entries.append({"name": "workspace", "present": copied > 0,
                            "reason": None if copied else
                                      "no files under %s" % sdd,
                            "count": copied})
            entries.append({"name": "ledger", "present": ledger,
                            "reason": None if ledger else
                                      "no progress.md under %s" % sdd})
    except Exception as exc:
        entries.append({"name": "assembly", "present": False,
                        "reason": "aborted: %s" % exc})

    try:
        with open(os.path.join(dest, "manifest.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"schema_version": SCHEMA_VERSION, "issue": int(issue),
                       "created": timestamp(), "artifacts": entries},
                      fh, indent=2, sort_keys=True)
            fh.write("\n")
    except Exception:
        pass
    return dest

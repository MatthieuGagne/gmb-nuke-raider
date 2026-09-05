---
name: subagent-driven-development
baseline: superpowers@6.3.0
---

Project (Nuke Raider) additions and overrides for the baseline subagent-driven-development
skill. On conflict, this overlay wins — but an override earns that only by stating what the
baseline cannot know. Every section below has a `**Why:**` in `references/sdd-rationale.md`,
keyed by the same heading; a section that could not state one was removed rather than kept
(#527 R7). Read that file before relaxing or deleting an override.

*Baseline audit provenance: `references/baseline-audits.md`.*

## Overrides (do NOT follow the baseline here)

### The fifth stop — the batch-boundary smoketest pause

**This overlay adds a fifth stop, and only this one:** the batch-boundary smoketest confirmation
in `### Batch boundaries are smoketest checkpoints` below.

Everything else in "Rulings, not stalls" is **adopted in full**: preflight conflicts,
plan-mandated findings, breaker adjudications and plan defects are the controller's to rule on
and ledger, never to ask about. Two notes on fit: the pre-PR push is already the baseline's third
stop, so `### Pre-PR Gate (HARD STOP)` needs no exception; and `### Factory mode` replaces the
fifth stop with a machine verdict, so a factory run uses the four-stop list unmodified.

## Accepted from the baseline — do NOT override

These belong to the baseline and this overlay deliberately adds nothing to them. Re-stating one
here in weaker form is how an overlay silently reverts an upstream improvement.

- **The workspace and ledger system**, and its fix loop — use them as written. Note only that
  its helper scripts are POSIX `sh`, live in the superpowers skill directory (they are **not**
  repo-local — this repo has no `scripts/`), and run under Git Bash on this machine; if the
  baseline's `scripts/sdd-workspace` fails on Windows, fall back to computing
  `<repo-root>/.superpowers/sdd/<plan-basename>/` by hand — same contract, same layout.
- **One task review per task**, covering spec compliance AND code quality in a single dispatch.
  Never split it into two dispatches, and never accept a report missing either verdict.
- **The diff handoff.** Hand the reviewer its diff as a file — the baseline's
  `scripts/review-package PLAN_FILE BASE HEAD` (in the superpowers skill directory, **not**
  repo-local) prints the path — and pass that path. If that script fails on Windows, write the
  diff by hand to `<repo-root>/.superpowers/sdd/<plan-basename>/review-<task>.diff`
  (`git diff BASE HEAD > <that path>`) and pass that path — same contract. The diff never enters
  the orchestrator's context.
- **The review range.** BASE is the commit recorded with `git rev-parse HEAD` *before*
  dispatching the implementer — never `HEAD~1`, which silently truncates a multi-commit task to
  its last commit.
- **Explicit model selection on every dispatch.** An omitted model inherits the session's model,
  usually the most capable and most expensive one.
- **The no-subagents contract** (new in 6.3.0): an implementer never dispatches subagents, and
  never a reviewer. Review arrives from the controller, after the report. This is what makes
  `### Who dispatches gb-c-optimizer` below the only possible arrangement.
- **The "Rulings I made" list** (new in 6.3.0): before deleting the workspace, collect every
  ledger line containing `Ruling:` into the final message. Do not abbreviate it — in this project
  it is also the only record that reaches the PR reviewer.

## Project additions

### Task-review model tier

Dispatch the per-task review with **`model: sonnet`** — the mid tier, not the session default.
Its charter is checking a diff against a fixed constraints block, and a reviewer miss is caught
downstream by `make test`, `make memory-check`, the blocking smoketest and human PR review; the
mid tier is the floor for reviewers, never the cheapest tier (#528 R3, R4). The *rule* — always
specify a model — stays with the baseline bullet under *Accepted from the baseline*; this
section supplies only the value.

### Adversarial charter for the final whole-branch review

**The charter block, and its precedence over the baseline charter, are in
`.claude/skill-overlays/references/adversarial-review-charter.md`.** Append it to the final
whole-branch review dispatch.

It binds that dispatch **wherever it runs** — `### Factory mode` does not override it. Known
limit: it reaches only the review *this skill dispatches*; a `superpowers:requesting-code-review`
invoked directly is a different dispatch with no overlay of its own.

### Verify subagent claims against version control

- A subagent's report is never proof that a build, a test, or a commit happened. After every
  implementer dispatch, verify against version-control state: `git log --oneline -1`. A missing
  commit means re-dispatch the task from scratch.
- Subagents run their own build, test, and commit commands. Do not run them on a subagent's
  behalf: that pulls every command's output into the longest-lived context in the run.

### Workspace hygiene

`.superpowers/` is gitignored here. Never commit it, never `git add -A` it into a feature commit.

### Commits

Tool choice is free — repository hooks fire for every actor (#441 voided the earlier
commit-routing premise). The `pre-commit` hook runs the tool suite on every commit and
serializes them: one commit per tool call, never chained. **Never `--no-verify`.**

### C task routing (include in every implementer brief)

All three route with the same dispatch phrasing: `implement this task: <full task text from plan>`.

- **Music C task** (`src/music_data.c`, `src/music_data.h`, or any new song `.c`) → implementer
  IS `music-expert`. It owns the whole music pipeline — export, BANKREF declarations,
  `music_song_validate.py`, `music_wire_check.py`, bank gates, build, commit. Add **no** separate
  gate instructions; its own body plus the PreToolUse/PostToolUse hooks enforce them.
- **All other C tasks** (`src/*.c` / `src/*.h`) → implementer IS `gbdk-expert`. It owns the TDD
  cycle, bank gates, build and commit — but **not** `gb-c-optimizer` (next section).
- **Non-C tasks** → a general implementer, task text as-is.

The full agent roster is in the `dispatching-parallel-agents` overlay. Follow the baseline's
brief-file discipline for the task text: the brief is the single source of requirements, and a
subagent never reads the whole plan file.

### Who dispatches `gb-c-optimizer`

**The controller dispatches it.** After the implementer's commit lands, the controller dispatches
`gb-c-optimizer` on the committed diff. R5 changed **who dispatches the gate, not what it does**:
post-implementation the agent's charter has fix mode on, so it may edit in place. Those edits are
committed through the task review's fix loop **before** the task review is dispatched — else the
reviewer builds against a tree holding uncommitted work (see *Dispatch order*).

This puts the gate **after** the commit, which is why the `writing-plans` Hard Gate Sequence, the
C-File Task Template and `docs/dev-workflow.md` all say so too — a rule stated in one of four
documents is the same defect wearing a different file name. A self-applied checklist is not this
gate; run #590 proved it (`references/sdd-provenance.md`).

### Dispatch order

The plan's group table is the **authoritative source** — do not re-analyze file dependencies
at runtime.

**One rule, and it is the only one: dispatch one implementer at a time.** A `(parallel)`
group is not an instruction to run its tasks concurrently.

- `(parallel)` group → its tasks write disjoint files, so dispatch them **in any order**, one
  at a time. One task's failure does not invalidate another's work.
- `(sequential)` group → one task at a time, in the listed order.
- No group table → fall back to per-task `**Parallelizable with:**` annotations for ordering
  only. Neither present → the plan's order stands.

**6.3.0's "Batch small same-shape work" applies to non-C tasks only.** Folding several small
same-shape edits into one dispatch does not break the one-at-a-time rule and is welcome for
markdown, JSON and asset tasks. It must not be used for `src/*.c` / `src/*.h` tasks: each C task
carries its own TDD cycle, its own bank gates and its own review surface, so batching them
collapses gates the Hard Gate Sequence requires per task.

**A task's review closes before the next task's implementer is dispatched** — the review and any
fix loop it opens finish first, because the reviewer builds in this same working tree and would
otherwise verify another task's uncommitted work without saying so.

Runs #430 and #590 settled both rules; the history is in
`.claude/skill-overlays/references/sdd-provenance.md`. Read it before relaxing either.

### Batch boundaries are smoketest checkpoints

**Why:** the deliverable is a Game Boy ROM; nothing the baseline runs proves it boots. This is
the fifth stop — see `### The fifth stop` above for why it survives 6.3.0's "Rulings, not
stalls".

At each batch boundary from the plan: pause dispatching, run the checkpoint sequence (fetch+merge
`origin/master`, `make clean && make`, `make memory-check`, ask the user before launching
Emulicious from the worktree, wait for visual confirmation), then continue.

### Factory mode

Active when `NUKE_FACTORY_RUN` is set — i.e. the BUILD stage of a `/factory` run. It **overrides
`### Batch boundaries are smoketest checkpoints` and `### The fifth stop` above**, and nothing
else in this overlay. With the fifth stop replaced by a machine verdict, the baseline's four-stop
list applies unmodified.

**Stage-log wrapper (#654).** `LOG BUILD -- <argv>` below is shorthand for

```
python tools/factory_log.py --stage BUILD --issue <N> -- <argv>
```

with `<N>` the run's issue number, passed explicitly because `NUKE_FACTORY_RUN` **does not cross a
dispatch**. Add `--stream` when the output is read rather than exit-code checked. The controller
wraps the checkpoint commands below; **every implementer wraps its own `make`, `make test` and
`git commit`, so the wrapper and the issue number must appear in the brief** — a subagent that is
not told the number cannot write to the run's log.

**Headless batch-boundary checkpoint** — run this instead of the Emulicious pause:

1. `LOG BUILD -- git fetch origin`, then `LOG BUILD -- git merge origin/master`
2. `LOG BUILD -- make clean`, then `LOG BUILD -- make`
3. `LOG BUILD -- make memory-check` — **any FAIL or ERROR aborts the run immediately.** No retry.
4. `LOG BUILD --stream -- python tools/smoketest_headless.py --scenario generic-smoke --json` —
   this replaces both "ask before launching Emulicious" and "wait for visual confirmation".

**Retry budget: 2 attempts per task**, then terminal failure. Per-actor logging detail, the
`factory_event.py` bookkeeping call and the retry-budget rationale are in
`.claude/skill-overlays/references/factory-build-checkpoint.md`.

Everything else stands unchanged and is **not** waived:

- The baseline's task review — one dispatch, both verdicts — after every implementer commit.
- `### Pre-PR Gate (HARD STOP)` — all four checks.
- `### Red flags — never` — all of them, including the worktree gate.

**A ruling that makes the plan stale is written into the plan file, in the same step that
records it.** Briefs are extracted from the plan once, at dispatch time, so a ruling amending a
fact a later brief states never reaches that task unless the plan changes. Record the `decision`
event **and** edit the plan file before dispatching the next task. 6.3.0 makes this more urgent,
not less: rulings are now the normal path, so the plan goes stale faster
(`references/sdd-provenance.md`, run #590).

Outside a factory run the batch-boundary Emulicious pause fires exactly as written.

### Pre-PR Gate (HARD STOP)

Run after the smoketest is confirmed and before pushing or creating a PR. All four must pass.

| # | Check | How to verify | On failure |
|---|-------|---------------|------------|
| 1 | **Full test suite passes** | `make test` → all PASS (no early-exit failures) | Fix failing test, re-run from scratch |
| 2 | **Clean build succeeds** | `make clean && make` → zero errors | Fix compiler error before continuing |
| 3 | **No header includes silently removed** | `git diff master...HEAD -- src/*.h` — every `#include` removal must be intentional and traceable to a task requirement | Restore removed include or justify removal in a commit comment |
| 4 | **No hardcoded values introduced** | `git diff master...HEAD -- src/*.c src/*.h` — no magic numeric literals that belong in `config.h` | Replace with a named constant, commit |

Any failure → fix and re-run this gate from check 1. Only then call
`finishing-a-development-branch`.

### Example workflow

See `.claude/skill-overlays/references/example-workflow.md` for a worked end-to-end walkthrough,
including a `(parallel)` group dispatched one implementer at a time.

### Red flags — never

- Start implementation on `master`, or skip the worktree gate.
- Launch the smoketest from the main repo's `build/` (use the worktree's).
- Accept "close enough" on spec compliance, or move to the next task with an open review issue.
- Make a subagent read the plan file instead of providing the full task text.
- Ignore a subagent's questions — answer them before letting it proceed.
- Rule your way past the batch-boundary smoketest. It is the fifth stop, not a stall.

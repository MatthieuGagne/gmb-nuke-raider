---
name: subagent-driven-development
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline subagent-driven-development
skill. On conflict, this overlay wins — but an override earns that only by stating what the
baseline cannot know. Every section below carries a `**Why:**` line; a section that could not
state one was removed rather than kept (#527 R7).

**Baseline audit:** content of `superpowers@6.2.0` read and compared on 2026-08-02, not merely
the version pin (#527 R6).

## Accepted from the baseline — do NOT override

These belong to the baseline and this overlay deliberately adds nothing to them. Re-stating one
here in weaker form is how an overlay silently reverts an upstream improvement.

- **The workspace and ledger system**, and its fix loop — use them as written. Note only that
  its helper scripts are POSIX `sh` and run under Git Bash on this machine; if
  `scripts/sdd-workspace` fails on Windows, fall back to computing
  `<repo-root>/.superpowers/sdd/<plan-basename>/` by hand — same contract, same layout.
- **One task review per task**, covering spec compliance AND code quality in a single dispatch.
  Never split it into two dispatches, and never accept a report missing either verdict.
- **The diff handoff.** Hand the reviewer its diff as a file — `scripts/review-package PLAN_FILE
  BASE HEAD` prints the path — and pass that path. The diff never enters the orchestrator's
  context.
- **The review range.** BASE is the commit recorded with `git rev-parse HEAD` *before*
  dispatching the implementer — never `HEAD~1`, which silently truncates a multi-commit task to
  its last commit.
- **Explicit model selection on every dispatch.** An omitted model inherits the session's model,
  usually the most capable and most expensive one.

## Project additions

### Verify subagent claims against version control

**Why:** the baseline treats the implementer's report as the record of what happened; this
project has seen reports name commits that did not exist.

- A subagent's report is never proof that a build, a test, or a commit happened. After every
  implementer dispatch, verify against version-control state: `git log --oneline -1`. A missing
  commit means re-dispatch the task from scratch.
- Subagents run their own build, test, and commit commands. Do not run them on a subagent's
  behalf: that pulls every command's output into the longest-lived context in the run.

### Workspace hygiene

**Why:** the baseline assumes its workspace is git-ignored; whether that is true is a fact about
*this* repo's `.gitignore`.

`.superpowers/` is gitignored here. Never commit it, never `git add -A` it into a feature commit.

### Commits

**Why:** the `pre-commit` repository hook and its tool suite are this project's, and their cost
shapes how commits are batched.

Tool choice is free — repository hooks fire for every actor (#441 voided the earlier
commit-routing premise). The `pre-commit` hook runs the tool suite on every commit and
serializes them: one commit per tool call, never chained. **Never `--no-verify`.**

### C task routing (include in every implementer brief)

**Why:** which agent owns a file type is project-specific routing the baseline cannot know.

- **Music C task** (creates or modifies `src/music_data.c`, `src/music_data.h`, or any new song
  `.c` file): the implementer IS `music-expert`. Dispatch with:
  > implement this task: \<full task text from plan\>

  It owns the full music pipeline — export, BANKREF declarations, `music_song_validate.py`,
  `music_wire_check.py`, the bank gates, build and commit. Do NOT add separate gate
  instructions; its own body and the PreToolUse/PostToolUse hooks enforce them.
- **All other C tasks** (`src/*.c` / `src/*.h`): the implementer IS `gbdk-expert`. Dispatch the
  same way. It owns the full TDD cycle, the bank gates, the build, `gb-c-optimizer` review AND
  fix (applied in-place before commit), and the commit.
- **Non-C tasks:** dispatch a general implementer with the task text as-is.

Follow the baseline's brief-file discipline for the task text itself: the brief is the single
source of requirements, and a subagent never reads the whole plan file.

### Parallel dispatch

**Why:** this genuinely overrides the baseline, which forbids parallel implementers outright.
The baseline cannot know that this project's plans carry a `#### Parallel Execution Groups`
table computed at plan time from file-level dependency analysis — a `(parallel)` group is
already proven to write disjoint files.

The plan's group table is the **authoritative source** — do not re-analyze file dependencies at
runtime.

- `(parallel)` group → dispatch all its tasks as concurrent implementers in one message.
  **Max 3 concurrent implementers.**
- `(sequential)` group → one task at a time.
- No group table → fall back to per-task `**Parallelizable with:**` annotations. Neither present
  → treat all tasks as sequential, exactly as the baseline requires.

**Never** parallelize tasks that write the same file, share git state (multiple committers on
one branch), or have sequential data dependencies.

### Batch boundaries are smoketest checkpoints

**Why:** the deliverable is a Game Boy ROM; nothing the baseline runs proves it boots.

At each batch boundary from the plan: pause dispatching, run the checkpoint sequence (fetch+merge
`origin/master`, `make clean && make`, `make memory-check`, ask the user before launching
Emulicious from the worktree, wait for visual confirmation), then continue.

### Factory mode

**Why:** the factory runs unattended, so every human-confirmation step must have a headless
replacement, and the run-level retry budget comes from the factory contract
(`.claude/skills/factory/SKILL.md`), which the baseline knows nothing about. The 2-attempt
budget below counts **task attempts inside a run**; it does not shorten the baseline's
five-round fix loop inside a single task review.

Active when `NUKE_FACTORY_RUN` is set — i.e. the BUILD stage of a `/factory` run. It **overrides
`### Batch boundaries are smoketest checkpoints` above**, and nothing else in this overlay.

At each batch boundary, run the headless checkpoint instead of the Emulicious pause:

1. `git fetch origin && git merge origin/master`
2. `make clean && make`
3. `make memory-check` — **any FAIL or ERROR aborts the run immediately.** No retry.
4. `python tools/smoketest_headless.py --scenario generic-smoke --json` — this replaces "ask the
   user before launching Emulicious" and "wait for visual confirmation". Exit 0 continues.
5. Record the outcome:
   ```
   python tools/factory_event.py --issue <N> --kind scenario --field scenario=generic-smoke --field result=<pass|fail> --field blocking=true
   ```

Everything else stands unchanged and is **not** waived:

- The baseline's task review — one dispatch, both verdicts — after every implementer commit.
- `### Pre-PR Gate (HARD STOP)` — all four checks.
- `### Red flags — never` — all of them, including the worktree gate.

Retry budget in factory mode is **2 attempts per task**. Append
`--kind retry --field stage=BUILD --attempt <k>` before the second attempt. Exhausted → terminal
failure; do not proceed to the next task.

Outside a factory run the batch-boundary Emulicious pause fires exactly as written.

### Pre-PR Gate (HARD STOP)

**Why:** checks 2-4 are GB/SDCC-specific failure modes the baseline has no reason to know about.

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

**Why:** the baseline's own example is upstream-shaped; this one shows the project's agent
routing and its parallel-batch override in one place.

See `.claude/skill-overlays/references/example-workflow.md` for a worked end-to-end walkthrough,
including a parallel batch.

### Red flags — never

**Why:** each names a project-specific trap — the worktree policy, the stale-`build/` trap, and
the brief discipline this project's plans depend on.

- Start implementation on `master`, or skip the worktree gate.
- Launch the smoketest from the main repo's `build/` (use the worktree's).
- Accept "close enough" on spec compliance, or move to the next task with an open review issue.
- Make a subagent read the plan file instead of providing the full task text.
- Ignore a subagent's questions — answer them before letting it proceed.

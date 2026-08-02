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

### Task-review model tier

**Why:** the baseline mandates an explicit model on every dispatch but cannot know which tier
this project wants for its own reviewer; without a declared value the review inherits the
session model, which is the failure the accepted bullet above warns about.

Dispatch the per-task review with **`model: sonnet`** — the mid tier, not the session default.
Its charter is checking a diff against a fixed constraints block, and a reviewer miss is caught
downstream by `make test`, `make memory-check`, the blocking smoketest and human PR review; the
mid tier is the floor for reviewers, never the cheapest tier (#528 R3, R4). The *rule* — always
specify a model — stays with the baseline bullet under *Accepted from the baseline*; this
section supplies only the value.

### Adversarial charter for the final whole-branch review

**Why:** the baseline dispatches this review with `../requesting-code-review/code-reviewer.md`, a
172-line charter carrying no falsification step and asking for no evidence — because it cannot
assume the repository under review has any way to produce evidence. This one does: `make test` is
a one-command host suite (gcc + Unity, no hardware), and
`python tools/smoketest_headless.py --scenario <name|path>` runs a scripted ROM headlessly and
returns a machine-readable verdict. That apparatus is what makes "demonstrate it" a fair thing to
ask of a reviewer here, and it is precisely what an upstream charter cannot know. The second
thing it cannot know: reviewer and reviewed are the same model in this project, so the observed
failure mode is a confident finding that nobody can reproduce (epic #531 R8, #533 R7).

**Append the block below to the final whole-branch review dispatch** — the one the baseline's
`## Final Review` describes, dispatched with `../requesting-code-review/code-reviewer.md` on the
baseline's most capable model, which this section does not change.

**Precedence, stated so the reviewer is not handed two contradictory instructions.** The
five-field finding form below **replaces** the baseline charter's per-issue format (File:line /
What's wrong / Why it matters / How to fix) — its four fields all survive inside the new ones.
Everything else in the baseline charter stands unchanged: the Critical / Important / Minor
headings, the Strengths and Recommendations sections, the `Ready to merge?` verdict, and
`## Read-Only Review`.

This section binds that dispatch **wherever it runs**. A `/factory` run and a manual session
execute the same review and get the same charter; `### Factory mode` below does not override it.
Known limit: it reaches the review *this skill dispatches*. A `superpowers:requesting-code-review`
invoked directly is a different dispatch and is not covered — overlays inject on skill
invocation, and that skill has no overlay here.

> **Adversarial charter — applies to every finding you report.**
>
> A finding is a claim about this branch, not an impression of it. Report each one in this form,
> under the severity heading you judge it to belong to:
>
> - **Claim:** one sentence — the defect you assert, and why it matters.
> - **Location:** `file:line` on this branch, with the lines quoted. Quote what you actually read.
> - **Disproof attempt:** what you did to show your own claim is wrong, and what happened.
> - **Evidence:** per the bar below.
> - **Blocking:** `yes` only when the evidence bar is met; otherwise `no — unverified`.
> - **Fix:** what to change.
>
> **Try to disprove your own finding before you report it.** Re-read the cited lines in full
> context. Look for the caller, guard, default, or existing test that makes the behaviour
> correct. Ask what the author would say. **A finding you disprove is dropped, not softened** —
> re-filing it at a lower severity instead of deleting it is the exact failure this charter
> exists to prevent.
>
> **Dropping is not discarding silently.** Close your report with a `### Disproved and dropped`
> list: one line per finding you killed, naming the claim and what disproved it. A reviewer that
> drops five findings and reports one must not read the same as a reviewer that found one.
>
> **The evidence bar depends on what the finding claims.**
>
> - A **runtime-behaviour** claim — wrong output, a crash, a corrupted value, a state machine
>   that goes the wrong way — meets the bar only with a re-runnable command and its actual
>   output: a failing host test case, or a `tools/smoketest_headless.py` scenario that fails on
>   this branch. Quote the command and the failing assertion.
> - A **static** claim — a banking pragma, an allowlist rule, a missing `bank-manifest.json`
>   entry, a missing test, two documents that contradict each other — meets the bar on **citation
>   verification alone.** Open the cited location, confirm it says what your finding says it
>   says, and report it. No test and no scenario is asked of a static finding. A citation that
>   does not survive that check is a disproved finding: drop it, and list it as dropped.
>
> **Produce evidence without writing into this checkout.** The read-only rule still binds, and
> both runners below default to writing inside the tree — so redirect their output. Write your
> repro test or scenario file in a temp directory, and:
>
> - **Host test** — run the compiler **from the repository root** (every include path below is
>   root-relative) and send the binary outside the tree. These are `make test`'s own flags,
>   expanded (`Makefile:18-22, 191-198`):
>   ```
>   gcc -Itests/mocks -Itests/unity/src -Isrc -Ilib/hUGEDriver/include -Wall -Wextra \
>       tests/unity/src/unity.c $(ls src/*.c | grep -v 'src/main.c$') tests/mocks/*.c \
>       <tmp>/your_test.c -o <tmp>/your_test.exe
>   ```
>   Every test links the whole library, so do not copy a module out and seed it — you get
>   duplicate symbols. Write a new test against the code as it stands.
> - **Scenario** — `python tools/smoketest_headless.py --scenario <tmp>/your-scenario.json
>   --out-dir <tmp>/smoketest --json`. `--out-dir` is required here: its default writes
>   screenshots, `trace.jsonl` and `results.json` into `build/smoketest` inside the checkout.
>
> **`Blocking` is a separate marker from severity, and never a cap on it.** Judge Critical /
> Important / Minor on the merits exactly as the severity section defines them, and never lower a
> severity because evidence was hard to get. `Blocking: no — unverified` says "not yet shown",
> never "not important".
>
> **An unverified finding is still reported, in full.** Say what you could not demonstrate and
> name, in one line, the test or scenario that would settle it. Staying quiet about a finding you
> could not demonstrate is worse than reporting it honestly labelled.
>
> **Nothing you report blocks anything.** No finding aborts the run, and none makes the pull
> request unmergeable — you report, and the human decides at the pull request. This is about the
> run and the merge, not about the controller: the baseline's fix wave, its scoped re-review and
> its adjudication of residual findings are unchanged.

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

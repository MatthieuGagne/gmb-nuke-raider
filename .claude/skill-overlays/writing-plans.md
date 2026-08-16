---
name: writing-plans
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline writing-plans skill. On conflict,
this overlay wins — but an override earns that only by stating what the baseline cannot know
(#527 R7).

**Baseline audit:** content of `superpowers@6.2.0` read and compared on 2026-08-02 (#527 R6).

## Overrides (do NOT follow the baseline here)

- **Save plans to `docs/plans/YYYY-MM-DD-issue<N>-<slug>.md`** — NOT `docs/superpowers/plans/`
  or any other baseline location, and NOT the issue-less `YYYY-MM-DD-<feature-name>.md` form.
  `<N>` is the GitHub issue number the plan implements; `<slug>` is lowercase, hyphen-separated
  (e.g. `docs/plans/2026-07-26-issue435-traceability.md`).
  **Why:** the baseline's own line says user preferences override the default location, and
  `tools/trace.py --check` parses this exact filename to link a plan to its spec issue.

## Project additions

### Before you begin

**Why:** the baseline assumes a worktree already exists and names no sync step; a stale branch
is this repo's most common plan-time defect, and `grill-with-docs` is a local skill.

- **First action, before anything else:** pull and merge latest master into the current worktree branch:
  ```bash
  git fetch origin && git merge origin/master
  ```
  Resolve any conflicts before proceeding. Never use `git merge master` alone — the local master ref may be stale.
- **Context:** this runs in a dedicated worktree. All file operations happen inside it.
- **Last step before writing:** invoke the `grill-with-docs` skill — it surfaces requirements, acceptance criteria, scope, and GB hardware constraints. Only once the grilling is satisfied, proceed to writing the plan.

### Hard Gate Sequence

**Why:** the baseline's task template is language-agnostic and knows nothing about ROM banking,
SDCC, or this project's agents. This table is **plan content** — what a plan document must
contain so an implementer sees the sequence — not a runtime invocation list, so #527 R4's
removal of manual gate invocations does not reach it. Steps 2 and 7 name gates that also fire
automatically as hooks; the plan records them so the implementer knows what must have reported.

Every task that touches `src/*.c` or `src/*.h` MUST follow this exact sequence — no exceptions:

| Step | Action |
|------|--------|
| 1 | Write failing test (`make test` → FAIL) |
| 2 | Invoke `bank-pre-write` skill (HARD GATE) |
| 3 | Invoke `gbdk-expert` agent (HARD GATE) |
| 4 | Write minimal implementation |
| 5 | Run tests (`make test` → PASS) |
| 6 | Build ROM (`make` → PASS) |
| 7 | Invoke `bank-post-build` skill (HARD GATE) |
| 8 | Refactor checkpoint ("breaks when N > 1?") |
| 9 | Commit |
| 10 | **Controller, not the implementer** — dispatch the `gb-c-optimizer` agent on the committed diff (HARD GATE). Whatever it reports or edits goes through the task review's fix loop, which commits it before the review is dispatched. |

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

Step 10 is the one step in this table an implementer does not perform. It is listed here
because the plan must show the whole sequence, and because an implementer that sees it
listed knows the gate exists and knows it is not being skipped (#633 R5).

**Constant-removal audit:** if any task removes or renames a shared constant (e.g. `PLAYER_ACCEL`, `PLAYER_MAX_SPEED`), add a grep step at the top of that task before listing affected files:
```bash
grep -r CONSTANT_NAME tests/
```
Include ALL matching test files in the task's file list — not just the ones you remembered. Missing a file means surprise failures during parallel execution, after other tasks' commits have already landed.

### Smoketestable batches

**Why:** the baseline right-sizes tasks around a reviewer's gate; it has no concept of a
checkpoint where a ROM must visibly run. The `#### Parallel Execution Groups` table is also what
licenses the `subagent-driven-development` overlay's free task ordering — without it, the plan's
written order stands. It never licenses concurrency: that overlay dispatches one implementer at a
time whatever the table says.

**Tasks MUST be grouped into batches of 2–4.** Each batch ends with a **Smoketest Checkpoint** — a point where the ROM runs in Emulicious and the user confirms it looks correct. A good batch boundary = any point where the game should visually work end-to-end (even partially). If a batch cannot be independently smoke-tested, the plan must explain why.

**Dependency analysis** (required before writing each Smoketest Checkpoint block):
1. List all output files for each task in the batch.
2. Mark as **sequential** any two tasks that write the same file, or where Task B compiles against a symbol Task A defines.
3. Group remaining tasks into independent layers — tasks with the same `Depends on` set are parallelizable with each other.
4. Fill in `**Depends on:**` and `**Parallelizable with:**` on every task.
5. Insert a `#### Parallel Execution Groups` table immediately before the Smoketest Checkpoint block — this is the executor's source of truth for parallel dispatch.

Checkpoint block template:

````markdown
#### Parallel Execution Groups — Smoketest Checkpoint N

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files, no shared state |
| B (sequential) | Task 3 | Depends on Group A — must run after both complete |

### Smoketest Checkpoint N — [what to verify visually]

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS. Fix any FAIL or ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory — use PowerShell tool, not Bash). Ask the user for confirmation first.**
```powershell
Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
```

**Step 5: Confirm with user**
Tell the user what to verify visually. Wait for confirmation before proceeding to the next batch.
````

### Plan document header

**Why:** only the `**Issue:** #N` line and the *Open questions* block are this project's — the
rest of the header, including `## Global Constraints`, is the baseline's and is reproduced here
so the two cannot drift apart. `tools/trace.py` parses the issue line; nothing upstream knows
this project files its specs as GitHub issues.

Every plan MUST start with this header:

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement this plan task-by-task — the choice is the user's,
> made at the Handoff below.

**Issue:** #N

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Open questions (must resolve before starting)

- [Question 1 — or delete this line if none]

## Global Constraints

[The spec's project-wide requirements — exact values copied verbatim. Every task's requirements
implicitly include this section, and it is the attention lens the task reviewer is handed.]
```

`## Global Constraints` is the baseline's block and is **mandatory**: the
`subagent-driven-development` baseline copies it verbatim into every task reviewer's prompt. A
plan without it hands each reviewer an empty constraints block.

The `**Issue:** #N` line is mandatory and must sit on its own line, exactly in this form —
`tools/trace.py` parses it to link the plan back to its spec issue, and the issue number must
match the one in the filename. If a plan has no originating issue, create one first (`/prd`);
a plan with no issue cannot be traced.

### Task templates

**Why:** the baseline's task template has no GB hard-gate steps and no `**Depends on:**` /
`**Parallelizable with:**` annotations, both of which this project's execution path requires.

See `.claude/skill-overlays/references/task-templates.md` for the two task templates: the 11-step C-File Task Template (for `src/*.c` / `src/*.h`, all HARD GATE steps) and the Non-C Task Template (markdown/Python/JSON/assets).

### Plan Self-Review Checklist (HARD STOP before presenting to user)

**Why:** this **extends** the baseline's three-point self-review (spec coverage, placeholder
scan, type consistency) rather than replacing it — checks #1, #3, #4 and #6 are project-specific
(magic numbers vs `config.h`, the parallel annotations, the group tables, `trace.py`). Run the
baseline's three as well; they are not repeated here.

Run this before offering the execution handoff. Fix any failures first.

| # | Check | Pass criteria |
|---|-------|---------------|
| 1 | **No hardcoded values** | Every numeric constant, tile index, capacity, or coordinate is sourced from `config.h`, a Tiled export, or an explicit named constant — never a magic number |
| 2 | **All tasks have explicit test criteria** | Every task states exactly how to verify it passes (command + expected output, or visual check description) |
| 3 | **Parallel annotations justified** | Every task has `**Depends on:**` and `**Parallelizable with:**` filled in. Any `**Parallelizable with:** none` MUST be followed by a one-sentence justification (e.g. "writes same file as Task M"). An unjustified `none` is a plan defect. |
| 4 | **Parallel Execution Groups tables present** | Every batch that precedes a Smoketest Checkpoint has a `#### Parallel Execution Groups` table |
| 5 | **No implementation details leaked from brainstorming** | Plan contains file paths and task steps, not design narrative or requirement rationale (those belong in the GitHub issue) |
| 6 | **Issue header + filename** | The plan has an `**Issue:** #N` line matching the `issue<N>` in its filename. Verify with `python tools/trace.py --check --plans-only` — expect `PASS` and no `ERROR` lines mentioning this plan |
| 7 | **Landed-test impact named** | Every task that changes behaviour an already-landed test asserts names that test by path and says how the task handles it — update the test, or state why it still passes. A task that breaks a landed test without saying so is a **plan defect**, not a build-stage surprise. |

**Failure handling:**
- Checks #1, #2, #4, #5, #7 fail → fix the plan now and re-run the checklist from the top.
- Check #6 fails → fix the header and/or rename the file now, then re-run `python tools/trace.py --check --plans-only`.
- Check #3 fails (unjustified `none`) → do NOT silently fix. Present the plan WITH the Incomplete Warning block below, immediately after the plan header. The user decides whether to proceed or fix first.

**Why #7 exists.** The `pre-commit` repository hook runs the whole tool suite on every
commit and `--no-verify` is forbidden, so every already-landed test is a hard gate on every
task in the plan. Three of run #590's four escalations were the same shape:
`tests/test_rom_parity.py` refused a commit at Tasks 2, 3 and 4, and each time the plan had
not said the task would break it. A plan that leaves this to BUILD converts a five-minute
plan-time edit into a mid-run ruling.

```markdown
> ⚠️ **Plan incomplete — unjustified parallelism annotations**
>
> The following tasks have `**Parallelizable with:** none` with no justification sentence:
> - Task N: [task name]
>
> For each: either (a) identify tasks it can parallelize with and update the annotation,
> or (b) add a one-sentence justification explaining why it cannot parallelize
> (e.g., "writes same file as Task M", "requires Task M's output symbol").
>
> Proceed with the plan as-is, or fix these annotations first?
```

### Handoff

**Why:** the baseline recommends subagent-driven execution and presents the choice immediately;
here the choice is the user's with no recommendation, and it is gated on an explicit affirmative.
The baseline cannot know that this project's plans are handed off across sessions and worktrees.

After saving the plan, present the full plan to the user.

<HARD-GATE>
Do NOT offer execution options until the user gives an explicit affirmative approval (e.g. "yes", "looks good", "let's go", "proceed", or equivalent). Do not interpret silence or continued conversation as approval.
</HARD-GATE>

Only after an explicit affirmative, offer the execution choice:

**"Plan complete and saved to `docs/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (this session)** — fresh subagent per task, review between tasks, fast iteration. Stays in this session.

**2. Parallel Session (separate)** — open a new session with executing-plans, batch execution with checkpoints.

If Parallel Session is chosen, guide the user to open a new session in the worktree; that session uses `superpowers:executing-plans`.

### Factory mode

**Why:** the factory runs unattended, so every step that waits on a human must have a
replacement or be waived; the baseline has no notion of an unattended run. Note the one place
this deliberately goes *beyond* the baseline: the baseline's self-review is explicitly "a
checklist you run yourself — not a subagent dispatch", while factory mode adds an adversarial
review subagent. That is bought with the absence of a human reviewer, not with a claim that the
baseline is wrong.

Active when `NUKE_FACTORY_RUN` is set — i.e. the PLAN stage of a `/factory` run. It **overrides
the `### Handoff` subsection above**, and nothing else in this overlay.

- The `<HARD-GATE>` blocking on explicit user approval **does not apply.** There is no user to
  approve. Do not present the plan for approval and do not offer execution options.
- The grill step in *Before you begin* is replaced by the **adversarial plan self-review**
  subagent described in `.claude/skills/factory/references/stages.md`. Its charter includes
  verifying the plan's *verification commands*, not just its code (#460).
- Every unresolved judgment call from that self-review is recorded as a decision:
  ```
  python tools/factory_event.py --issue <N> --kind decision --field "text=<what and why>"
  ```
- A ruling recorded after the plan is written can make the plan itself stale. The plan file
  is then amended in the same step that records the ruling — the operative rule lives in the
  `subagent-driven-development` overlay's `### Factory mode`, because that is the overlay
  loaded while tasks are being dispatched. What matters here is that **the plan file is a
  live document during BUILD, not a frozen one**: briefs are extracted from it, once, at
  dispatch time.
- The Plan Self-Review Checklist still runs in full. Check #3's Incomplete Warning block is
  **not** presented to a user — an unjustified `**Parallelizable with:** none` is fixed in place
  and the fix logged as a decision.
- Everything else — the filename convention, the `**Issue:** #N` header, the batch structure,
  the Smoketest Checkpoint blocks — is unchanged. The checkpoints themselves are executed
  headlessly; see the `subagent-driven-development` overlay's Factory mode.

Outside a factory run every checkpoint above fires exactly as written.

### Verifying verification steps

Every verification command in a plan must be paired with evidence it *can* fail, not only that it passes. A check that always passes on the correct file is not a check — it is a statement of the file's current state, and it will never catch a regression.

Three failure shapes, observed in [#441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/441):

1. **Self-defeating assert.** The check's own assertion string appears in the file being checked, so the assert passes on the correct file and fails on nothing. Example: `assert 'paths:' not in text` where the file's own comment explaining *why* there is no `paths:` filter contains that string. Fix: use a YAML-key regex (`^\s*paths:`) that cannot appear in the comment.

2. **Platform-wrong assertion.** The assertion hardcodes a platform-specific value (file extension, path separator, casing) that differs on the other platform the CI matrix covers. Example: asserting `find_make(...) == 'make.exe'` on a CI leg that runs `windows-latest` where `PATHEXT` returns `make.EXE`. Fix: normalize both sides with `os.path.normcase` before comparing.

3. **Environment-dependent test.** The check passes when run directly but fails under the hook or agent it was written for, because the hook/agent exports environment variables that override `cwd` or other assumptions. Example: `git config --local` reads the wrong repo under `GIT_DIR` exported by git into every hook's environment. Fix: scrub `GIT_DIR` (and friends) before running any git command, or use `install_hooks.clean_env()`.

For each verification command in a plan, the plan must name either (a) the input flip that makes the check fail, or (b) a probe file that triggers the failure.

### Remember

**Why:** the first three lines restate baseline rules on purpose — they are the ones this
project's plans most often drop. The rest (skill/agent names, the C template, the Lessons
Learned gate) are project-specific.

- Exact file paths always; complete code in the plan (not "add validation"); exact commands with expected output.
- Reference skills and agents by name (e.g. `bank-pre-write` skill, `gbdk-expert` agent).
- DRY, YAGNI, TDD, frequent commits.
- C files ALWAYS get the 11-step template with all HARD GATE steps.
- **Lessons Learned gate:** `executing-plans` runs a final Lessons Learned step after the smoketest passes — no action is needed in the plan itself.

---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Can be used with or without a prior brainstorming session.
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

## Before You Begin

**First action before anything else:** Pull and merge latest master into the current worktree branch:
```bash
git fetch origin && git merge origin/master
```
Resolve any conflicts before proceeding.

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

**Last step before writing:** Always invoke the `grill-me` skill — it will surface requirements, acceptance criteria, scope, and GB hardware constraints. Once grill-me is satisfied, proceed to writing the plan.

## Hard Gate Sequence

Every task that touches `src/*.c` or `src/*.h` MUST follow this exact sequence — no exceptions:

| Step | Action |
|------|--------|
| 1 | Write failing test (`make test` → FAIL) |
| 2 | Invoke `bank-pre-write` skill (HARD GATE) |
| 3 | Invoke `gbdk-expert` agent (HARD GATE) |
| 4 | Write minimal implementation |
| 5 | Run tests (`make test` → PASS) |
| 6 | Build ROM (`GBDK_HOME=/home/mathdaman/gbdk make` → PASS) |
| 7 | Invoke `bank-post-build` skill (HARD GATE) |
| 8 | Refactor checkpoint ("breaks when N > 1?") |
| 9 | Invoke `gb-c-optimizer` agent (HARD GATE) |
| 10 | Commit |

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Smoketestable Batches

**Tasks MUST be grouped into batches of 2-4.** Each batch ends with a **Smoketest Checkpoint** — a point where the ROM runs in Emulicious and the user confirms it looks correct.

A good batch boundary = any point where the game should visually work end-to-end (even partially). If a batch cannot be independently smoke-tested, the plan must explain why.

### Dependency Analysis (required before writing each smoketest checkpoint block)

After drafting all tasks in a batch, before inserting the Smoketest Checkpoint block:

1. List all output files for each task in the batch
2. Mark as **sequential** any two tasks that write the same file, or where Task B compiles against a symbol Task A defines
3. Group remaining tasks into independent layers — tasks with the same `Depends on` set are parallelizable with each other
4. Go back and fill in `**Depends on:**` and `**Parallelizable with:**` on each task
5. Insert a `#### Parallel Execution Groups` table immediately before the Smoketest Checkpoint block (use the template below)

Use this template for the parallel group table that precedes every checkpoint:

```markdown
#### Parallel Execution Groups — Smoketest Checkpoint N

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files, no shared state |
| B (sequential) | Task 3 | Depends on Group A — must run after both complete |
```

````markdown
### Smoketest Checkpoint N — [what to verify visually]

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS. Fix any FAIL or ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Tell the user what to verify visually. Wait for confirmation before proceeding to the next batch.
````

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Open questions (must resolve before starting)

- [Question 1 — or delete this line if none]

---
```

## C-File Task Template

Use this template for any task that creates or modifies `src/*.c` or `src/*.h`:

````markdown
### Task N: [Component Name]

**Files:**
- Create: `src/foo.c`, `src/foo.h`
- Test: `tests/test_foo.c`

**Depends on:** none   ← or "Task N, Task M" — tasks whose output this task reads or requires (use task numbers matching plan headings)
**Parallelizable with:** none   ← or "Task N, Task M" — tasks at the same dependency layer (use task numbers matching plan headings)

> **Entity system?** Use SoA (Structure-of-Arrays). Capacity constants in `src/config.h`.
> Never AoS — SDCC cannot eliminate stride multiplication on SM83.

**Step 1: Write the failing test**

```c
void test_foo_init(void) {
    foo_init();
    TEST_ASSERT_EQUAL_UINT8(0, foo_get_count());
}
```

**Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL (undefined symbol or missing include)

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Verify `bank-manifest.json` has an entry for `src/foo.c`.
Do NOT write the C file until this gate passes.

**Step 4: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm the planned API, data types, and any GBDK calls are
correct for this module before writing.

**Step 5: Write minimal implementation**

```c
/* src/foo.c */
#pragma bank 0
#include "foo.h"
/* ... */
```

**Step 6: Run tests to verify they pass**

Run: `make test`
Expected: PASS

**Step 7: HARD GATE — build**

Invoke the `build` skill (or run: `GBDK_HOME=/home/mathdaman/gbdk make`).
Expected: ROM produced at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify bank placements and ROM budgets are within limits.

**Step 9: Refactor checkpoint**

Ask: "Does this implementation generalize, or did I hard-code something that breaks when N > 1?"
- If generalized: proceed.
- If hard-coded and not fixing now: open a follow-up GitHub issue immediately before closing this task.

**Step 10: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on the new/modified C files.
Fix any AoS, performance, or ROM size issues before committing.

**Step 11: Commit**

```bash
git add src/foo.c src/foo.h tests/test_foo.c bank-manifest.json
git commit -m "feat: add foo module"
```
````

## Non-C Task Template

Use this template for tasks that do NOT involve `src/*.c` or `src/*.h`:

````markdown
### Task N: [Component Name]

**Files:**
- Create/Modify: `path/to/file.md`

**Depends on:** none   ← or "Task N, Task M" — tasks whose output this task reads or requires (use task numbers matching plan headings)
**Parallelizable with:** none   ← or "Task N, Task M" — tasks at the same dependency layer (use task numbers matching plan headings)

**Step 1: Write the content**

[exact content or diff]

**Step 2: Verify**

[manual check or command]

**Step 3: Commit**

```bash
git add path/to/file.md
git commit -m "feat: add/update X"
```
````

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- Reference skills by name (e.g., `bank-pre-write` skill, `gbdk-expert` agent)
- DRY, YAGNI, TDD, frequent commits
- C files ALWAYS get the 11-step template with all HARD GATE steps
- Group tasks into batches of 2-4; each batch MUST end with a Smoketest Checkpoint
- Annotate every task with `**Depends on:**` and `**Parallelizable with:**` — executor reads these; vague hints are not enough
- Insert a `#### Parallel Execution Groups` table before every Smoketest Checkpoint block — this is the executor's source of truth for parallel dispatch

## Lessons Learned Gate

**Note for plan authors:** The `executing-plans` skill includes a final "Lessons Learned" step (Step 7) that runs after the smoketest passes. The implementer will ask the user whether any lessons should be captured as documentation updates (CLAUDE.md, memory, skills, or agents). No action is needed in the plan itself — this gate runs automatically at execution time.

## Plan Self-Review Checklist (HARD STOP before presenting to user)

Before offering the execution handoff, run this checklist. Fix any failures before proceeding.

| # | Check | Pass criteria |
|---|-------|---------------|
| 1 | **No hardcoded values** | Every numeric constant, tile index, capacity, or coordinate is sourced from `config.h`, a Tiled export, or an explicit named constant — never a magic number |
| 2 | **All tasks have explicit test criteria** | Every task states exactly how to verify it passes (command + expected output, or visual check description) |
| 3 | **Parallel annotations justified** | Every task has `**Depends on:**` and `**Parallelizable with:**` filled in. Any `**Parallelizable with:** none` MUST be followed by a one-sentence justification (e.g., "writes same file as Task M", "requires Task M's output symbol"). An unjustified `none` is a plan defect. |
| 4 | **Parallel Execution Groups tables present** | Every batch that precedes a Smoketest Checkpoint has a `#### Parallel Execution Groups` table |
| 5 | **No implementation details leaked from brainstorming** | Plan contains file paths and task steps, not design narrative or requirement rationale (those belong in the GitHub issue) |

**Failure handling:**
- Checks #1, #2, #4, #5 fail → fix the plan now and re-run the checklist from the top.
- Check #3 fails (unjustified `none`) → do NOT silently fix. Present the plan WITH the Incomplete Warning block below, immediately after the plan header. The user decides whether to proceed or fix first.

### Incomplete Warning Block (use when check #3 fails)

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

## Execution Handoff

After saving the plan, **present the full plan to the user**.

<HARD-GATE>
Do NOT offer execution options until the user gives an explicit affirmative approval (e.g., "yes", "looks good", "let's go", "proceed", or equivalent). Do not interpret silence or continued conversation as approval.
</HARD-GATE>

Only after explicit affirmative, offer execution choice:

**"Plan complete and saved to `docs/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Stay in this session
- Fresh subagent per task + code review

**If Parallel Session chosen:**
- Guide them to open new session in worktree
- **REQUIRED SUB-SKILL:** New session uses superpowers:executing-plans

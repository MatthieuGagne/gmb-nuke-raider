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
| 6 | Build ROM (`make` → PASS) |
| 7 | Invoke `bank-post-build` skill (HARD GATE) |
| 8 | Refactor checkpoint ("breaks when N > 1?") |
| 9 | Invoke `gb-c-optimizer` agent (HARD GATE — validate only, report issues, do not apply fixes) |
| 10 | Commit |

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

**Constant-removal audit:** If any task removes or renames a shared constant (e.g. `PLAYER_ACCEL`, `PLAYER_MAX_SPEED`), add a grep step at the top of that task before listing affected files:
```bash
grep -r CONSTANT_NAME tests/
```
Include ALL matching test files in the task's file list — not just the ones the plan author remembered. Missing a file means surprise failures during parallel execution (other tasks' commits have already landed).

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
make clean && make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS. Fix any FAIL or ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory — use PowerShell tool, not Bash)**
```powershell
Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
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

## Task Templates

See `references/task-templates.md` for the two task templates: the 11-step C-File Task Template (for `src/*.c`/`src/*.h`, all HARD GATE steps) and the Non-C Task Template (markdown/Python/JSON/assets).

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

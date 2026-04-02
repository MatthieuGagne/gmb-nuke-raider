---
name: executing-plans
description: Use when you have a written implementation plan to execute in a separate session with review checkpoints
---

# Executing Plans

## Overview

Load plan, review critically, execute tasks in batches, report for review between batches.

**Core principle:** Batch execution with checkpoints for architect review.

**Announce at start:** "I'm using the executing-plans skill to implement this plan."

## The Process

### Step 1: HARD GATE — Enter Worktree

Before reading the plan or touching any file, confirm you are in a git worktree (NOT the main repo):

```bash
git worktree list
git branch --show-current
pwd
```

Expected: current directory is under `.claude/worktrees/` and branch is a feature branch (not `master`).

If not in a worktree: use the `using-git-worktrees` skill or `EnterWorktree` tool before proceeding.

### Step 2: Sync with master

After confirming you are in a worktree, pull and merge latest master:
```bash
git fetch origin && git merge origin/master
```
NEVER use `git merge master` alone — the local master ref may be stale. Resolve any conflicts before proceeding.

### Step 3: Load and Review Plan

1. Read plan file
2. Review critically — identify any questions or concerns about the plan
3. If concerns: raise them with your human partner before starting
4. If no concerns: create TodoWrite tasks and proceed

### Step 4: Execute Batch

**Before dispatching any task, read the parallel dispatch source of truth (priority order):**

1. **Primary:** Find the `#### Parallel Execution Groups` table for the current batch in the plan. Dispatch all tasks in a `(parallel)` group as concurrent implementer Agent calls in a **single message** (max 3).
2. **Fallback:** If no group table exists, scan each task's `**Parallelizable with:**` annotation. Batch tasks that name each other into a single message.
3. **Last resort:** If neither exists, run tasks sequentially.

**Batch atomicity rule (HARD):** If ANY implementer in a parallel group fails, halt the entire batch immediately. Passing implementers MUST discard their in-progress work — do NOT stage or commit partial results. Fix the failure, then re-dispatch the entire group from scratch.

For each task (whether parallel or sequential):
1. Mark as in_progress
2. Determine task type:
   - **C task** (creates or modifies `src/*.c` or `src/*.h`): dispatch `gbdk-expert` agent (Agent tool) with prompt `"implement this task: <full task text from plan>"`. `gbdk-expert` owns the full TDD cycle, bank gates, build, `gb-c-optimizer` review AND fix (fixes applied in-place before commit), and commit for this task.
   - **Non-C task** (docs, Python, JSON, assets): follow each step exactly as written in the plan.
3. After any successful build (C tasks only):
   - Invoke `bank-post-build` **skill** (HARD GATE — use the `Skill` tool)
   - Run `make memory-check` via the `gb-memory-validator` **skill** (HARD GATE); if any budget is FAIL or ERROR, stop and fix before continuing
4. Run verifications as specified
5. Mark as completed

**Parallel reviewer rule (within each batch):**
After each task's implementer work is committed, dispatch spec and quality reviewers as two concurrent Agent calls in a single message (see `dispatching-parallel-agents` skill). Both must pass before marking the task complete.

### Step 5: Report

When batch complete:
- Show what was implemented
- Show verification output
- Say: "Ready for feedback."

### Step 6: Continue

Based on feedback:
- Apply changes if needed
- Execute next batch
- Repeat until complete

### Step 7: Complete Development

After all tasks complete and verified, run the smoketest sequence:

Follow the **Smoketest gate** sequence from CLAUDE.md (fetch+merge origin/master, clean build, memory-check hook, ask for confirmation before launching, wait for confirmation).

Only after the user confirms:
   - Announce: "I'm using the finishing-a-development-branch skill to complete this work."
   - **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch
   - Follow that skill to verify tests, present options, execute choice.

### Step 8: Lessons Learned — HARD GATE (do not skip)

After the smoketest passes, **before pushing or creating the PR**, explicitly ask:

> "Any important lessons learned from this implementation? (e.g. surprises, sharp edges, things that should update CLAUDE.md / skills / agents / memory)"

**This step is mandatory — do not skip it, even if the implementation felt smooth.**

- If **yes** or the user provides lessons: invoke the `/prd` skill to create a GitHub issue capturing the needed documentation updates. Save anything session-relevant to memory as well.
- If the user explicitly says **no lessons**: note that in your response and proceed to push/PR.

Do not push or open the PR until you have received an explicit answer to this question.

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker mid-batch (missing dependency, test fails, instruction unclear)
- Plan has critical gaps preventing starting
- You don't understand an instruction
- Verification fails repeatedly
- Any HARD GATE fails (bank-pre-write, gbdk-expert, bank-post-build)

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Review (Step 3) when:**
- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking

**Don't force through blockers** — stop and ask.

## Remember
- Enter worktree FIRST (Step 1) before any other action
- Review plan critically before starting
- Follow plan steps exactly
- Don't skip verifications
- Reference skills when plan says to
- Between batches: just report and wait
- Stop when blocked, don't guess
- Never start implementation on main/master branch
- C tasks: dispatch gbdk-expert with "implement this task: …" — it owns TDD, bank gates, build, commit
- bank-post-build gate after every build
- Smoketest uses Emulicious, not mgba-qt
- Merge command is `git fetch origin && git merge origin/master`
- Parallel implementers: read `#### Parallel Execution Groups` table first; dispatch parallel groups as concurrent Agent calls (max 3); batch atomicity — if any fails, ALL discard and retry from scratch
- Parallel reviewers: fire spec + quality in one message after each implementer commit (see dispatching-parallel-agents)
- Explore agent: use for any codebase exploration > 2 files (see dispatching-parallel-agents)

## Integration

**Required workflow skills:**
- **superpowers:using-git-worktrees** — REQUIRED: set up isolated workspace before starting
- **superpowers:writing-plans** — creates the plan this skill executes
- **superpowers:finishing-a-development-branch** — complete development after all tasks
- **dispatching-parallel-agents** — consult before any agent dispatch decision (offload table, parallelize rules)

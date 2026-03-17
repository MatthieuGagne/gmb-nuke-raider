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

### Step 2: Load and Review Plan

1. Read plan file
2. Review critically — identify any questions or concerns about the plan
3. If concerns: raise them with your human partner before starting
4. If no concerns: create TodoWrite tasks and proceed

### Step 3: Execute Batch

**Default: first 3 tasks (or all remaining if fewer than 3)**

For each task:
1. Mark as in_progress
2. Follow each step exactly (plan has bite-sized steps)
3. Before writing any `src/*.c` or `src/*.h` file:
   - Invoke `bank-pre-write` **skill** (HARD GATE — use the `Skill` tool)
   - Invoke `gbdk-expert` **agent** (HARD GATE — use the `Agent` tool)
4. After any successful build:
   - Invoke `bank-post-build` **skill** (HARD GATE — use the `Skill` tool)
   - Run `gb-memory-validator` **agent** (HARD GATE — use the `Agent` tool); if any budget is FAIL, stop and fix before continuing
5. Run verifications as specified
6. Mark as completed

### Step 4: Report

When batch complete:
- Show what was implemented
- Show verification output
- Say: "Ready for feedback."

### Step 5: Continue

Based on feedback:
- Apply changes if needed
- Execute next batch
- Repeat until complete

### Step 6: Complete Development

After all tasks complete and verified, run the smoketest sequence:

1. Fetch and merge latest master (from the worktree directory):
   ```bash
   git fetch origin && git merge origin/master
   ```
   NEVER use `git merge master` alone — the local master ref may be stale.

2. Ensure a ROM exists — if `build/nuke-raider.gb` is missing, do a clean build first:
   ```bash
   ls build/nuke-raider.gb 2>/dev/null || (make clean && GBDK_HOME=/home/mathdaman/gbdk make)
   GBDK_HOME=/home/mathdaman/gbdk make
   ```

3. Run `gb-memory-validator` agent — if any budget is FAIL, stop and fix before continuing.

4. Launch the ROM immediately in the background (run from the worktree directory):
   ```bash
   java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
   ```
   Tell the user it's running and ask them to confirm it looks correct.

5. Only after the user confirms:
   - Announce: "I'm using the finishing-a-development-branch skill to complete this work."
   - **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch
   - Follow that skill to verify tests, present options, execute choice.

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker mid-batch (missing dependency, test fails, instruction unclear)
- Plan has critical gaps preventing starting
- You don't understand an instruction
- Verification fails repeatedly
- Any HARD GATE fails (bank-pre-write, gbdk-expert, bank-post-build)

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Review (Step 2) when:**
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
- bank-pre-write + gbdk-expert gates before every C write
- bank-post-build gate after every build
- Smoketest uses Emulicious, not mgba-qt
- Merge command is `git fetch origin && git merge origin/master`

## Integration

**Required workflow skills:**
- **superpowers:using-git-worktrees** — REQUIRED: set up isolated workspace before starting
- **superpowers:writing-plans** — creates the plan this skill executes
- **superpowers:finishing-a-development-branch** — complete development after all tasks

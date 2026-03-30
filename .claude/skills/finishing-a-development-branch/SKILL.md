---
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify tests → Merge master → Bank gates → Smoketest → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

## The Process

### Step 1: Concurrent batch — fetch/merge + bank manifest review

Run these two operations as a **concurrent batch** (dispatch in a single message / start both in parallel):

**1a. Fetch and merge latest master** (mandatory — always run, even for doc-only branches):
```bash
git fetch origin && git merge origin/master
```
If merge conflicts occur: resolve them now, commit the merge, then continue. Do NOT push until the merge is clean.

**1b. Bank manifest review** (parallel with 1a — read-only, no merge dependency):

Check `bank-manifest.json` against `src/*.c` files in the branch: every `src/*.c` file must have an entry. Flag any missing entries as a blocker before proceeding.

Wait for **both** 1a and 1b to complete before moving to Step 2.

### Step 2: Verify Tests (sequential — must run against merged state)

**Run after Step 1 completes** (tests must execute against the merged codebase):

```bash
make test
```

**If tests fail:**
```
Tests failing (<N> failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

Stop. Don't proceed to Step 3.

**If tests pass:** Continue to Step 3.

### Step 3: HARD GATE — bank-post-build

**Run before the smoketest:**

Invoke the `bank-post-build` skill. If it reports any FAIL, stop and fix before continuing.

Only continue to Step 4 when it passes.

### Step 4: Smoketest in Emulicious

**Skip this step for doc-only branches** (no `src/*.c`, `src/*.h`, or asset changes) — go directly to Step 5.

1. Always do a clean build (master is already merged from Step 1):
   ```bash
   make clean && GBDK_HOME=/home/mathdaman/gbdk make
   ```

3. Run `make memory-check` and report the output. If any budget is FAIL or ERROR, stop and fix before continuing.

4. Launch the ROM immediately in the background (from the worktree directory so `build/` resolves
   to the worktree's build output — NEVER from the main repo's `build/`):
   ```bash
   # Run from the worktree directory (cd there first if needed)
   java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
   ```

5. Tell the user it's running and ask them to confirm it looks correct before proceeding.

**Stop. Wait for explicit confirmation.**

- If issues found: work with user to fix before continuing
- If confirmed: Continue to Step 4.5

### Step 4.5: Update Docs Before PR

Before presenting options, check what changed in this branch:

**If any user-visible behavior changed** (new feature, changed controls, new screen, new module):
→ Update the **Game Modules table** in `README.md` to reflect additions or changes.

**If any `.claude/skills/`, `.claude/agents/`, or `CLAUDE.md` file changed**:
→ Update `docs/dev-workflow.md` to reflect the change. The two documents are co-authoritative —
  they must agree.

If neither applies, skip this step and continue to Step 5.

### Step 5: Present Options

Present exactly these 3 options:

```
Implementation complete. What would you like to do?

1. Push and create a Pull Request  ← default
2. Keep the branch as-is (I'll handle it later)
3. Discard this work

Which option?
```

**NEVER offer "merge to main locally"** — all work merges via PR.

**Don't add explanation** — keep options concise.

### Step 6: Execute Choice

#### Option 1: Push and Create PR

```bash
# Push branch
git push -u origin <feature-branch>

# Create PR
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] make test passes
- [ ] Emulicious smoketest confirmed by user
- [ ] bank-post-build gates passed
- [ ] gb-memory-validator: no FAIL budgets

Closes #N
EOF
)"
```

After PR is created, report to the user:

> "PR created: <URL>
> When the PR is merged, let me know and I'll clean up the worktree at <worktree-path>."

**Do NOT run Step 6 now.** Cleanup happens only after the user confirms the merge.

#### Option 2: Keep As-Is

Report: "Keeping branch `<name>`. Worktree preserved at `<path>`."

**Do NOT run Step 6.**

#### Option 3: Discard

**Confirm first:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for exact confirmation.

If confirmed, remove the worktree first, then delete the branch from the main repo:

```bash
# Step 1: Remove the worktree (from inside the worktree — git worktree remove works)
git worktree remove --force <worktree-path>

# Step 2: Delete the branch from the main repo
git -C /home/mathdaman/code/gmb-nuke-raider branch -D <feature-branch>
```

Then run Step 7 immediately.

### Step 7: Cleanup Worktree

#### After merge confirmation (Option 1 only)

Only run after the user explicitly confirms the PR was merged — **never preemptively**.

**Step 6a: Confirm worktree exists**
```bash
GIT_DIR=/home/mathdaman/code/nuke-raider/.git GIT_WORK_TREE=/home/mathdaman/code/nuke-raider git worktree list | grep <branch-name>
```
If not listed, skip removal (already gone).

**Step 6b: Remove the worktree**

Always use explicit `GIT_DIR` — the session CWD may be inside or point to the deleted worktree, which causes bare `git` commands to fail:
```bash
GIT_DIR=/home/mathdaman/code/nuke-raider/.git GIT_WORK_TREE=/home/mathdaman/code/nuke-raider git worktree remove <worktree-path>
```
If that fails (e.g. dirty working tree), use `--force` and warn the user:
```bash
GIT_DIR=/home/mathdaman/code/nuke-raider/.git GIT_WORK_TREE=/home/mathdaman/code/nuke-raider git worktree remove --force <worktree-path>
# Warn: "Worktree had uncommitted changes — removed with --force."
```

**Step 6c: Prune stale refs**
```bash
GIT_DIR=/home/mathdaman/code/nuke-raider/.git GIT_WORK_TREE=/home/mathdaman/code/nuke-raider git worktree prune
```

Report: "Worktree at `<path>` removed and pruned."

#### Immediately after discard confirmation (Option 3)

Run the same Step 6a → 6b → 6c sequence immediately after the user types 'discard'.

#### Option 2: Keep As-Is

**Do NOT run Step 6.** Report: "Keeping branch `<name>`. Worktree preserved at `<path>`."

## Quick Reference

| Option | Push | Cleanup Worktree | When |
|--------|------|-----------------|------|
| 1. Push and Create PR | ✓ | ✓ | After merge confirmed |
| 2. Keep as-is | - | - | Never |
| 3. Discard | - | ✓ | After 'discard' typed |

## Common Mistakes

**Wrong emulator or ROM name**
- **Problem:** Using `mgba-qt` or wrong ROM path loses time and gives wrong results
- **Fix:** Always use `java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb`

**Launching from wrong directory**
- **Problem:** Main repo's `build/` may be stale; must use worktree's `build/`
- **Fix:** Run emulator command from the worktree directory, not the main repo

**Skipping bank gates**
- **Problem:** Undetected bank overflow causes blank screen / ~1-2 FPS
- **Fix:** Always run bank-post-build and `make memory-check` before smoketest

**Using bare `git merge master`**
- **Problem:** Local master ref may be stale; silently merges old code
- **Fix:** Always `git fetch origin && git merge origin/master`

**`git worktree prune` fails when session CWD is the deleted worktree**
- **Problem:** After `git worktree remove`, if the session's working directory was inside that worktree, `git worktree prune` (and bare `git` commands) fail with "Working directory no longer exists"
- **Fix:** Use explicit `GIT_DIR` to target the main repo:
  ```bash
  GIT_DIR=/home/mathdaman/code/nuke-raider/.git GIT_WORK_TREE=/home/mathdaman/code/nuke-raider git worktree prune
  ```

**Merging directly to main**
- **Problem:** Bypasses review, violates branch policy
- **Fix:** Always use a PR — never `git merge` to main locally

**Skipping test verification**
- **Problem:** Merge broken code, create failing PR
- **Fix:** Always verify tests before offering options

## Red Flags

**Never:**
- Commit directly to `master`
- Merge feature branch locally without a PR
- Proceed with failing tests
- Delete work without confirmation
- Force-push without explicit request
- Use `mgba-qt` (wrong emulator)
- Reference `wasteland-racer.gb` (wrong ROM name)
- Launch emulator from main repo's `build/` (may be stale)
- Skip bank-post-build or `make memory-check` before smoketest
- Clean up worktree immediately after PR creation (wait for merge confirmation)
- Skip Step 4.5 when skills, agents, or CLAUDE.md were modified
- Push without running Step 1 (fetch/merge) — even doc-only branches can have conflicts

**Always:**
- Work on a feature branch
- Integrate via PR only
- Verify tests before offering options
- Run bank-post-build + `make memory-check` before smoketest
- Fetch + merge origin/master at Step 1 (concurrent with manifest review) — unconditionally, before any build or push
- Launch Emulicious from worktree directory
- Present exactly 3 options
- Get typed confirmation for Option 3
- Update `docs/dev-workflow.md` in the same PR as any skill/agent/CLAUDE.md change
- After PR creation (Option 1): tell user the worktree path and ask them to confirm when merged
- After merge confirmation: run git worktree remove → --force fallback → git worktree prune

## Integration

**Called by:**
- **subagent-driven-development** (final step) — after all tasks complete
- **executing-plans** (Step 7) — after all batches complete

**Pairs with:**
- **using-git-worktrees** — cleans up worktree created by that skill

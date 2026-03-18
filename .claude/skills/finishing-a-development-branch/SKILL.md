---
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify tests → Bank gates → Smoketest → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

## The Process

### Step 1: Verify Tests

**Before presenting options, verify tests pass:**

```bash
make test
```

**If tests fail:**
```
Tests failing (<N> failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

Stop. Don't proceed to Step 2.

**If tests pass:** Continue to Step 2.

### Step 2: HARD GATE — bank-post-build

**Run before the smoketest:**

Invoke the `bank-post-build` skill. If it reports any FAIL, stop and fix before continuing.

Only continue to Step 3 when it passes.

### Step 3: Smoketest in Emulicious

1. Fetch and merge latest master (from the **worktree** directory — never from the main repo):
   ```bash
   git fetch origin && git merge origin/master
   ```

2. Always do a clean build:
   ```bash
   make clean && GBDK_HOME=/home/mathdaman/gbdk make
   ```

3. Run `gb-memory-validator` agent on the clean build ROM. If any budget is FAIL, stop and fix before continuing.

4. Launch the ROM immediately in the background (from the worktree directory so `build/` resolves
   to the worktree's build output — NEVER from the main repo's `build/`):
   ```bash
   # Run from the worktree directory (cd there first if needed)
   java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
   ```

4. Tell the user it's running and ask them to confirm it looks correct before proceeding.

**Stop. Wait for explicit confirmation.**

- If issues found: work with user to fix before continuing
- If confirmed: Continue to Step 4

### Step 4: Present Options

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

### Step 5: Execute Choice

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

Then: Cleanup worktree (Step 6)

#### Option 2: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

**Don't cleanup worktree.**

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

### Step 6: Cleanup Worktree

**For Options 1 and 3:**

Check if in worktree:
```bash
git worktree list | grep $(git branch --show-current)
```

If yes:
```bash
git worktree remove <worktree-path>
```

**For Option 2:** Keep worktree.

## Quick Reference

| Option | Push | Keep Worktree | Cleanup Branch |
|--------|------|---------------|----------------|
| 1. Create PR | ✓ | - | - |
| 2. Keep as-is | - | ✓ | - |
| 3. Discard | - | - | ✓ (force) |

## Common Mistakes

**Wrong emulator or ROM name**
- **Problem:** Using `mgba-qt` or wrong ROM path loses time and gives wrong results
- **Fix:** Always use `java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb`

**Launching from wrong directory**
- **Problem:** Main repo's `build/` may be stale; must use worktree's `build/`
- **Fix:** Run emulator command from the worktree directory, not the main repo

**Skipping bank gates**
- **Problem:** Undetected bank overflow causes blank screen / ~1-2 FPS
- **Fix:** Always run bank-post-build and gb-memory-validator before smoketest

**Using bare `git merge master`**
- **Problem:** Local master ref may be stale; silently merges old code
- **Fix:** Always `git fetch origin && git merge origin/master`

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
- Skip bank-post-build or gb-memory-validator before smoketest

**Always:**
- Work on a feature branch
- Integrate via PR only
- Verify tests before offering options
- Run bank-post-build + gb-memory-validator before smoketest
- Fetch + merge origin/master before smoketest rebuild
- Launch Emulicious from worktree directory
- Present exactly 3 options
- Get typed confirmation for Option 3
- Clean up worktree for Options 1 & 3 only

## Integration

**Called by:**
- **subagent-driven-development** (final step) — after all tasks complete
- **executing-plans** (Step 6) — after all batches complete

**Pairs with:**
- **using-git-worktrees** — cleans up worktree created by that skill

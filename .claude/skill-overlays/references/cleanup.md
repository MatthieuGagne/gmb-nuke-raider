# Worktree Cleanup — Fallback Ladders

The detailed cleanup sequence for Step 7. Run after merge confirmation (Option 1) or immediately after discard confirmation (Option 3).

## After merge confirmation (Option 1 only)

Only run after the user explicitly confirms the PR was merged — **never preemptively**.

**Step 6a: Confirm worktree exists**
```bash
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree list | grep <branch-name>
```
If not listed, skip removal (already gone).

**Step 6b: Exit the EnterWorktree session if still active**

If the current session was started with `EnterWorktree` and is still inside this worktree, Claude Code will block all Bash commands once the directory is deleted. Use `ExitWorktree` first — it removes the directory, clears the session CWD, and returns to the main repo:
```
ExitWorktree(action="remove", discard_changes=true)
```
After `ExitWorktree` returns, skip to Step 6d — the worktree is already removed.

If the session is NOT inside an active `EnterWorktree` context, continue to Step 6c.

**Step 6c: cd to main repo root and remove the worktree**

Always `cd` first — if the session CWD is inside the worktree and the directory is already deleted, `git` will panic with "Unable to read current working directory":
```bash
cd C:/Code/nuke-raider
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree remove <worktree-path>
```
If that fails (e.g. dirty working tree), use `--force` and warn the user:
```bash
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree remove --force <worktree-path>
# Warn: "Worktree had uncommitted changes — removed with --force."
```
If `--force` also fails (directory already deleted from disk, stale git ref), clean up manually:
```bash
rm -rf <worktree-path>
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree prune
# Note: "Worktree directory was already gone — pruned stale ref."
```
Skip Step 6d in this case (prune already ran).

**Step 6d: Prune stale refs**
```bash
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree prune
```

Report: "Worktree at `<path>` removed and pruned."

## Immediately after discard confirmation (Option 3)

Run the same Step 6a → 6b → 6c → 6d sequence immediately after the user types 'discard'. Skip Step 6b if already at main repo root.

## Option 2: Keep As-Is

**Do NOT run cleanup.** Report: "Keeping branch `<name>`. Worktree preserved at `<path>`."

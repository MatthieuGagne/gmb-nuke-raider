# Worktree Cleanup — Fallback Ladders

The detailed cleanup sequence. Run after merge confirmation (menu option 1, "push and create a
PR"), or immediately after a discard the user asked for by typing `discard`. Discard is **not**
a menu option — the overlay presents exactly two — so nothing below is reachable by a user
merely picking from the menu.

## After merge confirmation (menu option 1 only)

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
**If it is refused with `contains modified or untracked files`, do NOT `--force`.** That
refusal means those files exist nowhere else. Follow the baseline (superpowers@6.3.0): show
what is at stake and ask.
```bash
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git -C <worktree-path> status --porcelain -uall
```
Present the file list with three options — (1) commit them to the branch, (2) move them to
`C:/Code/nuke-raider`, (3) delete them (unrecoverable) — carry out the choice, then remove the
worktree. `--force` here is authorized only by option 3, or by the discard path below where the
user has already typed `discard`.

If removal fails **mechanically** instead (directory already deleted from disk, stale git ref —
`is not a working tree`), no data is at risk; clean up manually:
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

## Immediately after a typed `discard`

Run the same Step 6a → 6b → 6c → 6d sequence immediately after the user types `discard`. Skip
Step 6b if already at main repo root. This is the one path where `--force` needs no further
question: the typed word already authorized the loss.

## Menu option 2: Keep As-Is

**Do NOT run cleanup.** Report: "Keeping branch `<name>`. Worktree preserved at `<path>`."

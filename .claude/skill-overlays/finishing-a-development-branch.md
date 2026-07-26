---
name: finishing-a-development-branch
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline finishing-a-development-branch skill. On conflict, this overlay wins.

## Overrides (do NOT follow the baseline here)

- **Never offer "merge to main locally."** All work integrates via PR. Present exactly three options: (1) push and create a Pull Request ← default, (2) keep the branch as-is, (3) discard this work. Keep them concise, no added explanation. Option 3 requires typed confirmation.
- **Never commit directly to `master`.**
- **The worktree-cleanup reference now lives at `.claude/skill-overlays/references/cleanup.md`** — not under the skill's own `references/` directory. It holds the full cleanup fallback ladders and per-option triggers.

## Project additions

### Before anything else: fetch + merge, and review the bank manifest

Run these two as a concurrent batch:

- **Fetch and merge latest master** — mandatory, always, even for doc-only branches:
  ```bash
  git fetch origin && git merge origin/master
  ```
  Never use bare `git merge master` — the local master ref may be stale and silently merges old code. Resolve any conflicts and commit the merge before pushing.
- **Bank manifest review** (read-only, no merge dependency): check `bank-manifest.json` against the branch's `src/*.c` files — every `src/*.c` file must have an entry. A missing entry is a blocker.

Wait for both before verifying tests.

### Verify tests against the merged state

Run `make test` **after** the merge, so tests execute against merged code. If tests fail, stop — do not proceed toward merge or PR until they pass.

### HARD GATE — bank-post-build

Invoke the `bank-post-build` skill before the smoketest. Any FAIL → stop and fix. Skipping it (or `make memory-check`) lets an undetected bank overflow through, which shows up as a blank screen or ~1–2 FPS.

### Smoketest gate — NEVER push or create a PR before it passes

Skip only for doc-only branches with no `src/*.c`, `src/*.h`, or asset changes.

1. Always do a clean build (master is already merged): `make clean && make`
2. Run `make memory-check` and report the output. Any budget FAIL or ERROR → stop and fix.
3. **Ask the user for confirmation before launching the ROM.** If they confirm, launch via the **PowerShell tool** (not Bash — Bash exits silently without showing the window on Windows), from the **worktree** directory, never the main repo's `build/`:
   ```powershell
   Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
   ```
4. Ask the user to confirm it looks correct. **Stop and wait for explicit confirmation.** Issues found → fix with the user before continuing.

Never use `mgba-qt` (wrong emulator) or reference `wasteland-racer.gb` (wrong ROM name).

### Update docs before the PR

- **Any user-visible behavior changed** (new feature, changed controls, new screen, new module) → update the **Game Modules table** in `README.md`.
- **Any `.claude/skills/`, `.claude/agents/`, or `CLAUDE.md` file changed** → update `docs/dev-workflow.md` in the same PR. The two are co-authoritative and must agree.
- **Any new tool permission approved this session** → commit `.claude/settings.local.json` alongside the feature work, so permissions are not lost.

### PR conventions

Use `gh` for push and all GitHub operations (`gh auth setup-git` if push fails on credentials). Run git commands through the **PowerShell tool** on Windows — the Bash tool triggers a global PreToolUse hook that can block them.

Always create a PR after pushing a branch — no need to ask. PR body:

```markdown
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] make test passes
- [ ] Emulicious smoketest confirmed by user
- [ ] bank-post-build gates passed
- [ ] gb-memory-validator: no FAIL budgets

Closes #N
```

`Closes #N` auto-closes the linked issue on merge. After the PR is created, report the URL and tell the user the worktree path, asking them to confirm when it is merged. **Do NOT clean up the worktree at PR-creation time** — wait for merge confirmation. Once merged, verify the linked issue actually closed; if not, `gh issue close N`.

### Cleanup failure recovery

Full ladders are in `.claude/skill-overlays/references/cleanup.md`. The three recurring traps:

- Bash blocked with "Path does not exist" after merge → the session is inside an active `EnterWorktree`; use `ExitWorktree(action="remove", discard_changes=true)` first.
- `git worktree remove` fails with "Unable to read current working directory" → `cd C:/Code/nuke-raider` before any `git worktree remove`.
- `git worktree remove --force` fails with "is not a working tree" → the directory is already gone; fall back to `rm -rf <path> && git worktree prune`.

To discard a branch, remove the worktree first, then delete the branch from the main repo:
```powershell
cd C:/Code/nuke-raider
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree remove --force <worktree-path>
git -C C:/Code/nuke-raider branch -D <feature-branch>
```

### Never

- Proceed with failing tests, or skip test verification before offering options.
- Delete work without typed confirmation, or force-push without an explicit request.
- Launch the emulator from the main repo's `build/`.
- Push without fetching and merging first — even doc-only branches can conflict.
- Skip the doc updates when skills, agents, or `CLAUDE.md` changed.

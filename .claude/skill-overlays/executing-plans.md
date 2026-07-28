---
name: executing-plans
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline executing-plans skill. On conflict, this overlay wins.

## Overrides (do NOT follow the baseline here)

- **The baseline's advice to prefer subagent-driven-development does not auto-apply.** In this project the choice between SDD and executing-plans belongs to the user at plan handoff. Use this skill when the user chose "Parallel Session" execution; do not redirect to SDD on your own initiative.

## Project additions

### Worktree discipline

- **Hard gate before reading the plan or touching any file:** confirm you are in a git worktree, not the main repo.
  ```bash
  git worktree list
  git branch --show-current
  pwd
  ```
  Expected: current directory under `.claude/worktrees/`, branch is a feature branch (not `master`). If not, enter one first.
- **Verify `pwd` before every `make` or emulator launch.** Never launch the ROM from the main repo's `build/` — it may be stale.
- **`make test` must be run from the worktree directory.** Running it from the main repo root tests stale compiled binaries and silently masks real failures.
- After confirming the worktree, sync: `git fetch origin && git merge origin/master`. Never `git merge master` alone — the local master ref may be stale.

### Per-task gate obligations

- **The plan's embedded hard-gate steps are mandatory, not advisory.** For any task touching `src/*.c` or `src/*.h`, every gate the plan lists must actually execute: `bank-pre-write`, `gbdk-expert`, `bank-post-build`, `gb-memory-validator`, `gb-c-optimizer`.
- A gate step phrased as "HARD GATE — <agent>: confirm X" is not complete until that agent has **run and returned findings**. Reading the plan's description of the consultation is not sufficient.
- **C tasks:** dispatch the `gbdk-expert` agent with `"implement this task: <full task text>"` — it owns the TDD cycle, bank gates, build, `gb-c-optimizer` review and fix, and the commit. **Music C tasks** (`src/music_data.c`, `src/music_data.h`, or any new song `.c`) go to `music-expert` the same way.
- **After every implementer dispatch, verify the commit landed:** run `git log --oneline -1`. Never treat the agent's return message as proof of a commit — agents often return only their final step's output. If the commit is missing, re-dispatch the task from scratch.
- **Batch atomicity:** if any implementer in a parallel group fails, halt the whole batch. Passing implementers discard in-progress work — do not stage or commit partial results. Fix, then re-dispatch the entire group.

### `make test` early-exit behavior

The Makefile uses `|| exit 1`, so it **stops at the first failing test binary** (alphabetical order). Test binaries after the first failure do NOT run. Fix failures starting from the earliest binary and re-run `make test` after each fix to reveal the next hidden failure. A single green run is the only proof the suite passes.

### Batch execution with Smoketest Checkpoints

Stop at each checkpoint the plan defines and run the full sequence:

1. `git fetch origin && git merge origin/master` (from the worktree directory)
2. `make clean && make` — always a clean build
3. `make memory-check` fires automatically via PostToolUse hook after the build; check the hook output. Any budget FAIL or ERROR stops the plan until fixed.
4. **Ask the user for confirmation before launching the ROM.** Only if they confirm, launch from the worktree directory:
   ```powershell
   Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
   ```
5. Ask the user to confirm it looks correct. Wait for that confirmation before continuing to the next batch.

Between batches: report what was implemented plus verification output, then wait. Do not roll into the next batch unprompted.

### Lessons Learned — HARD GATE

After the smoketest passes and **before pushing or creating the PR**, explicitly ask:

> "Any important lessons learned from this implementation? (e.g. surprises, sharp edges, things that should update CLAUDE.md / skills / agents / memory)"

This is mandatory even when the implementation felt smooth. If the user provides lessons, invoke the `prd` skill to capture the documentation updates as a GitHub issue, and save anything session-relevant to memory. If they explicitly say there are none, note that and proceed. Do not push or open the PR before receiving an explicit answer.

### Shipping

Never push or create a PR before the Emulicious smoketest passes with user confirmation. Only after confirmation: update `README.md` if user-visible behavior changed, promote any newly approved tool permission into the tracked `.claude/settings.json` as a generalized rule (never commit `.claude/settings.local.json` — it is gitignored scratch; see ADR 0001 (#466)), then push and open the PR with `Closes #N` in the body.

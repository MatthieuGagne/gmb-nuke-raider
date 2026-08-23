---
name: executing-plans
baseline: superpowers@6.3.0
---

Project (Nuke Raider) additions and overrides for the baseline executing-plans skill. On
conflict, this overlay wins — but an override earns that only by stating what the baseline
cannot know (#527 R7).

**Baseline audit:** content of `superpowers@6.3.0` read and compared on 2026-08-22 (#527 R6).
6.3.0's `SKILL.md` is **byte-identical** to 6.2.0's, so every section below was re-checked
against unchanged text and none was absorbed upstream.

## Overrides (do NOT follow the baseline here)

- **The baseline's advice to prefer subagent-driven-development does not auto-apply.** In this project the choice between SDD and executing-plans belongs to the user at plan handoff. Use this skill when the user chose "Parallel Session" execution; do not redirect to SDD on your own initiative.
  **Why:** the baseline's note ("if subagents are available, use subagent-driven-development
  instead") is written for a reader who has not already been asked. Here the `writing-plans`
  overlay's Handoff has already put the choice to the user, and silently overriding their answer
  is worse than the cost it saves.

## Project additions

### Worktree discipline

**Why:** the baseline delegates workspace setup to `using-git-worktrees` and stops there; the
stale-`build/` and stale-`make test` traps below are this project's, and both have bitten.

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

**Why:** the baseline says "follow each step exactly" and "don't skip verifications" but has no
concept of a gate that must have *reported*, no agent roster, and no warning that a subagent's
report can be false.

- **The plan's embedded hard-gate steps are mandatory, not advisory.** For any task touching `src/*.c` or `src/*.h`, every gate the plan lists must have **fired and reported** before the task is complete. `bank-pre-write`, `bank-post-build` and `gb-memory-validator` fire automatically as hooks (PreToolUse on `src/*` writes, PostToolUse after a build) — do not invoke them by hand; **read their output** and treat any FAIL as blocking. `gbdk-expert` and `gb-c-optimizer` are agent dispatches and must actually be dispatched.
- A gate step phrased as "HARD GATE — <agent>: confirm X" is not complete until that agent has **run and returned findings**. Reading the plan's description of the consultation is not sufficient.
- **C tasks:** dispatch the `gbdk-expert` agent with `"implement this task: <full task text>"` — it owns the TDD cycle, bank gates, build and the commit. It does **not** own `gb-c-optimizer`: the controller dispatches that after the commit. **Music C tasks** (`src/music_data.c`, `src/music_data.h`, or any new song `.c`) go to `music-expert` the same way.
- **After every implementer dispatch, verify the commit landed:** run `git log --oneline -1`. Never treat the agent's return message as proof of a commit — agents often return only their final step's output. If the commit is missing, re-dispatch the task from scratch.
- **Review range.** Record BASE with `git rev-parse HEAD` **before** dispatching an implementer, and review from that BASE — never `HEAD~1`, which silently truncates a multi-commit task to its last commit. Hand the reviewer its diff as a file path, not as pasted text, so the diff never enters this session's context.
- **Task atomicity:** implementers run one at a time — see the `subagent-driven-development` overlay's `### Dispatch order`. A failed task therefore invalidates only itself: committed, reviewed tasks stand. Fix and re-dispatch that task alone, never the whole group.

### `make test` early-exit behavior

**Why:** the baseline says "don't skip verifications" and assumes a green run means a full run.
This Makefile's `|| exit 1` breaks that assumption, and nothing upstream could know it.

The Makefile uses `|| exit 1`, so it **stops at the first failing test binary** (alphabetical order). Test binaries after the first failure do NOT run. Fix failures starting from the earliest binary and re-run `make test` after each fix to reveal the next hidden failure. A single green run is the only proof the suite passes.

### Batch execution with Smoketest Checkpoints

**Why:** the baseline has no checkpoint concept at all — it executes every task then finishes.
A ROM that compiles can still fail to boot, so batches end where a human can see it run.

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

### Factory mode

**Why:** the factory runs unattended; every baseline instruction to stop and ask a human needs a
headless replacement or an explicit waiver, and the baseline has no notion of such a run.

Active when `NUKE_FACTORY_RUN` is set. It **overrides `### Batch execution with Smoketest
Checkpoints`, `### Lessons Learned — HARD GATE` and `### Shipping` above.**

- Batch checkpoints run headlessly: steps 1-3 unchanged (fetch+merge, `make clean && make`,
  `make memory-check` — a FAIL still aborts), then
  `python tools/smoketest_headless.py --scenario generic-smoke --json` in place of steps 4-5.
  Do not launch Emulicious and do not wait for confirmation. Do not pause between batches.
- The **Lessons Learned HARD GATE becomes a decisions-log entry.** There is no user to ask.
  Record what a lesson would have been:
  ```
  python tools/factory_event.py --issue <N> --kind decision --field "text=lesson: <what surprised the run and what should change>"
  ```
  Do not invoke the `prd` skill and do not block the PR on an answer.
- `### Shipping` — "never push before the Emulicious smoketest passes with user confirmation"
  reads as "never push before the **headless** smoketest passes". The README rule and the
  allowlist-promotion rule still apply.

Outside a factory run every pause and every gate above fires exactly as written.

### Lessons Learned — HARD GATE

**Why:** the baseline ends at `finishing-a-development-branch` and captures nothing; this project
feeds surprises back into CLAUDE.md, skills and memory, which only the human can authorize.

After the smoketest passes and **before pushing or creating the PR**, explicitly ask:

> "Any important lessons learned from this implementation? (e.g. surprises, sharp edges, things that should update CLAUDE.md / skills / agents / memory)"

This is mandatory even when the implementation felt smooth. If the user provides lessons, invoke the `prd` skill to capture the documentation updates as a GitHub issue, and save anything session-relevant to memory. If they explicitly say there are none, note that and proceed. Do not push or open the PR before receiving an explicit answer.

### Shipping

**Why:** the baseline delegates shipping wholesale to `finishing-a-development-branch`. The
smoketest gate, the README rule and the allowlist-promotion rule ([ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466)) are
project policy that skill's baseline does not carry.

Never push or create a PR before the Emulicious smoketest passes with user confirmation. Only after confirmation: update `README.md` if user-visible behavior changed, promote any newly approved tool permission into the tracked `.claude/settings.json` as a generalized rule (never commit `.claude/settings.local.json` — it is gitignored scratch; see [ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466)), then push and open the PR with `Closes #N` in the body.

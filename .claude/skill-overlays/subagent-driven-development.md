---
name: subagent-driven-development
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline subagent-driven-development skill. On conflict, this overlay wins.

The baseline's workspace and ledger system (and its fix loop) are **accepted, not overridden** — use them as written. Note only that its helper scripts are POSIX `sh` and run under Git Bash on this machine; if `scripts/sdd-workspace` fails on Windows, fall back to computing `<repo-root>/.superpowers/sdd/<plan-basename>/` by hand — same contract, same layout.

## Project additions

### Subagent shell denial (read this before dispatching)

Dispatched implementer subagents have historically had **Bash and PowerShell denied** — they can edit files but cannot run commands. Therefore:

- **The orchestrator runs all `make`, `git`, and test commands itself**, and commits on the subagents' behalf.
- Never assume a subagent ran a build, a test, or a commit because its report says so. Verify with `git log --oneline -1` after every dispatch — the agent's return message is not proof.
- Read-only reviewer subagents still work normally.

### Workspace hygiene

The baseline's workspace ledger lives under `.superpowers/`, which is **gitignored in this repo**. Never commit it, never `git add -A` it into a feature commit.

### Commits

Route commits through the **PowerShell tool**, not Bash: `git commit -m @'...'@` (here-string, closing `'@` at column 0). The per-commit clean-build hook fires on Bash and is redundant with the per-task build gates this project already enforces.

### C task routing (include in every implementer brief)

Every C task brief must carry the project hard-gate sequence — subagents must not skip gates the plan lists.

- **Music C task** (creates or modifies `src/music_data.c`, `src/music_data.h`, or any new song `.c` file): the implementer IS `music-expert`. Dispatch with:
  > implement this task: \<full task text from plan\>

  It owns the full music pipeline — export, BANKREF declarations, `music_song_validate.py`, `music_wire_check.py`, bank-pre-write gate, build, bank-post-build gate, and commit. Do NOT add separate gate instructions; its own body enforces them.
- **All other C tasks** (`src/*.c` / `src/*.h`): the implementer IS `gbdk-expert`. Dispatch the same way. It owns the full TDD cycle, bank-pre-write, bank-post-build, build, `gb-c-optimizer` review AND fix (applied in-place before commit), and commit.
- **Non-C tasks:** dispatch a general implementer with the task text as-is.

Always include the full task text in the prompt (do NOT make the subagent read the plan file) plus scene-setting context for where the task fits in the feature.

### Parallel dispatch

Follow the project `dispatching-parallel-agents` skill for all dispatch decisions. The plan's `#### Parallel Execution Groups` table is the **authoritative source** — do not re-analyze file dependencies at runtime.

- `(parallel)` group → dispatch all its tasks as concurrent implementers in one message. **Max 3 concurrent implementers.**
- `(sequential)` group → one task at a time.
- No group table → fall back to per-task `**Parallelizable with:**` annotations. Neither present → treat all tasks as sequential.

**Never** parallelize tasks that write the same file, share git state (multiple committers on one branch), or have sequential data dependencies.

### Parallel reviewer dispatch (mandatory)

After every implementer commit, dispatch the spec-compliance reviewer AND the code-quality reviewer as **two concurrent Agent calls in a single message**. Wait for both. Spec fails → fix, re-dispatch spec alone; quality fails → fix, re-dispatch quality alone; both fail → fix both, re-dispatch both together. Both must pass before marking the task complete. Never run them sequentially in separate messages.

### Batch boundaries are smoketest checkpoints

At each batch boundary from the plan: pause dispatching, run the checkpoint sequence (fetch+merge `origin/master`, `make clean && make`, `make memory-check`, ask the user before launching Emulicious from the worktree, wait for visual confirmation), then continue.

### Factory mode

Active when `NUKE_FACTORY_RUN` is set — i.e. the BUILD stage of a `/factory` run. It **overrides
`### Batch boundaries are smoketest checkpoints` above**, and nothing else in this overlay.

At each batch boundary, run the headless checkpoint instead of the Emulicious pause:

1. `git fetch origin && git merge origin/master`
2. `make clean && make`
3. `make memory-check` — **any FAIL or ERROR aborts the run immediately.** No retry.
4. `python tools/smoketest_headless.py --scenario generic-smoke --json` — this replaces "ask the
   user before launching Emulicious" and "wait for visual confirmation". Exit 0 continues.
5. Record the outcome:
   ```
   python tools/factory_event.py --issue <N> --kind scenario --field scenario=generic-smoke --field result=<pass|fail> --field blocking=true
   ```

Everything else stands unchanged and is **not** waived:

- `### Parallel reviewer dispatch (mandatory)` — both reviewers, concurrently, every commit.
- `### Pre-PR Gate (HARD STOP)` — all four checks.
- `### Red flags — never` — all of them, including the bank gates and the worktree gate.

Retry budget in factory mode is **2 attempts per task**. Append
`--kind retry --field stage=BUILD --attempt <k>` before the second attempt. Exhausted → terminal
failure; do not proceed to the next task.

Outside a factory run the batch-boundary Emulicious pause fires exactly as written.

### Pre-PR Gate (HARD STOP)

Run after the smoketest is confirmed and before pushing or creating a PR. All four must pass.

| # | Check | How to verify | On failure |
|---|-------|---------------|------------|
| 1 | **Full test suite passes** | `make test` → all PASS (no early-exit failures) | Fix failing test, re-run from scratch |
| 2 | **Clean build succeeds** | `make clean && make` → zero errors | Fix compiler error before continuing |
| 3 | **No header includes silently removed** | `git diff master...HEAD -- src/*.h` — every `#include` removal must be intentional and traceable to a task requirement | Restore removed include or justify removal in a commit comment |
| 4 | **No hardcoded values introduced** | `git diff master...HEAD -- src/*.c src/*.h` — no magic numeric literals that belong in `config.h` | Replace with a named constant, commit |

Any failure → fix and re-run this gate from check 1. Only then call `finishing-a-development-branch`.

### Example workflow

See `.claude/skill-overlays/references/example-workflow.md` for a worked end-to-end walkthrough, including a parallel batch.

### Red flags — never

- Start implementation on `master`, or skip the worktree gate.
- Skip `bank-pre-write` / `gbdk-expert` before any C write, or `bank-post-build` / `gb-memory-validator` after any build.
- Launch the smoketest from the main repo's `build/` (use the worktree's).
- Accept "close enough" on spec compliance, or move to the next task with an open review issue.
- Make a subagent read the plan file instead of providing the full task text.
- Ignore a subagent's questions — answer them before letting it proceed.

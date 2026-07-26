---
name: writing-plans
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline writing-plans skill. On conflict, this overlay wins.

## Overrides (do NOT follow the baseline here)

- **Save plans to `docs/plans/YYYY-MM-DD-issue<N>-<slug>.md`** — NOT `docs/superpowers/plans/`
  or any other baseline location, and NOT the issue-less `YYYY-MM-DD-<feature-name>.md` form.
  `<N>` is the GitHub issue number the plan implements; `<slug>` is lowercase, hyphen-separated
  (e.g. `docs/plans/2026-07-26-issue435-traceability.md`).

## Project additions

### Before you begin

- **First action, before anything else:** pull and merge latest master into the current worktree branch:
  ```bash
  git fetch origin && git merge origin/master
  ```
  Resolve any conflicts before proceeding. Never use `git merge master` alone — the local master ref may be stale.
- **Context:** this runs in a dedicated worktree. All file operations happen inside it.
- **Last step before writing:** invoke the `grill-with-docs` skill — it surfaces requirements, acceptance criteria, scope, and GB hardware constraints. Only once the grilling is satisfied, proceed to writing the plan.

### Hard Gate Sequence

Every task that touches `src/*.c` or `src/*.h` MUST follow this exact sequence — no exceptions:

| Step | Action |
|------|--------|
| 1 | Write failing test (`make test` → FAIL) |
| 2 | Invoke `bank-pre-write` skill (HARD GATE) |
| 3 | Invoke `gbdk-expert` agent (HARD GATE) |
| 4 | Write minimal implementation |
| 5 | Run tests (`make test` → PASS) |
| 6 | Build ROM (`make` → PASS) |
| 7 | Invoke `bank-post-build` skill (HARD GATE) |
| 8 | Refactor checkpoint ("breaks when N > 1?") |
| 9 | Invoke `gb-c-optimizer` agent (HARD GATE — validate only, report issues, do not apply fixes) |
| 10 | Commit |

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

**Constant-removal audit:** if any task removes or renames a shared constant (e.g. `PLAYER_ACCEL`, `PLAYER_MAX_SPEED`), add a grep step at the top of that task before listing affected files:
```bash
grep -r CONSTANT_NAME tests/
```
Include ALL matching test files in the task's file list — not just the ones you remembered. Missing a file means surprise failures during parallel execution, after other tasks' commits have already landed.

### Smoketestable batches

**Tasks MUST be grouped into batches of 2–4.** Each batch ends with a **Smoketest Checkpoint** — a point where the ROM runs in Emulicious and the user confirms it looks correct. A good batch boundary = any point where the game should visually work end-to-end (even partially). If a batch cannot be independently smoke-tested, the plan must explain why.

**Dependency analysis** (required before writing each Smoketest Checkpoint block):
1. List all output files for each task in the batch.
2. Mark as **sequential** any two tasks that write the same file, or where Task B compiles against a symbol Task A defines.
3. Group remaining tasks into independent layers — tasks with the same `Depends on` set are parallelizable with each other.
4. Fill in `**Depends on:**` and `**Parallelizable with:**` on every task.
5. Insert a `#### Parallel Execution Groups` table immediately before the Smoketest Checkpoint block — this is the executor's source of truth for parallel dispatch.

Checkpoint block template:

````markdown
#### Parallel Execution Groups — Smoketest Checkpoint N

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files, no shared state |
| B (sequential) | Task 3 | Depends on Group A — must run after both complete |

### Smoketest Checkpoint N — [what to verify visually]

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS. Fix any FAIL or ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory — use PowerShell tool, not Bash). Ask the user for confirmation first.**
```powershell
Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
```

**Step 5: Confirm with user**
Tell the user what to verify visually. Wait for confirmation before proceeding to the next batch.
````

### Plan document header

Every plan MUST start with this header:

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Issue:** #N

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Open questions (must resolve before starting)

- [Question 1 — or delete this line if none]
```

The `**Issue:** #N` line is mandatory and must sit on its own line, exactly in this form —
`tools/trace.py` parses it to link the plan back to its spec issue, and the issue number must
match the one in the filename. If a plan has no originating issue, create one first (`/prd`);
a plan with no issue cannot be traced.

### Task templates

See `.claude/skill-overlays/references/task-templates.md` for the two task templates: the 11-step C-File Task Template (for `src/*.c` / `src/*.h`, all HARD GATE steps) and the Non-C Task Template (markdown/Python/JSON/assets).

### Plan Self-Review Checklist (HARD STOP before presenting to user)

Run this before offering the execution handoff. Fix any failures first.

| # | Check | Pass criteria |
|---|-------|---------------|
| 1 | **No hardcoded values** | Every numeric constant, tile index, capacity, or coordinate is sourced from `config.h`, a Tiled export, or an explicit named constant — never a magic number |
| 2 | **All tasks have explicit test criteria** | Every task states exactly how to verify it passes (command + expected output, or visual check description) |
| 3 | **Parallel annotations justified** | Every task has `**Depends on:**` and `**Parallelizable with:**` filled in. Any `**Parallelizable with:** none` MUST be followed by a one-sentence justification (e.g. "writes same file as Task M"). An unjustified `none` is a plan defect. |
| 4 | **Parallel Execution Groups tables present** | Every batch that precedes a Smoketest Checkpoint has a `#### Parallel Execution Groups` table |
| 5 | **No implementation details leaked from brainstorming** | Plan contains file paths and task steps, not design narrative or requirement rationale (those belong in the GitHub issue) |
| 6 | **Issue header + filename** | The plan has an `**Issue:** #N` line matching the `issue<N>` in its filename. Verify with `python tools/trace.py --check --plans-only` — expect `PASS` and no `ERROR` lines mentioning this plan |

**Failure handling:**
- Checks #1, #2, #4, #5 fail → fix the plan now and re-run the checklist from the top.
- Check #6 fails → fix the header and/or rename the file now, then re-run `python tools/trace.py --check --plans-only`.
- Check #3 fails (unjustified `none`) → do NOT silently fix. Present the plan WITH the Incomplete Warning block below, immediately after the plan header. The user decides whether to proceed or fix first.

```markdown
> ⚠️ **Plan incomplete — unjustified parallelism annotations**
>
> The following tasks have `**Parallelizable with:** none` with no justification sentence:
> - Task N: [task name]
>
> For each: either (a) identify tasks it can parallelize with and update the annotation,
> or (b) add a one-sentence justification explaining why it cannot parallelize
> (e.g., "writes same file as Task M", "requires Task M's output symbol").
>
> Proceed with the plan as-is, or fix these annotations first?
```

### Handoff

After saving the plan, present the full plan to the user.

<HARD-GATE>
Do NOT offer execution options until the user gives an explicit affirmative approval (e.g. "yes", "looks good", "let's go", "proceed", or equivalent). Do not interpret silence or continued conversation as approval.
</HARD-GATE>

Only after an explicit affirmative, offer the execution choice:

**"Plan complete and saved to `docs/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (this session)** — fresh subagent per task, review between tasks, fast iteration. Stays in this session.

**2. Parallel Session (separate)** — open a new session with executing-plans, batch execution with checkpoints.

If Parallel Session is chosen, guide the user to open a new session in the worktree; that session uses `superpowers:executing-plans`.

### Remember

- Exact file paths always; complete code in the plan (not "add validation"); exact commands with expected output.
- Reference skills and agents by name (e.g. `bank-pre-write` skill, `gbdk-expert` agent).
- DRY, YAGNI, TDD, frequent commits.
- C files ALWAYS get the 11-step template with all HARD GATE steps.
- **Lessons Learned gate:** `executing-plans` runs a final Lessons Learned step after the smoketest passes — no action is needed in the plan itself.

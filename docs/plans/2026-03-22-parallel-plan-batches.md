# Parallel Plan Batches Implementation Plan

> **For Claude:** Doc-only change (skill files under `.claude/skills/`). No bank gates, no TDD. Edit → verify → commit per the doc-only workflow.

**Goal:** Add per-task dependency annotations and a per-checkpoint parallel group table to `writing-plans`, and update `subagent-driven-development` to read those tables as the source of truth for parallel batch dispatch.

**Architecture:** Two independent skill file edits. `writing-plans` gets new annotation syntax on task templates, a dependency analysis step, and a group table template before each smoketest checkpoint. `subagent-driven-development` gets an updated Parallel Implementer Batches section that reads the group table instead of inferring parallelism at runtime.

**Tech Stack:** Markdown

## Open questions

- none

---

### Task 1: Update writing-plans/SKILL.md

**Depends on:** none
**Parallelizable with:** Task 2

**Files:**
- Modify: `.claude/skills/writing-plans/SKILL.md`

**Step 1: Add `**Depends on:**` and `**Parallelizable with:**` to C-file task template**

In the C-File Task Template, after the `**Files:**` block, insert:

```markdown
**Depends on:** none   ← or "Task N, Task M" — tasks whose output this task reads or requires
**Parallelizable with:** none   ← or "Task N, Task M" — tasks at the same dependency layer
```

**Step 2: Add same annotations to non-C task template**

In the Non-C Task Template, after the `**Files:**` block, insert:

```markdown
**Depends on:** none   ← or "Task N, Task M"
**Parallelizable with:** none   ← or "Task N, Task M"
```

**Step 3: Add "Dependency Analysis" subsection inside "Smoketestable Batches"**

After the paragraph ending `"...the plan must explain why."`, before `"Use this template for every checkpoint:"`, insert:

```markdown
### Dependency Analysis (required before writing each smoketest checkpoint block)

After drafting all tasks in a batch, before inserting the Smoketest Checkpoint block:

1. List all output files for each task in the batch
2. Mark as **sequential** any two tasks that write the same file, or where Task B compiles against a symbol Task A defines
3. Group remaining tasks into independent layers — tasks with the same `Depends on` set are parallelizable with each other
4. Go back and fill in `**Depends on:**` and `**Parallelizable with:**` on each task
5. Insert a `#### Parallel Execution Groups` table immediately before the Smoketest Checkpoint block (use the template below)
```

**Step 4: Add Parallel Execution Groups table template**

Immediately before the `### Smoketest Checkpoint N` fenced block, insert:

````markdown
Use this template for the parallel group table that precedes every checkpoint:

```markdown
#### Parallel Execution Groups — Smoketest Checkpoint N

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files, no shared state |
| B (sequential) | Task 3 | Depends on Group A — must run after both complete |
```
````

**Step 5: Update the "Remember" section**

Replace:
```
- Mark tasks that create independent files as parallelizable — implementer can dispatch them as concurrent subagents
```
With:
```
- Annotate every task with `**Depends on:**` and `**Parallelizable with:**` — executor reads these; vague hints are not enough
- Insert a `#### Parallel Execution Groups` table before every Smoketest Checkpoint block — this is the executor's source of truth for parallel dispatch
```

**Step 6: Verify**

Read `.claude/skills/writing-plans/SKILL.md` and confirm:
- C-file task template has both annotation lines after `**Files:**`
- Non-C task template has both annotation lines after `**Files:**`
- "Dependency Analysis" subsection exists inside "Smoketestable Batches"
- Group table template appears before the Smoketest Checkpoint template
- "Remember" has the two new bullets (old vague bullet removed)

**Step 7: Commit**

```bash
git add .claude/skills/writing-plans/SKILL.md
git commit -m "feat(writing-plans): add per-task dependency annotations + parallel group table template"
```

---

### Task 2: Update subagent-driven-development/SKILL.md

**Depends on:** none
**Parallelizable with:** Task 1

**Files:**
- Modify: `.claude/skills/subagent-driven-development/SKILL.md`

**Step 1: Update the "Parallel Implementer Batches" opening**

Replace:
```
When the plan flags tasks as **parallelizable** (different output files, no shared state), dispatch 2–3 implementer agents in a single message instead of sequentially.
```
With:
```
When the plan's `#### Parallel Execution Groups` table marks a group as `(parallel)`, dispatch all tasks in that group as concurrent implementer agents in a single message. The group table is the **authoritative source** — do not re-analyze file dependencies at runtime.

**How to read the group table:**
- `(parallel)` group → dispatch all tasks in the group as concurrent implementers in one message
- `(sequential)` group → dispatch one task at a time, waiting for completion before starting the next
- No group table in plan → fall back to per-task `**Parallelizable with:**` annotations
- Neither table nor annotations present → treat all tasks as sequential
```

**Step 2: Verify**

Read `.claude/skills/subagent-driven-development/SKILL.md` and confirm:
- "Parallel Implementer Batches" section references the group table as source of truth
- Fallback chain (table → per-task annotations → sequential) is described
- Existing "Batch size limit: Max 3 concurrent implementers" and "Red flag" lines are preserved

**Step 3: Commit**

```bash
git add .claude/skills/subagent-driven-development/SKILL.md
git commit -m "feat(subagent-driven-development): read parallel group table from plan as source of truth"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files — independent skill edits |

### Smoketest Checkpoint 1 — skill files coherent, ROM unchanged

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors. (No game code changed — build confirms no pre-existing breakage.)

**Step 3: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 4: Confirm with user**
Ask the user to confirm the game boots as before (title screen visible, no regression). Also ask them to review the updated skill files and confirm the new annotation format reads clearly.

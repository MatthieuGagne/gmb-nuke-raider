# Parallel Plan Batches Design

**Date:** 2026-03-22
**Status:** Approved

## Goal

Optimize the plan-writing phase so that task independence is analyzed upfront and encoded directly in the plan document, enabling `subagent-driven-development` to fire parallel implementer batches without re-analyzing dependencies at execution time.

## Problem

The `writing-plans` skill currently includes a single vague note: _"Mark tasks that create independent files as parallelizable — implementer can dispatch them as concurrent subagents."_ This leaves dependency analysis to the executor, who must re-read all tasks and re-assess independence at runtime — duplicating work that could be done once, correctly, during plan writing.

## Approach: Inline Annotation + Per-Checkpoint Group Table (Option B)

### 1. Task-Level Annotations

Each task (both C-file and non-C templates) gains two annotation lines in its header:

```markdown
**Depends on:** none   ← or "Task 2, Task 3"
**Parallelizable with:** Task 2   ← tasks at the same dependency layer; "none" if sequential
```

Rules for filling these in:
- **Depends on:** List any tasks whose output files this task reads, or whose commits must land before this task's tests can compile. If none, write `none`.
- **Parallelizable with:** List all tasks that share the same dependency layer (i.e., they each say `Depends on: none`, or all depend on the same prior group). If a task is strictly sequential, write `none`.
- Two tasks are **not** parallelizable if they write to the same file, or if one reads a symbol defined by the other.

### 2. Parallel Execution Group Summary (per Smoketest Checkpoint)

After all tasks in a smoketest checkpoint are written, insert a summary table **before** the smoketest checkpoint block:

```markdown
#### Parallel Execution Groups — Smoketest Checkpoint N

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files, no shared state |
| B (sequential) | Task 3 | Depends on Group A — must run after both complete |
```

Groups labeled `(parallel)` may be dispatched as concurrent implementer agents. Groups labeled `(sequential)` must wait for all prior groups to complete.

### 3. Analysis Step in `writing-plans`

After drafting all tasks within a checkpoint, before writing the smoketest checkpoint block, the plan author must:

1. List all task output files within the checkpoint
2. Identify shared files → those tasks are sequential
3. Identify data dependencies (Task B compiles against a symbol Task A defines) → sequential
4. Group remaining tasks into independent layers
5. Write per-task annotations and the group summary table

### 4. `subagent-driven-development` Update

When the controller reads the plan, it reads each checkpoint's group table and:
- Fires all tasks in a `(parallel)` group as concurrent implementer agents in a single message
- Waits for all to complete before starting the next group
- Fires `(sequential)` tasks one at a time

No re-analysis of file dependencies needed at execution time.

## Files to Change

- `.claude/skills/writing-plans/SKILL.md` — add analysis step, update both task templates with annotation lines, add group table template to the smoketest checkpoint template
- `.claude/skills/subagent-driven-development/SKILL.md` — update "Parallel Implementer Batches" section to reference the plan's group table as the source of truth

## Out of Scope

- `executing-plans` (parallel-session path) — not changed; this only targets subagent-driven-development
- Formal dependency graph or topological sort tooling — kept as human analysis guided by the skill
- Changes to any `.c`/`.h` files — doc-only change

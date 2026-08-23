# Plan Structure — Header and Smoketest Checkpoint Templates

Extracted from the `writing-plans` overlay. These are **plan content**: what a plan document
must literally contain. Copy them verbatim.

## Plan document header

Only the `**Issue:** #N` line and the *Open questions* block are this project's — the rest,
including `## Global Constraints`, is the baseline's and is reproduced here so the two cannot
drift apart. `tools/trace.py` parses the issue line; nothing upstream knows this project files
its specs as GitHub issues.

Every plan MUST start with this header:

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement this plan task-by-task — the choice is the user's,
> made at the Handoff below.

**Issue:** #N

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Open questions (must resolve before starting)

- [Question 1 — or delete this line if none]

## Global Constraints

[The spec's project-wide requirements — exact values copied verbatim. Every task's requirements
implicitly include this section, and it is the attention lens the task reviewer is handed.]
```

**`**Issue:** #N` is this plan's `**Spec:**` line.** superpowers@6.3.0 added a `**Spec:**` field
to the baseline header, described as "path to the spec/design doc this plan implements". Here the
spec is never a path — it is the GitHub issue — so the issue line fills that role and no
`**Spec:**` line is added. Do not write both; a second spec pointer is a second source of truth.

The `**Issue:** #N` line is mandatory and must sit on its own line, exactly in this form —
`tools/trace.py` parses it to link the plan back to its spec issue, and the issue number must
match the one in the filename. If a plan has no originating issue, create one first (`/prd`);
a plan with no issue cannot be traced.

`## Global Constraints` is the baseline's block and is **mandatory**: the
`subagent-driven-development` baseline copies it verbatim into every task reviewer's prompt. A
plan without it hands each reviewer an empty constraints block.

## Smoketest Checkpoint block

Insert a `#### Parallel Execution Groups` table immediately before each Smoketest Checkpoint
block — it is the executor's source of truth for task ordering.

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

## Incomplete Warning block

Presented — never silently fixed — when Self-Review check #3 fails outside a factory run.

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

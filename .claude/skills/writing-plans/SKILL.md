---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

## Hard Gate Sequence

Every task that touches `src/*.c` or `src/*.h` MUST follow this exact sequence — no exceptions:

| Step | Action |
|------|--------|
| 1 | Write failing test (`make test` → FAIL) |
| 2 | Invoke `bank-pre-write` skill (HARD GATE) |
| 3 | Invoke `gbdk-expert` agent (HARD GATE) |
| 4 | Write minimal implementation |
| 5 | Run tests (`make test` → PASS) |
| 6 | Build ROM (`GBDK_HOME=/home/mathdaman/gbdk make` → PASS) |
| 7 | Invoke `bank-post-build` skill (HARD GATE) |
| 8 | Commit |

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## C-File Task Template

Use this template for any task that creates or modifies `src/*.c` or `src/*.h`:

````markdown
### Task N: [Component Name]

**Files:**
- Create: `src/foo.c`, `src/foo.h`
- Test: `tests/test_foo.c`

**Step 1: Write the failing test**

```c
void test_foo_init(void) {
    foo_init();
    TEST_ASSERT_EQUAL_UINT8(0, foo_get_count());
}
```

**Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL (undefined symbol or missing include)

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Verify `bank-manifest.json` has an entry for `src/foo.c`.
Do NOT write the C file until this gate passes.

**Step 4: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm the planned API, data types, and any GBDK calls are
correct for this module before writing.

**Step 5: Write minimal implementation**

```c
/* src/foo.c */
#pragma bank 0
#include "foo.h"
/* ... */
```

**Step 6: Run tests to verify they pass**

Run: `make test`
Expected: PASS

**Step 7: HARD GATE — build**

Invoke the `build` skill (or run: `GBDK_HOME=/home/mathdaman/gbdk make`).
Expected: ROM produced at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify bank placements and ROM budgets are within limits.

**Step 9: Commit**

```bash
git add src/foo.c src/foo.h tests/test_foo.c bank-manifest.json
git commit -m "feat: add foo module"
```
````

## Non-C Task Template

Use this template for tasks that do NOT involve `src/*.c` or `src/*.h`:

````markdown
### Task N: [Component Name]

**Files:**
- Create/Modify: `path/to/file.md`

**Step 1: Write the content**

[exact content or diff]

**Step 2: Verify**

[manual check or command]

**Step 3: Commit**

```bash
git add path/to/file.md
git commit -m "feat: add/update X"
```
````

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- Reference skills by name (e.g., `bank-pre-write` skill, `gbdk-expert` agent)
- DRY, YAGNI, TDD, frequent commits
- C files ALWAYS get the 8-step template with all three HARD GATE steps

## Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved to `docs/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Stay in this session
- Fresh subagent per task + code review

**If Parallel Session chosen:**
- Guide them to open new session in worktree
- **REQUIRED SUB-SKILL:** New session uses superpowers:executing-plans

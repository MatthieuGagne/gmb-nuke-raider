# Task Templates

Copy the appropriate template for each task in the plan.

## Hard Gate Sequence (the C-file sequence in summary)

Every task that touches `src/*.c` or `src/*.h` MUST follow this exact sequence — no exceptions.
The template below is this same sequence expanded; the table is the at-a-glance form the plan's
prose refers to.

| Step | Action |
|------|--------|
| 1 | Write failing test (`make test` → FAIL) |
| 2 | Invoke `bank-pre-write` skill (HARD GATE) |
| 3 | Invoke `gbdk-expert` agent (HARD GATE) |
| 4 | Write minimal implementation |
| 5 | Run tests (`make test` → PASS) |
| 6 | Build ROM (`make` → PASS) |
| 7 | Read the post-build gate output (HARD GATE — fires automatically) |
| 8 | Refactor checkpoint ("breaks when N > 1?") |
| 9 | Commit |
| 10 | **Controller, not the implementer** — dispatch the `gb-c-optimizer` agent on the committed diff (HARD GATE). Whatever it reports or edits goes through the task review's fix loop, which commits it before the review is dispatched. |

Steps 2 and 7 name gates that also fire automatically as PreToolUse/PostToolUse hooks; the plan
records them so the implementer knows what must have **reported**. Step 10 is the one step an
implementer does not perform — it is listed because the plan must show the whole sequence, and
because an implementer that sees it listed knows the gate exists and is not being skipped
(#633 R5).

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

## C-File Task Template

Use this template for any task that creates or modifies `src/*.c` or `src/*.h`:

````markdown
### Task N: [Component Name]

**Files:**
- Create: `src/foo.c`, `src/foo.h`
- Test: `tests/test_foo.c`

**Depends on:** none   ← or "Task N, Task M" — tasks whose output this task reads or requires (use task numbers matching plan headings)
**Parallelizable with:** none   ← or "Task N, Task M" — tasks at the same dependency layer (use task numbers matching plan headings)

> **Entity system?** Use SoA (Structure-of-Arrays). Capacity constants in `src/config.h`.
> Never AoS — SDCC cannot eliminate stride multiplication on SM83.

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

Invoke the `build` skill (or run: `make`).
Expected: ROM produced at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — post-build gates**

`tools/post_build_hook.py` runs `make bank-post-build` then `make memory-check` automatically after
a non-clean `make`. Read those verdicts — do not re-run them. Verify bank placements and ROM/memory
budgets are within limits; any FAIL blocks. `post-build-gates` is the fallback reference skill.

**Step 9: Refactor checkpoint**

Ask: "Does this implementation generalize, or did I hard-code something that breaks when N > 1?"
- If generalized: proceed.
- If hard-coded and not fixing now: open a follow-up GitHub issue immediately before closing this task.

**Step 10: Commit**

```bash
git add src/foo.c src/foo.h tests/test_foo.c bank-manifest.json
git commit -m "feat: add foo module"
```

**Step 11: HARD GATE — gb-c-optimizer, dispatched by the controller**

This step is **not yours**. After your commit lands, the controller dispatches the
`gb-c-optimizer` agent on the committed diff. Do not invoke it yourself: your
dispatch forbids you from dispatching subagents, and this is an agent (#633 R5). Its findings
reach you through the task review's fix loop.
````

## Non-C Task Template

Use this template for tasks that do NOT involve `src/*.c` or `src/*.h`:

````markdown
### Task N: [Component Name]

**Files:**
- Create/Modify: `path/to/file.md`

**Depends on:** none   ← or "Task N, Task M" — tasks whose output this task reads or requires (use task numbers matching plan headings)
**Parallelizable with:** none   ← or "Task N, Task M" — tasks at the same dependency layer (use task numbers matching plan headings)

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

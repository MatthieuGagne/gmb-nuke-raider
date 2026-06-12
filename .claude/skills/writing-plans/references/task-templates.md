# Task Templates

Copy the appropriate template for each task in the plan.

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

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify bank placements and ROM budgets are within limits.

**Step 9: Refactor checkpoint**

Ask: "Does this implementation generalize, or did I hard-code something that breaks when N > 1?"
- If generalized: proceed.
- If hard-coded and not fixing now: open a follow-up GitHub issue immediately before closing this task.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke the `gb-c-optimizer` agent on the new/modified C files.
Validate only — report issues, do not apply fixes. Any issues found will be applied during execution (executing-plans / subagent-driven-development phase).

**Step 11: Commit**

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

---
name: gb-memory-validator
description: TRIGGER after every successful ROM build. Invokes the gb-memory-validator agent which checks all four GB hardware budgets (ROM, WRAM, VRAM, OAM) and reports PASS/WARN/FAIL. DO NOT TRIGGER when the build failed or no ROM has been built yet.
---

# GB Memory Validator Skill

## When This Skill Triggers

After a successful `make` — a fresh `build/junk-runner.gb` exists and the build succeeded.

## What to Do

1. Announce: "Running `gb-memory-validator` to check hardware budgets before smoketest."

2. Invoke the `gb-memory-validator` agent:
   ```
   Agent tool → subagent_type: "gb-memory-validator"
   Prompt: "Post-build validation for build/junk-runner.gb in [current worktree path]."
   ```

3. Review the report:
   - **All PASS** → proceed to smoketest.
   - **Any WARN** → proceed to smoketest, note the category in the PR description.
   - **ROM bank FAIL** → **STOP**. Tell the user to bump `-Wm-ya` to the next power of 2 in the Makefile (e.g. `-Wm-ya4` → `-Wm-ya8`). Never hardcode `#pragma bank N`.
   - **WRAM/VRAM/OAM FAIL** → **STOP**. Manual intervention required before proceeding.

## Blocker Behavior

- ROM bank FAIL: hard gate — bump `-Wm-ya` in Makefile, never edit `#pragma bank` lines.
- WRAM/VRAM/OAM FAIL: hard gate — do not proceed until resolved manually.
- WARN: advisory only — document, do not block.

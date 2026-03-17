---
name: gb-memory-validator
description: TRIGGER after every successful ROM build. Invokes the gb-memory-validator agent which checks WRAM, VRAM, and OAM budgets and reports PASS/WARN/FAIL. ROM bank budgets are checked by the bank-post-build skill — run that first. DO NOT TRIGGER when the build failed or no ROM has been built yet.
---

# GB Memory Validator Skill

## When This Skill Triggers

After a successful `make` — a fresh `build/nuke-raider.gb` exists and the build succeeded. Run the `bank-post-build` skill first for ROM bank budget checks.

## What to Do

1. Announce: "Running `gb-memory-validator` to check WRAM/VRAM/OAM budgets before smoketest."

2. Invoke the `gb-memory-validator` agent:
   ```
   Agent tool → subagent_type: "gb-memory-validator"
   Prompt: "Post-build validation for build/nuke-raider.gb in [current worktree path]."
   ```

3. Review the report:
   - **All PASS** → proceed to smoketest.
   - **Any WARN** → proceed to smoketest, note the category in the PR description.
   - **WRAM/VRAM/OAM FAIL** → **STOP**. Manual intervention required before proceeding.

## Blocker Behavior

- WRAM/VRAM/OAM FAIL: hard gate — do not proceed until resolved manually.
- WARN: advisory only — document, do not block.
- ROM bank FAIL: handled by `bank-post-build` skill, not this agent.

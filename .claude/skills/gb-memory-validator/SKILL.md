---
name: gb-memory-validator
description: TRIGGER after every successful ROM build. Runs `make memory-check` and reports PASS/WARN/FAIL for WRAM, VRAM, and OAM budgets. ROM bank budgets are checked by the bank-post-build skill — run that first. DO NOT TRIGGER when the build failed or no ROM has been built yet.
---

# GB Memory Validator Skill

## When This Skill Triggers

After a successful `make` — a fresh `build/nuke-raider.gb` exists and the build succeeded. Run the `bank-post-build` skill first for ROM bank budget checks.

## What to Do

1. Announce: "Running `make memory-check` to validate WRAM/VRAM/OAM budgets."

2. Run the script (from the worktree directory):
   ```bash
   make memory-check
   ```

3. Report the full output to the user.

4. Review the result:
   - **All PASS** → proceed to smoketest.
   - **Any WARN** → proceed to smoketest, note the category in the PR description.
   - **Any FAIL or ERROR** → **STOP**. Manual intervention required before proceeding.

## Blocker Behavior

- WRAM/VRAM/OAM FAIL: hard gate — do not proceed until resolved manually.
- ERROR (map symbol missing): treat as FAIL — ROM may not be built correctly.
- WARN: advisory only — document, do not block.
- ROM bank FAIL: handled by `bank-post-build` skill, not this script.

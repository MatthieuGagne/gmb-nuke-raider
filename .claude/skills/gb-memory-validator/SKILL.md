---
name: gb-memory-validator
description: TRIGGER after every successful ROM build, before running the smoketest or creating a PR. Invokes the gb-memory-validator agent to check all four GB hardware budgets (ROM, WRAM, VRAM, OAM). DO NOT TRIGGER when no ROM has been built yet or when the build failed.
---

# GB Memory Validator Skill

## When This Skill Triggers

After step 2 (Rebuild) of the smoketest gate — a fresh `build/junk-runner.gb` exists and the build succeeded.

## What to Do

1. Announce: "Running `gb-memory-validator` to check hardware budgets before smoketest."

2. Invoke the `gb-memory-validator` agent:
   ```
   Agent tool → subagent_type: "gb-memory-validator"
   Prompt: "Validate all GB memory budgets for build/junk-runner.gb in the current worktree."
   ```

3. Review the report:
   - **All PASS** → proceed to smoketest (step 3 of the smoketest gate).
   - **Any WARN** → proceed to smoketest, but note the category in your PR description so it's tracked.
   - **Any FAIL** → **STOP**. Do not launch the emulator. Fix the overrun first, rebuild, and re-run this skill.

## Blocker Behavior

A FAIL result is a hard gate — do not proceed to smoketest or PR creation until resolved.

A WARN is advisory — document it, do not block.

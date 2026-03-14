---
name: gb-memory-validator
description: TRIGGER after every successful ROM build. Invokes the proactive gb-memory-validator agent which checks all four GB hardware budgets (ROM, WRAM, VRAM, OAM) and auto-fixes ROM bank pressure by editing source files. DO NOT TRIGGER when the build failed or no ROM has been built yet.
---

# GB Memory Validator Skill

## When This Skill Triggers

After step 2 (Rebuild) of the smoketest gate — a fresh `build/junk-runner.gb` exists and the build succeeded.

Note: the pre-build phase (Phase 1) runs automatically inside the `build` skill — no separate trigger needed for that.

## What to Do

1. Announce: "Running `gb-memory-validator` to check hardware budgets before smoketest."

2. Invoke the `gb-memory-validator` agent (Phase 2 — post-build):
   ```
   Agent tool → subagent_type: "gb-memory-validator"
   Prompt: "Run Phase 2 post-build validation for build/junk-runner.gb in [current worktree path]."
   ```

3. Review the report:
   - **All PASS** → proceed to smoketest.
   - **Any WARN** → proceed to smoketest, note the category in the PR description.
   - **ROM bank FAIL** → the agent will attempt auto-fix (editing `#pragma bank` lines) and rebuild. If it succeeds, proceed to smoketest. If it cannot auto-fix, **STOP** and report to user.
   - **WRAM/VRAM/OAM FAIL** → **STOP**. The agent does not auto-fix these. Manual intervention required before proceeding.

## Blocker Behavior

- ROM bank FAIL: agent handles automatically. Only blocks if no safe candidates exist.
- WRAM/VRAM/OAM FAIL: hard gate — do not proceed until resolved manually.
- WARN: advisory only — document, do not block.

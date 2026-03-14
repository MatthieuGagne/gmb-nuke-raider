---
name: build
description: Use this skill to build the GBC ROM. Triggers when verifying a build, checking for compiler errors, or confirming the ROM was produced after making changes.
---

Three-step flow: pre-build analysis → build → post-build validation.

Determine the current worktree path (e.g. from `git rev-parse --show-toplevel` or the known worktree directory). Pass it to agent prompts so the agent uses the correct `build/` and `src/` directories.

## Step 1 — Pre-Build: Invoke gb-memory-validator (Phase 1)

```
Agent tool → subagent_type: "gb-memory-validator"
Prompt: "Run Phase 1 pre-build analysis for build/junk-runner.gb in [worktree path]."
```

- If agent reports **PASS** or applied **AUTO-FIX**: proceed to Step 2 (agent may have already edited source files).
- If agent reports it cannot auto-fix (no safe candidates, or WRAM/VRAM/OAM issue): **STOP**. Report to user. Do not build.

## Step 2 — Build

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```

Run from the worktree directory.

**On failure:** Extract lines containing `"error:"` from the output. Show each as `file:line: message`. Distinguish compiler errors (fixable in source) from linker errors. Identify which file to look at first. Do not attempt to fix compile errors automatically unless the user asks.

**On success:** Proceed to Step 3.

## Step 3 — Post-Build: Invoke gb-memory-validator (Phase 2)

```
Agent tool → subagent_type: "gb-memory-validator"
Prompt: "Run Phase 2 post-build validation for build/junk-runner.gb in [worktree path]."
```

- **All PASS** → report ROM size (`ls -lh build/junk-runner.gb`). Done.
- **AUTO-FIX applied** → report what moved; rebuild is already done inside the agent. Report final ROM size.
- **FAIL not auto-fixable** (WRAM/VRAM/OAM) → **STOP**. Report to user. Manual intervention required.

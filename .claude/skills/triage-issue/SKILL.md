---
name: triage-issue
description: "Bug investigation skill: gather symptoms, find root cause (module + ROM bank), write a TDD RED-GREEN fix plan, and create a GitHub issue. GB-adapted: root cause must name the bank; fix plan includes bank-pre-write gate. Use when a bug needs to be tracked and fixed with a test-first approach."
---

# Triage Issue

## Overview

Turn a bug report into an actionable GitHub issue with a TDD-first fix plan. The output is a GitHub issue that a future session can execute using `writing-plans` + `executing-plans`.

## Step 1: Gather Symptoms

Ask the user (or infer from context) for:
- **What fails:** exact symptom (visual glitch, crash, wrong value, missing behavior)
- **How to reproduce:** steps or conditions that trigger the bug
- **Expected behavior:** what should happen
- **Observed behavior:** what actually happens
- **Frequency:** always, sometimes, specific conditions

If the user has already described the bug, skip questions that are already answered.

## Step 2: Explore the Codebase

Before proposing a root cause, explore the code:
- Find the relevant module (`src/<module>.c`) and its header
- Identify which ROM bank the module is in (check `bank-manifest.json` or `#pragma bank` in the file)
- Trace the execution path from input to symptom
- Check for related tests in `tests/test_<module>.c`

Ask one clarifying question at a time if the codebase exploration doesn't resolve ambiguity.

## Step 3: Identify Root Cause

State the root cause concisely:
- **Module:** `src/<module>.c`
- **Bank:** N (from `bank-manifest.json`)
- **Location:** function name + approximate line
- **Cause:** one sentence describing what is wrong

If the root cause cannot be determined from static analysis, note what emulator inspection is needed (invoke the `emulicious-debug` skill).

## Step 4: Write the TDD Fix Plan

Structure the fix plan as RED-GREEN cycle(s):

```
### RED — Failing test

File: `tests/test_<module>.c`

Write a test that reproduces the bug:
```c
void test_<module>_<behavior>(void) {
    /* setup */
    /* call function under test */
    TEST_ASSERT_EQUAL_UINT8(expected, actual);
}
```

Run: `make test`
Expected: FAIL — test demonstrates the bug.

### HARD GATE — bank-pre-write

Before touching `src/<module>.c`, invoke the `bank-pre-write` skill.
Verify `bank-manifest.json` has a correct entry for `src/<module>.c`.

### GREEN — Fix

Minimal change to `src/<module>.c` that makes the test pass.
Do NOT fix unrelated issues in this cycle.

Run: `make test`
Expected: PASS — test and all others green.

### Build verification

Run: `GBDK_HOME=/home/mathdaman/gbdk make`
Expected: Zero errors, ROM produced at `build/nuke-raider.gb`.
```

If the fix requires multiple cycles (multiple functions to change), repeat the RED-GREEN block for each.

## Step 5: Create GitHub Issue

Create the issue using `gh`:

```bash
gh issue create --title "fix: <one-line description>" --body "$(cat <<'EOF'
## Symptom
<what fails, how to reproduce>

## Root Cause
- **Module:** `src/<module>.c`
- **Bank:** N
- **Location:** `<function>` (~line N)
- **Cause:** <one sentence>

## TDD Fix Plan
<paste the RED-GREEN cycle(s) from Step 4>

## Acceptance Criteria
- [ ] Failing test added that demonstrates the bug
- [ ] Fix makes the test pass
- [ ] All other tests still pass
- [ ] Clean ROM build succeeds
- [ ] Smoketest in Emulicious confirms fix

## Notes
<!-- Any additional context, related issues, or follow-up items -->
EOF
)"
```

Report the issue URL to the user.

## Coherence Notes

- This skill does NOT invoke `writing-plans` or `executing-plans` — the fix plan is embedded in the GitHub issue body and executed in a separate session.
- If the root cause requires emulator inspection, invoke `emulicious-debug` in Step 3 before writing the fix plan.
- The `bank-pre-write` gate is noted in the fix plan but enforced at execution time by `executing-plans` / `bank-pre-write` skill — not here.

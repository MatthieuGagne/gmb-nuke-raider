---
name: debug
description: Use when encountering any bug, test failure, or unexpected behavior — before proposing fixes. Enforces hypothesis-queue-first debugging with hard rules against fixation and cascading regressions. Shadows global systematic-debugging with GBC-specific tooling and a 3-strikes halt rule.
---

# debug — Structured Hypothesis-Driven Debugging

## The Iron Law

```
NO FIXES WITHOUT A VISIBLE, APPROVED HYPOTHESIS QUEUE FIRST
```

**Never touch code, instrument, or propose a fix until:**
1. You have a ranked list of hypotheses
2. The user has approved that list
3. You have stated which hypothesis you are currently testing

---

## Entry Modes

### Mode A: Start of Session

Use when beginning a new bug investigation.

Ask the user (one question at a time):
1. "What is the GitHub issue number for this bug?"
2. "Describe the symptom in one sentence: what do you observe, and when?"
3. "Which hypotheses have you already ruled out? (list them, or say 'none')"

Then:

**Generate a ranked hypothesis queue** — ordered most-likely to least-likely. Format:

```
Hypothesis Queue (pending user approval):
1. [Most likely] <hypothesis> — reasoning: <why>
2. [Likely]      <hypothesis> — reasoning: <why>
3. [Possible]    <hypothesis> — reasoning: <why>
...

Ruled out (will not re-test): <list from user>
```

**STOP. Show queue to user. Do not proceed until they approve.**

If the user asks to reorder or add/remove hypotheses, update and show again.

### Mode B: Mid-Session Interrupt

Use when already mid-investigation and going in circles, or when the user types `/debug` to reset.

1. **Snapshot current state** — state out loud:
   - Active hypothesis: X
   - Attempt count: N
   - Observations so far: (list)
2. **Halt current hypothesis** — do not make any further changes for it
3. **Re-enumerate** remaining untested hypotheses (updated with any new observations)
4. **Pick next highest-probability** and confirm with user before proceeding

---

## Per-Hypothesis Loop

For each hypothesis in the queue:

**Before touching anything:**
- State: "Testing hypothesis N: <text>"
- State: "Instrumentation plan: <exactly what I will add/change to test this>"
- Wait for implicit or explicit user go-ahead

**Then:**
1. Add instrumentation (use `emulicious-debug` agent for GBC runtime inspection)
2. Build: `make clean && GBDK_HOME=/home/mathdaman/gbdk make`
3. Run: launch ROM in Emulicious, observe output/behavior
4. Conclude: one of:
   - **Confirmed** — hypothesis is the root cause, proceed to fix
   - **Ruled out** — add to ruled-out list, advance queue
   - **Inconclusive** — refine instrumentation, count as attempt

---

## Expert Routing

When a hypothesis is **Confirmed** (or when instrumentation requires domain expertise), classify the hypothesis type and dispatch to the appropriate expert agent(s) using the Agent tool. Fire parallel agents when the routing table lists two agents.

| Hypothesis type | Agent(s) to dispatch | Notes |
|----------------|---------------------|-------|
| Sprite / OAM / palette issue | `sprite-expert` agent + `emulicious-debug` agent | Parallel |
| Map / tileset / BG rendering | `map-expert` agent + `emulicious-debug` agent | Parallel |
| Music / audio | `music-expert` agent + `emulicious-debug` agent | Parallel |
| Performance / ROM size / bank overrun | `gb-c-optimizer` agent + `bank-post-build` skill | Parallel |
| Regression ("worked in PR X, broken now") | `compare-prs` skill | Sequential |
| Runtime memory / registers / VRAM | `emulicious-debug` agent | Single |
| Compile error / GBDK API misuse | `gbdk-expert` agent | Single |

**Conflicting findings:** When parallel agents return contradictory conclusions, surface both findings to the user verbatim and ask for direction. Do NOT attempt to reconcile conflicting findings autonomously.

---

## Hard Rules

| Rule | Detail |
|------|--------|
| Never re-test a ruled-out hypothesis | Once ruled out, it stays ruled out |
| One variable per test | Never make two changes between test runs |
| 3-strikes halt | After 3 consecutive failed/inconclusive attempts on ANY hypothesis: halt, post findings to the GitHub issue, ask user for direction |

### 3-strikes action

When triggered:
1. Post a findings comment to the GitHub issue:
   ```bash
   gh issue comment <N> --repo MatthieuGagne/gmb-nuke-raider --body "..."
   ```
   Include: symptom, all tested hypotheses + outcomes, current observations, what remains untested
2. Say: "I've hit 3 consecutive inconclusive attempts. Findings posted to issue #N. What direction would you like to take?"
3. Do NOT push forward

---

## Instrumentation Tools

- **`emulicious-debug`** agent — step-through debugger, EMU_printf, memory/tile/sprite inspection, tracer, profiler
- **`/compare-prs <N>`** skill — for "worked in PR X, broken now" hypotheses: builds both, lets you compare ROMs and diffs side-by-side

---

## Notes

- Motivation: the ~33s stall bug investigation spanned 5+ sessions. Claude fixated on music/order_cnt, introduced a worse crash (26s stall), and dismissed the new symptom as the known issue. This skill prevents all three failure modes.
- Stateless across sessions — each invocation starts from what the user provides in Mode A
- This skill shadows the global `systematic-debugging` skill for this project

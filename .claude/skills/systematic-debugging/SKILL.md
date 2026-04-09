---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior — before proposing fixes. Enforces hypothesis-queue-first debugging with hard rules against fixation and cascading regressions. Shadows global systematic-debugging with GBC-specific tooling and a 3-strikes halt rule.
---

# debug — Structured Hypothesis-Driven Debugging

## The Iron Law

```
NO FIXES WITHOUT A VISIBLE, APPROVED HYPOTHESIS QUEUE FIRST
NO HYPOTHESIS IS APPROVABLE WITHOUT A confirm_when ARTIFACT
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
4. "Describe the exact reproduction steps: what do you do in the emulator and what do you observe?"

Question 4 is locked in before any investigation begins — do not proceed to hypothesis generation until the user answers it.

Then:

**Generate a ranked hypothesis queue** — ordered most-likely to least-likely. Format:

```
Hypothesis Queue (pending user approval):
1. [Most likely] <hypothesis> — reasoning: <why>
   confirm_when: <specific artifact> = <expected value or timing>
2. [Likely]      <hypothesis> — reasoning: <why>
   confirm_when: <specific artifact> = <expected value or timing>
3. [Possible]    <hypothesis> — reasoning: <why>
   confirm_when: <specific artifact> = <expected value or timing>
...

Ruled out (will not re-test): <list from user>
```

**confirm_when validity rule:**
A valid `confirm_when` MUST name at least one of: a specific variable/symbol, a hardware register, an `EMU_printf` output string, or a memory address — AND state the expected value or timing.

Valid examples:
- `confirm_when: EMU_printf "order_cnt=N" appears with N > 3 at the ~24s mark`
- `confirm_when: LCDC register reads 0x91 at frame 120`
- `confirm_when: WRAM address 0xC0A2 holds 0x00 after sp_exit()`

Invalid examples (vague — not approvable):
- `confirm_when: behavior improves`
- `confirm_when: crash disappears`
- `confirm_when: game runs better`

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
4. Conclude — one of:

| Outcome | Meaning | Next action |
|---------|---------|-------------|
| **Confirmed + clean** | `confirm_when` artifact observed; fix applied; original symptom gone; no new symptoms | Proceed — done |
| **Confirmed + shifted** | `confirm_when` artifact observed; fix applied; original symptom gone but **new symptom appeared** | See Shifted Symptom Handling below |
| **Ruled out** | Hypothesis is not the cause | Add to ruled-out list, advance queue |
| **Inconclusive** | Cannot determine yet | Refine instrumentation; counts as an attempt toward 3-strikes |

---

### Post-Fix Verification (mandatory after every fix)

Run after any fix is applied, before declaring success.

**Step 1 — Re-run reproduction scenario**
Observe for `crash_time + 30s` (or 60s if `crash_time` is unknown).
Confirm the `confirm_when` artifact is now absent.
- If fix had no effect (artifact still present) → counts as a **strike** against the hypothesis (see 3-strikes rule). Do not apply further changes — advance the queue.

**Step 2 — Shifted symptom check**
Observe for any new abnormal behavior during the same window.
- No new behavior → outcome is **Confirmed + clean**.
- New behavior observed → outcome is **Confirmed + shifted** (see Shifted Symptom Handling below).

---

### Shifted Symptom Handling

When outcome is **Confirmed + shifted**:

1. Declare out loud: `"Symptom shifted: <old symptom description> → <new symptom description>"`
2. Insert a new hypothesis for the new symptom at the **top** of the remaining queue (position 1), with:
   - Fresh strike counter (starts at 0)
   - `confirm_when` field required immediately — do not begin instrumentation until it is written and user-approved
3. **Confirmed + shifted does NOT count as a strike** against the original hypothesis — the fix correctly resolved the root cause; the new symptom is a separate bug.

---

## Expert Routing

When a hypothesis is **Confirmed + clean** or **Confirmed + shifted** (or when instrumentation requires domain expertise), classify the hypothesis type and dispatch to the appropriate expert agent(s) using the Agent tool. Fire parallel agents when the routing table lists two agents.

| Hypothesis type | Agent(s) to dispatch | Notes |
|----------------|---------------------|-------|
| Sprite / OAM / palette issue | `sprite-expert` agent + `emulicious-debug` agent | Parallel |
| Map / tileset / BG rendering | `map-expert` agent + `emulicious-debug` agent | Parallel |
| Music / audio | `music-expert` agent + `emulicious-debug` agent | Parallel |
| Performance / ROM size / bank overrun | `gb-c-optimizer` agent + `bank-post-build` skill | Parallel |
| Autobanker reassignment (data added to a full bank → autobanker pushes a file to a new bank → BANKED functions that assumed co-location silently read garbage) | `bank-post-build` skill + `gbdk-expert` agent | Compare `___bank_*` symbols in `.noi` between master and branch; fix: route reads through NONBANKED helpers in `loader.c` |
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
| **Confirmed + shifted ≠ strike** | Shifting a symptom is not a failed attempt. Only "fix had no effect" (artifact still present after post-fix verification) counts as a strike. |

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
- This skill is the local `systematic-debugging` skill, shadowing the global superpowers version with GBC-specific tooling

## GBC-Specific Diagnostic Hints

**Static WRAM symbol lookup:** SDCC does not export `static` file-scope variable names to the `.map` symbol table — `find_wram_sym_from_map` only works for non-static globals. For `static` WRAM variables, use `find_wram_read_in_fn(noi_path, rom_path, "_getter_fn")` from `tests/integration/helpers.py`. It decodes the getter function's disassembly from the ROM binary to locate the `LD A,(nn)` opcode and extract the WRAM address. Formula: `bank = noi_addr >> 16; phys = gb_addr if bank == 0 else (bank-1)*0x4000 + gb_addr`.

**"Grey screen, game logic running, text invisible" → check scroll registers first:** The VBL ISR in `main.c` calls `move_bkg(cam_scx_shadow, cam_scy_shadow)` every frame unconditionally. Any state entered after `state_playing` inherits the race's final scroll offset unless `sp_exit()` resets `cam_scx_shadow = 0u; cam_scy_shadow = 0u`. Before assuming a VRAM or palette bug, read `SCY`/`SCX` in Emulicious — non-zero values mean the tilemap is rendering off-screen.

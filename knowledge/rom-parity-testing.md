---
summary: test_rom_parity.py release-vs-debug ROM byte comparison — relocation classification, HOME trampoline shifts, CALL operand diffs, compared-banks derivation, byte-budget history (#590 Task 4 ruling)
tags: [rom-parity, debug, testing, trampoline, relocation, banks]
---

# ROM parity testing (release vs debug)

`tests/test_rom_parity.py` proves the debug build changes nothing real in the shipped
banks. Companion pages: [[dbg-static-visibility]] (what the debug build adds) and
[[autobank-symbol-placement]] (why HOME-bank layout shifts ripple into banks 1–3).

## Current invariants (RULING, #590 Task 4)

The coordinator ruled the fixed-64-byte / exactly-2-byte-run rom-parity invariant was
itself wrong, not the feature. `tests/test_rom_parity.py` now asserts three properties
instead:

1. Every differing byte, at alignment `p ∈ {i, i-1}`, has an unchanged opcode byte at
   `p-1` and both ROMs' 16-bit little-endian value at `(p,p+1)` is a HOME address
   (`< 0x4000`) — no opcode whitelist, so it also covers the `LD A,(nn)`/`LD rr,nn`
   new-trampoline preamble, not just `CALL`/`JP`.
2. The release→debug address mapping is a consistent function (one release address
   can't resolve to two debug addresses) — `_aggregate_relocations()` is a standalone
   testable helper for this.
3. At most `MAX_DISTINCT_RELOCATED_TARGETS = 128` distinct relocated HOME addresses
   (today 40) — replaces the byte-count budget with a measure of how much of HOME
   moved, not how many call sites reference it (which scales with feature count, not
   with correctness).

`_classify_bank_diff()` and `_relocation_at()` are the other two reusable helpers.
"Prove it bites" for this class of test: mutate in-memory `bytearray` copies of a real
bank (never the real `.gb` file) — flip a byte in a 4-byte-agreeing run for check-1,
fabricate a second `(same rel_target, different dbg_target)` tuple for check-2 — and
confirm a control run against the unmutated bytes shows zero findings first. (See
[[verification-techniques]] for the general technique family.)

## Superseded byte-budget era — kept for the byte-level diagnostic technique

A debug-only module's first-ever calls to previously-uncalled `BANKED` functions blow a
fixed rom-parity byte budget, even though every diff is a legitimate relocation (#590
Task 4). The old `test_rom_parity.py` compared release vs debug ROM banks 1–3 and
tolerated only 2-byte differing runs (an absolute `CALL`/`JP nn` operand shifted by a
HOME-trampoline insertion) under a fixed total-byte cap (64, calibrated at 32 for Task
3's 2-function addition). Adding a dispatcher (`src/debug.c`, bank 30,
`#ifdef DEBUG_MAILBOX`) that calls `turret_spawn`, `turret_despawn`,
`loadout_set_car/armor/weapon1/weapon2` — six functions with **zero prior cross-bank
callers anywhere in the codebase** — forces SDCC to emit six brand-new HOME trampolines
that exist **only in the debug ROM** (the release ROM compiles the whole file to an
inert typedef). That HOME-layout growth shifts the address of every HOME routine placed
after it, rippling into far more call sites than a small function count suggests,
blowing the byte budget from 32 to 429.

Grep every candidate function's `src/` call sites before wiring a debug dispatcher to
it: if its only call site becomes the new debug code, expect a NEW trampoline (not a
reused one), and budget accordingly — `loadout_set_car` etc. had never been called
outside `loadout_cycle_*`'s private `cycle()` helper, so they were "free" functions
with no prior calling-convention cost.

**Two failure shapes to distinguish when diagnosing:**

- (a) a run whose length is not a multiple the test expects but both bytes still form a
  `<0x4000` target after a same-opcode `CALL`/`JP` — genuine relocation, just with a
  same-high-byte address so only 1 byte visibly changed;
- (b) `LD A,(nn)` (0xFA) followed later by `LD DE,nn` (0x11) — SDCC's two-instruction
  preamble for a call site's *first-ever* target (reads the target's bank number from a
  `___bank_X` cell, then loads the trampoline's HOME address into DE) — not in
  `ABSOLUTE_CALL_JUMP_OPCODES`'s allowlist but still benign.

Classify every offset before concluding a parity failure is real code drift:
`runs = _consecutive_runs(diffs)`; for each length-1 run check byte at `start-1` is a
call/jump opcode AND the byte at `start+1` is IDENTICAL between ROMs (proves only the
low half of the operand shifted) AND the reconstructed 16-bit target is `< 0x4000` on
both sides. Do not raise the cap or widen the opcode allowlist unilaterally if the task
brief forbids it — the pre-commit hook runs the full `unittest discover` suite
(including this test) with `--no-verify` forbidden, so this is a hard,
unroutable-around blocker, not a style nit.

## Derive the compared-banks list, don't hardcode it (#590 final review item 10)

Deriving a "which ROM banks hold real game data" list instead of hardcoding it found an
extra bank the assumption missed, and the extra bank was harmless to include.
`tests/test_rom_parity.py`'s `COMPARED_BANKS = (1, 2, 3)` became
`_compared_banks(release_path)`: every bank in `range(1, total)` that isn't
`MAILBOX_BANK` (30) and isn't uniform (`len(set(bank_bytes)) > 1`) in the release ROM.
The literal rule also picks up bank 31 (`src/music_data.c`, pinned by hand, not
autobanked — see bank-manifest.json) because it's real (non-uniform) data, giving
`(1, 2, 3, 31)` today, not `(1, 2, 3)`. Measuring both sets side-by-side
(`_classify_bank_diff`/`_aggregate_relocations` over each) showed bank 31 contributes
exactly 0 differing bytes today (no BANKED trampoline lands there), so adding it to the
scan changed none of the other counts (unexplained/relocated/targets/deltas identical).
When a task brief assumes a specific derived value, measure before writing the
confirming test — don't force the assertion to match the brief's assumption if the
honest derivation disagrees; report the discrepancy instead.

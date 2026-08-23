---
name: gbdk-pre-write
description: "TRIGGER when: writing or editing any src/*.c or src/*.h file, using GBDK API functions, touching hardware registers, sprite/tile/palette/VBlank/interrupt/banking code, or hitting a GBDK compilation error. Sibling gate to bank-pre-write. DO NOT TRIGGER when: editing Python pipeline scripts, Tiled maps, Makefile, or any non-C work."
---

# GBDK Pre-Write Checklist

For deep hardware reference: **https://gbdev.io/pandocs/single.html** (fetch with a targeted
prompt when uncertain about any register, timing, or spec detail).

**Before writing any `src/*.c` / `src/*.h`:**

1. Headers: `gb/gb.h` (core), `gb/cgb.h` (CGB palettes), `gb/hardware.h` (raw regs), `stdio.h`
   for `printf`
2. No compound literals `(const T[]){...}` — use named `static const` arrays
3. Anything banking-related (bank pragma vs `bank-manifest.json`, `SET_BANK`/`SWITCH_ROM`
   placement, `BANKED` on cross-bank calls) → the `bank-pre-write` gate owns these rules and
   fires automatically on write
4. Entity pools → SoA (Structure-of-Arrays), not AoS; capacity constants in `config.h`
5. For everything else — deep hardware specs (OAM, palettes, PPU modes, interrupts), the VBlank
   ordering rule, SDCC traps, the host-test mock requirement, and implementation mode itself —
   dispatch the **`gbdk-expert` agent**. It is the authority; this checklist is only the
   pre-write skim.

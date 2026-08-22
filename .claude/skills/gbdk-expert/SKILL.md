---
name: gbdk-expert
description: "TRIGGER when: writing or editing any src/*.c or src/*.h file, using GBDK API functions, touching hardware registers, sprite/tile/palette/VBlank/interrupt/banking code, or hitting a GBDK compilation error. DO NOT TRIGGER when: editing Python pipeline scripts, Tiled maps, Makefile, or any non-C work."
---

# GBDK Expert — Pre-Write Checklist

For deep hardware reference: **https://gbdev.io/pandocs/single.html** (fetch with a targeted prompt when uncertain about any register, timing, or spec detail).

**Before writing any `src/*.c` / `src/*.h`:**
1. Headers: `gb/gb.h` (core), `gb/cgb.h` (CGB palettes), `gb/hardware.h` (raw regs), `stdio.h` for `printf`
2. All VRAM writes inside VBlank — always guard with `wait_vbl_done()` unless `DISPLAY_OFF`
3. No `malloc`/`free` — static allocation only; no `float`/`double` — use fixed-point integers
4. No compound literals `(const T[]){...}` — use named `static const` arrays
5. Prefer `uint8_t` loop counters; large locals (>64 B) → `static` or global to avoid stack overflow
6. Anything banking-related (bank pragma vs `bank-manifest.json`, `SET_BANK`/`SWITCH_ROM` placement, `BANKED` on cross-bank calls) → the `bank-pre-write` gate owns these rules and fires automatically on write
7. Entity pools → SoA (Structure-of-Arrays), not AoS; capacity constants in `config.h`
8. For deep hardware specs (OAM, palettes, PPU modes, interrupts, banking) → use `gbdk-expert` agent
9. If a new GBDK API function is added to `src/`, grep `tests/mocks/gb/gb.h` for it — if missing, add a `static inline` no-op stub before committing or `make test` will fail with "undefined reference"

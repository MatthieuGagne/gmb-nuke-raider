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
6. Bank pragma must match `bank-manifest.json` (bank-pre-write hook validates automatically on write)
7. No `SET_BANK`/`SWITCH_ROM` in banked files — route through `loader.c` (bank-0 only)
8. Entity pools → SoA (Structure-of-Arrays), not AoS; capacity constants in `config.h`
9. For deep hardware specs (OAM, palettes, PPU modes, interrupts, banking) → use `gbdk-expert` agent

# src/ — C coding rules (loads when editing source)

Authoritative copy with rationale lives in [`docs/dev-workflow.md`](../docs/dev-workflow.md) §4.

## Scalability Conventions (every feature, no matter how small)

- **Module structure:** each system gets its own `.c`/`.h` pair. New-module checklist: public API in `.h`, all state `static` in `.c`, `tests/test_<system>.c` written first (TDD), `gb-c-optimizer` review-and-fix before merge.
- **Entity management:** no singletons for things that could multiply — fixed-size pools with an `active` flag. Use **Structure-of-Arrays (SoA)**, not Array-of-Structs (AoS). Capacity constants live in `src/config.h`.
  ```c
  /* SoA canonical template — one array per field */
  #define MAX_ENEMIES 8
  static uint8_t enemy_x[MAX_ENEMIES];
  static uint8_t enemy_y[MAX_ENEMIES];
  static uint8_t enemy_active[MAX_ENEMIES];
  static uint8_t enemy_type[MAX_ENEMIES];
  ```
- **Refactor checkpoint (before closing any task):** "Does this generalize, or did we hard-code something that breaks when N > 1?" If hard-coded and not fixing now → open a follow-up issue.
- **YAGNI balance:** don't pre-build systems for nonexistent features; DO apply the entity-pool pattern at first instance (not second).

## Memory budgets

- OAM: 40 sprites total (player = 2; budget the rest for enemies/projectiles/HUD)
- VRAM: 192 tiles (DMG bank 0) + 192 (CGB bank 1 for color variants)
- WRAM: 8 KB — large arrays must be global or `static`, never local
- ROM: MBC5, 32 banks declared (`-Wm-ya32`), up to 512 KB — assets tagged for banking, code stays in bank 0

## GBDK / SDCC constraints

- **No compound literals**: SDCC rejects `(const uint16_t[]){...}` — use named `static const` arrays.
- **`printf`** requires `#include <stdio.h>`, not just `<gbdk/console.h>`.
- **No `malloc`/`free`**: static allocation only.
- **No `float`/`double`**: use fixed-point integers.
- **Large local arrays** (>~64 bytes) risk stack overflow — use `static` or global.
- Prefer `uint8_t` loop counters over `int`.
- All VRAM writes must occur during VBlank; use `wait_vbl_done()` or a VBlank ISR.
- Only bank-0 files (no `#pragma bank`) may call `SET_BANK` / `SWITCH_ROM`.
- Warning "conditional flow changed by optimizer: so said EVELYN" is harmless.

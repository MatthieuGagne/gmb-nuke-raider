---
name: rom-banking
description: Use when the ROM shows a blank screen at low FPS (~2 FPS), when questions arise about ROM memory management, bank assignments, or where to place new data assets in Nuke Raider.
---

# ROM Banking — Nuke Raider

## The Critical Constraint

`state_manager` dispatches states via **plain (non-BANKED) function pointers**. `state_manager_update()` is `BANKED` — it switches to bank 1, then calls `stack[depth-1]->update()` as a plain jump. If the target function landed in bank 2, the wrong bytes execute → blank-screen crash at ~2 FPS.

**All state code (`state_*.c`, `state_manager.c`) must stay in bank 1.**

## Bank Budget

| Bank | Used  | Notes |
|------|-------|-------|
| ROM_0 | ~46% | Fixed/HOME code, always mapped |
| ROM_1 | ~100% | All autobanked modules — overflows naturally into bank 2+ |
| ROM_2 | ~5%  | Autobank overflow + portrait data (explicit `#pragma bank 2`) |

Total autobanked data: ~16,370 + 788 bytes across banks 1–2 (MBC5, 16 banks declared).

## Diagnosing Bank Overflow

**Symptom:** Blank screen, ~2 FPS, game never progresses past boot.

```sh
# Step 1: Check bank percentages
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -a

# Step 2: Find symbols placed in bank 2+ — state_* code here = crash
grep "024[0-9A-Fa-f]\{3\}" build/nuke-raider.map
```

If `_state_ti`, `_state_hu`, `_state_pl`, `_state_ov` appear at `0x024xxx` addresses, bank 1 overflowed and the game will crash at boot.

## Fix: Move Data Files to Explicit Banks

Data-only assets (portraits, tilesets, maps) must NOT use `#pragma bank 255` — that puts them in the autobank pool competing with state code for bank 1 space.

```c
// ❌ BAD — competes with state code for bank 1
#pragma bank 255

// ✅ GOOD — goes directly to bank 2, never touches bank 1
#pragma bank 2
```

`BANKREF` / `BANK()` / `SET_BANK()` resolve correctly at link time regardless of whether the file uses `255` or an explicit number. No changes needed in callers or headers.

## Asset Banking Rules

| Asset type | Pragma | Reason |
|------------|--------|--------|
| `npc_*_portrait.c` | `#pragma bank 2` | Pure data, large |
| `*_tiles.c` (generated) | `#pragma bank 2` | Pure data, large |
| `*_map.c` (generated) | `#pragma bank 2` | Pure data, large |
| State modules (`state_*.c`) | `#pragma bank 255` | Must stay in bank 1 with state_manager |
| Music data | check — may be large | If bank 1 is tight, move to explicit bank |

## Checklist: After Adding Any Large Asset

1. Build: `GBDK_HOME=/home/mathdaman/gbdk make`
2. Check bank 1: `romusage build/nuke-raider.gb -a` → if bank 1 ≥ 95%, act now
3. Check for state code overflow: `grep "024[0-9A-Fa-f]\{3\}" build/nuke-raider.map`
4. If state code appears in bank 2+: find the largest new data file, change it to `#pragma bank 2`, rebuild

## Autobanker Behavior

- `#pragma bank 255` → bankpack assigns automatically, fills bank 1 first, then bank 3+ if bank 2 is explicitly used
- `#pragma bank 2` → linker places in bank 2 directly; bankpack does not touch it
- Explicit and autobanked files coexist; bankpack fills auto-banks around the explicit ones
- Bank 2 explicit data does **not** get mixed with bank 2 autobank overflow — autobank overflow goes to bank 3+

## Why BANKED Function Pointers Aren't the Fix

CLAUDE.md documents that `void (*fn)(void) BANKED` in a struct field is **broken on SDCC/SM83**: it generates double-dereference code (reads 2 bytes from the function's address, then jumps there → garbage). The correct fix is to keep all state code in bank 1, not to add `BANKED` to the struct fields.

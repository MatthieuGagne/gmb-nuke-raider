---
name: rom-banking
description: Use when the ROM shows a blank screen at low FPS (~2 FPS), when questions arise about ROM memory management, bank assignments, or where to place new data assets in Junk Runner.
---

# ROM Banking — Junk Runner

## The Critical Constraint

`state_manager` dispatches states via **plain (non-BANKED) function pointers**. `state_manager_update()` is `BANKED` — it switches to bank 1, then calls `stack[depth-1]->update()` as a plain jump. If the target function landed in bank 2, the wrong bytes execute → blank-screen crash at ~2 FPS.

**All state code (`state_*.c`, `state_manager.c`) must stay in bank 1.**

## Bank Budget

| Bank | Used  | Notes |
|------|-------|-------|
| ROM_0 | ~46% | Fixed/HOME code, always mapped |
| ROM_1 | ~100% | All autobanked modules — very tight (~26 bytes headroom) |
| ROM_2 | ~2%  | Portrait data (explicit `#pragma bank 2`) |

Total autobanked data: ~16,358 bytes (bank 1 max = 16,384).

## Diagnosing Bank Overflow

**Symptom:** Blank screen, ~2 FPS, game never progresses past boot.

```sh
# Step 1: Check bank percentages
/home/mathdaman/gbdk/bin/romusage build/junk-runner.gb -a

# Step 2: Find symbols placed in bank 2+ — state_* code here = crash
grep "024[0-9A-Fa-f]\{3\}" build/junk-runner.map
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
2. Check bank 1: `romusage build/junk-runner.gb -a` → if bank 1 ≥ 95%, act now
3. Check for state code overflow: `grep "024[0-9A-Fa-f]\{3\}" build/junk-runner.map`
4. If state code appears in bank 2+: find the largest new data file, change it to `#pragma bank 2`, rebuild

## Autobanker Behavior

- `#pragma bank 255` → bankpack assigns automatically, fills bank 1 first, then bank 3+ if bank 2 is explicitly used
- `#pragma bank 2` → linker places in bank 2 directly; bankpack does not touch it
- Explicit and autobanked files coexist; bankpack fills auto-banks around the explicit ones
- Bank 2 explicit data does **not** get mixed with bank 2 autobank overflow — autobank overflow goes to bank 3+

## Why BANKED Function Pointers Aren't the Fix

CLAUDE.md documents that `void (*fn)(void) BANKED` in a struct field is **broken on SDCC/SM83**: it generates double-dereference code (reads 2 bytes from the function's address, then jumps there → garbage). The correct fix is to keep all state code in bank 1, not to add `BANKED` to the struct fields.

---

## Native GBDK Banking Macros

The project's `SET_BANK`/`RESTORE_BANK` wrappers call these internally:

| Macro | Description |
|-------|-------------|
| `SWITCH_ROM(bank)` | Switch ROM bank (MBC1 or MBC5) |
| `SWITCH_ROM_MBC5_8M()` | MBC5 variant for >4 MB ROMs |
| `SWITCH_RAM(bank)` | Switch external RAM bank |
| `ENABLE_RAM` | Enable external RAM access |
| `DISABLE_RAM` | Disable external RAM access |

**`CURRENT_BANK` global** tracks the currently active ROM bank. Safe restore pattern:
```c
uint8_t saved = CURRENT_BANK;
SWITCH_ROM(target_bank);
/* ... use data in target_bank ... */
SWITCH_ROM(saved);
```

**DANGER:** Never call `SWITCH_ROM` from inside a `BANKED` function — this switches out the ROM page currently executing → instant crash.

**`NONBANKED` keyword:** Forces a function/data into fixed bank 0 regardless of the file's `#pragma bank` setting.

---

## MBC5 vs MBC1

**MBC5 is recommended for new projects.** MBC1 has unavailable banks in its addressing range (banks 0x20, 0x40, 0x60 alias to adjacent banks). MBC5 gives a clean 0–255 bank range via `SWITCH_ROM`.

Current project uses MBC1 (`-Wm-yt1`). To switch: change to `-Wm-yt2` and update `SWITCH_ROM` calls.

**Far pointer limits:**
- MBC1: max bank 15 for far pointers
- MBC5: max bank 255 for far pointers

---

## Bankpack Flags

| Flag | Purpose |
|------|---------|
| `-Wb-min=N` | Constrain auto-bank range minimum |
| `-Wb-max=N` | Constrain auto-bank range maximum |
| `-ext=` | Force bankpack to reassess all files each compile cycle (prevents stale assignments) |

---

## Overflow Detection

```sh
# ihxcheck warns on cross-bank spillage
/home/mathdaman/gbdk/bin/ihxcheck build/junk-runner.ihx

# romusage shows full per-bank usage
/home/mathdaman/gbdk/bin/romusage build/junk-runner.gb -a
```

**Bank 0 constraint:** Fixed section (HOME) must be ≤ 16 KB. If bank 0 overflows, code spills into bank 1 which corrupts the switchable bank region.

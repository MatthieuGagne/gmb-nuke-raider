---
name: bank-pre-write
description: "Reference for the pre-write bank gate — bank manifest entry, `#pragma bank`, SET_BANK/SWITCH_ROM safety, BANKED placement. IT NORMALLY FIRES AUTOMATICALLY: tools/bank_check_hook.py runs it as a PreToolUse `Write|Edit` hook on `src/*`. Read this to understand or fix a block it reported, or when writing `src/*.c` / `src/*.h` somewhere the hook does not fire (e.g. a Pi `pwsh-*` background job)."
---

# Bank Pre-Write Gate

The `bank-pre-write` PreToolUse hook (`tools/bank_check_hook.py`) enforces these checks on every
`src/*` write; `tools/bank_check.py` re-checks at build time. The rules below are what it
enforces — apply them while writing so the gate does not block you.

Before writing or editing any `src/*.c` or `src/*.h` file, run the checks below. For `.c` files: all 5 checks apply. For `.h` files: Checks 3, 4, and 5 apply (headers carry no `#pragma bank`; the manifest covers `.c` files only).

## Check 1 — Manifest entry exists

Read `bank-manifest.json` at the repo root.

- If the file you are about to write is a `.c` file and is NOT in the manifest → **BLOCK**:
  > "Add an entry to `bank-manifest.json` for `src/<file>.c` before writing it. Specify bank number (255 for autobank, 0 for HOME bank code that calls SET_BANK/SWITCH_ROM) and reason."

- If creating a new `state_*.c` file → manifest bank **must** be 255 (autobank), unless it calls SET_BANK/SWITCH_ROM in which case it must be 0.
- If creating a new `npc_*_portrait.c` file → manifest bank **must** be 255 (autobank); loader.c handles bank switching.

## Check 2 — Pragma matches manifest

Look up the file's expected bank in `bank-manifest.json`.

| Manifest bank | Required in first 5 lines of `.c` file |
|---------------|----------------------------------------|
| 0             | No `#pragma bank` line at all |
| 255           | `#pragma bank 255` |
| N (any other) | `#pragma bank N` |

If the pragma you are about to write doesn't match → **BLOCK and correct it before writing.**

## Check 3 — No `SET_BANK` or `SWITCH_ROM` inside banked code

If the file's manifest bank is **not 0** (i.e., it lives in the switchable window 0x4000–0x7FFF):

- **BLOCK** any `SET_BANK(...)` or `SWITCH_ROM(...)` call inside that file.
  > Reason: calling SET_BANK/SWITCH_ROM from banked code switches the window away from the running function → crash.
  > Fix: move the SET_BANK call into `loader.c` (a bank-0 NONBANKED wrapper), or into another bank-0 file.

Only these bank-0 files may call `SET_BANK`/`SWITCH_ROM`: `main.c`, `music.c`, `sfx.c`, `hub_data.c`, `state_hub.c`, `state_overmap.c`, `loader.c`, `state_manager.c`.

## Check 4 — No `BANKED` on static functions or bank-0 functions

- `static` functions must NOT be `BANKED` — they cannot be called cross-bank anyway.
- Bank-0 functions must NOT be `BANKED` — they're always mapped; the keyword generates useless trampoline overhead.
- Function pointer fields in structs must NOT be `BANKED` — SDCC generates broken double-dereference code. Use plain `void (*fn)(void)`.

## Check 5 — Makefile `--bank` flags consistent

All generated asset files use `--bank 255` (autobank). Use `--bank N` only for architecturally justified overrides (documented in `bank-manifest.json`).

If adding a new generated file, ensure the Makefile passes `--bank 255` to `png_to_tiles.py` and the manifest entry is `bank: 255`.

Two files are pinned rather than autobanked: `src/music_data.c` at bank 31 and `src/debug.c`
at bank 30. Bank 30 holds the test command mailbox and exists in the debug ROM only. Do not
add a third pin without an ADR — banks 1 and 2 are too full to absorb a displaced module.

## If all checks pass

Proceed with writing the file. Announce: "bank-pre-write: all checks passed for `src/<file>.c` (bank N)."

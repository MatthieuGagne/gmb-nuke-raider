---
summary: Autobank symbol packing and co-location — ___bank_* symbol moves, forced relink baselines, incremental make non-determinism, sdld whole-module linking (no dead-code elimination / gc-sections), HOME bank-0 module ordering, .noi DEF grep
tags: [gbdk, sdld, autobank, linker, banks, rom, noi]
---

# Autobank packing & symbol co-location

How `-autobank` assigns `#pragma bank 255` code/data to banks 1–3, why symbols move
between builds, and how to prove a move is safe. See [[sdcc-banking-rules]] for the
calling conventions and [[rom-parity-testing]] for the release-vs-debug byte checks.

## Forced relink for a valid co-location baseline

The bank-post-build co-location check needs a **forced relink** to produce a valid
baseline. Stashing the change and running `make` does NOT relink if the only removed
input is the new `.o` — `make` sees `nuke-raider.gb` newer than every remaining object,
so the `.noi` comes back byte-identical and the diff falsely reports "no symbols moved".
Delete `build/nuke-raider.gb` (and the new object) inside the stash before rebuilding.
Confirm the baseline is real by checking the symbol COUNT dropped (99 vs 100 in the
beam.c case).

## Why displaced symbols are safe by architecture, not luck

Adding `beam.c`'s code to bank 2 displaced 26 symbols (`track3_*`,
`overmap_car_tile_data`, `state_prerace`) from bank 2 → bank 3. **This was safe, and
the reason is the standing architecture:** every one of those symbols is read only from
`loader.c` (bank 0, NONBANKED) with `SWITCH_ROM(BANK(sym))` at the point of use, and
the BANKED consumers (`track.c`, `racer.c`, `patrol.c`) copy into WRAM statics
(`active_start_x`, `s_wp_tx[][]`) rather than dereferencing ROM pointers. The whole
`track3_*` group also moved together, preserving mutual co-location. **The check to run
when symbols move:** grep each moved symbol's read sites and confirm none is a direct
deref inside a `#pragma bank 255` file.

Second instance (#430 Task 7): adding ~200 bytes across three autobanked gameplay
modules re-packed 26 `___bank_*` symbols, all safe by the same architecture. ROM_1 went
16382/16384 → 16384/16384 (0 bytes free, still linked cleanly) while ROM_2 FREED 817
bytes — the autobanker redistributes rather than overflowing, so "a bank got fuller" is
not by itself a failure signal. Movers: the whole `track_*` group (24 symbols) 0x1 →
0x2 **together** (mutual co-location preserved), `dialog_border_tiles` 0x3 → 0x2,
`turret_tile_data` 0x2 → 0x3, `state_playing` 0x2 → 0x1. Safe because every read site
is `loader.c` (bank 0, NONBANKED) with `SWITCH_ROM(BANK(sym))` at the point of use;
`track.c`'s `track_table[]` stores POINTERS to those symbols but only ever dereferences
`.reward`, a scalar in its own bank; and `state_playing` is only address-taken, its
fields copied out by `state_manager.c`'s `load_entry()` under `SWITCH_ROM`.

**The `.noi` grep is `grep -E '^DEF ___bank_'`** — the symbols are `DEF ___bank_X 0xN`,
so a pattern expecting `=` matches nothing and silently reports "0 symbols".

## Only a clean build is authoritative

Incremental `make` relinks give a **non-deterministic** autobank packing; only a clean
build is authoritative for the co-location check. Building the same sources three ways
(first incremental after the edit, forced-relink baseline, restored incremental)
produced three different `___bank_*` maps — one byte-identical to the baseline, one
with 5 symbols moved. `make clean && make` is what the pre-push hook and the smoketest
use, so run the co-location diff against the CLEAN build's `.noi`, not an incremental
one, or you will draw a conclusion the shipped ROM does not share. The 5 symbols that
shuffle around banks 1–3 on this codebase (`beam_tile_data`, `overmap_tile_data`,
`overmap_car_tile_data`, `turret_tile_data`, `state_game_over`) are all safe by
construction: the four tile-data arrays are read only from `loader.c` (bank 0,
NONBANKED, `SWITCH_ROM` at the use site) and `state_overmap.c` (bank 0, `SET_BANK` at
the use site); `state_game_over` is only address-taken (`&state_game_over` +
`BANK(state_game_over)`) and its fields are copied out by `state_manager.c` (bank 0)
under `SWITCH_ROM` (state_manager.c:29-34).

## Header-only additions can reorder HOME-bank module placement (#590 Task 3)

Adding declarations-only content to a shared header (`debug.h`, included by every
`src/*.c` for `DBG_STATIC` — see [[dbg-static-visibility]]) can reorder `-autobank`'s
HOME-bank (bank-0) module placement between release and debug builds — even though
every affected TU's own compiled assembly is byte-identical. Appending a new enum +
typedefs + `extern` declarations (zero executable bytes: confirmed via `.asm` listing
diff, only difference is pre-existing `DBG_STATIC` `.globl`/`label::` visibility) under
`#ifdef DEBUG_MAILBOX` still grows the compiled `.o`'s symbol/relocation metadata for
every file that transitively includes `debug.h` (`state_hub.o` +502 B, `loader.o`
+213 B, `state_overmap.o` +282 B, `state_manager.o` +72 B, `sfx.o` +102 B, `music.o`
+65 B — every one a file that `#include "debug.h"`; `main.o`/`hub_data.o`, which
don't include it, are untouched). That metadata growth alone changes `-autobank`'s
HOME-bank module ordering decision (confirmed: release links bank-0 functions
`main→sfx→hub_data→state_manager→…`, debug links `main→state_manager→sfx→hub_data→…`),
which shifts every reordered function's absolute address (`state_manager_init` moved
586 bytes). Any code in banks 1–3 that `CALL`s a shifted bank-0 function embeds the new
address as a literal 16-bit operand — so bytes in banks 1–3 change too, even though the
calling code there is 100% logically unchanged (confirmed: diffs are tiny — 16/4/12
bytes across banks 1/2/3, every diff a 2-byte pair, the signature of a shifted CALL
operand).

**Diagnostic method:** diff the `.asm` listing files SDCC emits alongside `.o`
(`build/obj/X.asm` vs `build/debug/obj/X.asm`) before suspecting real logic drift — if
the assembly is identical apart from `.globl`/`::`, the break is in linker module
ordering, not in the source. Cross-check with `grep -E '^DEF ___bank_' *.noi` (bank
*assignment* unchanged) vs a full bank-0 `DEF` address diff (module *order* within HOME
changed). This means any hard gate asserting release-vs-debug byte-identity on the
autobank pool (banks 1–3) is fragile the moment ANY bank-0 file's compiled size changes
for ANY reason — including pure declarations with zero runtime cost. See
[[rom-parity-testing]] for how the parity test was rewritten to tolerate this.

## sdld links whole modules — no dead-code elimination (#590 Task 5)

GBDK's `sdld` links whole `.o` modules from the explicit `$(OBJS)` list, not per-symbol
with dead-code elimination. A non-`static` function in a `.c` file that is already
compiled into the build (e.g. via a `#pragma bank N` file that always builds under a
flag like `DEBUG_MAILBOX`) shows up in the `.noi` / consumes ROM bytes in its bank the
moment the file is compiled and linked — **regardless of whether anything calls it
yet**. Confirmed: `debug_mailbox_start`/`debug_mailbox_poll` (both `BANKED`,
`src/debug.c`, bank 30) were already present in the debug `.noi` and already counted
toward bank 30's used-byte total *before* `main.c` gained any call to them, because
`src/debug.c` was already fully compiled+linked (its own internal cross-bank calls into
`debug_run` gave it other trampolines already) — there is no equivalent of
`--gc-sections` stripping the two unused exported functions.

**Consequence for TDD on this codebase: a test asserting "symbol X reaches the `.noi`"
or "bank N has content" cannot RED on "nothing calls X yet"** — it can only RED on "the
file isn't compiled into this build at all" (e.g. gated out by an `#ifdef` at file
scope, like `src/debug.c`'s whole-file `#ifdef DEBUG_MAILBOX`). If a task brief
predicts such a test will fail before a wiring change and it doesn't, this is very
likely why — verify with `grep 'DEF _fn_name' build/.../nuke-raider.noi` before
assuming the test is broken; the wiring change is usually still correct and necessary
for *runtime* behavior even though it doesn't move this particular needle.

## Host-test-only functions in a banked file are a bank-safety trap (#590 final review)

Non-BANKED functions in a `#pragma bank N` file that exist only for host tests are a
bank-safety trap even though nothing calls them from ROM code — `sdld` links whole
compiled `.o` modules, not per-symbol, so they still occupy bank N and are still
callable by direct address. `debug_mb_read`/`debug_mb_write` in `src/debug.c` (bank 30)
were non-`BANKED`, non-`static`, and used only by `tests/test_debug.c`; a future bank-0
caller could compile a direct `call` to a bank-30 address with no `SWITCH_ROM`. Fix:
wrap BOTH the declarations (`src/debug.h`) and the definitions (`src/debug.c`) in
`#ifndef __SDCC ... #endif` — the host/gcc test build (`__SDCC` undefined) keeps them,
the SDCC ROM build drops them entirely. Verify with
`grep -E "_fnname" build/debug/nuke-raider.noi` before/after — confirms the symbols
vanish from the bank's `.noi`. A function that stays exported unconditionally in the
same file for a *different* reason (here `debug_decide`, asserted by
`tests/test_debug_symbols.py` to reach the debug `.noi`) needs a comment explaining why
it's the one exception, or the pattern looks inconsistent.

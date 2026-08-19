---
summary: DBG_STATIC visibility macro, DEBUG vs DEBUG_TRACE gates, dbg_static_lint.py, exporting static WRAM symbols for headless scenarios (.noi/.map symbol resolution), the #588 sweep, sm_slot_src
tags: [debug, dbg-static, symbols, wram, noi, headless, lint, gbdk]
---

# Debug symbol visibility (DBG_STATIC & WRAM exports)

How module-`static` WRAM data is made visible to external tooling (`.noi`/`.map`
symbol lookup for headless scenarios and the debug mailbox) without changing the ROM.
See [[rom-parity-testing]] for the byte-identity checks and
[[autobank-symbol-placement]] for the linker-ordering side effects.

## Exporting a module-static WRAM array for headless scenarios (#448, race_state.c)

Headless scenarios (`tools/scenarios/*.json`) resolve WRAM symbols by name from
`build/game-manifest.json` → `build/nuke-raider.noi` → `build/nuke-raider.map`;
`static` variables appear in NONE of those, so a scenario can only prove a lap happened
geometrically, never that the game COUNTED one. Fix is visibility-only: drop `static`
on the definition in the `.c` and add a matching `extern uint8_t X[N];` in the `.h`.
Safe in a `#pragma bank 255` autobank module — `#pragma bank` places `_CODE` only;
uninitialized module data goes to `_DATA`/`_BSS` (WRAM, not banked), so size/placement
are unchanged and a scenario reading the address needs no bank context. `BANKED` is a
FUNCTION calling-convention qualifier (selects the bank-0 trampoline for a cross-bank
`call`) and must NOT be applied to data — nothing about the call graph changes, so the
"BANKED missing → wrong bank" class of bug can't be introduced (see
[[sdcc-banking-rules]]). Keep the accessors (`race_state_get_laps`/`_get_cp`) as the
caller API and change NO caller to read the array directly; comment both the `.c` and
`.h` with "NOT a caller API". Only export what the scenario asserts
(`rs_laps`/`rs_cp_next`); leave siblings like `rs_active`/`rs_lap_total` static. Before
adding the `extern`, grep `src/` AND `tests/` for the name — external linkage can now
collide/shadow where `static` could not. `MAX_RACERS`/`PLAYER_SLOT` reach
`race_state.h` (and the test TU) via `race_state.h`→`track.h`→`config.h`; never
hardcode 3/0. The host test's load-bearing evidence is that the test TU COMPILES AND
LINKS against the array; add an `accessor == array[slot]` assert as a guard against a
later refactor repointing the accessor. Only cost is losing SDCC's module-private proof
(watch the ROM line in bank-post-build; WRAM is byte-identical). Manifest/mocks
unchanged — no new .c, no new GBDK API.

## DBG_STATIC macro + DEBUG_TRACE gate (#588 Task 2)

`src/debug.h` defines `DBG_STATIC` as empty under `-DDEBUG`, `static` otherwise — a
file-scope MUTABLE data declaration wrapped in it reaches `.noi`/`.map` under DEBUG
builds without ever changing SDCC's area/address/access-codegen (confirmed: `static` vs
external linkage only changes linker symbol visibility, not placement — same mechanism
as the race_state.c #448 pattern above). The previously-`-DDEBUG`-gated emitting macros
(`DBG_STR`, `DBG_INT`, `DBG_TICK_INC`, the `dbg_write` helper) moved to their own
`#ifdef DEBUG_TRACE` block — `DEBUG` is now visibility-only and must not add a single
instruction (AC2), while `DEBUG_TRACE` (built via `make build-debug DEBUG_TRACE=1`)
still compiles the real WRAM/EMU_printf diagnostics. `src/music.c`'s
`#include "debug.h"` and `DBG_TICK_INC()` call at line 50 needed NO changes — the call
site is unaware which macro definition it expands to. Verified:
`make clean && make && make build-debug` (no `DEBUG_TRACE`) produces two byte-identical
`.gb` files (SHA-256 match, 524,288 bytes, 1,077 `DEF` lines each) — proof that
`-DDEBUG` alone changes zero bytes now that `DBG_TICK_INC()` is gated behind
`DEBUG_TRACE` instead. `tests/test_rom_parity.py` (root-level `tests/`, not `src/`)
hashes both ROMs and skips if either is absent (so `make test-tools`/pre-commit is safe
pre-build). Before adding this kind of gate, grep `src/*.c src/*.h` for
`ifdef DEBUG\b|defined\(DEBUG\)` — any second emitter besides `debug.h` itself would
also need moving to `DEBUG_TRACE`, and would break AC2 if missed. Task 2 deliberately
applied `DBG_STATIC` to ZERO declarations (the sweep was separate tasks) — `DEF`-line
counts diverge from 1077 once file-scope statics start using it.

## dbg_static_lint.py counts declaration LINES, not symbols

Its "N violations" understates the actual `.noi` DEF delta when a line declares
multiple vars (e.g. `static int16_t s_x0, s_x1;` = 1 lint violation but 2 `DEF` symbols
in the debug `.noi`). Confirmed on `src/beam.c`: 14 lint-flagged lines → 16 actual
symbols (two two-var lines). Sum across beam.c+patrol.c+racer.c (14→16, 17→17, 20→20)
= 51 lint violations but 53 new debug-only `.noi` DEF entries. Not a bug — expect
"about N", not exactly N, when verifying `.noi` DEF counts against the lint count.

## The #588 sweep, task by task

**Task 4 (beam.c, patrol.c, racer.c):** renaming three identically-named `s_tile_base`
statics with module prefixes (`beam_tile_base`/`patrol_tile_base`/`racer_tile_base`)
plus `DBG_STATIC` linked clean on the first try — no duplicate-symbol collision for any
other name in those files. Confirms R6's fix (module-prefix the loser) is sufficient
when the only collision is the well-known `s_tile_base` one;
`s_wp_tx`/`s_wp_ty`/`s_wp_count`/`s_finish_dir` in `racer.c` needed `DBG_STATIC` only,
no rename.

**Task 5 (camera.c, damage.c, economy.c, hud.c, loadout.c, player.c, track.c,
turret.c):** 54 lint lines, zero multi-var lines, zero collisions — the debug `.noi`
DEF delta equals the lint count exactly: 1130→1184 (+54). No `s_tile_base`-style rename
needed — every name already module-prefixed (`s_track_tile_base`,
`s_player_tile_base`, `s_turret_tile_base`) or otherwise module-specific (`ld_*`,
`hud_*`, `active_*`, `turret_*`), including the generically-named
`vx`/`vy`/`current_gear` in player.c, cross-checked against all 192 identifiers.
`track.c`'s `active_start_x`/`active_start_y` swapped from `static int16_t` to
`DBG_STATIC int16_t` — confirms the macro is type-agnostic (works on `int16_t`,
`uint16_t`, `CheckpointDef` array, not just `uint8_t`). `track.c:13`'s
`static const TrackDesc track_table[]` and the already-non-static
`active_map_w/h`/`active_lap_count` were left untouched exactly as scoped. Clean link
both ROMs, release SHA unchanged, parity test passed (not skipped).

**Task 6 (dialog.c, explosion.c, loader.c, music.c, powerup.c, projectile.c,
race_state.c, sfx.c, sprite_pool.c, state_hub.c, state_overmap.c, state_playing.c,
state_prerace.c, state_results.c):** 83 lint lines, zero multi-var lines, zero
collisions. Debug `.noi` DEF delta again equals the lint count exactly: 1184→1267
(+83). Two more instances of the mutable-pointer-to-const trap beyond
`const uint16_t *`: `src/loader.c:59`
`static const uint8_t *loader_active_map_ptr = track_map + 2u;` and `src/state_hub.c:51`
`static const HubDef *hub;` both took `DBG_STATIC const T *name` — the pointer OBJECT
is the mutable WRAM data that needs visibility, `const` on the pointee is untouched.
`src/music.c:21` `static volatile uint8_t music_ticks_owed` →
`DBG_STATIC volatile uint8_t` confirmed `volatile` composes fine with the macro (order:
`DBG_STATIC volatile T`, not `volatile DBG_STATIC T`). This batch's generic names
(`cursor`, `hub`, `traveling`, `sub_state`, `dest_tx`, `spawn_tx`, `car_tx`,
`finish_armed`) linked clean on the first try against the rest of the project and
hUGEDriver — no rename needed. (An environmental gotcha surfaced in this task — see
[[host-test-gotchas]] for the intermittent `Permission denied` on a just-linked test
binary.)

**Task 7 (state_manager.c — the last file, completing the 190-declaration sweep):**
`sm_depth` rename + `STACK_MAX` publicized + `sm_slot_src` debug array.
`python tools/dbg_static_lint.py src` now reports `OK` (0 violations) across the whole
tree. This was the one sweep task with a real logic change:
`load_entry(uint8_t slot, const State *s, uint8_t bank)` takes a slot INDEX rather than
a `StateEntry *`, both to avoid an SM83 division (pointer subtraction on a 7-byte
struct) and so it can record `sm_slot_src[slot] = s` — a
`DBG_STATIC const State *sm_slot_src[STACK_MAX]` array naming which `State` struct each
stack slot came from, compiled into BOTH ROMs (not `#ifdef DEBUG`-guarded) so the two
ROMs stay byte-identical (AC2); only `DBG_STATIC` gates its `.noi` visibility.
`state_pop` clears `sm_slot_src[sm_depth] = 0` right after decrementing, so a stale
pointer never survives past the state it named. **Storing `sm_slot_src[slot] = s` is
safe regardless of which ROM bank happens to be mapped at that instant** — it's a plain
16-bit register→WRAM value copy, not a dereference; only `s->bank`/`s->enter`/etc.
inside `load_entry` need the correct bank mapped, and that was already guarded by the
pre-existing `SWITCH_ROM(bank)`. Because `depth`/`stack` were plain `static` (not
`DBG_STATIC`) before this task, neither symbol reached ANY `.noi` pre-task — so the
release DEF count is unchanged (1077→1077) while debug goes 1267→1270 (+3: `_stack`,
`_sm_depth`, `_sm_slot_src`), and the release ROM SHA-256 legitimately changes (real
code added to both ROMs: the array + the extra store), while the debug ROM stays
byte-identical to the new release ROM (parity test still passes). WRAM cost is exactly
`STACK_MAX * 2` = 4 bytes (two 2-byte pointers).

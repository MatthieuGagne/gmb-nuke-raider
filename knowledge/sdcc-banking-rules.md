---
summary: SDCC / GBDK banking calling-convention rules — BANKED trampoline, ternary register-corruption hazard, SWITCH_ROM, #pragma bank 255 autobank, static same-bank helpers, declarations at block start, compound literal rejection
tags: [gbdk, sdcc, banking, calling-convention, gotcha]
---

# SDCC banking rules (recurring hazards)

The canonical statement of the SDCC/GBDK banking and codegen rules that recur across
this codebase. Feature pages ([[enemy-damage-pipeline]], [[beam-laser-module]],
[[explosion-oam-patterns]], [[state-hub-shop]]) record the concrete instances.

## The ternary register-corruption hazard

The documented SDCC bug shape: **a ternary feeding a BANKED return value into another
BANKED call** corrupts the return register. Whenever both arms of a conditional are
BANKED calls, use `if`/`else`, never a ternary (e.g. `beam_update()` picking
`camera_invalidate_row` vs `_col` — see [[beam-laser-module]]).

Shapes that are **NOT** the hazard (all proven safe in this codebase):

- A ternary that selects a **scalar** into a local or return register
  (`enemy_apply_damage`'s `return (dmg >= hp) ? 0u : (uint8_t)(hp - dmg);`).
- A ternary selecting a `const char*` argument to `printf`
  (`printf(owned ? "[OWNED]" : "...")` in the shop code).
- Sequential BANKED→BANKED→BANKED calls as plain statements.
- Nested single-arg BANKED calls dispatched via the bank-0 trampoline
  (`damage_set_armor_tier(loadout_get_armor())`).
- Storing a BANKED return into a stack local, then passing that local as an arg to
  another BANKED call (the proven #424 Task 3 shape).
- A BANKED return → comparison → BANKED arg (`beam_set_equipped(loadout_get_weapon1()
  == LOADOUT_WEAPON1_LASER)`) — the comparison result is a materialized scalar.

## BANKED, static, and call directions

- `BANKED` is a **function calling-convention qualifier** (selects the bank-0 trampoline
  for a cross-bank `call`). It must NOT be applied to data — see
  [[dbg-static-visibility]] for the #448 export pattern where this mattered.
- A `static` helper called only from its own translation unit is a **same-bank call**
  and must NOT be `BANKED` (e.g. `patrol_destroy`, `turret_destroy`, bank-0 statics in
  `state_hub.c`).
- Bank-0 (no `#pragma bank`, SET_BANK allow-list) code can call BANKED functions
  directly — the bank-0 trampoline handles dispatch ([[state-hub-shop]]).
- BANKED→NONBANKED is the safe direction: `sfx_play` is bank-0 NONBANKED (manifest
  bank 0) and is called from bank-255 modules (`player.c`, `powerup.c`,
  `projectile.c`, `beam.c`).
- Widening a `BANKED` function's return type from `void` to `uint8_t` is just what goes
  in the A register before `ret far` — the autobank trampoline needs no changes
  ([[camera-streaming]]).

## Data placement under #pragma bank

`#pragma bank` places `_CODE` only; uninitialized module data goes to `_DATA`/`_BSS`
(WRAM, not banked). So dropping `static` on a WRAM array in a bank-255 file changes
size/placement not at all, and a reader needs no bank context ([[dbg-static-visibility]]).

Cross-bank ROM reads are the hazard: a bank-0 state dereferencing a table that lives in
a banked file reads whatever bank is currently paged in → garbage
([[state-hub-shop]] / dialog generated tables). Reads of a header `static const` table
from the TU's own bank are same-bank and safe (`WEAPON1_DAMAGE_TABLE` read from
`state_playing.c`).

## Codegen / syntax rules

- SDCC requires declarations to be the **first statements of their block**. When a hit
  block needs a `uint8_t dmg` local and a prior statement exists, wrap the block in a
  new `{ }` with the decl first (#424 Task 3, turret.c).
- SDCC rejects `(const uint8_t[]){...}` (an anonymous **compound-literal** expression),
  but `#define X { 8u, 7u, ... }` consumed as `static const uint8_t T[8] = X;` is
  standard aggregate init and compiles fine — see [[config-h-patterns]].
- SM83 has no divide instruction — value→period mappings must be table lookups, never
  arithmetic (`PLAYER_TURN_FRAMES_TABLE` in [[config-h-patterns]]); avoid pointer
  subtraction on odd-sized structs (a 7-byte struct forces a division — see the
  `load_entry(slot, ...)` change in [[dbg-static-visibility]]).
- On z80/SM83, each read of a file-scope static is an absolute load; hoist a
  repeatedly-branched static into a stack local (`is_h` in `beam_fire`,
  [[beam-laser-module]]).
- `(void)` on a discarded BANKED return is zero codegen; discarding a BANKED return at
  a bare-statement call site is not a warning under this codebase's build flags
  ([[camera-streaming]]).
- Watch `uint8_t` overflow when narrowing: use `(uint16_t)n * 8u` for pixel spans, never
  `(uint8_t)(n << 3u)` ([[beam-laser-module]]); cast every `+`/`-` explicitly when
  values are proven ≤ a small bound.

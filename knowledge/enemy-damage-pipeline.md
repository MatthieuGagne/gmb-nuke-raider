---
summary: Enemy combat & damage pipeline — enemy_apply_damage underflow floor, patrol_destroy / hit-flash / ram cooldown, racer contact damage, HEAVY armor tier in damage.c, per-weapon damage cache in projectile.c, loadout seeding order in state_playing.enter()
tags: [damage, combat, patrol, racer, turret, armor, weapon, loadout, projectile, gbdk]
---

# Enemy combat & damage pipeline

How player-bullet/LASER damage, ram damage, armor, and death paths flow through
`damage.c`, `projectile.c`, `enemy_common.c` and the three enemy modules. Beam-side
polling is in [[beam-laser-module]]; explosion hand-off in [[explosion-oam-patterns]];
the SDCC call-shape rules cited throughout are in [[sdcc-banking-rules]].

## enemy_apply_damage — pure underflow-safe HP helper (#424 Task 1)

`enemy_apply_damage(hp, dmg)` in `enemy_common.c`: `#pragma bank 255`, `BANKED`, decl
in `enemy_common.h` before `#endif` (header already `#include "banking.h"` for BANKED +
`#include <stdint.h>`). Body is one line:
`return (dmg >= hp) ? 0u : (uint8_t)(hp - dmg);` — floors at 0 so per-hit damage >1
(LASER=2) can't wrap a 1-HP enemy (TURRET_HP) to 255. Pure, no static state; the
ternary returns a SCALAR into the return register (NOT feeding a BANKED return into
another BANKED call) → the SDCC ternary register-corruption gotcha does NOT apply. No
new .c file → `enemy_common.c` already bank-255 in the manifest, no manifest change, no
new GBDK API to mock. test_enemy_common 37→41 tests. The header top comment was updated
"enemy-AI math" → "enemy AI and combat math" and dropped the stale "(PR4)" before
patrol.c.

## patrol_destroy — same-bank static death helper (#417 Task 3)

`patrol_destroy(uint8_t i)` is a same-bank `static` helper in patrol.c, extracted from
the inline bullet-hit death block. Sets `patrol_active[i]=0u` and parks all 4 OAM slots
off-screen via `move_sprite(...,0u,0u)` (slot order 0,1,2,3); the caller must
`continue` after calling it (the helper does NOT decrement hp or continue). It is
`static` so NOT `BANKED` (same-bank call from `patrol_update`). Reused later by the
ram-damage lethal path. The `patrol_hp[i]--` stays at the call site, outside the
helper. No behavior change vs the removed inline block;
`test_fatal_hit_destroys_and_deactivates` + `test_bullet_hit_decrements_hp` are the
regression guards.

## Patrol hit-flash mirrors racer 1:1 (#417 Task 4)

Added `static uint8_t patrol_hit_flash[MAX_PATROLS]` SoA field (after `patrol_hp`),
init `=0u` in BOTH `patrol_init` per-slot loop AND `patrol_init_empty`. Per-frame tick
goes immediately after `if (!patrol_active[i]) continue;` in `patrol_update`:
`if (h>0u) h=(uint8_t)(h-1u);`. Set on NON-lethal bullet hit only — placed AFTER the
`patrol_hp[i]==0u → patrol_destroy(i); continue;` check so a fatal hit never sets it:
`patrol_hit_flash[i] = (uint8_t)PATROL_HIT_FLASH_FRAMES;`. Render blink inserted in
`patrol_render` AFTER `d = patrol_dir[i];` and BEFORE the first `set_sprite_tile`:
`if (patrol_hit_flash[i] & 2u) { move_sprite x4 to 0,0; continue; }`.
`#define PATROL_HIT_FLASH_FRAMES RACER_HIT_FLASH_FRAMES` (=8) in config.h's patrol
block; both macros visible in patrol.c so expansion order is irrelevant. Test helper
`patrol_get_hit_flash_for_test` is `#ifndef __SDCC` only (host, zero ROM cost). The
`& 2u` mask, the tick, the set, and the assignment are all plain statements — none of
the SDCC ternary/precedence/overflow/static-in-ISR gotchas apply. No new GBDK API
(move_sprite already used+mocked). Generalizes to N>1 (per-slot, indexed by loop
counter). Patrol previously had NO hit-flash (pre-existing gap); this was the first
feedback on bullet hits.

## Patrol enemy-side ram damage + per-patrol cooldown (#417 Task 5)

Added `static uint8_t patrol_ram_cooldown[MAX_PATROLS]` SoA field (after
`patrol_hit_flash`), init `=0u` in BOTH `patrol_init` per-slot loop AND
`patrol_init_empty`. Per-frame decrement tick goes immediately AFTER the hit-flash tick
in `patrol_update`: `if (c>0u) c=(uint8_t)(c-1u);`. The 16x16 ram overlap block now:
always calls `damage_apply(RACER_RAM_DAMAGE)` (mutual player damage, unchanged), then —
guarded by `if (patrol_ram_cooldown[i]==0u)` — sets cooldown=`ENEMY_RAM_COOLDOWN`,
hit_flash=`PATROL_HIT_FLASH_FRAMES`, and uses if/else (NOT ternary) to either
`patrol_hp[i]=0; patrol_destroy(i); continue;` (lethal — `continue` targets the
per-patrol for-loop, mirrors the bullet path) or `patrol_hp[i] -= ENEMY_RAM_DAMAGE`.
config.h: `ENEMY_RAM_DAMAGE=1u`, `ENEMY_RAM_COOLDOWN=DAMAGE_INVINCIBILITY_FRAMES(30u)`,
`PATROL_HIT_FLASH_FRAMES=RACER_HIT_FLASH_FRAMES`. Test helpers
`patrol_get_ram_cooldown_for_test`/`patrol_set_ram_cooldown_for_test` are
`#ifndef __SDCC` only (zero ROM/WRAM on hardware). No new GBDK API
(damage_apply/move_sprite/patrol_destroy already used+mocked). All new statements are
plain (no SDCC ternary/precedence/overflow gotchas; values ≤100 so uint8_t casts safe).
The destroyed-patrol no-op is free via the `if (!patrol_active[i]) continue;`
top-of-loop guard. WRAM +MAX_PATROLS bytes (=1).

## Racer contact damage extracted to a testable BANKED helper (#412)

`racer_apply_contact_damage(px,py)` in `racer.c` (`#pragma bank 255`) wraps
`if (racer_overlaps_player(...)) { damage_apply(RACER_RAM_DAMAGE); return 1; }`. Keep
the SFX in `state_playing` (return 1 = hit) so `racer.c` needs no `sfx` dependency.
Cross-bank `damage_apply` (BANKED) from a bank-255 file is the established pattern —
`patrol.c` already does it; needs `#include "damage.h"`. Reusing the existing overlap
predicate inherits its active/dying exclusion (dying racers are active=0) for free. The
BANKED→BANKED→BANKED calls here are sequential statements (NOT a ternary feeding a
BANKED return into another BANKED call), so the SDCC register-corruption gotcha does
NOT apply. The host test uses `damage_init()` + `damage_get_hp()` to assert HP drained
by exactly `RACER_RAM_DAMAGE`; `TEST_LIB_SRC` links every `src/*.c` except `main.c`, so
`damage.c` resolves automatically in `test_racer`.

## HEAVY armor flat damage reduction cached in damage.c (#423 Task 1)

Added `static uint8_t armor_tier` (after `invincibility_cooldown`) to damage.c (bank
255 autobank); `damage_init()` resets it to `0u` (LIGHT); new
`damage_set_armor_tier(uint8_t)` BANKED setter (decl in damage.h after `damage_init`,
header already `#include <gb/gb.h>`). Reduction block at the top of `damage_apply`
AFTER the invincible/dead early-returns, BEFORE the `amount >= hp` clamp:
`if (amount > 0u && armor_tier == 1u) amount = (amount > ARMOR_HEAVY_REDUCTION) ?
(uint8_t)(amount - ARMOR_HEAVY_REDUCTION) : 1u;`. The `amount > 0u` guard keeps a
0-damage call a true no-op (not floored up to 1). The ternary selects a SCALAR into a
local (NOT feeding a BANKED return into another BANKED call) → the SDCC
register-corruption ternary gotcha does NOT apply. `static armor_tier` is NOT BANKED
(module static). `ARMOR_HEAVY_REDUCTION=2u` in config.h's Damage block. No new .c file
→ no bank-manifest change. Tier values 0/1 match loadout_get_armor()
(LOADOUT_OPTIONS_PER_FIELD=2). test_damage: 27→33 tests. No new GBDK API to mock.

## Seeding the armor tier from loadout at race start (#423 Task 2)

In `state_playing.c` `enter()`, immediately AFTER `damage_init()`, call
`damage_set_armor_tier(loadout_get_armor());` (added `#include "loadout.h"` alongside
`#include "damage.h"`). `state_playing.c` is autobank (`#pragma bank 255`, assigned
bank 0x2), and BOTH `loadout_get_armor()` and `damage_set_armor_tier()` are BANKED — a
BANKED arg feeding a BANKED call here is fine because they are NESTED single-arg calls
dispatched via the bank-0 trampoline, NOT a ternary feeding a BANKED return into
another BANKED call. **Order matters: `damage_init()` resets `armor_tier` to 0 (LIGHT),
so the setter MUST come after it.** Tier values 0/1 match `loadout_get_armor()` returns
directly (no remap). No new .c file → no bank-manifest change; no new GBDK API to mock.
2-line change, no test added (pure integration of two already-tested modules).

## Per-weapon damage cache in projectile.c (#424 Task 2)

Added `static uint8_t s_weapon1_damage = WEAPON1_CANNON_DAMAGE;` (after
`s_proj_tile_base`) to projectile.c (`#pragma bank 255`, autobank). `projectile_init()`
RESETS it to `WEAPON1_CANNON_DAMAGE` (after `proj_cooldown_tick=0u;`) — this keeps the
pre-existing `test_check_hit_enemy_player_bullet` (asserts `==1u`) green because
default==CANNON==1. New `projectile_set_weapon1_damage(uint8_t) BANKED` setter (public,
NOT static). `projectile_check_hit_enemy()`'s hit path now `return s_weapon1_damage;`
(was `return 1u;`) → returns cached per-hit damage (>=1) on hit, 0 on miss. CRITICAL:
`projectile_check_hit_player()`'s `return 1u;` was left UNCHANGED — enemy bullets stay
a 0/1 flag. config.h Damage section: `WEAPON1_CANNON_DAMAGE=1u`,
`WEAPON1_LASER_DAMAGE=2u` (after `ENEMY_BULLET_DAMAGE`); plus a guarded
`static const uint8_t WEAPON1_DAMAGE_TABLE[LOADOUT_OPTIONS_PER_FIELD] = {CANNON, LASER}`
(after the `LOADOUT_STRINGS_DEFINED` `#endif`, guard `WEAPON1_DAMAGE_TABLE_DEFINED`,
mirrors the LOADOUT_STRINGS header-array pattern, consumed by Task 4). All new
statements plain (no ternary/cast/precedence/static-in-ISR gotchas). No new .c file →
no manifest change; no new GBDK API to mock. test_projectile 21→25 tests.

## Routing enemy HP subtraction through the returned damage (#424 Task 3)

The three `#pragma bank 255` enemy modules' PLAYER-bullet-hit blocks now do
`uint8_t dmg = projectile_check_hit_enemy(...); if (dmg) { X_hp[i] =
enemy_apply_damage(X_hp[i], dmg); ... }` instead of a hardcoded `X_hp[i] - 1u` /
`X_hp[i]--`. SDCC requires the `uint8_t dmg` decl to be the FIRST statement of its
block: racer.c/patrol.c hit-blocks already opened a fresh `{ }` with no prior statement
so the decl slots in directly; turret.c had a prior statement so the whole hit block
was wrapped in a NEW `{ }` with `dmg` first. Storing the BANKED
`projectile_check_hit_enemy` return into the `dmg` local and THEN passing it as an arg
to `enemy_apply_damage` round-trips through a stack local (NOT a ternary feeding a
BANKED return into another BANKED call) → the SDCC register-corruption gotcha does NOT
apply. `dmg` ≤ 2, hp small → no uint8_t overflow. CRITICAL: the `ENEMY_RAM_DAMAGE`
ram-collision paths (racer.c ~L616
`racer_hp[i]=(uint8_t)(racer_hp[i]-ENEMY_RAM_DAMAGE)`, patrol.c ~L275) are OUT OF SCOPE
(R6: player-bullet damage only) — left untouched.

**GOTCHA in the host test (`test_racer_laser_kills_in_three_hits`):** the racer
ACCELERATES toward its ty=0 waypoint each `racer_update`, drifting ~9px north over 3
hits → the fixed (48,56) bullet falls outside RACER_HIT_RADIUS=8 (hit test `<=r`) by
hit 3 (scr_cy 56→54→51→47). Fix: `racer_set_pos_for_test(1u, 32, 32)` before EACH
`projectile_fire` to re-anchor at spawn so every shot lands; the 5→3→1→0 numeric
expectations are unchanged. All three files already `#include "enemy_common.h"`; no new
.c/manifest/GBDK-mock change. test_racer 61→62 tests. `projectile_check_hit_player`
still returns a 0/1 flag — only the enemy path returns cached damage.

## Seeding weapon-1 damage from loadout at race start (#424 Task 4)

In `state_playing.c` `enter()`, immediately AFTER
`projectile_init(loader_get_slot(TILE_ASSET_BULLET));` (at the time, L95), added
`projectile_set_weapon1_damage(WEAPON1_DAMAGE_TABLE[loadout_get_weapon1()]);`.
**ORDER IS LOAD-BEARING: `projectile_init()` RESETS the cache to
`WEAPON1_CANNON_DAMAGE`, so the setter MUST follow it or the LASER value gets wiped** —
the exact mirror of the `damage_init(); damage_set_armor_tier(loadout_get_armor());`
idiom two lines above (#423 Task 2). `state_playing.c` already `#include`s
projectile.h, loadout.h, config.h. `WEAPON1_DAMAGE_TABLE` is a header static-const in
config.h read from state_playing.c's OWN TU (bank 255, autobank 0x2) → same-bank read,
safe (no cross-bank ROM-read hazard). `loadout_get_weapon1()` (BANKED) return
array-indexes the table, then the scalar result feeds BANKED
`projectile_set_weapon1_damage` — a plain scalar arg (NOT a ternary feeding a BANKED
return into another BANKED call), so the SDCC register-corruption gotcha does NOT
apply. Table-indexed so it generalizes to any N weapon-1 options (no hard-coding).
1-line change, no test added (pure integration of already-tested Task 2+3 modules); no
new .c → no manifest change, no new GBDK API to mock. Verify order: the seed line must
sit between `projectile_init` and `turret_init`.

# Race State Unification Design

**Date:** 2026-06-05
**Topic:** Unified race-tracking state for player and enemies via `race_state.c`

---

## Problem

Player and enemy racers track checkpoints and laps through completely separate modules
(`checkpoint.c` / `lap.c` for the player; `racer_cp_next[]` / `s_laps_done` in `racer.c`
for the enemy). The detection logic is nearly identical but duplicated. The enemy lap
counter (`s_laps_done`) is a single module-level variable shared across all racer slots —
it does not scale to multiple enemies. Race position, HUD updates, and win/loss conditions
all wire up player vs. enemy through separate code paths in `state_playing.c`.

---

## Goals

- One code path for checkpoint detection, lap advancement, and position ranking — used by
  every slot including the player.
- Each slot has its own independent lap counter and checkpoint cursor.
- Scalable to N enemies by changing `MAX_RACERS` in `config.h` only.
- HUD lap display and position display read from the unified pool.
- Win and loss conditions read from the unified pool.

---

## Slot Layout

| Slot | Entity | Notes |
|------|--------|-------|
| 0 | Enemy racer 0 | First (and currently only) AI opponent |
| 1 | Player | `PLAYER_SLOT = 1` constant in `race_state.h` |
| 2+ | Future enemies | Increase `MAX_RACERS` in `config.h` to add |

`MAX_RACERS` bumps from 1 to 2. All SoA arrays in both `racer.c` and `race_state.c` are
sized by this constant — no other changes needed when adding racers.

---

## New Module: `race_state.c` / `race_state.h`

### Responsibilities

Owns all per-slot race-tracking state. Neither `player.c` nor `racer.c` hold checkpoint or
lap state — they call into `race_state`.

`racer.c` retains: AI navigation, physics, OAM, health, hit-flash.
`player.c` retains: input-driven physics, position, velocity, direction, gear.

### Public API

```c
/* Lifecycle */
void race_state_init(uint8_t lap_total);
void race_state_set_active(uint8_t slot, uint8_t active);  /* call on spawn/despawn */

/* Per-frame update — call once per slot per frame; caller passes its own coords */
void race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir);

/* Lap gate — call when finish tile + direction validated */
/* Returns 1 if the race is over for this slot, 0 if lap incremented */
uint8_t race_state_advance_lap(uint8_t slot);

/* Accessors */
uint8_t race_state_get_cp(uint8_t slot);
uint8_t race_state_get_laps(uint8_t slot);     /* 0-based completed laps */
uint8_t race_state_get_lap_total(void);
uint8_t race_state_all_cp_cleared(uint8_t slot);

/* Position ranking — returns player's ordinal rank (1 = leading) */
uint8_t race_state_rank_player(void);
```

### Internal SoA

```c
static uint8_t rs_cp_next[MAX_RACERS];
static uint8_t rs_laps[MAX_RACERS];
static uint8_t rs_active[MAX_RACERS];
static uint8_t rs_lap_total;
```

### `race_state_update_cp(slot, x, y, dir)`

AABB + direction check against `track_get_checkpoints()[rs_cp_next[slot]]` — identical
logic currently duplicated between `checkpoint_update()` and `racer_checkpoint_update()`.
Caller passes entity world position and direction; `race_state.c` does not reach into
`player.c` or `racer.c` internals. Increments `rs_cp_next[slot]` on clear.
Requires `rs_active[slot] == 1`.

### `race_state_advance_lap(slot)`

- If `rs_laps[slot] + 1 >= rs_lap_total`: returns 1 (race over for this slot).
- Otherwise: `rs_laps[slot]++`, `rs_cp_next[slot] = 0`, returns 0.
- Checkpoint reset is internal — callers do not call any separate reset.

### `race_state_rank_player()`

Loops over all active slots. For each pair (PLAYER_SLOT vs. slot i), applies the
3-level comparison: laps → checkpoints → Manhattan distance to next checkpoint.
Returns player's 1-based rank among all active slots.

---

## Modules Retired

| Module | Replacement |
|--------|-------------|
| `checkpoint.c` / `checkpoint.h` | `race_state_update_cp()`, `race_state_get_cp()`, `race_state_all_cp_cleared()` |
| `lap.c` / `lap.h` | `race_state_advance_lap()`, `race_state_get_laps()`, `race_state_get_lap_total()` |

Removed from `racer.c`:
- `racer_cp_next[MAX_RACERS]` array and its update logic
- `s_laps_done` module variable
- `racer_get_cp_next()` and `racer_get_laps_done()` accessors

---

## `state_playing.c` Changes

### HUD lap display

Before:
```c
hud_set_lap(lap_get_current(), lap_get_total());
```
After:
```c
hud_set_lap(race_state_get_laps(PLAYER_SLOT) + 1, race_state_get_lap_total());
```
No changes needed inside `hud.c`.

### Race position display

Before: separate calls for player (`checkpoint_get_cp_next()`, `lap_get_current()-1`) and
enemy (`racer_get_cp_next(0)`, `racer_get_laps_done(0)`).

After: `race_state_rank_player()` returns the rank directly. Position calculation loop
lives in `race_state.c` and reads `rs_cp_next[slot]` / `rs_laps[slot]` uniformly for
every slot.

### Player finish / win condition

Before:
```c
uint8_t cps_ok = checkpoint_all_cleared();
...
if (lap_advance()) {
    /* win */
} else {
    checkpoint_reset();
    hud_set_lap(lap_get_current(), lap_get_total());
}
```
After:
```c
uint8_t cps_ok = race_state_all_cp_cleared(PLAYER_SLOT);
...
if (race_state_advance_lap(PLAYER_SLOT)) {
    /* win */
} else {
    hud_set_lap(race_state_get_laps(PLAYER_SLOT) + 1, race_state_get_lap_total());
    /* checkpoint reset happens inside race_state_advance_lap */
}
```

### Enemy finish / loss condition

`racer_update()` keeps its return-1-on-finish contract. Internally it replaces:
```c
if (s_laps_done >= s_lap_total && ...)
```
with:
```c
if (race_state_advance_lap(slot) && ...)
```
`state_playing.c` needs no change here — it still checks `if (racer_update())`.

For scalability: `racer_update()` loops over all active enemy slots. If any slot finishes,
it returns 1 and triggers the loss state. First-to-finish wins.

---

## Scalability Summary

| Concern | How it scales |
|---------|--------------|
| Adding enemies | Increase `MAX_RACERS` in `config.h` |
| Per-enemy lap counters | `rs_laps[slot]` — one entry per slot |
| Position ranking | `race_state_rank_player()` loops all active slots |
| Loss condition | `racer_update()` loops all active enemy slots |
| HUD rank display | `hud_set_position()` already takes `uint8_t` — shows correct rank for any N |
| OAM budget | 40 sprites total; player=2, each enemy=4 → fits 9 enemies before overflow |

---

## Files Changed

| File | Change |
|------|--------|
| `src/race_state.c` | New — owns all per-slot cp/lap tracking |
| `src/race_state.h` | New — public API |
| `src/checkpoint.c` / `.h` | Deleted |
| `src/lap.c` / `.h` | Deleted |
| `src/racer.c` | Remove `racer_cp_next`, `s_laps_done`, `racer_checkpoint_update()`, lap-advance logic; call `race_state` instead |
| `src/racer.h` | Remove `racer_get_cp_next()`, `racer_get_laps_done()` |
| `src/state_playing.c` | Update all call sites (HUD, position, win, loss) |
| `src/config.h` | `MAX_RACERS` 1 → 2; add `PLAYER_SLOT = 1` |
| `bank-manifest.json` | Add entry for `race_state.c`; remove entries for `checkpoint.c`, `lap.c` |

# Car Physics Design — Velocity Layer

**Date:** 2026-03-09
**Feature:** Add per-axis velocity, acceleration, and friction to player movement

---

## Overview

Replace the current instant 1px/frame D-pad movement with a velocity-based model. The player car accumulates speed when a direction is held and decelerates when released. Movement remains omnidirectional (4-axis independent). Full heading/angle system is out of scope.

---

## Data Model

Two new fields in `player.c` (static, not exposed in header):

```c
static int8_t vx;  /* horizontal velocity, range [-MAX_SPEED, +MAX_SPEED] */
static int8_t vy;  /* vertical velocity,   range [-MAX_SPEED, +MAX_SPEED] */
```

Both reset to 0 in `player_init()`.

Three new constants in `src/config.h`:

```c
#define PLAYER_ACCEL      1   /* pixels/frame added per held frame */
#define PLAYER_FRICTION   1   /* pixels/frame removed when direction released */
#define PLAYER_MAX_SPEED  3   /* hard cap on velocity per axis */
```

---

## Per-Frame Update Logic

Each axis is processed independently. Example for X:

```
if J_RIGHT held:  vx = min(vx + ACCEL, +MAX_SPEED)
elif J_LEFT held: vx = max(vx - ACCEL, -MAX_SPEED)
else:             vx += (vx > 0) ? -FRICTION : (vx < 0) ? +FRICTION : 0
```

- Holding a direction accelerates toward `MAX_SPEED` in `MAX_SPEED / ACCEL` frames (3 frames at defaults).
- Releasing decelerates to 0 in `MAX_SPEED / FRICTION` frames (3 frames at defaults).
- Holding the opposite direction is treated as normal acceleration in that direction — no special "slam brakes" case.

---

## Collision Interaction

Axes are tested separately so the car can slide along walls:

```
new_px = px + vx
if corners_passable(new_px, py): px = new_px
else: vx = 0              ← zero velocity on impact

new_py = py + vy
if corners_passable(px, new_py): py = new_py
else: vy = 0
```

Hitting a wall zeroes velocity on the blocked axis only. The car stops dead on impact — no bouncing or sliding. Terrain friction modifiers are out of scope for this feature.

---

## Testing

New file: `tests/test_player_physics.c`

| Test | Description |
|------|-------------|
| Accel to max | Holding J_RIGHT for `MAX_SPEED/ACCEL` frames reaches `vx == MAX_SPEED` |
| Cap at max | Additional frames beyond cap do not exceed `MAX_SPEED` |
| Friction decay | Releasing decays `vx` to 0 over `MAX_SPEED/FRICTION` frames |
| Wall zeros vx | `corners_passable` returns false → `vx` set to 0, `vy` unchanged |
| Wall zeros vy | `corners_passable` returns false on Y → `vy` set to 0, `vx` unchanged |
| Independent axes | J_RIGHT + J_UP simultaneously accumulates both `vx` and `vy` |

`track_passable` mock already exists. No new mocks needed.

---

## Files Changed

| File | Change |
|------|--------|
| `src/config.h` | Add `PLAYER_ACCEL`, `PLAYER_FRICTION`, `PLAYER_MAX_SPEED` |
| `src/player.c` | Add `vx`/`vy`, rewrite `player_update()` |
| `tests/test_player_physics.c` | New test file |

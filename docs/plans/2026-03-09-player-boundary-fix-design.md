# Player Boundary Fix Design

**Date:** 2026-03-09

## Problem

`PX_MAX` and `PY_MAX` in `player.c` use the sprite's upper-left pixel position as the clamp point for the right and bottom screen edges. For an 8×8 sprite this allows 7 pixels of overdraw off-screen on the right and bottom.

## Root Cause

Game Boy hardware offsets: sprite X register = screen_x + 8, sprite Y register = screen_y + 16.
For an 8×8 sprite:

- Right edge at screen x=159 → sprite X register = 152 + 8 = **160**
- Bottom edge at screen y=143 → sprite Y register = 136 + 16 = **152**

Current values 167 and 159 place the sprite's *right* and *bottom* edges 7 pixels off-screen.

## Fix

### `src/player.c`

| Constant | Old | New | Reason |
|----------|-----|-----|--------|
| `PX_MAX` | 167 | 160 | right edge clamps at screen x=159 |
| `PY_MAX` | 159 | 152 | bottom edge clamps at screen y=143 |

### `tests/test_player.c`

| Test | Change |
|------|--------|
| `test_player_update_clamps_at_right_boundary` | set_pos(160, 72), expect 160 |
| `test_player_update_clamps_at_bottom_boundary` | set_pos(80, 152), expect 152 |

## Non-changes

- `PX_MIN = 8` and `PY_MIN = 16` are already correct (upper-left pixel IS the left/top edge).
- No API changes; no new abstractions needed.

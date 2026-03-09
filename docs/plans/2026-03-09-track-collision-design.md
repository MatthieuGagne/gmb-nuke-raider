# Track & Collision Design

Date: 2026-03-09

## Summary

Add a static oval track to the game rendered as a BG tile map. The player sprite is blocked from leaving the track: any movement that would place any corner of the 8×8 sprite on an off-track tile is rejected for that axis.

---

## Tile Data

Two 8×8 2bpp tile patterns, defined as `static const uint8_t` arrays in ROM:

- **Tile 0** — off-track (dark fill, wasteland/sand)
- **Tile 1** — track surface (medium fill, road)

Loaded at init with `set_bkg_data(0, 2, tile_data)`.

---

## Track Map (20×18)

`static const uint8_t track_map[18][20]` in ROM. `0` = off-track, `1` = track.

The oval ring is 4 tiles wide to comfortably fit the 8×8 (1-tile) player sprite.

```
Row  0: 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
Row  1: 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0
Row  2: 0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0
Row  3: 0,0,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,0,0
Row  4: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row  5: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row  6: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row  7: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row  8: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row  9: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row 10: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row 11: 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0
Row 12: 0,0,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,0,0
Row 13: 0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0
Row 14: 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0
Row 15: 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
Row 16: 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
Row 17: 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
```

Loaded at init with `set_bkg_tiles(0, 0, 20, 18, track_map)`.

---

## Collision

Tile lookup helper: `track_passable(uint8_t screen_x, uint8_t screen_y)` — returns 1 if the tile at that screen-pixel coordinate is track (tile 1), 0 otherwise. Uses `get_bkg_tile_xy(screen_x / 8, screen_y / 8)`.

In `player_update()`, before committing movement:

1. Convert sprite hardware coords to screen pixel coords:
   - `screen_x = px - 8`
   - `screen_y = py - 16`
2. Test X axis independently: compute candidate `new_px`, check all 4 corners of the sprite at `(new_px-8, screen_y)` to `(new_px-8+7, screen_y+7)`. Accept only if all 4 corners are passable.
3. Test Y axis independently: same check with `new_py`.

Independent axis testing allows the player to slide along track edges.

---

## Player Start Position

The player start position must be updated to place the sprite on the track. Bottom straight (row 14) at column 10 is a good default: screen pixel (80, 112) → hardware `px=88, py=128`.

---

## New Files

| File | Purpose |
|------|---------|
| `src/track.c` | Tile data, map array, `track_init()`, `track_passable()` |
| `src/track.h` | Public API |

## Modified Files

| File | Change |
|------|--------|
| `src/main.c` | Call `track_init()` during init (display off), `#include "track.h"` |
| `src/player.c` | Add 4-corner collision checks in `player_update()`, update start position |
| `src/player.h` | No change expected |

---

## Testing

- Unit tests for `track_passable()`: known on-track and off-track tile coordinates
- Unit tests for `player_update()` collision: player blocked when moving into off-track tile, player slides along edge when one axis is blocked
- Player start position confirmed to be on-track

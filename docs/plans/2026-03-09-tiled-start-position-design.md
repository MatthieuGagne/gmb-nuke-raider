# Design: Tiled-Driven Start Position + Upward-Only Camera Scroll

**Issue:** #31 — track scrolls downward instead of upward
**Date:** 2026-03-09

## Problem

Two bugs remain after PR #32:

1. **Wrong start position**: `PLAYER_START_Y=80` places the player near the top of the
   map (row 10). An upward-scrolling racer requires the player to start at the
   bottom and drive toward row 0.

2. **Camera scrolls both ways**: `camera_update` allows `cam_y` to increase
   (scrolling down). The camera should only ever advance upward — once road is
   behind the player, it stays behind.

## Design

### Worktree

All implementation work happens in a Git worktree (e.g. `feat/tiled-start-position`)
to keep `master` clean throughout development.

### 1. TMX — "start" object layer

Add an `<objectgroup>` named `"start"` to `assets/maps/track.tmx` containing one
point object at the desired pixel spawn coordinates (col 11, row 90 → pixel 88, 720):

```xml
<objectgroup id="2" name="start">
  <object id="1" x="88" y="720">
    <point/>
  </object>
</objectgroup>
```

Update `nextlayerid="3"` and `nextobjectid="2"` in the `<map>` element.

### 2. `tools/tmx_to_c.py` — extract spawn point

Parse the `"start"` objectgroup and emit two `int16_t` constants into `track_map.c`:

```c
const int16_t track_start_x = 88;
const int16_t track_start_y = 720;
```

Error if the layer is missing or has no objects.

### 3. `src/track.h` — expose the spawn point

```c
extern const int16_t track_start_x;
extern const int16_t track_start_y;
```

### 4. `src/player.c` — use generated spawn values

Remove the hardcoded `PLAYER_START_X` / `PLAYER_START_Y` macros.
In `player_init()`:

```c
px = track_start_x;
py = track_start_y;
```

### 5. `src/camera.c` — upward-only scroll

In `camera_update`, block any downward camera movement:

```c
if (ncy >= cam_y) return;   /* camera never scrolls down */
```

Remove the now-dead downward-scroll branch (the `ncy > cam_y` case).
The existing player clamp `new_py <= cam_y + 143` still prevents the player
from going below the current camera bottom.

## Testing

- Unit test `tmx_to_c.py`: TMX with a "start" layer produces correct `track_start_x/y`.
- Unit test `camera_update`: calling with increasing player Y never increases `cam_y`.
- Unit test `player_init`: `player_get_x()/y()` return `track_start_x/y` after init.
- Smoketest in Emulicious: player spawns at bottom of track, pressing UP scrolls
  toward row 0, pressing DOWN is bounded by camera floor.

## Files Changed

| File | Change |
|------|--------|
| `assets/maps/track.tmx` | Add "start" object layer |
| `tools/tmx_to_c.py` | Parse "start" layer, emit spawn constants |
| `src/track_map.c` | Re-generated (spawn constants added) |
| `src/track.h` | `extern` declarations for spawn constants |
| `src/player.c` | Remove hardcoded macros, use `track_start_x/y` |
| `src/camera.c` | Upward-only scroll in `camera_update` |
| `tests/test_tmx_to_c.py` | New Python unit test |
| `tests/test_camera.c` | New camera direction test |
| `tests/test_player.c` | Player init spawn test |

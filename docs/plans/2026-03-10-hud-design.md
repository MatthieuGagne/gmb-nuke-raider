# HUD Design — Race Timer & HP Display

Date: 2026-03-10

## Overview

Add a 2-row Window-layer HUD at the bottom of the screen showing HP (numeric, constant 100 for
now) on the left and a MM:SS race timer on the right. The play area shrinks from 20×18 to 20×16
tiles; the camera and BG scroll system are unaffected.

## Screen Layout

Window layer pinned to bottom 2 rows via `move_win(7, 128)`.

```
Row 0: [ H P : 1 0 0 _ _ _ _ _ _ _ _ _ _ 0 0 : 0 0 ]
         0 1 2 3 4 5 6 7 8 9 ...          15 16 17 18 19
Row 1: [ (blank — reserved for future: gear, speed bar, etc.) ]
```

- `HP:100` occupies tile cols 0–5
- `00:00` occupies tile cols 15–19
- Remaining cols are blank tiles

## Module: `hud`

New module `src/hud.c` + `src/hud.h`. All state is `static` in `hud.c`.

### Public API

```c
void    hud_init(void);          // call in state_playing enter()
void    hud_update(void);        // call in game logic phase each frame
void    hud_render(void);        // call in VBlank phase (VRAM writes)
void    hud_set_hp(uint8_t hp);  // future use
```

### State

```c
static uint8_t  hud_hp;           // current HP value (init 100)
static uint8_t  hud_frame_tick;   // 0–59, resets each second
static uint16_t hud_seconds;      // total elapsed seconds
static uint8_t  hud_dirty;        // set when values change, triggers re-render
```

### Timer Logic

- `hud_update()` increments `hud_frame_tick` each call (once per frame at 60 fps)
- When `hud_frame_tick` reaches 60: reset to 0, increment `hud_seconds`, set `hud_dirty`
- Display: `MM = hud_seconds / 60`, `SS = hud_seconds % 60`
- `uint16_t` holds up to 65535 seconds (~18 hours) — sufficient

### Font Tiles

- 13 unique tiles needed: `0–9`, `H`, `P`, `:`, space
- Defined as `static const uint8_t hud_font_tiles[]` in `hud.c`
- Loaded during `hud_init()` via `set_bkg_data()` at a safe tile index offset (128+) to avoid
  collision with track tiles (Window layer shares BG tile data)

### Dirty Rendering

`hud_render()` only calls `set_win_tiles()` when `hud_dirty` is set, then clears it. This avoids
redundant VRAM writes every frame.

## Integration Points

- `state_playing.c`: call `hud_init()` in `enter()`, `hud_render()` in VBlank phase, `hud_update()`
  in game logic phase
- `config.h`: add `PLAYER_HP_MAX 100`
- No changes needed to camera, track, or player modules

## Future Extensions

- Row 1 reserved for gear indicator, speed bar, or mini-map
- `hud_set_hp()` wired to player damage system when implemented
- Timer stop/reset on state transitions (game over, title)

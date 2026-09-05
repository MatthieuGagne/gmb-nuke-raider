# Sprite coordinate system

Read by the `sprite-expert` agent — OAM-to-screen coordinate conversion, the player's 16×16 quad
render pattern, and the sprite-flip mock stubs the host tests need.

## Coordinate System

OAM stores raw hardware coordinates. `move_sprite(slot, oam_x, oam_y)`:

```
screen_x = oam_x - 8    (DEVICE_SPRITE_PX_OFFSET_X = 8)
screen_y = oam_y - 16   (DEVICE_SPRITE_PX_OFFSET_Y = 16)
```

**To place a sprite at screen pixel (sx, sy):**
```c
move_sprite(slot, (uint8_t)(sx + 8), (uint8_t)(sy + 16));
```

**Fully visible range (8×8 sprite):**
- `oam_x` ∈ [8, 167] → screen x ∈ [0, 159]
- `oam_y` ∈ [16, 159] → screen y ∈ [0, 143]

**Hide a sprite:** `move_sprite(slot, 0, 0)` — OAM y=0 is always off-screen.

**Common mistake:** using 152 or 136 as max oam_x/oam_y — these cut off ~15px of valid screen area.

**Player render pattern:** the player is a **16×16 quad of four 8×8 sprites**, not a two-slot
stack. `src/player.c` declares `DBG_STATIC uint8_t player_sprite_slot[4];  /* 0=TL, 1=BL, 2=TR, 3=BR */`,
populated by four `get_sprite()` calls in `player_init()`. Rendering sets
per-slot tiles from the `DIR_TILE_TL/BL/TR/BR` tables plus a shared `set_sprite_prop(slot, flip)`
from `DIR_FLIP[player_dir]`, then camera-adjusts one `hw_x`/`hw_y` origin. Read the sequence
around the `hw_x`/`hw_y` assignment in `player.c` for the canonical order rather than copying a paraphrase.

---

## Mock Header — Sprite Flip Stubs

Before writing any sprite-flip feature or test, confirm the mock stubs exist:

```bash
grep "S_FLIPX\|set_sprite_prop" tests/mocks/gb/gb.h
```

If either is absent, add it to the mock header before writing tests or implementation code.

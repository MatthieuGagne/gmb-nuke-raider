---
name: sprite-builder
description: Use when adding a new sprite type to Junk Runner — creating the Aseprite source, exporting PNG, running png_to_tiles, allocating OAM slots, loading tile data, and rendering the sprite in game.
---

# Sprite Builder

## Overview

Step-by-step guide to add a new sprite from scratch. Uses the Aseprite → `png_to_tiles.py` → OAM pool pipeline.

**REQUIRED BACKGROUND:** Invoke the `sprite-expert` skill before writing any code — it has the full API reference, OAM coordinate math, palette setup, and VBlank rules.

**REQUIRED — Aseprite CLI:** ALWAYS invoke the **`aseprite`** skill before running any `aseprite` command. It has the complete flag reference and prevents common mistakes.

---

## Quick Checklist

1. [ ] Draw sprite in Aseprite (indexed color, 4-shade GBC palette, 8×N canvas)
2. [ ] Export PNG → run `png_to_tiles.py` → verify generated C
3. [ ] Declare `extern` symbols in the consumer `.c`
4. [ ] Load tile data during VBlank (`set_sprite_data`)
5. [ ] Allocate OAM slots via `get_sprite()` — one per 8×8 tile visible at once
6. [ ] Assign tile indices (`set_sprite_tile`) and position (`move_sprite`)
7. [ ] Update `src/config.h` if pool budget changes
8. [ ] Build and smoketest in Emulicious

---

## Step 1 — Draw in Aseprite

- Open Aseprite → New → width/height multiples of 8 (e.g., 8×16 for a 2-tile tall sprite)
- Color mode: **Sprite → Color Mode → Indexed**
- Set palette to exactly 4 entries: `#FFFFFF` (idx 0), `#AAAAAA` (idx 1), `#555555` (idx 2), `#000000` (idx 3)
- **Index 0 is always transparent** — never use it for visible pixels
- Save as `assets/sprites/<name>.aseprite`

---

## Step 2 — Export and Convert

```sh
# Export PNG (batch mode)
aseprite --batch assets/sprites/<name>.aseprite --save-as assets/sprites/<name>.png

# Or batch-export all sources at once
make export-sprites

# Convert PNG → GB 2bpp C array
python3 tools/png_to_tiles.py --bank <N> assets/sprites/<name>.png src/<name>_sprite.c <name>_tile_data
```

This generates `src/<name>_sprite.c` with:
```c
const uint8_t <name>_tile_data[];       /* 16 bytes × N tiles */
const uint8_t <name>_tile_data_count;   /* number of tiles */
```

**Never edit generated `src/<name>_sprite.c` by hand.**

Run converter tests after any change:
```sh
python3 -m unittest discover -s tests -p "test_png_to_tiles.py" -v
```

---

## Step 3 — Declare and Load

In the `.c` file that manages this sprite:

```c
/* Declare generated symbols */
extern const uint8_t <name>_tile_data[];
extern const uint8_t <name>_tile_data_count;

/* Reserve a tile base index in config.h, e.g.: */
/* #define SPRITE_TILE_BASE_<NAME>  4 */
```

Load during init (must be during VBlank or with display off):

```c
wait_vbl_done();
SPRITES_8x8;   /* set mode before loading data */
set_sprite_data(SPRITE_TILE_BASE_<NAME>, <name>_tile_data_count, <name>_tile_data);
```

---

## Step 4 — Allocate OAM Slots

```c
/* In your init function — always use the pool, never hardcode slot numbers */
uint8_t slot = get_sprite();
if (slot == SPRITE_POOL_INVALID) {
    /* handle exhausted pool */
    return;
}
set_sprite_tile(slot, SPRITE_TILE_BASE_<NAME>);
```

For a 2-tile sprite (e.g., 8×16 = top + bottom):
```c
uint8_t slot_top = get_sprite();
uint8_t slot_bot = get_sprite();
set_sprite_tile(slot_top, SPRITE_TILE_BASE_<NAME>);
set_sprite_tile(slot_bot, SPRITE_TILE_BASE_<NAME> + 1);
```

---

## Step 5 — Position the Sprite

OAM coordinates include a hardware offset — always add it:

```c
/* Place sprite at screen pixel (sx, sy) */
move_sprite(slot, (uint8_t)(sx + 8), (uint8_t)(sy + 16));

/* For a 2-tile sprite: */
move_sprite(slot_top, (uint8_t)(sx + 8), (uint8_t)(sy + 16));
move_sprite(slot_bot, (uint8_t)(sx + 8), (uint8_t)(sy + 24));  /* +8 for second tile */
```

Fully visible screen range: `oam_x ∈ [8, 167]`, `oam_y ∈ [16, 159]`.
To hide: `move_sprite(slot, 0, 0)`.

---

## Step 6 — CGB Palette (optional)

```c
/* Define 4 colors (5-bit RGB, index 0 = transparent) */
const uint16_t my_palette[] = {
    RGB(31, 31, 31),  /* idx 0: white (transparent) */
    RGB(20, 20, 20),  /* idx 1: light grey */
    RGB(10, 10, 10),  /* idx 2: dark grey */
    RGB(0,  0,  0),   /* idx 3: black */
};
set_sprite_palette(0, 1, my_palette);  /* palette 0, 1 palette entry */
```

Must be called during VBlank. OAM attribute bits 2–0 select which of the 8 OBJ palettes to use.

---

## Step 7 — Update Config

If adding sprite slots changes the OAM budget, update `src/config.h`:
```c
#define MAX_ENEMY_SPRITES  8  /* adjust pool-dependent limits here */
```

Document the OAM layout comment at the top of `config.h` so the budget stays auditable.

---

## Step 8 — Build & Smoketest

```sh
GBDK_HOME=/home/mathdaman/gbdk make
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/junk-runner.gb
```

Check:
- Sprite appears at correct position
- No tile corruption (wrong tile base index?)
- No flicker (pool exhausted? mode set after load?)

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `set_sprite_tile_data(...)` | Use `set_sprite_data(first, count, ptr)` |
| Hardcoding OAM slot number | Use `get_sprite()` / `clear_sprite()` |
| Calling `set_sprite_data` outside VBlank | Wrap with `wait_vbl_done()` |
| Palette index 0 for visible pixels | Always transparent — use indices 1–3 |
| Using 152/136 as max OAM position | Valid bounds: oam_x ∈ [8,167], oam_y ∈ [16,159] |
| Editing `src/*_sprite.c` by hand | Generated — edit `.aseprite` → re-export → re-run `png_to_tiles.py` |
| Not calling `SPRITES_8x8` before loading | Set mode first, then load data |
| Not checking `SPRITE_POOL_INVALID` | `get_sprite()` returns `0xFF` when pool is full |
| Tile base collides with another sprite | Track tile base assignments in `config.h` |

---

## Cross-References

- **`sprite-expert`** — Full API reference, coordinate system details, pool internals, CGB palette registers
- **`aseprite`** — Full Aseprite CLI reference: all flags, sprite sheet export, scripting, filtering
- **`gbdk-expert`** — OAM hardware, PPU modes, VBlank timing, LCDC register
- **`map-expert`** — Background tile pipeline (BG tiles are separate from sprite tiles)

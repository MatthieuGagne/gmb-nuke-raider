---
name: sprite-expert
description: Use when creating sprites, editing sprite assets, changing how sprites are loaded or rendered, adding new sprite types, modifying the sprite pool, changing OAM slot assignments, updating sprite tile data, or working with the Aseprite pipeline or png_to_tiles converter.
---

# Sprite Expert — Junk Runner

**Update this skill whenever the sprite system changes** (new pipeline steps, new API usage, pool budget changes, coordinate system corrections).

---

## Asset Pipeline

```
assets/sprites/<name>.aseprite  →  (make export-sprites)  →  assets/sprites/<name>.png  →  tools/png_to_tiles.py  →  src/<name>_sprite.c
```

| Step | Tool | Notes |
|------|------|-------|
| Draw pixels | Aseprite | Indexed color mode, 4-color GBC palette; canvas must be multiples of 8 |
| Export PNG | `make export-sprites` or Aseprite File → Export As | Requires `aseprite` in PATH; PNGs are checked in for CI |
| Convert | `python3 tools/png_to_tiles.py <in.png> src/<name>_sprite.c <array_name>` | Emits `const uint8_t <array_name>[]` + `<array_name>_count` |
| Use | `extern` declare in `.c` file that calls `set_sprite_data` | Generated file — **never edit by hand** |

**Aseprite setup for GBC sprites:**
- Color mode: Sprite → Color Mode → **Indexed**
- Palette: exactly 4 entries — index 0 = white `#FFFFFF`, 1 = light grey `#AAAAAA`, 2 = dark grey `#555555`, 3 = black `#000000`
- Canvas: multiples of 8 in both dimensions (each 8×8 block = one GB tile)
- **Palette index 0 is always transparent in OBJ mode** — use indices 1–3 for visible sprite pixels
- Export: File → Export As → PNG, or `make export-sprites` to batch-export all sources

**All assets in the project that use this pipeline:**

| Asset | Source | PNG | Generated C |
|-------|--------|-----|-------------|
| Player car | `assets/sprites/player_car.aseprite` | `assets/sprites/player_car.png` | `src/player_sprite.c` |
| Track tileset (7 tiles: wall/road/dashes/sand/oil/boost/finish) | `assets/maps/tileset.aseprite` | `assets/maps/tileset.png` | `src/track_tiles.c` |
| Overmap tiles (4 tiles: blank/road/hub/dest) | `assets/maps/overmap_tiles.aseprite` | `assets/maps/overmap_tiles.png` | `src/overmap_tiles.c` |

**PNG requirements for `png_to_tiles.py`:**
- Color type 3 (indexed), bit depth 8 — **default output from Aseprite** `--save-as` export; indices must be 0–3
- Color type 3 (indexed), bit depth 2 — also accepted; indices used directly
- Color type 2 (RGB8) with ≤ 4 distinct luminance values — also accepted
- Dimensions must be multiples of 8
- Each 8×8 block = one tile; tiles read left-to-right, top-to-bottom

**Aseprite CLI export (correct flag):**
```sh
aseprite --batch assets/sprites/<name>.aseprite --save-as assets/sprites/<name>.png
```
Note: `--export-type` is NOT a valid flag. Use `--save-as` with a `.png` extension.

**REQUIRED — Aseprite CLI:** ALWAYS invoke the **`aseprite`** skill before running any `aseprite` command. It has the complete flag reference and prevents common mistakes (e.g., `--export-type` is not a valid flag).

**Run tests after any converter change:**
```sh
python3 -m unittest discover -s tests -p "test_png_to_tiles.py" -v
```

---

## Sprite Pool (`src/sprite_pool.h`)

Manages OAM slot allocation. **Always use the pool** — never hardcode OAM indices.

```c
sprite_pool_init();              /* call once in player_init(); resets all 40 slots */
uint8_t slot = get_sprite();     /* returns next free slot, or SPRITE_POOL_INVALID */
clear_sprite(slot);              /* move_sprite(slot,0,0) + mark free */
clear_sprites_from(slot);        /* clear slot..MAX_SPRITES-1 */
```

`SPRITE_POOL_INVALID = 0xFF` — always check return value before using slot.

**OAM budget (MAX_SPRITES = 40):**
- Player: 2 slots (top half + bottom half in 8×8 mode)
- Remaining 38 for enemies, projectiles, HUD sprites

---

## GBDK Sprite API

```c
/* Load tile data into VRAM (do this during VBlank or with display off) */
set_sprite_data(first_tile_idx, n_tiles, data_ptr);  /* NOT set_sprite_tile_data */

/* Assign a VRAM tile to an OAM slot */
set_sprite_tile(oam_slot, tile_idx);

/* Position a sprite (OAM coordinate system — see below) */
move_sprite(oam_slot, oam_x, oam_y);

/* Mode and visibility */
SPRITES_8x8;    /* LCDC bit 2 = 0; call before loading sprite data */
SPRITES_8x16;   /* LCDC bit 2 = 1; tile bit 0 is ignored; top=tile&0xFE, bot=tile|0x01 */
SHOW_SPRITES;   /* LCDC bit 1 = 1 */
HIDE_SPRITES;   /* LCDC bit 1 = 0 */
```

**Wrong name:** `set_sprite_tile_data` does NOT exist. Use `set_sprite_data`.

---

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

**Player render pattern (camera-adjusted):**
```c
uint8_t hw_x = (uint8_t)(px + 8);
uint8_t hw_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
move_sprite(player_sprite_slot,     hw_x, hw_y);
move_sprite(player_sprite_slot_bot, hw_x, (uint8_t)(hw_y + 8u));
```

---

## CGB Palettes for Sprites

- Use `set_sprite_palette(pal_nb, n_palettes, pal_data)` or `OCPD` registers
- 8 OBJ palettes (0–7), 4 colors each, 5-bit RGB: `RGB(r, g, b)` (values 0–31)
- **Color index 0 is always transparent** — usable sprite colors: indices 1, 2, 3
- OAM attribute byte bits 2–0 select CGB palette (0–7)
- Cannot write OCPD during PPU Mode 3 — update during VBlank only

---

## VBlank Timing

`set_sprite_data` writes to VRAM — **must be called during VBlank or with display off**.

```c
wait_vbl_done();                          /* wait for VBlank */
set_sprite_data(0, n, tile_data_array);   /* VRAM write — safe in VBlank */
```

`move_sprite` writes to OAM shadow buffer (GBDK copies it via DMA) — safe anytime.

---

## Adding a New Sprite

1. Create or edit `assets/sprites/<name>.aseprite` in Aseprite (indexed color, 4-shade GBC palette, multiples of 8)
2. Export PNG: `make export-sprites` or File → Export As → `assets/sprites/<name>.png`
3. Run: `python3 tools/png_to_tiles.py assets/sprites/<name>.png src/<name>_sprite.c <name>_tile_data`
4. In your `.c` file: `extern const uint8_t <name>_tile_data[]; extern const uint8_t <name>_tile_data_count;`
5. In init: `wait_vbl_done(); set_sprite_data(base_tile, <name>_tile_data_count, <name>_tile_data);`
6. Allocate OAM slots via `get_sprite()` — one per 8×8 tile used on screen at once
7. Position with `move_sprite(slot, sx + 8, sy + 16)`
8. Update `config.h` capacity constants if pool budget changes

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `set_sprite_tile_data(...)` | Use `set_sprite_data(first, count, ptr)` |
| Hardcoding OAM slot numbers | Use `get_sprite()` / `clear_sprite()` |
| Calling `set_sprite_data` outside VBlank | Wrap with `wait_vbl_done()` unless display is off |
| Using 152/136 as max position | Visible bounds: oam_x ∈ [8,167], oam_y ∈ [16,159] |
| Editing `src/*_sprite.c` by hand | Generated — edit the `.aseprite`, re-export, re-run `png_to_tiles.py` |
| Hardcoding `uint8_t tile_data[] = {0xFF,0x00,...}` in `.c` | **NEVER** — every tile/sprite must have `.aseprite` → PNG → `png_to_tiles.py` pipeline |
| Using palette index 0 for sprite pixels | Always transparent; use indices 1–3 |
| Forgetting to check `SPRITE_POOL_INVALID` | `get_sprite()` returns `0xFF` when pool is full |
| Loading tile data before `SPRITES_8x8` | Set mode first, then load data and assign tiles |

---

## Cross-References

- **`aseprite`** — Full Aseprite CLI reference: all flags, sprite sheet options, scripting, layer/tag filtering
- **`gbdk-expert`** — OAM hardware registers, PPU modes, CGB palette registers, VBlank timing details
- **`map-expert`** — Tiled map/tileset format; tile data pipeline for background tiles (not sprites)

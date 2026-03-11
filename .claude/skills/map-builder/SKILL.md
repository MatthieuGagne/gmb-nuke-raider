---
name: map-builder
description: Use when creating a new map or track for Wasteland Racer — designing the layout, drawing in Tiled, running the TMX conversion pipeline, and wiring the generated C files into the game.
---

# Map Builder

## Overview

Step-by-step guide to create a new map from scratch. Uses the Tiled → `tmx_to_c.py` → GB pipeline.

**REQUIRED BACKGROUND:** Invoke the `map-expert` skill before writing any code — it has the full pipeline reference, GID rules, and GBDK API details.

---

## Quick Checklist

1. [ ] Design tile vocabulary (what terrain types does the map need?)
2. [ ] Draw or update tileset in Aseprite → export PNG → run `png_to_tiles.py`
3. [ ] Open/create map in Tiled — set dimensions, tile size 8×8
4. [ ] Paint layout — place `start` objectgroup with one spawn object
5. [ ] Save TMX → run `tmx_to_c.py` → verify generated C
6. [ ] Wire C files into the game (update `#include`, call init/load)
7. [ ] Build and smoketest in Emulicious

---

## Step 1 — Tileset

If extending the existing tileset (`assets/maps/tileset.aseprite`):
- Add new 8×8 tiles in Aseprite (indexed color, 4-shade GBC palette)
- Export: `make export-sprites` or `aseprite --batch assets/maps/tileset.aseprite --save-as assets/maps/tileset.png`
- Regenerate tile C array: `python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data`

If creating a new tileset for a new map:
- New `.aseprite` under `assets/maps/<mapname>_tiles.aseprite`
- Export to `assets/maps/<mapname>_tiles.png`
- Convert: `python3 tools/png_to_tiles.py assets/maps/<mapname>_tiles.png src/<mapname>_tiles.c <mapname>_tile_data`

**Tile budget:** 192 tiles in DMG bank 0, 192 more in CGB bank 1. Keep total unique tiles ≤ 192 for DMG compat.

---

## Step 2 — Draw the Map in Tiled

1. Open Tiled → New Map → **Tile size: 8×8px**, map dimensions in tiles (current: 40×36)
2. Add your tileset: Map → Add External Tileset → point to `.tsx` (or create one from the PNG)
3. Paint the tile layer named **"Track"** (layer name matters for `tmx_to_c.py`)
4. Add spawn point: Layer → New Object Layer named **"start"** → Insert Point → place it on the road
5. Save as `assets/maps/<name>.tmx` with **CSV encoding** (File → Map Properties → Tile Layer Format: CSV)

**Map constraints:**
- Tile size must be **8×8** (one GB tile)
- Layer encoding must be **CSV** (not base64/zlib)
- Must have one objectgroup named `start` with exactly one object

---

## Step 3 — Convert TMX → C

```sh
python3 tools/tmx_to_c.py assets/maps/<name>.tmx src/<name>_map.c
```

Outputs `src/<name>_map.c` with:
- `track_start_x`, `track_start_y` — spawn pixel coords
- `track_map[]` — tile index array, row-major

Run the conversion tests to verify the tool still works:
```sh
python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v
```

**Never edit `src/<name>_map.c` by hand** — it is generated. Edit the TMX and re-run.

---

## Step 4 — Wire Into the Game

In the relevant `.h` / `.c` for your map system:

```c
/* Declare generated symbols (in your map .h) */
extern const uint8_t track_map[];
extern const int16_t track_start_x;
extern const int16_t track_start_y;
extern const uint8_t track_tile_data[];
extern const uint8_t track_tile_data_count;
```

Loading sequence (must happen during / immediately after VBlank):

```c
wait_vbl_done();
set_bkg_data(0, track_tile_data_count, track_tile_data);  /* load tile graphics */
set_bkg_tiles(0, 0, MAP_TILES_W, MAP_TILES_H, track_map); /* write tilemap */
SHOW_BKG;
```

**Map dimensions** must be declared in `src/config.h`:
```c
#define MAP_TILES_W  40
#define MAP_TILES_H  36
```

Update these if your new map has different dimensions.

---

## Step 5 — Banking (if map data is large)

Generated files from `tmx_to_c.py` already include `#pragma bank 255` and `BANKREF`. When loading:

```c
{ SET_BANK(track_map);
  set_bkg_tiles(0, 0, MAP_TILES_W, MAP_TILES_H, track_map);
  RESTORE_BANK(); }
```

Wrap tile data load similarly if `track_tile_data` is in a banked file.

---

## Step 6 — Build & Smoketest

```sh
GBDK_HOME=/home/mathdaman/gbdk make
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb
```

Check:
- Map renders correctly (no garbage tiles)
- Player spawns at the right position
- Scrolling wraps without glitches

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Editing generated `src/*_map.c` by hand | Always edit the TMX and re-run `tmx_to_c.py` |
| Map layer not named "Track" | `tmx_to_c.py` looks for this layer name exactly |
| Missing `start` objectgroup | Script requires exactly one objectgroup named `start` |
| VRAM writes after game logic | Always call `wait_vbl_done()` → tile data → tilemap → then game logic |
| Tile count > 192 | DMG VRAM limit; use CGB bank 1 for overflow or reduce tiles |
| Using base64 encoding in Tiled | Set Tile Layer Format to **CSV** before saving |

---

## Cross-References

- **`map-expert`** — Full pipeline reference, GID math, GBDK BG API, CGB attribute map
- **`sprite-expert`** — For OAM sprites on top of the map
- **`gbdk-expert`** — VBlank rules, LCDC register, set_bkg_data details

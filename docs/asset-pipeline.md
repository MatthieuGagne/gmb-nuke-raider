# Asset Pipeline

This document describes how source art and map data flow from authoring tools
into the Game Boy ROM.

---

## Overview

```
Sprite editor / external tool
         │
         ▼
   assets/maps/tileset.png       (background tile art, 16×8 = 2 tiles)
   assets/maps/track.tmx         (tile map layout, 40×36)
         │                               │
         ▼                               ▼
  tools/png_to_tiles.py          tools/tmx_to_c.py
         │                               │
         ▼                               ▼
  src/track_tiles.c              src/track_map.c
  (2bpp tile data array)         (tilemap index array)
         │                               │
         └──────────┬────────────────────┘
                    ▼
            GBDK/SDCC compiler
                    │
                    ▼
         build/wasteland-racer.gb
```

Both generated `.c` files are **checked into git** so CI builds work without
Python or Tiled installed.

---

## Background Tiles

### Source file
`assets/maps/tileset.png` — an 8-pixel-tall PNG strip, one 8×8 tile per column.

### Authoring
- Open `tileset.png` in Aseprite, GIMP, or the sprite editor (`tools/run_sprite_editor.py`).
- Use at most **4 distinct grey shades** (or 4 colours from the sprite editor's palette).
- Save / export as PNG (8-bit RGB or 2-bit indexed).

### Conversion
```bash
python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data
```

Or just run `make` — the Makefile regenerates `src/track_tiles.c` automatically
when `tileset.png` is newer.

#### How it works
Each pixel's luminance is rounded to the nearest of 4 GB grey levels:
`index = round((255 - L) / 85)`, where `L = 0.299·R + 0.587·G + 0.114·B`.

Index 0 = lightest display shade; index 3 = darkest.

Each 8×8 tile is encoded as 16 bytes of GB 2bpp:
- For each row: `low_byte` (bit 0 of each pixel, MSB-first), then `high_byte` (bit 1).

### Adding more tiles
1. Extend `tileset.png` by appending 8×8 columns to the right.
2. Run `make` to regenerate `src/track_tiles.c`.
3. In Tiled, add the new tile index to `assets/maps/track.tsx` and use it in `track.tmx`.
4. Run `make` again to regenerate `src/track_map.c`.
5. Verify the ROM renders correctly: `mgba-qt build/wasteland-racer.gb`.

---

## Tile Map (Track Layout)

### Source files
- `assets/maps/track.tmx` — Tiled map file (40×36 tiles)
- `assets/maps/track.tsx` — Tiled tileset reference

### Authoring
Open `track.tmx` in [Tiled](https://www.mapeditor.org/) (free, cross-platform).
Edit tile placement, then save. The TMX uses CSV encoding; tile IDs are Tiled
1-based (GB value + 1 — so tile 0 in game = tile 1 in Tiled).

### Conversion
```bash
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

Or just `make` — same automatic-regeneration rule.

---

## Sprites

Sprites are authored in the built-in sprite editor.

```bash
python3 tools/run_sprite_editor.py
```

The editor saves a 2-bit indexed PNG (32×32 pixels = 4×4 tiles) via
`tools/sprite_editor/model.py::TileSheet.save_png`.

**Sprite → ROM** (manual step for now):
1. Save the sprite sheet from the editor.
2. Use `tools/png_to_tiles.py` to convert the PNG to a C array:
   ```bash
   python3 tools/png_to_tiles.py assets/sprites/player.png src/player_tiles.c player_tile_data
   ```
3. `#include` or `extern` the symbol in the relevant module.

> **Note:** A Makefile auto-rule for sprite sheets is out of scope for this
> pipeline (sprites are not yet stored under `assets/sprites/`). Add one when
> the sprite art workflow is established.

---

## Full Rebuild

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

This runs all generation rules (if source files are newer than generated files)
and then links the ROM.

---

## Running Unit Tests

```bash
make test          # C unit tests (gcc + Unity, no GBDK needed)
make test-tools    # Python tool tests (sprite editor, png_to_tiles)
```

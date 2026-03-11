# Asset Pipeline

This document describes how source art and map data flow from authoring tools
into the Game Boy ROM.

---

## Overview

```
  assets/maps/tileset.aseprite   (background tile art — canonical source)
  assets/sprites/*.aseprite      (sprite art — canonical source)
         │
         ▼  aseprite --batch  (or: make export-sprites)
         │
   assets/maps/tileset.png       (exported PNG, checked in for CI)
   assets/sprites/*.png          (exported PNG, checked in for CI)
   assets/maps/track.tmx         (tile map layout, 40×36)
         │               │               │
         ▼               ▼               ▼
  png_to_tiles.py  png_to_tiles.py  tmx_to_c.py
         │               │               │
         ▼               ▼               ▼
  src/track_tiles.c  src/*_sprite.c  src/track_map.c
  (2bpp tile data)   (2bpp tile data) (tilemap index array)
         │               │               │
         └───────────────┴───────────────┘
                         ▼
                 GBDK/SDCC compiler
                         │
                         ▼
              build/wasteland-racer.gb
```

Generated `.c` files and exported `.png` files are **checked into git** so CI
builds work without Aseprite, Python, or Tiled installed.

---

## Background Tiles

### Source file
`assets/maps/tileset.aseprite` — canonical Aseprite source.
`assets/maps/tileset.png` — exported PNG (checked in; regenerate with `make export-sprites`).

The PNG is an 8-pixel-tall strip, one 8×8 tile per column.

### Authoring in Aseprite
1. Open `assets/maps/tileset.aseprite` in Aseprite.
2. Canvas is 8px tall, N×8px wide (one 8×8 tile per column). Extend rightward to add tiles.
3. Use **indexed color mode** (Sprite → Color Mode → Indexed) with exactly **4 palette entries**:

   | Index | Colour | RGB |
   |-------|--------|-----|
   | 0 | White | `#FFFFFF` |
   | 1 | Light grey | `#AAAAAA` |
   | 2 | Dark grey | `#555555` |
   | 3 | Black | `#000000` |

4. Export: **File → Export As**, format PNG. Or run `make export-sprites`.

### Conversion
```bash
python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data
```

Or just `make` — regenerates `src/track_tiles.c` automatically when `tileset.png` is newer.

#### How it works
Each pixel's luminance is rounded to the nearest of 4 GB grey levels:
`index = round((255 - L) / 85)`, where `L = 0.299·R + 0.587·G + 0.114·B`.

Index 0 = lightest display shade; index 3 = darkest.

Each 8×8 tile is encoded as 16 bytes of GB 2bpp:
- For each row: `low_byte` (bit 0 of each pixel, MSB-first), then `high_byte` (bit 1).

### Adding more tiles
1. Open `assets/maps/tileset.aseprite` in Aseprite, extend canvas rightward by 8px per new tile, draw tiles.
2. Export PNG: `make export-sprites` (requires Aseprite in PATH) or File → Export As.
3. Run `make` to regenerate `src/track_tiles.c`.
4. In Tiled, add the new tile index to `assets/maps/track.tsx` and use it in `track.tmx`.
5. Run `make` again to regenerate `src/track_map.c`.
6. Verify in Emulicious: `java -jar ~/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb`.

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

### Source files
`assets/sprites/<name>.aseprite` — canonical Aseprite source.
`assets/sprites/<name>.png` — exported PNG (checked in; regenerate with `make export-sprites`).

### Authoring in Aseprite
1. Open or create `assets/sprites/<name>.aseprite` in Aseprite.
2. Canvas dimensions must be **multiples of 8** in both axes. Each 8×8 block = one GB tile.
3. Use **indexed color mode** with the same 4-shade GBC palette as above (indices 0–3).
   - Palette index 0 (white) renders as the lightest GBC shade.
   - In OBJ (sprite) mode, **palette index 0 is always transparent** — use indices 1–3 for visible pixels.
4. A 32×32 canvas = 4×4 = 16 tiles (useful for a full sprite sheet).
5. Export: **File → Export As**, format PNG, filename `assets/sprites/<name>.png`.
   Or run `make export-sprites` to re-export all `.aseprite` sources at once.

### Conversion
```bash
python3 tools/png_to_tiles.py assets/sprites/<name>.png src/<name>_sprite.c <name>_tile_data
```

Or just `make` — the Makefile has a pattern rule for `src/*_sprite.c`.

### Sprite → ROM
1. Draw in Aseprite → export to `assets/sprites/<name>.png`.
2. Run `make` to regenerate `src/<name>_sprite.c`.
3. In your `.c` file: `extern const uint8_t <name>_tile_data[]; extern const uint8_t <name>_tile_data_count;`
4. In init (during VBlank): `wait_vbl_done(); set_sprite_data(base_tile, <name>_tile_data_count, <name>_tile_data);`

---

## Exporting All Aseprite Sources

Requires Aseprite installed and available as `aseprite` in `$PATH`.

```bash
make export-sprites
```

This re-exports all `.aseprite` files under `assets/` to their corresponding `.png` files.
Commit both the `.aseprite` and the regenerated `.png` together.

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
make test-tools    # Python tool tests (png_to_tiles, tmx_to_c)
```

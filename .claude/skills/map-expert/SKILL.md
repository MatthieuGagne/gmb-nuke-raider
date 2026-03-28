---
name: map-expert
description: Use when creating, editing, or converting maps for Junk Runner — Tiled TMX format, GID decoding, Python pipeline (tmx_to_c, png_to_tiles, gen_tileset), or GB background tilemap hardware (BG tile maps, SCX/SCY, VRAM layout, CGB attributes).
---

# Map Expert

## Quick Command Reference

| Tool | Command | Notes |
|------|---------|-------|
| `gen_tileset.py` | `python3 tools/gen_tileset.py assets/maps/tileset.png` | Generates 6-tile hardcoded tileset PNG |
| `png_to_tiles.py` | `python3 tools/png_to_tiles.py --bank <N> <in.png> <out.c> <array>` | `--bank` required; use `255` for autobanker |
| `tmx_to_c.py` | `python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c` | Track map only |
| `tmx_to_array_c.py` | `python3 tools/tmx_to_array_c.py assets/maps/overmap.tmx src/overmap_map.c overmap_map config.h` | Overmap only |
| `create_assets.py` | `python3 assets/maps/create_assets.py` | One-time bootstrap |

**Source of truth:** `assets/maps/track.tmx` (and `overmap.tmx`) are canonical. Never hand-edit `src/track_map.c` or `src/overmap_map.c` — they are silently overwritten on the next build.

**Test:** `python3 -m unittest discover -s tests -p "test_png_to_tiles.py" -v`

Map dimensions: **40×36 tiles** (W×H).

---

## Tileset Tile Indices

| Index | Name | Visual |
|-------|------|--------|
| 0 | Wall / off-track | Solid dark-grey |
| 1 | Road | Solid light-grey |
| 2 | Center dashes | Solid black |
| 3 | Sand | White/dark-grey checkerboard |
| 4 | Oil puddle | Black with grey center rect |
| 5 | Boost stripes | Alternating row pattern |

---

## Overview

Full reference for the Junk Runner map pipeline: Tiled authoring → Python conversion → GB hardware rendering.

**Keep this skill current:** When you modify any tool in `tools/` or `assets/maps/`, add a new map tool, change the TMX schema, or add GB tilemap features — update the relevant section in the same PR. The skill is the source of truth for the pipeline.

**Track pipeline:**
```
assets/maps/tileset.png   ←─ gen_tileset.py (or hand-drawn in Aseprite)
         │
         ▼
tools/png_to_tiles.py  →  src/track_tiles.c  (2bpp C array)
assets/maps/track.tmx  →  tools/tmx_to_c.py  →  src/track_map.c  (tile index array)
```

**Overmap pipeline (separate converter):**
```
assets/maps/overmap_tiles.aseprite  →  (Aseprite export)  →  assets/maps/overmap_tiles.png
assets/maps/overmap_tiles.png  →  tools/png_to_tiles.py  →  src/overmap_tiles.c
assets/maps/overmap.tmx  →  tools/tmx_to_array_c.py assets/maps/overmap.tmx src/overmap_map.c overmap_map config.h  →  src/overmap_map.c
```

Note: the overmap uses `tmx_to_array_c.py` (not `tmx_to_c.py`) and takes `config.h` as an extra arg.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Hardcoding `- 1` as tile offset | Read `firstgid` from `<tileset>` element |
| GID 0 underflows to 255 (uint8) | Check `gid == 0` before subtracting; return 0 |
| Ignoring GID flip flags | Mask with `& 0x0FFFFFFF` before subtracting `firstgid` |
| Editing `src/track_map.c` by hand | It's generated — edit `assets/maps/track.tmx` and re-run |
| Missing `start` objectgroup | TMX must have `<objectgroup name="start">` with one object |
| `encoding: "csv"` in XML = string | Split on `','`, not a JSON array |
| Object `type` vs `class` | Pre-1.9: `type` field; since 1.9: `class` field |
| Assuming RGB PNG from Aseprite | Aseprite exports indexed color (type 3) — check IHDR before reading pixels |

**For full Python implementation code, PNG read/write utilities, Aseprite sync, GB hardware deep-dive (VRAM layout, LCDC bits, scroll registers, CGB attributes), and Tiled format reference — see [`REFERENCE.md`](REFERENCE.md).**

---

## Cross-References

- **`sprite-expert`** — OAM sprite asset pipeline, sprite pool, sprite tile loading; use for anything that involves sprites rather than background/window tiles

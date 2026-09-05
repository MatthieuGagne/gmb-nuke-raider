# Map conversion pipeline

Read by the `map-expert` agent — the step-by-step data flow from tileset art and TMX sources to
the generated C files, for both the track and the overmap converters.

## Pipeline Overview

**Track pipeline (3-step, driven by Makefile):**
```
assets/maps/tileset.png  ─┐
assets/maps/track.tsx     ├─→ png_to_tiles.py → src/track_tiles.c + build/track_tile_id_map.json + src/track_tileset_meta.h
assets/maps/track*.tmx   ─┤
                           └─→ tmx_to_c.py (--id-map) → src/track*_map.c
```

Step 1: `tmx_to_c.py --emit-rotation-manifest` scans all track TMXs for rotated tiles → `build/track_rotation_manifest.json`
Step 2: `png_to_tiles.py` encodes tileset + rotation variants → `src/track_tiles.c`, `build/track_tile_id_map.json`, `src/track_tileset_meta.h`
Step 3: `tmx_to_c.py --id-map` converts each TMX → `src/track*_map.c` using the id map

**Overmap pipeline (separate converter):**
```
assets/maps/overmap_tiles.aseprite  →  (Aseprite export)  →  assets/maps/overmap_tiles.png
assets/maps/overmap_tiles.png  →  tools/png_to_tiles.py --bank 255  →  src/overmap_tiles.c  (array `overmap_tile_data`)
assets/maps/overmap.tmx  →  tools/overmap_to_c.py  →  src/overmap_map.c
```

Both outputs are checked into git; `make` regenerates them when sources change (Makefile rules
`src/overmap_tiles.c`, `src/overmap_map.c`).

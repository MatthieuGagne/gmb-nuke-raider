---
name: track-build
description: Rebuild the track pipeline and ROM after editing a .tmx map or tileset PNG. Use when the user says "build the track", "build the track and the game", or after any change to track.tmx / track2.tmx / track3.tmx / tileset.png.
---

Run the full build. The Makefile auto-detects which track files changed and regenerates only what's needed (rotation manifest → tile data → map C files → link ROM).

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```

On success: report ROM size with `ls -lh build/nuke-raider.gb`.

On failure: extract lines containing `error:` and show each as `file:line: message`. Distinguish compiler errors (fixable in source) from linker errors.

## Pipeline steps triggered automatically by make

1. `tmx_to_c.py --emit-rotation-manifest` — scans all TMX files for rotated tiles
2. `png_to_tiles.py` — encodes `tileset.png` → `src/track_tiles.c` + `src/track_tileset_meta.h`
3. `tmx_to_c.py --id-map` — converts each `.tmx` → `src/track_map.c`, `src/track2_map.c`, `src/track3_map.c`
4. GBDK `lcc` compiler — compiles changed `.c` files and links the ROM

## Common workflow

If the tileset was also edited in Aseprite, run `aseprite-build` first to export the PNG, then `track-build`.

If the turret tile (col 8, row 0 = tile index 8) changed in the tileset, also sync `turret.png` before building:

```sh
python3 - <<'EOF'
from PIL import Image
tileset = Image.open("assets/maps/tileset.png")
tileset.crop((64, 0, 72, 8)).save("assets/sprites/turret.png")
EOF
```

`make` will then auto-regenerate `src/turret_sprite.c` from the updated PNG.

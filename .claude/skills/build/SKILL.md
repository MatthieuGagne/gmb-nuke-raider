---
name: build
description: Build the GBC ROM with `make` — including after editing a map or tileset. Use when verifying a build, checking for compiler errors, confirming the ROM was produced, or when the user says "build the track", "build the track and the game", or has changed track*.tmx / tileset.png.
---

Run `make`.

On success: report ROM size with `ls -lh build/nuke-raider.gb`.

On failure: extract lines containing "error:" from the output, show each as
`file:line: message`. Distinguish compiler errors (fixable in source) from
linker errors. Identify which file to look at first. Do not attempt to fix
errors automatically unless the user asks.

## Track/map pipeline

`make` auto-detects which track files changed and regenerates only what's needed — no separate
command: `tmx_to_c.py --emit-rotation-manifest` (scan TMXs for rotated tiles) → `png_to_tiles.py`
(`tileset.png` → `src/track_tiles.c` + `src/track_tileset_meta.h`) → `tmx_to_c.py --id-map`
(each `.tmx` → `src/track*_map.c`) → `lcc` compile and link.

If the tileset was edited in Aseprite, run the `aseprite-build` skill first to export the PNG
(it also covers syncing `turret.png` when the turret tile changed), then build.

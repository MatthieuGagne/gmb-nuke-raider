---
name: aseprite-build
description: Export .aseprite source files to PNG. Use when the user says "build the aseprite", "export the tileset", or has edited an .aseprite file and needs the PNG updated before a game build.
---

Export the modified .aseprite file(s) to PNG using Aseprite in batch mode.

## Tileset (most common)

```sh
aseprite --batch assets/maps/tileset.aseprite --save-as assets/maps/tileset.png
```

## All sprites (full re-export)

```sh
make export-sprites
```

## Single sprite

```sh
aseprite --batch assets/sprites/<name>.aseprite --save-as assets/sprites/<name>.png
```

On success: confirm the PNG was written (no output = success for Aseprite batch mode).

On failure: show the error output. Common causes: wrong file path, unsupported color mode (must be indexed, 4 colours), dimensions not a multiple of 8.

After export, run the `track-build` skill (or `build` skill) to regenerate the game ROM from the updated PNG.

## After editing tileset.aseprite — sync turret.png

`assets/sprites/turret.png` is extracted from the tileset (tile index 8, col 8 row 0). It has no `.aseprite` source of its own. When `tileset.aseprite` changes the turret tile, sync it manually before building:

```sh
python3 - <<'EOF'
from PIL import Image
tileset = Image.open("assets/maps/tileset.png")
tileset.crop((64, 0, 72, 8)).save("assets/sprites/turret.png")
EOF
```

Then `make` will auto-regenerate `src/turret_sprite.c` from the updated PNG.

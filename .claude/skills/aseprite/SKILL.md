---
name: aseprite
description: "Use when running Aseprite from the command line, exporting sprites or sprite sheets, using --batch mode, working with Aseprite layers/tags/frames, scripting Aseprite, or looking up any aseprite CLI flag. Also covers exporting .aseprite sources to PNG before a game build — \"build the aseprite\", \"export the tileset\", or an edited .aseprite whose PNG needs regenerating."
---

# Aseprite Reference

Full flag tables (core, sprite sheet, filtering, filename variables, image manipulation,
padding, scripting, introspection) are in **`references/flags.md`** — read it when you need a
flag this file does not name.

## Invocation Pattern

Always use `--batch` for non-interactive use. Without it, the GUI launches.

```sh
aseprite --batch <input.aseprite> [options]
```

**Order matters:** options apply to the most recently opened file. Put filters (`--layer`,
`--tag`) *before* `--save-as` or `--sheet`. `--split-layers` / `--split-tags` must precede the
input filename.

## Export: single file

```sh
aseprite --batch sprite.aseprite --save-as output.png     # PNG
aseprite --batch sprite.aseprite --save-as output.gif     # GIF
aseprite --batch sprite.aseprite --scale 2 --save-as output.png
```

`--save-as <filename>` exports the current sprite. **With multiple frames Aseprite writes
numbered files** (`output1.png`, `output2.png`, …) — not a sheet. Use `--sheet` for multi-frame
sources, or `--oneframe` if you only want frame 0.

**NOT a valid flag:** `--export-type` — use `--save-as` with the desired extension.

## Nuke Raider pipeline

```sh
# All sources at once (preferred)
make export-sprites

# Single sprite
aseprite --batch assets/sprites/<name>.aseprite --save-as assets/sprites/<name>.png

# Tileset
aseprite --batch assets/maps/tileset.aseprite --save-as assets/maps/tileset.png
```

Aseprite batch mode prints nothing on success — confirm by checking the PNG was written. On
failure, show the error output; the usual causes are a wrong path, a non-indexed color mode, or
dimensions that are not a multiple of 8.

PNG requirements for `png_to_tiles.py` downstream:

- Indexed color (color type 3), 4-color palette, dimensions multiples of 8
- Do **not** pass `--color-mode` unless you need to force conversion

After exporting, run the `build` skill to regenerate the ROM from the updated PNG.

### After editing `tileset.aseprite` — sync `turret.png`

`assets/sprites/turret.png` is extracted from the tileset (tile index 8, col 8 row 0). It has no
`.aseprite` source of its own. When `tileset.aseprite` changes the turret tile, sync it before
building:

```sh
py -c "from PIL import Image; Image.open('assets/maps/tileset.png').crop((64,0,72,8)).save('assets/sprites/turret.png')"
```

(One line on purpose — worktree-isolated sessions refuse shell heredocs.) Then `make`
auto-regenerates `src/turret_sprite.c` from the updated PNG.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `--export-type png` | Not a valid flag — use `--save-as file.png` |
| Omitting `--batch` | GUI launches; script hangs |
| Filters after `--save-as` | Filters must come *before* `--save-as` / `--sheet` |
| `--split-tags` after input | `--split-layers` / `--split-tags` must precede the input filename |
| Expecting single PNG for multi-frame | Aseprite auto-appends frame numbers; use `--sheet`, or `--oneframe` for frame 0 only |

## Cross-References

- **`references/flags.md`** — the complete CLI flag tables
- **`sprite-expert`** agent — Nuke Raider sprite pipeline, OAM API, indexed palette setup,
  the Makefile override rule needed for multi-frame sprites
- **`map-expert`** agent — Background tileset export pipeline

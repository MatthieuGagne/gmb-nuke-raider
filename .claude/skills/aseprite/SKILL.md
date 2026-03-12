---
name: aseprite
description: Use when running Aseprite from the command line, exporting sprites or sprite sheets, using --batch mode, working with Aseprite layers/tags/frames, scripting Aseprite, or looking up any aseprite CLI flag.
---

# Aseprite Reference

## Invocation Pattern

Always use `--batch` for non-interactive use. Without it, the GUI launches.

```sh
aseprite --batch <input.aseprite> [options]
```

**Order matters:** options apply to the most recently opened file. Put filters (--layer, --tag) *before* --save-as or --sheet.

---

## Core Flags

| Flag | Effect |
|------|--------|
| `-b, --batch` | Run headless — no GUI. Required for scripts and CI. |
| `-p, --preview` | Dry-run: print what would happen, write nothing. |
| `-v, --verbose` | Log details to `aseprite.log`. |
| `--debug` | Write `DebugOutput.txt` to desktop. |
| `--version` | Print version and exit. |
| `-?, --help` | List all CLI flags. |

---

## Export: Single File

```sh
# Export all frames as a PNG sequence (frame001.png, frame002.png, …)
aseprite --batch sprite.aseprite --save-as output.png

# Export as GIF
aseprite --batch sprite.aseprite --save-as output.gif

# Scale 2×
aseprite --batch sprite.aseprite --scale 2 --save-as output.png
```

`--save-as <filename>` — exports the current sprite. When the sprite has multiple frames, Aseprite appends a zero-padded frame number automatically (e.g., `frame001.png`).

**NOT a valid flag:** `--export-type` — use `--save-as` with the desired extension instead.

---

## Export: Sprite Sheet

```sh
aseprite --batch sprite.aseprite \
  --sheet sheet.png \
  --data sheet.json \
  --format json-hash \
  --sheet-type packed
```

| Flag | Values / Notes |
|------|----------------|
| `--sheet <file>` | Output PNG for the atlas |
| `--data <file>` | Output JSON metadata |
| `--format` | `json-hash` (default) or `json-array` |
| `--sheet-type` | `horizontal` · `vertical` · `rows` · `columns` · `packed` |
| `--sheet-width <px>` | Fix atlas width; height expands as needed |
| `--sheet-height <px>` | Fix atlas height; width expands as needed |
| `--sheet-pack` | Enable packing algorithm (same as `--sheet-type packed`) |
| `--merge-duplicates` | Deduplicate identical frames in the atlas |
| `--ignore-empty` | Skip empty frames/layers |
| `--export-tileset` | Export tilesets from visible tilemap layers |

---

## Layer & Frame Filtering

Apply these **before** `--save-as` or `--sheet`:

```sh
# Export only "Outline" layer
aseprite --batch sprite.aseprite --layer "Outline" --save-as out.png

# Export frames tagged "Run"
aseprite --batch sprite.aseprite --tag "Run" --save-as run.png

# Export frames 2–5 (0-based)
aseprite --batch sprite.aseprite --frame-range 2,5 --save-as out.png

# Split each tag into its own file  (use {tag} in filename)
aseprite --batch sprite.aseprite --split-tags --save-as frames_{tag}.png
```

| Flag | Effect |
|------|--------|
| `--layer <name>` | Export one layer only |
| `--all-layers` | Include hidden layers |
| `--ignore-layer <name>` | Exclude a layer |
| `--tag <name>` | Export frames within this animation tag |
| `--frame-range from,to` | Export frame range (0-based inclusive) |
| `--split-layers` | Each visible layer → separate file (must precede input filename) |
| `--split-tags` | Each animation tag → separate file |
| `--split-slices` | Each slice → separate file |
| `--split-grid` | Each grid cell → separate file in sheet |

---

## Filename Format Variables

Used with `--filename-format` and `--tagname-format`:

| Variable | Expands to |
|----------|-----------|
| `{title}` | Sprite filename without extension |
| `{tag}` | Current animation tag name |
| `{layer}` | Layer name |
| `{frame}` | Frame number (zero-padded) |
| `{frames}` | Total frame count |
| `{framenum}` | Frame number (no padding) |

```sh
aseprite --batch sprite.aseprite --split-tags \
  --filename-format "{title}_{tag}_{frame}.png" \
  --save-as out.png
```

---

## Image Manipulation

| Flag | Effect |
|------|--------|
| `--scale <factor>` | Resize (e.g., `--scale 2`) |
| `--color-mode <mode>` | Convert: `rgb` · `grayscale` · `indexed` |
| `--dithering-algorithm` | `none` · `ordered` · `old` |
| `--dithering-matrix` | `bayer8x8` · `bayer4x4` · `bayer2x2` |
| `--palette <file>` | Apply palette before export |
| `--trim` | Remove empty border pixels |
| `--trim-sprite` | Trim entire sprite bounds |
| `--trim-by-grid` | Trim to grid boundaries |
| `--crop x,y,w,h` | Export only this rect |
| `--extrude` | Duplicate edge pixels outward by 1px |
| `--slice <name>` | Export only the area of a named slice |
| `--oneframe` | Load only the first frame |

---

## Padding (for sprite sheets)

| Flag | Effect |
|------|--------|
| `--border-padding <px>` | Padding around the whole sheet |
| `--shape-padding <px>` | Gap between frames |
| `--inner-padding <px>` | Padding inside each frame border |

---

## Scripting

```sh
# Run a Lua script
aseprite --batch --script my_script.lua

# Pass parameters to the script
aseprite --batch sprite.aseprite --script process.lua --script-param key=value
```

In the Lua script, read params via `app.params["key"]`.

The `--shell` flag opens an interactive Lua REPL (not useful in CI).

---

## Introspection

```sh
# List layers (also adds to JSON if --data is present)
aseprite --batch sprite.aseprite --list-layers

# List tags with frame ranges
aseprite --batch sprite.aseprite --list-tags

# List slices
aseprite --batch sprite.aseprite --list-slices

# List layers with group hierarchy
aseprite --batch sprite.aseprite --list-layer-hierarchy
```

---

## Junk Runner Pipeline

```sh
# Export a sprite to PNG (used by make export-sprites)
aseprite --batch assets/sprites/<name>.aseprite --save-as assets/sprites/<name>.png

# Batch-export all sprites
make export-sprites
```

PNG requirements for `png_to_tiles.py` downstream:
- Indexed color (color type 3), 4-color palette, dimensions multiples of 8
- Do **not** pass `--color-mode` unless you need to force conversion

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `--export-type png` | Not a valid flag — use `--save-as file.png` |
| Omitting `--batch` | GUI launches; script hangs |
| Filters after `--save-as` | Filters must come *before* `--save-as` / `--sheet` |
| `--split-tags` after input | `--split-layers` / `--split-tags` must precede the input filename |
| Expecting single PNG for multi-frame | Aseprite auto-appends frame numbers; use `--oneframe` if you want frame 0 only |

---

## Cross-References

- **`sprite-expert`** — Junk Runner sprite pipeline, OAM API, indexed palette setup
- **`map-expert`** — Background tileset export pipeline

# Aseprite CLI — full flag reference

Companion to `../SKILL.md`. Ordering rule still applies: filters go **before** `--save-as` /
`--sheet`, and `--split-layers` / `--split-tags` must precede the input filename.

## Core

| Flag | Effect |
|------|--------|
| `-b, --batch` | Run headless — no GUI. Required for scripts and CI. |
| `-p, --preview` | Dry-run: print what would happen, write nothing. |
| `-v, --verbose` | Log details to `aseprite.log`. |
| `--debug` | Write `DebugOutput.txt` to desktop. |
| `--version` | Print version and exit. |
| `-?, --help` | List all CLI flags. |

## Sprite sheet

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

## Layer & frame filtering

```sh
aseprite --batch sprite.aseprite --layer "Outline" --save-as out.png
aseprite --batch sprite.aseprite --tag "Run" --save-as run.png
aseprite --batch sprite.aseprite --frame-range 2,5 --save-as out.png
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

## Filename format variables

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

## Image manipulation

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

## Padding (sprite sheets)

| Flag | Effect |
|------|--------|
| `--border-padding <px>` | Padding around the whole sheet |
| `--shape-padding <px>` | Gap between frames |
| `--inner-padding <px>` | Padding inside each frame border |

## Scripting

```sh
aseprite --batch --script my_script.lua
aseprite --batch sprite.aseprite --script process.lua --script-param key=value
```

In the Lua script, read params via `app.params["key"]`.
`--shell` opens an interactive Lua REPL (not useful in CI).

## Introspection

```sh
aseprite --batch sprite.aseprite --list-layers            # also added to --data JSON if present
aseprite --batch sprite.aseprite --list-tags              # tags with frame ranges
aseprite --batch sprite.aseprite --list-slices
aseprite --batch sprite.aseprite --list-layer-hierarchy   # layers with group hierarchy
```

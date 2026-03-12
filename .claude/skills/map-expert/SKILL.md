---
name: map-expert
description: Use when creating, editing, or converting maps for Junk Runner — Tiled TMX format, GID decoding, Python pipeline (tmx_to_c, png_to_tiles, gen_tileset), or GB background tilemap hardware (BG tile maps, SCX/SCY, VRAM layout, CGB attributes).
---

# Map Expert

## Overview

Full reference for the Junk Runner map pipeline: Tiled authoring → Python conversion → GB hardware rendering.

**Keep this skill current:** When you modify any tool in `tools/` or `assets/maps/`, add a new map tool, change the TMX schema, or add GB tilemap features — update the relevant section of this skill in the same PR. The skill is the source of truth for the pipeline.

**Track pipeline:**
```
assets/maps/tileset.png   ←─ gen_tileset.py (or hand-drawn in Aseprite)
         │
         ▼
tools/png_to_tiles.py  →  src/track_tiles.c  (2bpp C array)
assets/maps/track.tmx  →  tools/tmx_to_c.py  →  src/track_map.c  (tile index array)
```

**Overmap pipeline (separate converter — note different script name):**
```
assets/maps/overmap_tiles.aseprite  →  (Aseprite export or Python)  →  assets/maps/overmap_tiles.png
assets/maps/overmap_tiles.png  →  tools/png_to_tiles.py  →  src/overmap_tiles.c
assets/maps/overmap.tmx        →  tools/tmx_to_array_c.py assets/maps/overmap.tmx src/overmap_map.c overmap_map config.h  →  src/overmap_map.c
```

Note: the overmap uses `tmx_to_array_c.py` (not `tmx_to_c.py`) and takes `config.h` as an extra arg.

---

## Python Tool Reference

### `tools/gen_tileset.py` — Generate Tileset PNG

Generates the 6-tile hardcoded tileset PNG (48×8, RGB).

```
python3 tools/gen_tileset.py assets/maps/tileset.png
```

**Tile indices:**
| Index | Name            | Visual                        |
|-------|-----------------|-------------------------------|
| 0     | Wall / off-track| Solid dark-grey               |
| 1     | Road            | Solid light-grey              |
| 2     | Center dashes   | Solid black                   |
| 3     | Sand            | White/dark-grey checkerboard  |
| 4     | Oil puddle      | Black with grey center rect   |
| 5     | Boost stripes   | Alternating row pattern       |

---

### `tools/png_to_tiles.py` — PNG → GB 2bpp C Array

```
python3 tools/png_to_tiles.py <tileset.png> <out.c> <array_name>
```

Outputs:
```c
const uint8_t <array_name>[];        // 16 bytes × N tiles (2bpp)
const uint8_t <array_name>_count;   // number of tiles
```

**Supported PNG formats:**
- Color type 3 (indexed), bit depth 2 — palette index used directly (0–3)
- Color type 2 (RGB), bit depth 8 — luminance quantised to GB index 0–3 (rejects >4 distinct luminance values)

**Luminance → GB index:** 0=white (L≈255), 1=light-grey, 2=dark-grey, 3=black (L≈0)

**2bpp encoding:** each 8×8 tile = 16 bytes; each row = 2 bytes (low bit plane, high bit plane). Pixel color = `(high_bit << 1) | low_bit`, bit 7 = leftmost pixel.

Test: `python3 -m unittest discover -s tests -p "test_png_to_tiles.py" -v`

---

### Manipulating Tileset PNGs with Python stdlib (no PIL)

**Aseprite exports tileset PNGs as indexed color (type 3), bit depth 8, not RGB.**
Always check the IHDR color_type before reading pixels — assuming RGB will cause `IndexError`.

**Read + write recipe (handles Aseprite's indexed format):**

```python
import struct, zlib

def read_indexed_png(fname):
    """Returns (width, height, palette, rows) where rows[y] is a list of palette indices."""
    with open(fname, 'rb') as f:
        data = f.read()
    pos = 8; idat = b''; w = h = 0; palette = []
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        ct = data[pos+4:pos+8].decode('ascii')
        cd = data[pos+8:pos+8+length]
        if ct == 'IHDR':
            w, h, bd, color_type = struct.unpack('>IIBB', cd[:10])
            assert color_type == 3 and bd == 8, f"Expected indexed/8-bit got ct={color_type} bd={bd}"
        elif ct == 'PLTE':
            palette = [(cd[i], cd[i+1], cd[i+2]) for i in range(0, len(cd), 3)]
        elif ct == 'IDAT':
            idat += cd
        pos += 12 + length
    raw = zlib.decompress(idat)
    rows = [list(raw[y*(1+w)+1 : y*(1+w)+1+w]) for y in range(h)]
    return w, h, palette, rows

def write_indexed_png(fname, width, height, palette, rows):
    def chunk(name, payload):
        c = name.encode('ascii') + payload
        return struct.pack('>I', len(payload)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    raw = b''.join(b'\x00' + bytes(row) for row in rows)
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0)
    plte = b''.join(bytes(c) for c in palette)
    with open(fname, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk('IHDR', ihdr))
        f.write(chunk('PLTE', plte))
        f.write(chunk('IDAT', zlib.compress(raw)))
        f.write(chunk('IEND', b''))

# Palette index lookup by luminance:
def palette_map(palette):
    """Returns dict {'W':idx, 'L':idx, 'D':idx, 'B':idx} from a 4-entry GB palette."""
    m = {}
    for i, rgb in enumerate(palette):
        l = rgb[0]  # all channels equal for greyscale
        if l >= 230: m['W'] = i
        elif l >= 140: m['L'] = i
        elif l >= 60:  m['D'] = i
        else:          m['B'] = i
    return m
```

**Adding a new tile to a tileset:**
```python
w, h, palette, rows = read_indexed_png('assets/maps/overmap_tiles.png')
pm = palette_map(palette)
W, L, D, B = pm['W'], pm['L'], pm['D'], pm['B']
new_tile = [
    [W, W, B, B, B, B, W, W],  # row 0
    # ... 7 rows of 8 palette indices ...
]
new_rows = [rows[y] + new_tile[y] for y in range(h)]
write_indexed_png('assets/maps/overmap_tiles.png', w + 8, h, palette, new_rows)
```

**Aseprite CLI: syncing the `.aseprite` file after manually editing the PNG**

When you expand a tileset PNG using Python, sync the `.aseprite` source with a Lua script:

```lua
-- Usage: aseprite --batch assets/maps/overmap_tiles.aseprite --script sync_tile.lua
local sprite = app.activeSprite
-- NOTE: sprite:crop(0,0,W,H) expands the canvas but NOT the cel image.
-- Check image.width and create a new Image if smaller than the desired width:
local image = sprite.cels[1].image
if image.width < TARGET_W then
  local newImage = Image(TARGET_W, 8, image.colorMode)
  for y = 0, 7 do
    for x = 0, image.width - 1 do
      newImage:putPixel(x, y, image:getPixel(x, y))
    end
  end
  -- Draw new tile pixels into newImage at x = old_width
  sprite.cels[1].image = newImage
end
sprite:saveAs(sprite.filename)
```

Key pitfalls:
- `sprite:resize(W, H)` **scales** content — never use to expand canvas
- `sprite:crop(0, 0, W, H)` expands canvas but cel image stays at original size
- `sprite:save()` does not exist; use `sprite:saveAs(sprite.filename)`
- The Aseprite file's canvas and cel size are independent — always check both

---

### `tools/tmx_to_c.py` — TMX → C Map Array

```
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

Outputs `src/track_map.c`:
```c
/* GENERATED — do not edit by hand. Source: assets/maps/track.tmx */
#include "track.h"
const int16_t track_start_x = <px>;
const int16_t track_start_y = <px>;
const uint8_t track_map[MAP_TILES_H * MAP_TILES_W] = {
    /* row  0 */ 0,1,1,...,
    ...
};
```

**Key logic:**
```python
GID_CLEAR_FLAGS = 0x0FFFFFFF

def gid_to_tile_id(gid, firstgid):
    if gid == 0:
        return 0           # empty cell → 0
    gid &= GID_CLEAR_FLAGS  # strip H/V/D flip bits
    return gid - firstgid   # 0-indexed GB tile ID
```

- Reads `firstgid` from `<tileset firstgid="...">` — **do not hardcode `- 1`**
- Requires a `start` objectgroup with one object; spawn position read from object `x`/`y`
- Only CSV encoding supported

**Common conversion mistakes:**
| Mistake | Fix |
|---------|-----|
| Hardcoding `- 1` as tile offset | Read `firstgid` from `<tileset>` element |
| GID 0 underflows to 255 (uint8) | Check `gid == 0` before subtracting; return 0 |
| Ignoring GID flip flags | Mask with `& 0x0FFFFFFF` before subtracting `firstgid` |
| Editing `src/track_map.c` by hand | It's generated — edit `assets/maps/track.tmx` and re-run |
| Missing `start` objectgroup | TMX must have `<objectgroup name="start">` with one object |

Test: `python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v`

---

### `assets/maps/create_assets.py` — Bootstrap Map Assets

One-time helper that generates `tileset.png`, `track.tsx`, and `track.tmx` from the hardcoded oval track shape.

```
python3 assets/maps/create_assets.py
```

Map dimensions: **40×36 tiles** (W×H). TMX uses 1-based Tiled IDs (GB value + 1).

---

## Adding a New Converter

1. Create `tools/<name>_to_c.py` following the same pattern as `tmx_to_c.py`
2. Write `tests/test_<name>_to_c.py` first (TDD)
3. Run tests: `python3 -m unittest discover -s tests -p "test_<name>_to_c.py" -v`
4. Emit a `/* GENERATED */` header and `#include` in all output `.c` files

---

## GB Background Tilemap Hardware

### VRAM Layout

| Region        | Address     | Contents                                     |
|---------------|-------------|----------------------------------------------|
| Tile data     | $8000–$97FF | 384 tiles × 16 bytes = 6 KiB (bank 0)       |
| BG tile map 0 | $9800–$9BFF | 32×32 = 1024 bytes (one byte per tile cell)  |
| BG tile map 1 | $9C00–$9FFF | 32×32 = 1024 bytes (alternate map area)      |

**Tile budget (DMG bank 0):** 192 tiles; **CGB bank 1:** 192 additional tiles (384 total per bank).

### LCDC Bits for BG

| Bit | Name                       | 0 = …           | 1 = …           |
|-----|----------------------------|-----------------|-----------------|
| 4   | BG & Window tile data area | $8800 (signed)  | $8000 (unsigned)|
| 3   | BG tile map area           | $9800           | $9C00           |
| 0   | BG enable                  | Off (DMG blank) | On              |

**Always use `$8000` mode (LCDC.4=1)** for game tiles — sprites always use $8000 and it simplifies sharing tile data between BG and sprites.

### Scroll Registers

| Register | Address | Purpose                                            |
|----------|---------|----------------------------------------------------|
| SCY      | FF42    | BG scroll Y (0–255, wraps at 256 pixels = 32 tiles)|
| SCX      | FF43    | BG scroll X (0–255, wraps)                         |

GBDK: write `SCY_REG` / `SCX_REG` directly, or use `move_bkg(x, y)`.

The BG tile map is 32×32 tiles (256×256 px); the 160×144 viewport is a window into it. Scrolling wraps seamlessly.

### GBDK API

```c
// Load tile graphics into VRAM (must be during VBlank or display off)
set_bkg_data(first_tile, n_tiles, tile_data);  // tile_data = 2bpp bytes

// Write tile indices into BG tile map
set_bkg_tiles(x, y, w, h, tile_map);           // x/y in tiles, tile_map = uint8_t array

// Scroll the viewport
move_bkg(x, y);   // or write SCX_REG/SCY_REG directly

// CGB: set BG palette
set_bkg_palette(palette_index, n_palettes, palette_data);
```

**VBlank rule:** `set_bkg_data` and `set_bkg_tiles` spin-wait per byte (WAIT_STAT). Call only during VBlank (after `wait_vbl_done()`) or with display off. Calling them after game logic burns the VBlank window.

### CGB BG Attribute Map (VRAM Bank 1)

Each cell in the BG tile map has a corresponding attribute byte in **VRAM bank 1** at the same address ($9800/$9C00):

| Bit | Meaning                                     |
|-----|---------------------------------------------|
| 7   | BG-to-OBJ priority (1 = BG covers sprites)  |
| 6   | Vertical flip                               |
| 5   | Horizontal flip                             |
| 4   | (unused)                                    |
| 3   | VRAM bank (0=bank0, 1=bank1 tile data)      |
| 2–0 | BG palette number (0–7)                     |

Write attribute map via `VBK_REG = 1` then `set_bkg_tiles(...)`, then `VBK_REG = 0`.

**Default:** all BG tiles use palette 0 (set `set_bkg_palette(0, 1, pal)` to control their colors). Font/console tiles also use palette 0 — load game tiles starting at ID 96+ to avoid overwriting font.

---

## Tiled Format Reference

**Canonical docs:** https://doc.mapeditor.org/en/stable/reference/json-map-format/

### Critical Concept: Global Tile IDs (GIDs)

GIDs identify tiles across all tilesets. **GID 0 = empty cell.**

**Resolve GID → local tile ID:**
1. Sort tilesets by `firstgid` descending
2. Find tileset where `tileset.firstgid <= gid`
3. `local_id = gid - tileset.firstgid`

**Flip flags in the top 4 bits of each 32-bit GID:**

| Bit | Hex Mask     | Meaning                            |
|-----|--------------|------------------------------------|
| 32  | `0x80000000` | Horizontal flip                    |
| 31  | `0x40000000` | Vertical flip                      |
| 30  | `0x20000000` | Diagonal flip / 60° rotation (hex) |
| 29  | `0x10000000` | 120° rotation (hexagonal only)     |

**Always mask out flags before using the GID:**
```c
#define GID_FLAGS_MASK 0xF0000000u
uint32_t raw_gid = gid & ~GID_FLAGS_MASK;
```

### Tile Layer Data (CSV — used by this project)

The project uses **TMX (XML)** with **CSV encoding**:
```xml
<layer id="1" name="Track" width="40" height="36">
  <data encoding="csv">
1,2,3,0,...
  </data>
</layer>
```
`data` is a **plain comma-separated text string** inside the `<data>` element — split on `','` after stripping whitespace. (Not a JSON array.)

**Tile order:** row-major, left-to-right, top-to-bottom. Index formula: `tile[y * layer_width + x]`

### TMX Map Structure

| Attribute   | Notes                                      |
|-------------|--------------------------------------------|
| `width`     | Map width in tiles                         |
| `height`    | Map height in tiles                        |
| `tilewidth` | Tile width in pixels (8 for this project)  |
| `tileheight`| Tile height in pixels (8 for this project) |

**External tileset** (`<tileset firstgid="1" source="track.tsx"/>`): load and merge using `firstgid`. The `source` path is relative to the TMX file.

### Common Tiled Mistakes

| Mistake | Fix |
|---------|-----|
| Using GID directly as tile index | Always subtract `tileset.firstgid` |
| Forgetting GID 0 = empty cell | Check `raw_gid == 0` before lookup |
| Not clearing flip bits | Mask with `& ~0xF0000000u` first |
| `encoding: "csv"` in XML = string | Split on `','`, not a JSON array |
| Tile index formula wrong | Use `layer.width`, not map `width` |
| Object `type` vs `class` | Pre-1.9: `type` field; since 1.9: `class` field |

---

## Cross-References

- **`sprite-expert`** — OAM sprite asset pipeline, sprite pool, sprite tile loading; use for anything that involves sprites rather than background/window tiles

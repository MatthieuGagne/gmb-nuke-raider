# PNG Tileset → GB 2bpp C Array Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `tools/png_to_tiles.py` to convert tile art PNGs into GB 2bpp C arrays, then wire it into the Makefile so `src/track_tiles.c` is generated from `assets/maps/tileset.png`.

**Architecture:** The converter reads any PNG (RGB or 2-bit indexed) using stdlib `zlib`/`struct` only (no Pillow), quantises each pixel to one of 4 GB grey indices (0 = lightest, 3 = darkest), then emits a `.c` file containing the 2bpp byte array and a count symbol. `src/track.c` is updated to reference the generated symbols via `extern`. A Makefile rule regenerates the file when the PNG changes.

**Tech Stack:** Python 3 stdlib (`struct`, `zlib`, `unittest`), GBDK `set_bkg_data`, `make`.

---

## Background: Key Concepts

### GB 2bpp encoding

For each 8×8 tile, 16 bytes (2 bytes per row × 8 rows):
- **low byte** for a row: bit 7 = `pixel[0] & 1`, …, bit 0 = `pixel[7] & 1`
- **high byte** for a row: bit 7 = `(pixel[0] >> 1) & 1`, …, bit 0 = `(pixel[7] >> 1) & 1`

Index 0 = lightest display shade; index 3 = darkest.

### RGB → GB index mapping (for RGB PNGs)

Luminance: `L = round(0.299*R + 0.587*G + 0.114*B)` (integer arithmetic: `(299*R + 587*G + 114*B + 500) // 1000`)

GB index = nearest in inverted scale (brighter = lower index):
```
index = min(3, max(0, round((255 - L) / 85)))
```

Verification with `tileset.png` colors (must produce identical bytes to current hand-written data):
- OFF_TRACK `(34, 85, 34)` → L≈64 → index 2 → 2bpp row: `(0x00, 0xFF)`
- ROAD `(136, 136, 136)` → L=136 → index 1 → 2bpp row: `(0xFF, 0x00)`

### PNG formats accepted

| Color type | Bit depth | How pixels are extracted |
|------------|-----------|--------------------------|
| 3 (indexed) | 2 | Raw index 0–3 directly |
| 2 (RGB) | 8 | Compute luminance, map to index |

Only filter type 0 (None) is expected — all our tools produce that.

---

## Task 1: `tools/png_to_tiles.py` — converter (TDD)

**Files:**
- Create: `tools/png_to_tiles.py`
- Create: `tests/test_png_to_tiles.py`

---

### Step 1.1 — Write the failing tests (Python unittest)

Create `tests/test_png_to_tiles.py`:

```python
"""Tests for tools/png_to_tiles.py"""
import io
import struct
import tempfile
import unittest
import zlib

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.png_to_tiles import load_png_pixels, encode_2bpp, png_to_c


# ── Minimal PNG helpers ────────────────────────────────────────────────────

def _chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)


def _make_indexed_png(width, height, pixel_indices):
    """Create a 2-bit indexed PNG. pixel_indices: flat list of 0-3."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 2, 3, 0, 0, 0))
    plte = _chunk(b'PLTE', bytes([255,255,255, 170,170,170, 85,85,85, 0,0,0]))
    raw  = b''
    for row in range(height):
        raw += b'\x00'              # filter type None
        for col in range(0, width, 4):
            byte = 0
            for k in range(4):
                byte = (byte << 2) | (pixel_indices[row * width + col + k] if col + k < width else 0)
            raw += bytes([byte])
    idat = _chunk(b'IDAT', zlib.compress(raw))
    iend = _chunk(b'IEND', b'')
    return sig + ihdr + plte + idat + iend


def _make_rgb_png(width, height, pixels_rgb):
    """Create an 8-bit RGB PNG. pixels_rgb: flat list of (R,G,B)."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw  = b''
    for row in range(height):
        raw += b'\x00'
        for col in range(width):
            r, g, b = pixels_rgb[row * width + col]
            raw += bytes([r, g, b])
    idat = _chunk(b'IDAT', zlib.compress(raw))
    iend = _chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


# ── Tests ──────────────────────────────────────────────────────────────────

class TestLoadPngPixels(unittest.TestCase):

    def test_indexed_single_tile_all_index2(self):
        """8×8 indexed PNG with all pixels=2 → 64 pixels each equal to 2."""
        data = _make_indexed_png(8, 8, [2] * 64)
        pixels, w, h = load_png_pixels(data)
        self.assertEqual(w, 8)
        self.assertEqual(h, 8)
        self.assertEqual(pixels, [2] * 64)

    def test_rgb_off_track_color_maps_to_index2(self):
        """OFF_TRACK RGB (34,85,34) → index 2 (luminance≈64)."""
        data = _make_rgb_png(8, 8, [(34, 85, 34)] * 64)
        pixels, w, h = load_png_pixels(data)
        self.assertEqual(pixels, [2] * 64)

    def test_rgb_road_color_maps_to_index1(self):
        """ROAD RGB (136,136,136) → index 1 (luminance=136)."""
        data = _make_rgb_png(8, 8, [(136, 136, 136)] * 64)
        pixels, w, h = load_png_pixels(data)
        self.assertEqual(pixels, [1] * 64)

    def test_too_many_colors_raises(self):
        """RGB PNG with 5 distinct luminance values raises ValueError."""
        # Five grey shades with distinct luminance after quantisation
        colors = [(0,0,0), (50,50,50), (100,100,100), (150,150,150), (220,220,220)]
        flat = [colors[i % 5] for i in range(8 * 8)]
        data = _make_rgb_png(8, 8, flat)
        with self.assertRaises(ValueError):
            load_png_pixels(data)


class TestEncode2bpp(unittest.TestCase):

    def test_single_tile_all_index2(self):
        """8×8 pixels all=2 → 16 bytes: (0x00,0xFF)×8."""
        pixels = [2] * 64
        result = encode_2bpp(pixels, 8, 8)
        expected = bytes([0x00, 0xFF] * 8)
        self.assertEqual(result, expected)

    def test_single_tile_all_index1(self):
        """8×8 pixels all=1 → 16 bytes: (0xFF,0x00)×8."""
        pixels = [1] * 64
        result = encode_2bpp(pixels, 8, 8)
        expected = bytes([0xFF, 0x00] * 8)
        self.assertEqual(result, expected)

    def test_two_tile_strip(self):
        """16×8 strip: left tile all-index2, right tile all-index1."""
        pixels = []
        for _ in range(8):
            pixels += [2] * 8 + [1] * 8
        result = encode_2bpp(pixels, 16, 8)
        tile0 = bytes([0x00, 0xFF] * 8)
        tile1 = bytes([0xFF, 0x00] * 8)
        self.assertEqual(result, tile0 + tile1)


class TestPngToC(unittest.TestCase):

    def test_c_file_contains_array_name(self):
        """Generated C source contains the requested array name."""
        data = _make_indexed_png(8, 8, [2] * 64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'my_tiles')
        with open(c_path) as f:
            src = f.read()
        self.assertIn('my_tiles[]', src)
        self.assertIn('my_tiles_count', src)
        self.assertIn('0x00', src)

    def test_count_symbol_value(self):
        """16×8 PNG (2 tiles) produces count symbol = 2."""
        data = _make_indexed_png(16, 8, [1] * 128)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'tiles')
        with open(c_path) as f:
            src = f.read()
        self.assertIn('tiles_count = 2', src)


if __name__ == '__main__':
    unittest.main()
```

---

### Step 1.2 — Run tests to confirm they fail

```bash
PYTHONPATH=. python3 -m unittest tests.test_png_to_tiles -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'tools.png_to_tiles'`

---

### Step 1.3 — Implement `tools/png_to_tiles.py`

Create `tools/png_to_tiles.py`:

```python
#!/usr/bin/env python3
"""PNG tileset → GB 2bpp C array converter.

Usage:
    python3 tools/png_to_tiles.py <tileset.png> <out.c> <array_name>

Reads a PNG tileset (one or more 8×8 tiles, left-to-right strip).
Writes a C source file defining:
    const uint8_t <array_name>[];        -- 2bpp tile data
    const uint8_t <array_name>_count;    -- number of tiles

Supported PNG formats:
    - Color type 3 (indexed), bit depth 2: pixel index used directly (0–3).
    - Color type 2 (RGB), bit depth 8: luminance quantised to GB index 0–3.

Rejects PNGs with more than 4 distinct colour values.
"""
import struct
import sys
import zlib


def _parse_chunks(data):
    """Yield (chunk_type, chunk_data) for each PNG chunk."""
    pos = 8  # skip signature
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        ctype  = data[pos + 4:pos + 8]
        cdata  = data[pos + 8:pos + 8 + length]
        pos   += 12 + length
        yield ctype, cdata
        if ctype == b'IEND':
            break


def _lum_to_index(r, g, b):
    """Convert RGB888 to GB palette index 0–3 (0=white, 3=black)."""
    L = (299 * r + 587 * g + 114 * b + 500) // 1000
    return min(3, max(0, round((255 - L) / 85)))


def load_png_pixels(data):
    """Parse PNG bytes and return (pixel_list, width, height).

    pixel_list: flat list of GB palette indices (0–3), row-major.
    Raises ValueError if PNG has >4 distinct colour values.
    """
    ihdr = None
    plte = None
    idat = b''

    for ctype, cdata in _parse_chunks(data):
        if ctype == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', cdata)
        elif ctype == b'PLTE':
            plte = cdata
        elif ctype == b'IDAT':
            idat += cdata

    width, height, bit_depth, color_type = ihdr[0], ihdr[1], ihdr[2], ihdr[3]
    raw = zlib.decompress(idat)

    pixels = []

    if color_type == 3 and bit_depth == 2:
        # 2-bit indexed: 4 pixels per byte, 2 bits each (MSB first)
        bytes_per_row = (width + 3) // 4  # rounded up
        # Account for filter byte per row
        row_stride = 1 + bytes_per_row
        for y in range(height):
            row_start = y * row_stride + 1  # +1 skip filter byte
            col = 0
            for bx in range(bytes_per_row):
                byte = raw[row_start + bx]
                for shift in (6, 4, 2, 0):
                    if col < width:
                        pixels.append((byte >> shift) & 3)
                        col += 1

    elif color_type == 2 and bit_depth == 8:
        # 8-bit RGB: 3 bytes per pixel
        row_stride = 1 + width * 3
        lum_set = set()
        rgb_rows = []
        for y in range(height):
            row_start = y * row_stride + 1
            row = []
            for x in range(width):
                off = row_start + x * 3
                r, g, b = raw[off], raw[off + 1], raw[off + 2]
                lum = (299 * r + 587 * g + 114 * b + 500) // 1000
                lum_set.add(lum)
                row.append((r, g, b))
            rgb_rows.append(row)
        if len(lum_set) > 4:
            raise ValueError(
                f"PNG has {len(lum_set)} distinct luminance values (max 4). "
                "Reduce colours to ≤4 grey shades."
            )
        for row in rgb_rows:
            for r, g, b in row:
                pixels.append(_lum_to_index(r, g, b))
    else:
        raise ValueError(
            f"Unsupported PNG format: color_type={color_type}, bit_depth={bit_depth}. "
            "Expected indexed 2-bit (type 3) or RGB 8-bit (type 2)."
        )

    return pixels, width, height


def encode_2bpp(pixels, width, height):
    """Convert flat pixel index list to GB 2bpp bytes.

    Returns bytes: 16 bytes per 8×8 tile, left-to-right, top-to-bottom.
    """
    if width % 8 != 0 or height % 8 != 0:
        raise ValueError(f"Image dimensions {width}×{height} must be multiples of 8.")

    result = bytearray()
    tiles_x = width // 8

    for tx in range(tiles_x):
        for ty in range(height // 8):
            for row in range(8):
                y = ty * 8 + row
                low_byte  = 0
                high_byte = 0
                for col in range(8):
                    x = tx * 8 + col
                    v = pixels[y * width + x]
                    bit_pos = 7 - col
                    low_byte  |= (v & 1)       << bit_pos
                    high_byte |= ((v >> 1) & 1) << bit_pos
                result += bytes([low_byte, high_byte])

    return bytes(result)


def png_to_c(png_path, out_path, array_name):
    """Convert PNG file to a C source file with the 2bpp array."""
    with open(png_path, 'rb') as f:
        data = f.read()

    pixels, width, height = load_png_pixels(data)
    raw_2bpp = encode_2bpp(pixels, width, height)
    n_tiles = (width // 8) * (height // 8)

    lines = [
        f"/* Auto-generated by tools/png_to_tiles.py from {png_path} -- do not edit manually */",
        "#include <stdint.h>",
        "",
        f"const uint8_t {array_name}[] = {{",
    ]

    tile_bytes = 16
    for t in range(n_tiles):
        hex_vals = ', '.join(f'0x{b:02X}' for b in raw_2bpp[t * tile_bytes:(t + 1) * tile_bytes])
        lines.append(f"    /* tile {t} */ {hex_vals},")

    lines += [
        "};",
        "",
        f"const uint8_t {array_name}_count = {n_tiles}u;",
        "",
    ]

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <tileset.png> <out.c> <array_name>", file=sys.stderr)
        sys.exit(1)
    _, png_path, out_path, array_name = sys.argv
    try:
        png_to_c(png_path, out_path, array_name)
        print(f"Wrote {out_path}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
```

---

### Step 1.4 — Run tests to confirm they pass

```bash
PYTHONPATH=. python3 -m unittest tests.test_png_to_tiles -v
```

Expected: `OK` with all tests passing.

---

### Step 1.5 — Add `test-tools` coverage and smoke-run

Update the `test-tools` target in `Makefile` to include the new test module.

Change:
```makefile
test-tools:
	PYTHONPATH=. python3 -m unittest tests.test_sprite_editor -v
```

To:
```makefile
test-tools:
	PYTHONPATH=. python3 -m unittest tests.test_sprite_editor tests.test_png_to_tiles -v
```

Verify:
```bash
make test-tools
```

Expected: all tests pass.

---

### Step 1.6 — Commit

```bash
git add tools/png_to_tiles.py tests/test_png_to_tiles.py Makefile
git commit -m "feat: add png_to_tiles converter with Python unit tests"
```

---

## Task 2: Makefile rule + generate `src/track_tiles.c`

**Files:**
- Modify: `Makefile`
- Create: `src/track_tiles.c` (generated, then checked into git)

---

### Step 2.1 — Add Makefile rule

In `Makefile`, after the `src/track_map.c` rule block, add:

```makefile
# src/track_tiles.c is checked into git so CI works without Python.
# Running `make src/track_tiles.c` (or plain `make`) regenerates it when needed.
src/track_tiles.c: assets/maps/tileset.png tools/png_to_tiles.py
	python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data

# Ensure regeneration happens before ROM link if PNG is newer
$(TARGET): src/track_tiles.c
```

The existing `$(TARGET): src/track_map.c` line is already present — just add the new dependency line.

---

### Step 2.2 — Generate the file and verify output

```bash
python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data
cat src/track_tiles.c
```

Expected output (verify bytes match current `track_tile_data` in `track.c`):
```
/* tile 0 */ 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
/* tile 1 */ 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
```

---

### Step 2.3 — Commit generated file

```bash
git add Makefile src/track_tiles.c
git commit -m "feat: Makefile rule + generated src/track_tiles.c from tileset.png"
```

---

## Task 3: Wire `track.c` to use generated symbols

**Files:**
- Modify: `src/track.c`
- Modify: `src/track.h` (optional — expose count extern for callers if needed)

---

### Step 3.1 — Update `src/track.c`

Remove the hand-written `track_tile_data[]` array and update `track_init()` to use the generated symbols.

**Before** (`src/track.c` lines 4–21):
```c
/*
 * Tile 0: off-track (color index 2)  — 2bpp: low=0x00, high=0xFF
 * Tile 1: road surface (color index 1) — 2bpp: low=0xFF, high=0x00
 */
static const uint8_t track_tile_data[] = {
    /* Tile 0: off-track */
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    /* Tile 1: road */
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00
};

void track_init(void) {
    set_bkg_data(0, 2, track_tile_data);
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}
```

**After**:
```c
/* Tile data generated from assets/maps/tileset.png — see src/track_tiles.c */
extern const uint8_t track_tile_data[];
extern const uint8_t track_tile_data_count;

void track_init(void) {
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}
```

---

### Step 3.2 — Run C unit tests (no regressions)

```bash
make test
```

Expected: all C tests pass. `track.c` unit tests (`tests/test_track.c`) should still pass because `set_bkg_data` is mocked.

---

### Step 3.3 — Build the ROM

Use the `/build` skill or:
```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `build/wasteland-racer.gb` produced with no errors. `track_tile_data` should NOT be defined in `track.c` (AC4).

Verify:
```bash
grep -n 'track_tile_data\s*=' src/track.c
```

Expected: no output (array is now in `track_tiles.c`).

---

### Step 3.4 — Commit

```bash
git add src/track.c
git commit -m "feat: track.c uses generated track_tile_data from track_tiles.c"
```

---

## Task 4: Document the asset pipeline

**Files:**
- Create: `docs/asset-pipeline.md`

---

### Step 4.1 — Write `docs/asset-pipeline.md`

Create `docs/asset-pipeline.md` with the following content:

```markdown
# Asset Pipeline

This document describes how source art and map data flow from authoring tools
into the Game Boy ROM.

---

## Overview

```
Sprite editor / external tool
         │
         ▼
   assets/maps/tileset.png       (background tile art, 16×8 = 2 tiles)
   assets/maps/track.tmx         (tile map layout, 40×36)
         │                               │
         ▼                               ▼
  tools/png_to_tiles.py          tools/tmx_to_c.py
         │                               │
         ▼                               ▼
  src/track_tiles.c              src/track_map.c
  (2bpp tile data array)         (tilemap index array)
         │                               │
         └──────────┬────────────────────┘
                    ▼
            GBDK/SDCC compiler
                    │
                    ▼
         build/wasteland-racer.gb
```

Both generated `.c` files are **checked into git** so CI builds work without
Python or Tiled installed.

---

## Background Tiles

### Source file
`assets/maps/tileset.png` — an 8-pixel-tall PNG strip, one 8×8 tile per column.

### Authoring
- Open `tileset.png` in Aseprite, GIMP, or the sprite editor (`tools/run_sprite_editor.py`).
- Use at most **4 distinct grey shades** (or 4 colours from the sprite editor's palette).
- Save / export as PNG (8-bit RGB or 2-bit indexed).

### Conversion
```bash
python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data
```

Or just run `make` — the Makefile regenerates `src/track_tiles.c` automatically
when `tileset.png` is newer.

#### How it works
Each pixel's luminance is rounded to the nearest of 4 GB grey levels:
`index = round((255 - L) / 85)`, where `L = 0.299·R + 0.587·G + 0.114·B`.

Index 0 = lightest display shade; index 3 = darkest.

Each 8×8 tile is encoded as 16 bytes of GB 2bpp:
- For each row: `low_byte` (bit 0 of each pixel, MSB-first), then `high_byte` (bit 1).

### Adding more tiles
1. Extend `tileset.png` by appending 8×8 columns to the right.
2. Run `make` to regenerate `src/track_tiles.c`.
3. In Tiled, add the new tile index to `assets/maps/track.tsx` and use it in `track.tmx`.
4. Run `make` again to regenerate `src/track_map.c`.
5. Verify the ROM renders correctly: `mgba-qt build/wasteland-racer.gb`.

---

## Tile Map (Track Layout)

### Source files
- `assets/maps/track.tmx` — Tiled map file (40×36 tiles)
- `assets/maps/track.tsx` — Tiled tileset reference

### Authoring
Open `track.tmx` in [Tiled](https://www.mapeditor.org/) (free, cross-platform).
Edit tile placement, then save. The TMX uses CSV encoding, tile IDs are Tiled
1-based (GB value + 1 — so tile 0 in game = tile 1 in Tiled).

### Conversion
```bash
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

Or just `make` — same automatic-regeneration rule.

---

## Sprites

Sprites are authored in the built-in sprite editor.

```bash
python3 tools/run_sprite_editor.py
```

The editor saves a 2-bit indexed PNG (32×32 pixels = 4×4 tiles) via
`tools/sprite_editor/model.py::TileSheet.save_png`.

**Sprite → ROM** (manual step for now):
1. Save the sprite sheet from the editor.
2. Use `tools/png_to_tiles.py` to convert the PNG to a C array:
   ```bash
   python3 tools/png_to_tiles.py assets/sprites/player.png src/player_tiles.c player_tile_data
   ```
3. `#include` or `extern` the symbol in the relevant module.

> **Note:** A Makefile auto-rule for sprite sheets is out of scope for this
> pipeline (sprites are not yet stored under `assets/sprites/`). Add one when
> the sprite art workflow is established.

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
make test-tools    # Python tool tests (sprite editor, png_to_tiles)
```
```

---

### Step 4.2 — Commit docs

```bash
git add docs/asset-pipeline.md
git commit -m "docs: add asset-pipeline.md covering tiles, maps, sprites, and full rebuild"
```

---

## Task 5: Final verification

### Step 5.1 — Full clean build

```bash
GBDK_HOME=/home/mathdaman/gbdk make clean && GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: ROM produced, no errors or warnings (EVELYN warning is harmless).

### Step 5.2 — All tests pass

```bash
make test && make test-tools
```

### Step 5.3 — Smoketest (emulator) — **USER CONFIRMS**

Load and visually verify track renders identically to before:
```bash
mgba-qt build/wasteland-racer.gb
```

**Wait for user confirmation before creating PR.**

### Step 5.4 — Create PR

```bash
git push -u origin <branch>
gh pr create --title "feat: PNG tileset → GB 2bpp C array pipeline" \
  --body "..."
```

Closes #20.

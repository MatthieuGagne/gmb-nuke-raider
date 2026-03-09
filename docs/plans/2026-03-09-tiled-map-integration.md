# Tiled Map Editor Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hardcoded `track_map[]` in `track.c` with a Tiled-authored TMX file and a Python converter that auto-generates `src/track_map.c`.

**Architecture:** A Python script (`tools/tmx_to_c.py`) reads a Tiled TMX (CSV encoding, 1-based IDs) and writes `src/track_map.c` defining `track_map[]`. The Makefile regenerates that file when TMX or converter changes. The generated file is checked into git so CI needs neither Tiled nor Python.

**Tech Stack:** Python 3 (stdlib only: `xml.etree.ElementTree`, `struct`, `zlib`), Tiled TMX format (XML/CSV), GNU Make, Unity (existing C test harness).

---

### Task 1: Create `tools/tmx_to_c.py`

**Files:**
- Create: `tools/tmx_to_c.py`

**Step 1: Create the file**

```python
#!/usr/bin/env python3
"""TMX to C converter for Wasteland Racer track maps.

Usage: python3 tools/tmx_to_c.py <track.tmx> <track_map.c>

Converts a Tiled CSV-encoded TMX to a C source file defining track_map[].
Tiled tile IDs are 1-based; this script subtracts 1 to match 0-indexed GB
tile values (0=off-track, 1=road, etc.).
"""
import sys
import xml.etree.ElementTree as ET


def tmx_to_c(tmx_path, out_path):
    tree = ET.parse(tmx_path)
    root = tree.getroot()

    width  = int(root.get('width'))
    height = int(root.get('height'))

    layer   = root.find('layer')
    data_el = layer.find('data')
    encoding = data_el.get('encoding', 'xml')

    if encoding != 'csv':
        raise ValueError(f"Only CSV encoding supported, got: {encoding}")

    # Tiled uses 1-based tile IDs; subtract 1 for 0-indexed GB tile values.
    raw      = data_el.text.strip()
    tile_ids = [int(x) - 1 for x in raw.split(',')]

    if len(tile_ids) != width * height:
        raise ValueError(
            f"Expected {width * height} tiles, got {len(tile_ids)}"
        )

    with open(out_path, 'w') as f:
        f.write("/* GENERATED — do not edit by hand."
                " Source: assets/maps/track.tmx */\n")
        f.write("/* Regenerate: python3 tools/tmx_to_c.py"
                " assets/maps/track.tmx src/track_map.c */\n")
        f.write('#include "track.h"\n\n')
        f.write("const uint8_t track_map[MAP_TILES_H * MAP_TILES_W] = {\n")
        for row in range(height):
            start = row * width
            vals  = ','.join(str(v) for v in tile_ids[start:start + width])
            f.write(f"    /* row {row:2d} */ {vals},\n")
        f.write("};\n")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <track.tmx> <track_map.c>",
              file=sys.stderr)
        sys.exit(1)
    tmx_to_c(sys.argv[1], sys.argv[2])
```

**Step 2: Make executable**

```bash
chmod +x tools/tmx_to_c.py
```

---

### Task 2: Write and run Python converter tests

**Files:**
- Create: `tests/test_tmx_to_c.py`

**Step 1: Write the test**

```python
#!/usr/bin/env python3
"""Unit tests for tools/tmx_to_c.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import tmx_to_c as conv

# 3×2 map: Tiled IDs 1,2,1 / 2,1,2  →  GB values 0,1,0 / 1,0,1
MINIMAL_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal"
     width="3" height="2" tilewidth="8" tileheight="8">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="3" height="2">
  <data encoding="csv">
1,2,1,
2,1,2
  </data>
 </layer>
</map>
"""


class TestTmxToC(unittest.TestCase):

    def _convert(self, tmx_text):
        with tempfile.NamedTemporaryFile('w', suffix='.tmx', delete=False) as tf:
            tf.write(tmx_text)
            tmx_path = tf.name
        out_path = tmx_path.replace('.tmx', '.c')
        try:
            conv.tmx_to_c(tmx_path, out_path)
            with open(out_path) as f:
                return f.read()
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_generated_header_comment(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('GENERATED', result)
        self.assertIn('do not edit by hand', result)

    def test_subtracts_one_from_tile_ids(self):
        result = self._convert(MINIMAL_TMX)
        # IDs 1,2,1 → 0,1,0 and 2,1,2 → 1,0,1
        self.assertIn('0,1,0', result)
        self.assertIn('1,0,1', result)

    def test_includes_track_header(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('#include "track.h"', result)

    def test_defines_track_map_array(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('track_map[MAP_TILES_H * MAP_TILES_W]', result)

    def test_wrong_encoding_raises(self):
        bad = MINIMAL_TMX.replace('encoding="csv"', 'encoding="base64"')
        with self.assertRaises(ValueError):
            self._convert(bad)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run to verify all pass**

```bash
python3 tests/test_tmx_to_c.py -v
```

Expected: `5 tests, 0 failures`

**Step 3: Commit**

```bash
git add tools/tmx_to_c.py tests/test_tmx_to_c.py
git commit -m "feat: add TMX-to-C converter with Python unit tests"
```

---

### Task 3: Create Tiled assets (tileset.png, track.tsx, track.tmx)

These are one-time migration assets. A helper script generates all three from the
known track shape so the output is deterministic and doesn't require Tiled to be
installed.

**Files:**
- Create: `assets/maps/create_assets.py`  (helper script, checked in for reproducibility)
- Create: `assets/maps/tileset.png`
- Create: `assets/maps/track.tsx`
- Create: `assets/maps/track.tmx`

**Step 1: Write the helper script**

Create `assets/maps/create_assets.py`:

```python
#!/usr/bin/env python3
"""One-time helper: generate tileset.png, track.tsx, and track.tmx.

Run from the repo root:
    python3 assets/maps/create_assets.py

The TMX encodes the same oval shape as the original track_map[] in track.c.
Tile colours are representative only; final art is drawn in Aseprite.
"""
import os
import struct
import zlib

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)))
W, H = 40, 36  # map width × height in tiles


# ── Track shape (matches original track_map[]) ──────────────────────────────
def row_a(): return [0] * W
def row_e(): return [0]*4 + [1]*32 + [0]*4
def row_d(): return [0]*4 + [1]*4 + [0]*24 + [1]*4 + [0]*4

rows = (
    [row_a()] * 2   +   # rows  0–1
    [row_e()] * 4   +   # rows  2–5
    [row_d()] * 24  +   # rows  6–29
    [row_e()] * 4   +   # rows 30–33
    [row_a()] * 2       # rows 34–35
)
assert len(rows) == H, f"Expected {H} rows, got {len(rows)}"


# ── Minimal PNG writer (stdlib only) ────────────────────────────────────────
def png_chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)

def make_png_rgb(pixels, width, height):
    """pixels: list of (R,G,B) tuples, row-major."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = png_chunk(b'IHDR',
                     struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw  = b''
    for row in range(height):
        raw += b'\x00'                          # filter type: None
        for col in range(width):
            r, g, b = pixels[row * width + col]
            raw += bytes([r, g, b])
    idat = png_chunk(b'IDAT', zlib.compress(raw))
    iend = png_chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


# ── tileset.png — 16×8 strip: left 8 cols = tile 0, right 8 cols = tile 1 ──
OFF_TRACK = (34,  85,  34)   # dark green  (tile 0)
ROAD      = (136, 136, 136)  # mid-gray    (tile 1)

pixels = []
for _ in range(8):
    pixels += [OFF_TRACK] * 8
    pixels += [ROAD]      * 8

png_bytes = make_png_rgb(pixels, 16, 8)
png_path  = os.path.join(ASSETS, 'tileset.png')
with open(png_path, 'wb') as f:
    f.write(png_bytes)
print(f"Wrote {png_path}")


# ── track.tsx ────────────────────────────────────────────────────────────────
tsx = """\
<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.0"
         name="track" tilewidth="8" tileheight="8"
         spacing="0" margin="0" tilecount="2" columns="2">
 <image source="tileset.png" width="16" height="8"/>
</tileset>
"""
tsx_path = os.path.join(ASSETS, 'track.tsx')
with open(tsx_path, 'w') as f:
    f.write(tsx)
print(f"Wrote {tsx_path}")


# ── track.tmx — CSV, 1-based Tiled IDs (GB value + 1) ─────────────────────
csv_rows = [','.join(str(v + 1) for v in row) for row in rows]
csv_data = ',\n'.join(csv_rows)

tmx = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.0"
     orientation="orthogonal" renderorder="right-down"
     width="{W}" height="{H}" tilewidth="8" tileheight="8"
     infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="{W}" height="{H}">
  <data encoding="csv">
{csv_data}
  </data>
 </layer>
</map>
"""
tmx_path = os.path.join(ASSETS, 'track.tmx')
with open(tmx_path, 'w') as f:
    f.write(tmx)
print(f"Wrote {tmx_path}")
```

**Step 2: Run the helper**

```bash
mkdir -p assets/maps
python3 assets/maps/create_assets.py
```

Expected output:
```
Wrote .../assets/maps/tileset.png
Wrote .../assets/maps/track.tsx
Wrote .../assets/maps/track.tmx
```

**Step 3: Sanity-check the TMX**

```bash
python3 - <<'EOF'
import xml.etree.ElementTree as ET
root  = ET.parse('assets/maps/track.tmx').getroot()
data  = root.find('layer/data').text.strip()
vals  = [int(x) for x in data.split(',')]
print(f"Tile count : {len(vals)}  (expected 1440)")
print(f"Unique IDs : {sorted(set(vals))}  (expected [1, 2])")
EOF
```

Expected: `Tile count : 1440`, `Unique IDs : [1, 2]`

---

### Task 4: Generate `src/track_map.c` and spot-check it

**Files:**
- Create: `src/track_map.c`

**Step 1: Run the converter**

```bash
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

**Step 2: Check the header comment**

```bash
head -4 src/track_map.c
```

Expected:
```
/* GENERATED — do not edit by hand. Source: assets/maps/track.tmx */
/* Regenerate: python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c */
#include "track.h"

```

**Step 3: Spot-check rows match the original**

Row 0 should be all-zeros (40 values):
```bash
grep "row  0" src/track_map.c
```
Expected: `/* row  0 */ 0,0,0,0,...,0,`

Row 2 is type E (4 zeros, 32 ones, 4 zeros):
```bash
grep "row  2" src/track_map.c
```
Expected: `/* row  2 */ 0,0,0,0,1,1,...,1,1,0,0,0,0,`

Row 6 is type D (4z, 4o, 24z, 4o, 4z):
```bash
grep "row  6" src/track_map.c
```
Expected: `/* row  6 */ 0,0,0,0,1,1,1,1,0,0,...,0,0,1,1,1,1,0,0,0,0,`

---

### Task 5: Remove `track_map[]` from `track.c`

**Files:**
- Modify: `src/track.c` lines 17–58

Delete the comment block and array that begins `/* * 40×36 world tile map...` and ends with the closing `};` (the entire `track_map[]` definition). Leave `track_tile_data[]`, `track_init()`, and `track_passable()` intact.

After deletion `src/track.c` should look like this (verify line count shrank from 75 to ~37):

```c
#include <gb/gb.h>
#include "track.h"

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

uint8_t track_passable(int16_t world_x, int16_t world_y) {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return 0u;
    tx = (uint8_t)((uint16_t)world_x / 8u);
    ty = (uint8_t)((uint16_t)world_y / 8u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return track_map[(uint16_t)ty * MAP_TILES_W + tx] != 0u;
}
```

`track.h` already has `extern const uint8_t track_map[]`, so no header changes needed.

---

### Task 6: Update `Makefile` with generation rule

**Files:**
- Modify: `Makefile`

Add this block **after** the `SRCS` / `OBJS` lines (after line 11) and **before** `.PHONY`:

```makefile
# ── Generated sources ─────────────────────────────────────────────────────────
# src/track_map.c is checked into git so CI works without Python/Tiled.
# Running `make src/track_map.c` (or plain `make`) regenerates it when needed.
src/track_map.c: assets/maps/track.tmx tools/tmx_to_c.py
	python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c

# Ensure regeneration happens before ROM link if TMX is newer
$(TARGET): src/track_map.c
```

**Important:** `SRCS := $(wildcard src/*.c)` is evaluated at Makefile parse time.
`src/track_map.c` **must** exist on disk (it is checked into git) for it to appear
in `SRCS` and be compiled. The rule above only handles *re*generation.

The final `Makefile` relevant section should look like:

```makefile
SRCS      := $(wildcard src/*.c)
OBJS      := $(patsubst src/%.c,$(OBJ_DIR)/%.o,$(SRCS))

# ── Generated sources ─────────────────────────────────────────────────────────
src/track_map.c: assets/maps/track.tmx tools/tmx_to_c.py
	python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c

$(TARGET): src/track_map.c

.PHONY: all clean test
```

---

### Task 7: Run existing C tests

The Makefile `test` target uses `TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))`,
which automatically includes `src/track_map.c`. So the existing `test_track.c` tests
exercise `track_passable()` against the generated data — no test file changes needed.

**Step 1: Run tests**

```bash
make test
```

Expected: all tests pass (9 track tests + all others). If you see a linker error
about `track_map` being defined twice, the old definition was not fully removed
from `track.c` — fix that first.

**Step 2: Run the Python converter test**

```bash
python3 tests/test_tmx_to_c.py -v
```

Expected: 5 tests pass.

---

### Task 8: Build the ROM

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `build/wasteland-racer.gb` produced with no errors.

**Verify regeneration is idempotent** (running make again should not rebuild):

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `make: Nothing to be done for 'all'.`

---

### Task 9: Commit and push

**Step 1: Stage all new/modified files**

```bash
git add tools/tmx_to_c.py \
        tests/test_tmx_to_c.py \
        assets/maps/create_assets.py \
        assets/maps/tileset.png \
        assets/maps/track.tsx \
        assets/maps/track.tmx \
        src/track_map.c \
        src/track.c \
        Makefile
```

**Step 2: Commit**

```bash
git commit -m "feat: Tiled map editor integration (TMX → track_map.c)"
```

**Step 3: Push and open PR**

```bash
git push -u origin feat/tiled-map-integration
gh pr create \
  --title "feat: Tiled map editor integration" \
  --body "$(cat <<'EOF'
## Summary
- Adds `tools/tmx_to_c.py` converter (Python stdlib only, CSV encoding)
- Creates Tiled assets: `tileset.png`, `track.tsx`, `track.tmx` (40×36, same oval shape)
- Generates `src/track_map.c` (checked in; GENERATED header comment)
- Removes hardcoded `track_map[]` from `track.c`
- Makefile regenerates `src/track_map.c` when TMX or converter changes

Closes #8

## Test plan
- [ ] `python3 tests/test_tmx_to_c.py -v` → 5 pass
- [ ] `make test` → all C tests pass (track_passable tests exercise generated data)
- [ ] `GBDK_HOME=~/gbdk make` → ROM builds cleanly
- [ ] Emulator smoketest: track shape matches original
- [ ] Edit a tile in `track.tmx`, run `make`, confirm change appears in game
EOF
)"
```

> **Smoketest gate (CLAUDE.md):** Do NOT merge until the user confirms the emulator smoketest passes in `mgba-qt build/wasteland-racer.gb`.

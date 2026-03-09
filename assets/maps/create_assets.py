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

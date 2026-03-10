#!/usr/bin/env python3
"""Generate the 6-tile Wasteland Racer tileset PNG (48×8, RGB).

Run: python3 tools/gen_tileset.py assets/maps/tileset.png
"""
import struct
import zlib
import sys

PALETTE = [
    (255, 255, 255),  # 0 = white
    (170, 170, 170),  # 1 = light-grey
    (85,  85,  85),   # 2 = dark-grey
    (0,   0,   0),    # 3 = black
]

def make_tile(fn):
    return [[fn(r, c) for c in range(8)] for r in range(8)]

TILES = [
    make_tile(lambda r, c: 2),                                          # 0: wall
    make_tile(lambda r, c: 1),                                          # 1: road
    make_tile(lambda r, c: 3),                                          # 2: center dashes
    make_tile(lambda r, c: 1 + ((r + c) % 2)),                         # 3: sand checkerboard
    make_tile(lambda r, c: 2 if (2 <= r <= 4 and 2 <= c <= 5) else 3), # 4: oil puddle
    make_tile(lambda r, c: r % 2),                                      # 5: boost stripes
]

WIDTH  = 8 * len(TILES)  # 48
HEIGHT = 8

def write_chunk(ctype, data):
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + ctype + data + struct.pack('>I', crc)

ihdr = struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 2, 0, 0, 0)

raw = b''
for row in range(HEIGHT):
    raw += b'\x00'  # filter byte = None
    for tile in TILES:
        for col in range(8):
            raw += bytes(PALETTE[tile[row][col]])

out = (b'\x89PNG\r\n\x1a\n' +
       write_chunk(b'IHDR', ihdr) +
       write_chunk(b'IDAT', zlib.compress(raw)) +
       write_chunk(b'IEND', b''))

path = sys.argv[1] if len(sys.argv) > 1 else 'assets/maps/tileset.png'
with open(path, 'wb') as f:
    f.write(out)
print(f"Wrote {WIDTH}x{HEIGHT} PNG ({len(TILES)} tiles) to {path}")

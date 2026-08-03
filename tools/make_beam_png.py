#!/usr/bin/env python3
"""Generate assets/sprites/beam.png — the two LASER beam BG tiles (#430).

Tile 0 (left, x 0-7):   horizontal beam segment — a bright band across the middle.
Tile 1 (right, x 8-15): vertical beam segment   — a bright band down the middle.

Emits a 16x8 8-bit indexed (PLTE, color_type 3) PNG using palette indices
0 (white), 2 (grey), 3 (black) — index 1 is reserved/unused. This is one of
the two formats tools/png_to_tiles.py accepts (see its load_png_pixels):
color_type 3 (indexed) at bit depth 8 or 2, or color_type 2 (RGB) at bit
depth 8 quantised by luminance.

RGB (color_type 2) was tried first and rejected: Pillow's PNG encoder
chooses adaptive per-row filters (Up/Paeth) for RGB data, and
png_to_tiles.py's _defilter_rows assumes bytes-per-pixel == 1 when
undoing the Sub/Average/Paeth filters. That assumption only holds for
color_type 3 (1 byte/pixel at bit depth 8); for RGB (3 bytes/pixel) it
reads the wrong "left" reference byte and corrupts most rows, which
surfaced as a bogus "11 distinct luminance values" rejection even though
the source image only used 3 flat grey levels. Indexed mode sidesteps
the bug entirely (bpp == 1) and is explicitly supported.

Run from the repository root:

    python tools/make_beam_png.py

Re-run only when the beam art changes; both the PNG and the generated
src/beam_tiles.c are committed so CI works without Pillow.
"""
from PIL import Image

IDX_WHITE = 0  # bright beam core
IDX_GREY  = 2  # dim beam edge
IDX_BLACK = 3  # background / unlit

# Palette: index -> (r, g, b). Index 1 is unused, kept black as a filler.
PALETTE = [
    255, 255, 255,   # 0 white
    0,   0,   0,     # 1 unused
    85,  85,  85,    # 2 grey
    0,   0,   0,     # 3 black
] + [0, 0, 0] * 252  # pad to 256 entries

img = Image.new("P", (16, 8), color=IDX_BLACK)
img.putpalette(PALETTE)
px = img.load()

# Tile 0 — horizontal: rows 3-4 bright, rows 2 and 5 dim.
for x in range(8):
    px[x, 2] = IDX_GREY
    px[x, 3] = IDX_WHITE
    px[x, 4] = IDX_WHITE
    px[x, 5] = IDX_GREY

# Tile 1 — vertical: columns 3-4 bright, columns 2 and 5 dim.
for y in range(8):
    px[8 + 2, y] = IDX_GREY
    px[8 + 3, y] = IDX_WHITE
    px[8 + 4, y] = IDX_WHITE
    px[8 + 5, y] = IDX_GREY

img.save("assets/sprites/beam.png")
print("wrote assets/sprites/beam.png")

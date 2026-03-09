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

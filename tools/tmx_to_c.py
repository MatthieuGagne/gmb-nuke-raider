#!/usr/bin/env python3
"""TMX to C converter for Junk Runner track maps.

Usage: python3 tools/tmx_to_c.py <track.tmx> <track_map.c>

Converts a Tiled CSV-encoded TMX to a C source file defining track_map[].
Tiled tile IDs are 1-based; this script subtracts 1 to match 0-indexed GB
tile values (0=off-track, 1=road, etc.).
"""
import sys
import xml.etree.ElementTree as ET

# Top 4 bits of a 32-bit GID encode H/V/D flip and hex rotation — never tile data.
GID_CLEAR_FLAGS = 0x0FFFFFFF


def gid_to_tile_id(gid: int, firstgid: int) -> int:
    """Convert a Tiled GID to a 0-indexed GB tile ID.

    GID 0 (empty cell) maps to 0, matching track.c's `!= 0u` on-track check.
    Flip flags (bits 28-31) are stripped before subtracting firstgid.
    """
    if gid == 0:
        return 0
    gid &= GID_CLEAR_FLAGS
    return gid - firstgid


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

    tileset_el = root.find('tileset')
    firstgid = int(tileset_el.get('firstgid', '1')) if tileset_el is not None else 1

    raw      = data_el.text.strip()
    tile_ids = [gid_to_tile_id(int(x), firstgid) for x in raw.split(',') if x.strip()]

    if len(tile_ids) != width * height:
        raise ValueError(
            f"Expected {width * height} tiles, got {len(tile_ids)}"
        )

    # Parse "start" objectgroup for spawn coordinates.
    start_group = next(
        (og for og in root.findall('objectgroup')
         if og.get('name') == 'start'),
        None
    )
    if start_group is None:
        raise ValueError("TMX is missing an objectgroup named 'start'")
    start_obj = start_group.find('object')
    if start_obj is None:
        raise ValueError("'start' objectgroup has no objects")
    spawn_x = int(float(start_obj.get('x')))
    spawn_y = int(float(start_obj.get('y')))

    # Parse "finish" objectgroup for finish line tile row.
    finish_group = next(
        (og for og in root.findall('objectgroup')
         if og.get('name') == 'finish'),
        None
    )
    if finish_group is None:
        raise ValueError("TMX is missing an objectgroup named 'finish'")
    finish_obj = finish_group.find('object')
    if finish_obj is None:
        raise ValueError("'finish' objectgroup has no objects")
    finish_tile_y = int(float(finish_obj.get('y'))) // 8

    with open(out_path, 'w') as f:
        f.write("/* GENERATED — do not edit by hand."
                " Source: assets/maps/track.tmx */\n")
        f.write("/* Regenerate: python3 tools/tmx_to_c.py"
                " assets/maps/track.tmx src/track_map.c */\n")
        f.write("#pragma bank 255\n")
        f.write('#include <gb/gb.h>\n')
        f.write('#include "track.h"\n')
        f.write('#include "banking.h"\n\n')
        f.write(f"BANKREF(track_start_x)\n")
        f.write(f"const int16_t track_start_x = {spawn_x};\n")
        f.write(f"BANKREF(track_start_y)\n")
        f.write(f"const int16_t track_start_y = {spawn_y};\n\n")
        f.write(f"BANKREF(track_finish_line_y)\n")
        f.write(f"const uint8_t track_finish_line_y = {finish_tile_y};\n\n")
        f.write("BANKREF(track_map)\n")
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

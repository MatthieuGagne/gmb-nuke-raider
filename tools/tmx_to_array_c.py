#!/usr/bin/env python3
"""Generic TMX tile layer → C uint8_t array converter.

Usage: python3 tools/tmx_to_array_c.py <map.tmx> <out.c> <array_name> <header>

Converts the first tile layer of a Tiled CSV-encoded TMX into a C source file
defining a BANKREF'd uint8_t array. Tiled GIDs are 1-based (firstgid is
subtracted); GID 0 (empty cell) maps to 0.

Use this for simple tilemaps that don't need spawn/finish metadata.
For the track map, use tmx_to_c.py instead.
"""
import sys
import xml.etree.ElementTree as ET

GID_CLEAR_FLAGS = 0x0FFFFFFF


def gid_to_tile_id(gid, firstgid):
    if gid == 0:
        return 0
    return (gid & GID_CLEAR_FLAGS) - firstgid


def convert(tmx_path, out_path, array_name, header):
    tree = ET.parse(tmx_path)
    root = tree.getroot()

    width  = int(root.get('width'))
    height = int(root.get('height'))

    layer   = root.find('layer')
    data_el = layer.find('data')
    if data_el.get('encoding', 'xml') != 'csv':
        raise ValueError("Only CSV encoding supported")

    tileset_el = root.find('tileset')
    firstgid = int(tileset_el.get('firstgid', '1')) if tileset_el is not None else 1

    raw      = data_el.text.strip()
    tile_ids = [gid_to_tile_id(int(x), firstgid) for x in raw.split(',') if x.strip()]

    if len(tile_ids) != width * height:
        raise ValueError(f"Expected {width * height} tiles, got {len(tile_ids)}")

    with open(out_path, 'w', newline='\n') as f:
        f.write(f"/* GENERATED — do not edit. Source: {tmx_path} */\n")
        f.write(f"/* Regenerate: python3 tools/tmx_to_array_c.py"
                f" {tmx_path} {out_path} {array_name} {header} */\n")
        f.write("#pragma bank 255\n")
        f.write("#include <gb/gb.h>\n")
        f.write(f'#include "{header}"\n')
        f.write('#include "banking.h"\n\n')
        f.write(f"BANKREF({array_name})\n")
        f.write(f"const uint8_t {array_name}[{height * width}] = {{\n")
        for row in range(height):
            start = row * width
            vals  = ','.join(str(v) for v in tile_ids[start:start + width])
            f.write(f"    /* row {row:2d} */ {vals},\n")
        f.write("};\n")

    print(f"Wrote {width}x{height} map → {out_path}")


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <map.tmx> <out.c> <array_name> <header>",
              file=sys.stderr)
        sys.exit(1)
    _, tmx_path, out_path, array_name, header = sys.argv
    try:
        convert(tmx_path, out_path, array_name, header)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

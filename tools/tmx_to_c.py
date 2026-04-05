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

# NPC type → numeric constant. Must match NPC_TYPE_* in src/config.h.
NPC_TYPE_MAP = {
    "turret":     0,
    "car":        1,
    "pedestrian": 2,
}

# dir string → numeric constant. Must match player_dir_t in src/player.h.
# DIR_T=0 (N), DIR_R=2 (E), DIR_B=4 (S), DIR_L=6 (W). Absent = 0xFF (DIR_NONE).
DIR_MAP = {
    "N": 0,
    "E": 2,
    "S": 4,
    "W": 6,
}
DIR_NONE = 0xFF
MAX_NPCS = 8  # Must match MAX_ENEMIES in src/config.h.

# Powerup type → numeric constant. Must match POWERUP_TYPE_* in src/config.h.
POWERUP_TYPE_MAP = {
    "heal": 0,
}

MAX_POWERUPS = 4  # Must match MAX_POWERUPS in src/config.h.


def gid_to_tile_id(gid: int, firstgid: int) -> int:
    """Convert a Tiled GID to a 0-indexed GB tile ID.

    GID 0 (empty cell) maps to 0, matching track.c's `!= 0u` on-track check.
    Flip flags (bits 28-31) are stripped before subtracting firstgid.
    """
    if gid == 0:
        return 0
    gid &= GID_CLEAR_FLAGS
    return gid - firstgid


def parse_npc_objects(root):
    """Extract NPC spawn data from the 'enemies' object layer.

    Each object must be snapped to an 8px tile grid.
    Object 'name' field selects NPC type (must be a key in NPC_TYPE_MAP).
    Optional 'dir' custom property selects fixed facing direction (N/S/E/W);
    absent dir defaults to DIR_NONE (0xFF) — type-specific behavior at runtime.

    Returns a list of (tx, ty, type_val, dir_val) tuples capped at MAX_NPCS.
    Raises ValueError on unknown NPC name or unknown dir string.
    """
    npcs = []
    for og in root.findall('objectgroup'):
        if og.get('name') != 'enemies':
            continue
        for obj in og.findall('object'):
            name = obj.get('name', '')
            if name not in NPC_TYPE_MAP:
                raise ValueError(
                    f"Unknown NPC name '{name}' in enemies layer. "
                    f"Valid names: {list(NPC_TYPE_MAP.keys())}"
                )
            type_val = NPC_TYPE_MAP[name]
            # Parse optional 'dir' custom property
            dir_val = DIR_NONE
            props = obj.find('properties')
            if props is not None:
                for prop in props.findall('property'):
                    if prop.get('name') == 'dir':
                        raw = prop.get('value', '')
                        if raw not in DIR_MAP:
                            raise ValueError(
                                f"Unknown dir value '{raw}' on object '{name}'. "
                                f"Valid values: {list(DIR_MAP.keys())}"
                            )
                        dir_val = DIR_MAP[raw]
            px = float(obj.get('x', 0))
            py = float(obj.get('y', 0))
            tx = int(px) // 8
            ty = int(py) // 8
            npcs.append((tx, ty, type_val, dir_val))
            if len(npcs) >= MAX_NPCS:
                break
        break  # only process first 'enemies' layer
    return npcs


def parse_powerup_objects(root):
    """Extract powerup spawn data from the 'powerups' object layer.

    Each object must be snapped to an 8px tile grid.
    Object 'name' field selects powerup type (must be a key in POWERUP_TYPE_MAP).

    Returns a list of (tx, ty, type_val) tuples capped at MAX_POWERUPS.
    Missing 'powerups' objectgroup returns an empty list (backwards compat).
    Raises ValueError on unknown powerup name.
    """
    powerups = []
    for og in root.findall('objectgroup'):
        if og.get('name') != 'powerups':
            continue
        for obj in og.findall('object'):
            name = obj.get('name', '')
            if name not in POWERUP_TYPE_MAP:
                raise ValueError(
                    f"Unknown powerup name '{name}' in powerups layer. "
                    f"Valid names: {list(POWERUP_TYPE_MAP.keys())}"
                )
            type_val = POWERUP_TYPE_MAP[name]
            px = float(obj.get('x', 0))
            py = float(obj.get('y', 0))
            tx = int(px) // 8
            ty = int(py) // 8
            powerups.append((tx, ty, type_val))
            if len(powerups) >= MAX_POWERUPS:
                break
        break  # only process first 'powerups' layer
    return powerups


def tmx_to_c(tmx_path, out_path, prefix='track', emit_powerup_header=None):
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

    # Read map_type property (map-level custom properties)
    map_type_val = 0  # default: TRACK_TYPE_RACE
    map_props_el = root.find('properties')
    if map_props_el is not None:
        for p in map_props_el.findall('property'):
            if p.get('name') == 'map_type':
                val = p.get('value', 'race')
                map_type_val = 0 if val == 'race' else 1

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

    # Parse optional "checkpoints" objectgroup — missing = 0 checkpoints (backwards compat).
    checkpoints_group = next(
        (og for og in root.findall('objectgroup')
         if og.get('name') == 'checkpoints'),
        None
    )
    checkpoint_defs = []
    if checkpoints_group is not None:
        dir_map = {'N': 'CHECKPOINT_DIR_N', 'S': 'CHECKPOINT_DIR_S',
                   'E': 'CHECKPOINT_DIR_E', 'W': 'CHECKPOINT_DIR_W'}
        for obj in checkpoints_group.findall('object'):
            props = {}
            props_el = obj.find('properties')
            if props_el is not None:
                for p in props_el.findall('property'):
                    props[p.get('name')] = p.get('value')
            cx = int(float(obj.get('x')))
            cy = int(float(obj.get('y')))
            cw = int(float(obj.get('width',  '16')))
            ch = int(float(obj.get('height', '16')))
            idx = int(props.get('index', '0'))
            direction = dir_map.get(props.get('direction', 'S'), 'CHECKPOINT_DIR_S')
            checkpoint_defs.append((idx, cx, cy, cw, ch, direction))
        checkpoint_defs.sort(key=lambda t: t[0])

    npcs = parse_npc_objects(root)
    npc_count = len(npcs)

    powerups = parse_powerup_objects(root)
    powerup_count = len(powerups)

    def fmt_arr(values):
        return ', '.join(f'{v}u' for v in values)

    npc_tx   = [t[0] for t in npcs] + [0] * (MAX_NPCS - npc_count)
    npc_ty   = [t[1] for t in npcs] + [0] * (MAX_NPCS - npc_count)
    npc_type = [t[2] for t in npcs] + [0] * (MAX_NPCS - npc_count)
    npc_dir  = [t[3] for t in npcs] + [0] * (MAX_NPCS - npc_count)

    pw_tx   = [p[0] for p in powerups] + [0] * (MAX_POWERUPS - powerup_count)
    pw_ty   = [p[1] for p in powerups] + [0] * (MAX_POWERUPS - powerup_count)
    pw_type = [p[2] for p in powerups] + [0] * (MAX_POWERUPS - powerup_count)

    with open(out_path, 'w') as f:
        f.write(f"/* GENERATED — do not edit by hand."
                f" Source: {tmx_path} */\n")
        f.write(f"/* Regenerate: python3 tools/tmx_to_c.py"
                f" {tmx_path} {out_path} --prefix {prefix} */\n")
        f.write("#pragma bank 255\n")
        f.write('#include <gb/gb.h>\n')
        f.write('#include "track.h"\n')
        f.write('#include "banking.h"\n\n')
        f.write(f"BANKREF({prefix}_start_x)\n")
        f.write(f"const int16_t {prefix}_start_x = {spawn_x};\n")
        f.write(f"BANKREF({prefix}_start_y)\n")
        f.write(f"const int16_t {prefix}_start_y = {spawn_y};\n\n")
        f.write(f"BANKREF({prefix}_finish_line_y)\n")
        f.write(f"const uint8_t {prefix}_finish_line_y = {finish_tile_y};\n\n")
        f.write(f"BANKREF({prefix}_map_type)\n")
        f.write(f"const uint8_t {prefix}_map_type = {map_type_val}u;\n\n")
        f.write(f"BANKREF({prefix}_map)\n")
        total_bytes = 2 + width * height   # 2 header bytes + tile data
        f.write(f"const uint8_t {prefix}_map[{total_bytes}] = {{\n")
        f.write(f"    /* header */ {width}, {height},\n")
        for row in range(height):
            start = row * width
            vals  = ','.join(str(v) for v in tile_ids[start:start + width])
            f.write(f"    /* row {row:2d} */ {vals},\n")
        f.write("};\n\n")
        f.write('#include "checkpoint.h"\n\n')
        f.write(f"BANKREF({prefix}_checkpoints)\n")
        # SDCC (sm83) rejects empty array initializers — emit a 1-element placeholder
        # when there are no checkpoints so the symbol exists for BANKREF resolution.
        # The count=0 ensures load_checkpoints() never accesses the placeholder.
        array_size = len(checkpoint_defs) if checkpoint_defs else 1
        f.write(f"const CheckpointDef {prefix}_checkpoints[{array_size}]"
                f" = {{\n")
        if checkpoint_defs:
            for idx, cx, cy, cw, ch, direction in checkpoint_defs:
                f.write(f"    {{ {cx}, {cy}, {cw}, {ch}, {idx}, {direction} }},\n")
        else:
            f.write(f"    {{ 0, 0, 0, 0, 0, 0 }},\n")
        f.write("};\n")
        f.write(f"const uint8_t {prefix}_checkpoint_count = {len(checkpoint_defs)};\n")
        f.write(f"\nBANKREF({prefix}_npc_count)\n")
        f.write(f"const uint8_t {prefix}_npc_count = {npc_count}u;\n\n")
        f.write(f"BANKREF({prefix}_npc_tx)\n")
        f.write(f"const uint8_t {prefix}_npc_tx[8] = {{ {fmt_arr(npc_tx)} }};\n\n")
        f.write(f"BANKREF({prefix}_npc_ty)\n")
        f.write(f"const uint8_t {prefix}_npc_ty[8] = {{ {fmt_arr(npc_ty)} }};\n\n")
        f.write(f"BANKREF({prefix}_npc_type)\n")
        f.write(f"const uint8_t {prefix}_npc_type[8] = {{ {fmt_arr(npc_type)} }};\n\n")
        f.write(f"BANKREF({prefix}_npc_dir)\n")
        f.write(f"const uint8_t {prefix}_npc_dir[8] = {{ {fmt_arr(npc_dir)} }};\n")
        f.write(f"\nBANKREF({prefix}_powerup_count)\n")
        f.write(f"const uint8_t {prefix}_powerup_count = {powerup_count}u;\n\n")
        f.write(f"BANKREF({prefix}_powerup_tx)\n")
        f.write(f"const uint8_t {prefix}_powerup_tx[{MAX_POWERUPS}] = {{ {fmt_arr(pw_tx)} }};\n\n")
        f.write(f"BANKREF({prefix}_powerup_ty)\n")
        f.write(f"const uint8_t {prefix}_powerup_ty[{MAX_POWERUPS}] = {{ {fmt_arr(pw_ty)} }};\n\n")
        f.write(f"BANKREF({prefix}_powerup_type)\n")
        f.write(f"const uint8_t {prefix}_powerup_type[{MAX_POWERUPS}] = {{ {fmt_arr(pw_type)} }};\n")


def emit_npc_header(out_path, tmx_paths):
    """Generate src/track_npc_externs.h with extern declarations for all tracks.

    tmx_paths: list of TMX file paths in track order (track, track2, track3).
    Prefixes are derived: first path → 'track', rest → 'track2', 'track3', etc.
    """
    prefixes = []
    for i, p in enumerate(tmx_paths):
        prefixes.append('track' if i == 0 else f'track{i + 1}')

    lines = [
        '/* GENERATED — do not edit by hand. Regenerate with:',
        ' *   python3 tools/tmx_to_c.py --emit-header src/track_npc_externs.h \\',
        ' *     assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx',
        ' */',
        '#ifndef TRACK_NPC_EXTERNS_H',
        '#define TRACK_NPC_EXTERNS_H',
        '',
        '#include <stdint.h>',
        '#include "banking.h"',
        '',
    ]

    for prefix in prefixes:
        lines += [
            f'extern const uint8_t  {prefix}_npc_count;',
            f'extern const uint8_t  {prefix}_npc_tx[];',
            f'extern const uint8_t  {prefix}_npc_ty[];',
            f'extern const uint8_t  {prefix}_npc_type[];',
            f'extern const uint8_t  {prefix}_npc_dir[];',
            f'BANKREF_EXTERN({prefix}_npc_count)',
            f'BANKREF_EXTERN({prefix}_npc_tx)',
            f'BANKREF_EXTERN({prefix}_npc_ty)',
            f'BANKREF_EXTERN({prefix}_npc_type)',
            f'BANKREF_EXTERN({prefix}_npc_dir)',
            '',
        ]

    lines += ['#endif /* TRACK_NPC_EXTERNS_H */']

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def emit_powerup_header(out_path, tmx_paths):
    """Generate src/track_powerup_externs.h with extern declarations for all tracks.

    tmx_paths: list of TMX file paths in track order (track, track2, track3).
    Prefixes are derived: first path → 'track', rest → 'track2', 'track3', etc.
    """
    prefixes = []
    for i, p in enumerate(tmx_paths):
        prefixes.append('track' if i == 0 else f'track{i + 1}')

    lines = [
        '/* GENERATED — do not edit by hand. Regenerate with:',
        ' *   python3 tools/tmx_to_c.py --emit-powerup-header src/track_powerup_externs.h \\',
        ' *     assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx',
        ' */',
        '#ifndef TRACK_POWERUP_EXTERNS_H',
        '#define TRACK_POWERUP_EXTERNS_H',
        '',
        '#include <stdint.h>',
        '#include "banking.h"',
        '',
    ]

    for prefix in prefixes:
        lines += [
            f'extern const uint8_t  {prefix}_powerup_count;',
            f'extern const uint8_t  {prefix}_powerup_tx[];',
            f'extern const uint8_t  {prefix}_powerup_ty[];',
            f'extern const uint8_t  {prefix}_powerup_type[];',
            f'BANKREF_EXTERN({prefix}_powerup_count)',
            f'BANKREF_EXTERN({prefix}_powerup_tx)',
            f'BANKREF_EXTERN({prefix}_powerup_ty)',
            f'BANKREF_EXTERN({prefix}_powerup_type)',
            '',
        ]

    lines += ['#endif /* TRACK_POWERUP_EXTERNS_H */']

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    import argparse
    import sys

    if '--emit-powerup-header' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--emit-powerup-header', metavar='OUT_H', required=True,
                            help='Generate src/track_powerup_externs.h from all TMX inputs')
        parser.add_argument('tmx', nargs='+', help='TMX input file(s)')
        args = parser.parse_args()
        emit_powerup_header(args.emit_powerup_header, args.tmx)
    elif '--emit-header' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--emit-header', metavar='OUT_H', required=True,
                            help='Generate src/track_npc_externs.h from all TMX inputs')
        parser.add_argument('tmx', nargs='+', help='TMX input file(s)')
        args = parser.parse_args()
        emit_npc_header(args.emit_header, args.tmx)
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument('tmx_path')
        parser.add_argument('out_path')
        parser.add_argument('--prefix', default='track')
        args = parser.parse_args()
        tmx_to_c(args.tmx_path, args.out_path, prefix=args.prefix)

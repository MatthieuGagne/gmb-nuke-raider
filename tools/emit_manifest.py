#!/usr/bin/env python3
"""Emit build/game-manifest.json from build artifacts and source files.

Usage:
    python3 tools/emit_manifest.py \
        --noi   build/nuke-raider.noi \
        --overmap assets/maps/overmap.tmx \
        --tracks  assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx \
        --tsx     assets/maps/track.tsx \
        --config  src/config.h \
        --state-overmap src/state_overmap.c \
        --state-prerace src/state_prerace.c \
        > build/game-manifest.json
"""
import sys
import json
import os
import re
import argparse
import xml.etree.ElementTree as ET
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import debug_protocol  # noqa: E402

GID_FLAGS = 0x0FFFFFFF

# Curated WRAM symbols exported into build/game-manifest.json (None when the name
# does not resolve). Module-level so tests/test_emit_manifest.py can assert it.
# _rs_laps / _rs_cp_next are deliberately non-static in src/race_state.c so the
# headless scenario engine can assert lap progress by name (#448).
# _racer_active was retired here (#508): it is racer_active[0], the player's own
# slot in the shared pool, and the enemy loader activates slots 1 and up only, so
# it is 0 on every track. A constant byte cannot serve as a liveness sentinel.
CURATED_SYMBOLS = [
    '_cam_scx_shadow', '_cam_scy_shadow', '_current_race_id',
    '_px', '_py', '_hp', '_active_lap_count',
    '_rs_laps', '_rs_cp_next'
]

TILE_PX = 8            # a Game Boy background tile is 8x8 pixels
CAR_SIZE_PX = 16       # the car is 16x16; vehicle_step_axis_* clamps to map - 16

# One character per tile type, for the text grid of R12. The names are the
# `type` properties the TSX already carries and the manifest already emits in
# its `tiles` block — this adds no second source of truth.
TILE_TYPE_CHARS = {
    'TILE_WALL':   '#',
    'TILE_ROAD':   '.',
    'TILE_SAND':   's',
    'TILE_OIL':    'o',
    'TILE_BOOST':  'b',
    'TILE_FINISH': 'F',
}
# A tile id the TSX gives no `type` property. The game resolves it through the
# generated rotation LUT, which the TSX does not describe.
UNKNOWN_TILE_CHAR = '?'
SOLID_TILE_TYPES = ['TILE_WALL']


def bfs(grid, w, h, start_tx, start_ty, end_tx, end_ty):
    """BFS on a flat tile grid (0=not walkable). Returns direction list or None."""
    if start_tx == end_tx and start_ty == end_ty:
        return []
    DIRS = [('left', -1, 0), ('right', 1, 0), ('up', 0, -1), ('down', 0, 1)]
    visited = {(start_tx, start_ty): None}
    queue = deque([(start_tx, start_ty)])
    while queue:
        cx, cy = queue.popleft()
        if cx == end_tx and cy == end_ty:
            path = []
            pos = (cx, cy)
            while visited[pos] is not None:
                prev, dname = visited[pos]
                path.append(dname)
                pos = prev
            return list(reversed(path))
        for dname, dx, dy in DIRS:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                if grid[ny * w + nx] != 0:
                    visited[(nx, ny)] = ((cx, cy), dname)
                    queue.append((nx, ny))
    return None


def parse_noi(noi_path):
    """Parse DEF lines from .noi -> {name: hex_str} for WRAM-range addresses only."""
    syms = {}
    pat = re.compile(r'^DEF\s+(_\w+)\s+(0x[0-9A-Fa-f]+)')
    try:
        with open(noi_path) as f:
            for line in f:
                m = pat.match(line.strip())
                if m:
                    addr = int(m.group(2), 16) & 0xFFFF
                    if 0xC000 <= addr <= 0xDFFF:
                        syms[m.group(1)] = hex(addr)
    except FileNotFoundError:
        pass
    return syms


def parse_tsx_tile_types(tsx_path):
    """Parse track.tsx -> {tile_id_int: type_string}"""
    types = {}
    tree = ET.parse(tsx_path)
    root = tree.getroot()
    for tile in root.findall('tile'):
        tid = int(tile.attrib['id'])
        for prop in tile.findall('.//property'):
            if prop.attrib['name'] == 'type':
                types[tid] = prop.attrib['value']
    return types


def _parse_objects(tmx_root):
    """Return dict: layer_name -> list of (tx, ty, props, w, h)."""
    tw = int(tmx_root.attrib['tilewidth'])
    th = int(tmx_root.attrib['tileheight'])
    layers = {}
    for og in tmx_root.findall('objectgroup'):
        name = og.attrib['name']
        objs = []
        for obj in og.findall('object'):
            tx = int(float(obj.attrib['x'])) // tw
            ty = int(float(obj.attrib['y'])) // th
            px = int(float(obj.attrib['x']))
            py = int(float(obj.attrib['y']))
            pw = int(float(obj.attrib.get('width', 0)))
            ph = int(float(obj.attrib.get('height', 0)))
            props = {p.attrib['name']: p.attrib['value']
                     for p in obj.findall('.//property')}
            objs.append({'tx': tx, 'ty': ty, 'px': px, 'py': py,
                          'pw': pw, 'ph': ph, 'props': props})
        layers[name] = objs
    return layers


def parse_overmap(tmx_path):
    """Parse overmap.tmx -> {w, h, grid, spawn, nodes}."""
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    firstgid = int(root.find('.//tileset').attrib['firstgid'])
    w = int(root.attrib['width'])
    h = int(root.attrib['height'])

    data_el = root.find('.//layer/data')
    raw = [int(v.strip()) for v in data_el.text.strip().split(',') if v.strip()]
    grid = [((gid & GID_FLAGS) - firstgid) if gid != 0 else 0 for gid in raw]

    layers = _parse_objects(root)
    spawn = None
    nodes = []
    for obj in layers.get('hub_spawn', []):
        spawn = {'tx': obj['tx'], 'ty': obj['ty']}
    for obj in layers.get('dest_tracks', []):
        nodes.append({'tx': obj['tx'], 'ty': obj['ty'], 'type': 'track',
                      'track_id': int(obj['props']['track_id'])})
    for obj in layers.get('city_hubs', []):
        nodes.append({'tx': obj['tx'], 'ty': obj['ty'], 'type': 'hub',
                      'hub_id': int(obj['props']['hub_id'])})
    return {'w': w, 'h': h, 'grid': grid, 'spawn': spawn, 'nodes': nodes}


def parse_track(tmx_path):
    """Parse a track TMX -> {spawn, racer_waypoints, checkpoints} in pixel coords."""
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    layers = _parse_objects(root)
    spawn = None
    for obj in layers.get('start', []):
        if spawn is None:
            spawn = {'x': obj['px'], 'y': obj['py']}
    waypoints = [{'x': o['px'], 'y': o['py']}
                 for o in layers.get('racer_waypoints', [])]
    checkpoints = [{'x': o['px'], 'y': o['py'], 'w': o['pw'], 'h': o['ph']}
                   for o in layers.get('checkpoints', [])]
    return {'spawn': spawn, 'racer_waypoints': waypoints, 'checkpoints': checkpoints}


def parse_track_grid(tmx_path, tile_types):
    """Return (w, h, rows) for one track TMX.

    rows[ty] is a string of w characters, one per tile, from TILE_TYPE_CHARS.
    GID rotation flags are stripped, so a rotated tile reads as its base type.
    """
    root = ET.parse(tmx_path).getroot()
    w = int(root.get('width'))
    h = int(root.get('height'))
    firstgid = int(root.find('tileset').get('firstgid'))
    data = root.find('layer/data')
    if (data.get('encoding') or '') != 'csv':
        raise ValueError('%s: layer encoding %r is not csv'
                         % (tmx_path, data.get('encoding')))
    gids = [int(v) for v in data.text.replace('\n', '').split(',') if v.strip()]
    if len(gids) != w * h:
        raise ValueError('%s: %d cells for a %dx%d map'
                         % (tmx_path, len(gids), w, h))
    rows = []
    for ty in range(h):
        chars = []
        for tx in range(w):
            tile_id = (gids[ty * w + tx] & GID_FLAGS) - firstgid
            name = tile_types.get(tile_id)
            chars.append(TILE_TYPE_CHARS.get(name, UNKNOWN_TILE_CHAR))
        rows.append(''.join(chars))
    return w, h, rows


def parse_map_property(tmx_path, name):
    """Value of a <map><properties> property, or None."""
    root = ET.parse(tmx_path).getroot()
    for prop in root.findall('./properties/property'):
        if prop.get('name') == name:
            return prop.get('value')
    return None


def finish_line_from_grid(rows):
    """Bounding box of the TILE_FINISH cells, or None when a track has none."""
    mark = TILE_TYPE_CHARS['TILE_FINISH']
    cells = [(tx, ty) for ty, row in enumerate(rows)
             for tx, c in enumerate(row) if c == mark]
    if not cells:
        return None
    return {
        'tx_min': min(c[0] for c in cells), 'tx_max': max(c[0] for c in cells),
        'ty_min': min(c[1] for c in cells), 'ty_max': max(c[1] for c in cells),
        'tiles': [{'tx': tx, 'ty': ty} for tx, ty in cells],
    }


def describe_track(tmx_path, tile_types, hud_scanline):
    """The R10 description of one track: size, limits, grid, finish, laps."""
    w, h, rows = parse_track_grid(tmx_path, tile_types)
    laps = parse_map_property(tmx_path, 'lap_count')
    return {
        'size_tiles': {'w': w, 'h': h},
        'size_px':    {'w': w * TILE_PX, 'h': h * TILE_PX},
        # Same rule as vehicle_step_axis_x / vehicle_step_axis_y: the car is
        # 16 px wide and 16 px tall, so it stops 16 px short of the far edge.
        'drive_limits': {
            'x_min': 0, 'x_max': w * TILE_PX - CAR_SIZE_PX,
            'y_min': 0, 'y_max': h * TILE_PX - CAR_SIZE_PX,
        },
        'hud_scanline': hud_scanline,
        'lap_target':   int(laps) if laps is not None else None,
        'finish_line':  finish_line_from_grid(rows),
        'solid_grid':   rows,
    }


def parse_define(path, name):
    """Extract integer value from `#define NAME <int>[u]` in a C source file."""
    pat = re.compile(r'#define\s+' + re.escape(name) + r'\s+(\d+)')
    try:
        with open(path) as f:
            for line in f:
                m = pat.search(line)
                if m:
                    return int(m.group(1))
    except FileNotFoundError:
        pass
    return None


def parse_define_list(path, name):
    """Extract the integers from `#define NAME { a, b, ... }` in a C source file.

    Returns a list of ints, or None when the define is absent or the file is
    missing. Trailing `u` suffixes are accepted, exactly as parse_define accepts
    them for scalars. The `\\s+\\{` is what keeps NAME from matching a longer
    define's prefix: after a prefix match the next character is part of the
    longer name, not whitespace."""
    pat = re.compile(r'#define\s+' + re.escape(name) + r'\s+\{([^}]*)\}')
    try:
        with open(path) as f:
            m = pat.search(f.read())
    except FileNotFoundError:
        return None
    if m is None:
        return None
    return [int(tok) for tok in re.findall(r'\d+', m.group(1))]


def main():
    ap = argparse.ArgumentParser(description='Emit build/game-manifest.json')
    ap.add_argument('--noi',           required=True)
    ap.add_argument('--overmap',       required=True)
    ap.add_argument('--tracks',        nargs='+', required=True,
                    help='Track TMX files in order: track.tmx track2.tmx track3.tmx')
    ap.add_argument('--tsx',           required=True)
    ap.add_argument('--config', default='src/config.h',
                    help='src/config.h — read for HUD_SCANLINE')
    ap.add_argument('--state-overmap', required=True, dest='state_overmap')
    ap.add_argument('--state-prerace', required=True, dest='state_prerace')
    args = ap.parse_args()

    # Navigation
    overmap = parse_overmap(args.overmap)
    spawn = overmap['spawn']
    travel_fps = parse_define(args.state_overmap, 'TRAVEL_FRAMES_PER_TILE') or 4

    nav_to_track = {}
    nav_to_hub = {}
    for node in overmap['nodes']:
        path = bfs(overmap['grid'], overmap['w'], overmap['h'],
                   spawn['tx'], spawn['ty'], node['tx'], node['ty'])
        if node['type'] == 'track':
            nav_to_track[str(node['track_id'])] = path if path is not None else []
        else:
            nav_to_hub[str(node['hub_id'])] = path if path is not None else []

    # Controls
    pr_rows = parse_define(args.state_prerace, 'PR_CONFIG_ROWS') or 4
    # #688 — the car's turn cost, read from src/config.h rather than hardcoded:
    # PLAYER_HANDLING indexes PLAYER_TURN_FRAMES_TABLE. None when either define
    # is unreadable, matching how every other parsed value degrades here.
    turn_table = parse_define_list(args.config, 'PLAYER_TURN_FRAMES_TABLE')
    handling = parse_define(args.config, 'PLAYER_HANDLING')
    turn_frames = None
    if turn_table and handling is not None and 0 <= handling < len(turn_table):
        turn_frames = turn_table[handling]
    controls = {
        'overmap':  {'move': ['up', 'down', 'left', 'right']},
        'prerace':  {
            'cursor':          ['up', 'down'],
            'adjust':          ['left', 'right'],
            'confirm':         'a',
            'cancel':          'b',
            'cursor_to_start': pr_rows
        },
        # A D-pad direction requests a facing, not an instant thrust direction:
        # the car turns one 45-degree notch every TURN_FRAMES[PLAYER_HANDLING]
        # frames, and player_apply_physics() thrusts along the car's CURRENT
        # facing, so thrust follows the pressed direction only once the turn
        # completes. It still gates gas on J_UP|J_DOWN|J_LEFT|J_RIGHT, and
        # decode_dir() resolves eight facings, diagonals included (reached by
        # pressing two directions at once). There is no accelerate button —
        # J_A fires (#684). tests/test_emit_manifest.py asserts this block
        # against src/player.c.
        #
        # `facing` (#688) makes those two sentences machine-readable. It is a
        # dict on purpose: the cross-check test reads a top-level str as a
        # one-button spec and a top-level list as a button list, so either shape
        # would leak into the emitted button set. A dict is skipped.
        'playing':  {
            'drive': ['up', 'down', 'left', 'right'],
            'fire':  'a',
            'facing': {
                'count':                  8,
                'turn_frames_per_45_deg': turn_frames,
                'frames_per_180_deg':     None if turn_frames is None else 4 * turn_frames,
                'thrust_follows_facing':  True,
                'diagonals': {
                    'up_right':   ['up', 'right'],
                    'down_right': ['down', 'right'],
                    'down_left':  ['down', 'left'],
                    'up_left':    ['up', 'left'],
                },
            },
        }
    }

    # Tracks (args.tracks must be in order: track.tmx, track2.tmx, track3.tmx)
    tracks = {str(i): parse_track(tmx) for i, tmx in enumerate(args.tracks, start=1)}

    # Overmap
    overmap_sec = {
        'spawn': {'tx': spawn['tx'], 'ty': spawn['ty']},
        'nodes': overmap['nodes']
    }

    # Tiles (string keys for JSON compatibility)
    tile_types = parse_tsx_tile_types(args.tsx)
    tiles = {str(k): v for k, v in tile_types.items()}

    # Track description (#588 R10-R12) — size, drive limits, HUD scan line, a
    # text grid of tile types, the finish line and the lap target.
    hud_scanline = parse_define(args.config, 'HUD_SCANLINE')
    for i, tmx in enumerate(args.tracks, start=1):
        tracks[str(i)].update(describe_track(tmx, tile_types, hud_scanline))

    # Symbols — curated WRAM addresses from .noi (None if static or not yet promoted)
    curated = CURATED_SYMBOLS
    all_syms = parse_noi(args.noi)
    symbols = {name: all_syms.get(name) for name in curated}

    manifest = {
        'navigation': {
            'travel_frames_per_tile': travel_fps,
            'overmap_to_track':       nav_to_track,
            'overmap_to_hub':         nav_to_hub
        },
        'controls': controls,
        'tracks':   tracks,
        'overmap':  overmap_sec,
        'tiles':    tiles,
        'tile_legend': TILE_TYPE_CHARS,
        'solid_tile_types': SOLID_TILE_TYPES,
        'symbols':  symbols,
        'mailbox': ({
            'base': debug_protocol.base(),
            'ready_value': debug_protocol.ready_value(),
            'seed': debug_protocol.seed(),
            'addresses': debug_protocol.addresses(),
        } if debug_protocol.has_mailbox() else None),
    }

    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()

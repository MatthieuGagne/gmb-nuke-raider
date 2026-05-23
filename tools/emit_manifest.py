#!/usr/bin/env python3
"""Emit build/game-manifest.json from build artifacts and source files.

Usage:
    python3 tools/emit_manifest.py \
        --noi   build/nuke-raider.noi \
        --overmap assets/maps/overmap.tmx \
        --tracks  assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx \
        --tsx     assets/maps/track.tsx \
        --state-overmap src/state_overmap.c \
        --state-prerace src/state_prerace.c \
        > build/game-manifest.json
"""
import sys
import json
import re
import argparse
import xml.etree.ElementTree as ET
from collections import deque

GID_FLAGS = 0x0FFFFFFF


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


def main():
    ap = argparse.ArgumentParser(description='Emit build/game-manifest.json')
    ap.add_argument('--noi',           required=True)
    ap.add_argument('--overmap',       required=True)
    ap.add_argument('--tracks',        nargs='+', required=True,
                    help='Track TMX files in order: track.tmx track2.tmx track3.tmx')
    ap.add_argument('--tsx',           required=True)
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
    controls = {
        'overmap':  {'move': ['up', 'down', 'left', 'right']},
        'prerace':  {
            'cursor':          ['up', 'down'],
            'adjust':          ['left', 'right'],
            'confirm':         'a',
            'cancel':          'b',
            'cursor_to_start': pr_rows
        },
        'playing':  {
            'accelerate': 'a',
            'fire':        'a',
            'steer':       ['left', 'right']
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
    tiles = {str(k): v for k, v in parse_tsx_tile_types(args.tsx).items()}

    # Symbols — curated WRAM addresses from .noi (None if static or not yet promoted)
    curated = [
        '_cam_scx_shadow', '_cam_scy_shadow', '_current_race_id',
        '_px', '_py', '_hp', '_active_lap_count', '_cp_next', '_racer_active'
    ]
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
        'symbols':  symbols
    }

    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()

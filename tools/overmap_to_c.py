#!/usr/bin/env python3
"""Overmap TMX → C converter.

Parses assets/maps/overmap.tmx and emits src/overmap_map.c with:
  overmap_map[]         — tile type array (20×18 = 360 bytes, bank 255)
  overmap_id_map[]      — flat id map (360 bytes, 0xFF=no id, bank 255)
                          DEST tiles: 0-based track index (Tiled track_id - 1)
                          CITY_HUB tiles: 0-based hub index (Tiled hub_id - 1)
  overmap_hub_spawn_tx  — spawn tile column (uint8_t scalar, bank 255)
  overmap_hub_spawn_ty  — spawn tile row    (uint8_t scalar, bank 255)

Object layers required in overmap.tmx:
  dest_tracks  — one point object per OVERMAP_TILE_DEST cell; property track_id (int, 1-based)
  city_hubs    — one point object per OVERMAP_TILE_CITY_HUB cell; property hub_id (int, 1-based)
  hub_spawn    — exactly one point object at the OVERMAP_TILE_HUB cell; no properties

Hard-errors at build time if:
  - Any DEST tile has no matching dest_tracks object (or vice versa)
  - Any CITY_HUB tile has no matching city_hubs object (or vice versa)
  - hub_spawn layer has != 1 object, or object does not coincide with a HUB tile
  - Any dest_tracks object missing track_id property
  - Any city_hubs object missing hub_id property
"""
import sys
import xml.etree.ElementTree as ET

GID_CLEAR_FLAGS = 0x0FFFFFFF

# Tile type constants — must match src/config.h
TILE_BLANK    = 0
TILE_ROAD     = 1
TILE_HUB      = 2
TILE_DEST     = 3
TILE_CITY_HUB = 4

ID_EMPTY = 0xFF


def gid_to_tile_id(gid, firstgid):
    if gid == 0:
        return 0
    return (gid & GID_CLEAR_FLAGS) - firstgid


def parse_object_layers(root):
    """Return dict: layer_name -> list of (tx, ty, props_dict)."""
    tile_w = int(root.get('tilewidth', 8))
    tile_h = int(root.get('tileheight', 8))
    layers = {}
    for og in root.findall('objectgroup'):
        name = og.get('name', '')
        objects = []
        for obj in og.findall('object'):
            tx = int(float(obj.get('x', 0))) // tile_w
            ty = int(float(obj.get('y', 0))) // tile_h
            props = {}
            props_el = obj.find('properties')
            if props_el is not None:
                for prop in props_el.findall('property'):
                    props[prop.get('name')] = prop.get('value')
            objects.append((tx, ty, props))
        layers[name] = objects
    return layers


def convert(tmx_path, out_path):
    tree = ET.parse(tmx_path)
    root = tree.getroot()

    width  = int(root.get('width'))
    height = int(root.get('height'))

    # ── Parse tile layer ─────────────────────────────────────────────────────
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

    # ── Collect tile positions by type ───────────────────────────────────────
    dest_tile_pos     = set()
    city_hub_tile_pos = set()
    hub_tile_pos      = set()
    for ty in range(height):
        for tx in range(width):
            t = tile_ids[ty * width + tx]
            if t == TILE_DEST:
                dest_tile_pos.add((tx, ty))
            elif t == TILE_CITY_HUB:
                city_hub_tile_pos.add((tx, ty))
            elif t == TILE_HUB:
                hub_tile_pos.add((tx, ty))

    obj_layers = parse_object_layers(root)

    # ── Validate dest_tracks ─────────────────────────────────────────────────
    if 'dest_tracks' not in obj_layers:
        raise ValueError("Missing object layer: dest_tracks")
    dest_obj_pos  = set()
    dest_id_by_pos = {}
    for tx, ty, props in obj_layers['dest_tracks']:
        if 'track_id' not in props:
            raise ValueError(f"dest_tracks object at ({tx},{ty}) missing 'track_id' property")
        dest_obj_pos.add((tx, ty))
        dest_id_by_pos[(tx, ty)] = int(props['track_id']) - 1  # 1-based → 0-based
    for pos in dest_tile_pos - dest_obj_pos:
        raise ValueError(f"DEST tile at {pos} has no matching dest_tracks object")
    for pos in dest_obj_pos - dest_tile_pos:
        raise ValueError(f"dest_tracks object at {pos} has no matching DEST tile")

    # ── Validate city_hubs ───────────────────────────────────────────────────
    if 'city_hubs' not in obj_layers:
        raise ValueError("Missing object layer: city_hubs")
    city_obj_pos  = set()
    city_id_by_pos = {}
    for tx, ty, props in obj_layers['city_hubs']:
        if 'hub_id' not in props:
            raise ValueError(f"city_hubs object at ({tx},{ty}) missing 'hub_id' property")
        city_obj_pos.add((tx, ty))
        city_id_by_pos[(tx, ty)] = int(props['hub_id']) - 1  # 1-based → 0-based
    for pos in city_hub_tile_pos - city_obj_pos:
        raise ValueError(f"CITY_HUB tile at {pos} has no matching city_hubs object")
    for pos in city_obj_pos - city_hub_tile_pos:
        raise ValueError(f"city_hubs object at {pos} has no matching CITY_HUB tile")

    # ── Validate hub_spawn ───────────────────────────────────────────────────
    if 'hub_spawn' not in obj_layers:
        raise ValueError("Missing object layer: hub_spawn")
    spawn_objs = obj_layers['hub_spawn']
    if len(spawn_objs) != 1:
        raise ValueError(f"hub_spawn layer must have exactly 1 object, found {len(spawn_objs)}")
    if len(hub_tile_pos) != 1:
        raise ValueError(f"Expected exactly 1 HUB tile, found {len(hub_tile_pos)}")
    spawn_tx, spawn_ty, _ = spawn_objs[0]
    if (spawn_tx, spawn_ty) not in hub_tile_pos:
        raise ValueError(
            f"hub_spawn object at ({spawn_tx},{spawn_ty}) does not coincide with a HUB tile")

    # ── Build overmap_id_map ─────────────────────────────────────────────────
    id_map = [ID_EMPTY] * (width * height)
    for (tx, ty), track_id in dest_id_by_pos.items():
        id_map[ty * width + tx] = track_id
    for (tx, ty), hub_id in city_id_by_pos.items():
        id_map[ty * width + tx] = hub_id

    # ── Emit C source ────────────────────────────────────────────────────────
    with open(out_path, 'w') as f:
        f.write(f"/* GENERATED — do not edit. Source: {tmx_path} */\n")
        f.write(f"/* Regenerate: python3 tools/overmap_to_c.py {tmx_path} {out_path} */\n")
        f.write("#pragma bank 255\n")
        f.write("#include <gb/gb.h>\n")
        f.write('#include "config.h"\n')
        f.write('#include "banking.h"\n\n')
        f.write("BANKREF(overmap_map)\n")
        f.write(f"const uint8_t overmap_map[{height * width}] = {{\n")
        for row in range(height):
            start = row * width
            vals = ','.join(str(v) for v in tile_ids[start:start + width])
            f.write(f"    /* row {row:2d} */ {vals},\n")
        f.write("};\n\n")
        f.write("/* 0xFF = no id; DEST tiles: 0-based track index; "
                "CITY_HUB tiles: 0-based hub index */\n")
        f.write(f"const uint8_t overmap_id_map[{height * width}] = {{\n")
        for row in range(height):
            start = row * width
            vals = ','.join(f"0x{v:02X}" for v in id_map[start:start + width])
            f.write(f"    /* row {row:2d} */ {vals},\n")
        f.write("};\n\n")
        f.write(f"const uint8_t overmap_hub_spawn_tx = {spawn_tx}u;\n")
        f.write(f"const uint8_t overmap_hub_spawn_ty = {spawn_ty}u;\n")

    print(f"Wrote {width}x{height} overmap → {out_path}")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <map.tmx> <out.c>", file=sys.stderr)
        sys.exit(1)
    _, tmx_path, out_path = sys.argv
    try:
        convert(tmx_path, out_path)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

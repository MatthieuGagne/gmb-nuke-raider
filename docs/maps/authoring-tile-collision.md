# Authoring Per-Tile Collision in Tiled

## Overview

`track.tsx` stores per-tile collision polygons in Tiled's built-in Tile Collision
Editor. The build pipeline (`tools/png_to_tiles.py`) reads these polygons,
rasterizes them to 8×8 bitmasks, and emits `track_collision_mask` in
`src/track_tileset_meta.h`. Running `make` auto-regenerates the header.

## Default behaviour (no polygon authored)

| Tile type        | Default mask      |
|------------------|-------------------|
| `TILE_WALL`      | All `0x00` — fully solid |
| Any other type   | All `0xFF` — fully passable |

## How to author a collision polygon

1. Open `assets/maps/track.tsx` in Tiled (**File → Open**).
2. Select the tile you want to edit in the tileset panel.
3. Open the **Tile Collision Editor** (**View → Tile Collision Editor**).
4. Draw a **polygon** (or rectangle) covering the **passable area** of the tile.
   - The polygon interior = passable pixels (value `1`).
   - Pixels outside the polygon = solid (value `0`).
   - Coordinates are tile-local (0,0 = top-left corner, 8,8 = bottom-right).
5. Save the TSX file (**Ctrl+S**).
6. Run `make` — the header regenerates automatically.

## Bitmask encoding

`track_collision_mask[tile_idx * 8 + oy]`:
- Bit `ox` (LSB = leftmost pixel) is **1** if pixel `(ox, oy)` is passable.
- `0xFF` = entire row passable. `0x00` = entire row solid.

## Rotation variants

Rotated tile variants (e.g. tile 10 flag 1) get their collision mask by
applying the same Tiled rotation flags to the base tile's rasterized polygon.
You only need to author the polygon for the **base tile**; all rotations are
derived automatically.

## Example: lower-left diagonal wall corner

To author a tile where only the lower-left triangle is solid:

1. Select the tile in Tiled.
2. In Tile Collision Editor, draw a triangle polygon with points:
   `(0,0) → (8.001,8) → (0,8)`
   This polygon covers the lower-left triangle = passable area.
3. Save and `make`.

The generated mask will have row `oy` with bits `0..oy` set (passable).

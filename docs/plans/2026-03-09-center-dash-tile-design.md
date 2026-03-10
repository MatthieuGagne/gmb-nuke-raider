# Center Dash Tile — Debug Visual Variety

## Goal

Add a third tile type to the track so camera scrolling is visually obvious in the emulator. Without visual landmarks, a uniform road gives no feedback on whether scrolling is working.

## Design

### Tile 2: center dash

A solid all-pixel tile (`0xFF, 0xFF` × 8 rows — all black on DMG). Placed at the two center road columns (cols 10–11 of the 20-wide map) every 5th row.

### Track map changes

`track_map.c` rows where `row % 5 == 0`: columns 10 and 11 → tile 2 instead of tile 1.
All other cells unchanged (sand=0, road=1).

### Tile data changes

`track_tiles.c`: append tile 2 (16 bytes, all `0xFF`) and bump `track_tile_data_count` to 3.

## Scope

- No new collision logic — tile 2 is treated as road (passable) by `corners_passable`.
- No test changes needed — track tests use tile indices 0/1 and are unaffected.
- Both source files are hand-edited (the "auto-generated" comments are stale; the PNG/TMX pipeline is not in active use).

## Files changed

- `src/track_tiles.c` — add tile 2
- `src/track_map.c` — place tile 2 at cols 10–11 on every 5th row

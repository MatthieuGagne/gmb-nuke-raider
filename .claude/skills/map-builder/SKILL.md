---
name: map-builder
description: Use when creating a new map or track for Nuke Raider — designing the layout, drawing in Tiled, running the TMX conversion pipeline, and wiring the generated C files into the game.
---

# Map Builder — dispatch stub

This skill owns no pipeline detail of its own. The **`map-expert` agent** does, and it executes
the whole job end-to-end autonomously (Tiled/TMX schema, GID decoding, `tmx_to_c.py` and
`png_to_tiles.py` invocation, per-map dimensions, BG tilemap hardware).

**Do this:** dispatch the `map-expert` agent (Agent tool) with

```
implement this task: <the map task, verbatim>
```

Then read its report. Do not hand-run the converters from memory — the Makefile passes flags
(`--rotation-manifest`, `--tsx`, `--id-map`, `--id-map-out`, `--meta-header-out`, `--prefix`)
that a bare invocation omits, and the omission silently produces a half-generated map.

## Facts that survive outside the agent

- **Source of truth:** `assets/maps/*.tmx`. Never hand-edit `src/*_map.c` or `src/*_tiles.c` —
  they are generated and are overwritten on the next `make`.
- **Map dimensions are per-map and runtime**, read from the TMX by the generator and consumed
  at runtime as `active_map_w` / `active_map_h` (set by `load_track_header()`, `src/track.h`).
  There are no `MAP_TILES_W` / `MAP_TILES_H` compile-time constants. `MAX_MAP_TILES_W`
  (`src/config.h`) is a ROM-budget cap, not a dimension.
- **Tracks are streamed, not blitted.** A track is far taller than the 32×32 hardware BG map, so
  rows are streamed in as the camera moves (`loader_map_fill_row`, `src/loader.h`) — there is no
  one-shot `set_bkg_tiles` of the whole map.
- **Never write `SET_BANK` / `SWITCH_ROM` in a banked file.** Banked map data is read through the
  NONBANKED helpers in `src/loader.c`. The `bank-pre-write` gate blocks the inline form.
- **Tile budget:** ≤ 192 unique tiles for DMG compatibility (192 more in CGB VRAM bank 1).
- Tiled must save **CSV** tile-layer encoding at **8×8** tile size.

## Cross-references

- **`map-expert`** agent — the real pipeline reference; dispatch it
- **`bank-pre-write`** skill — banking rules (fires automatically on `src/*` writes)
- **`gbdk-expert`** agent — VBlank rules, LCDC, `set_bkg_data` details

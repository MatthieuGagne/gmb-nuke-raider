# TILES.md — Tile System Reference

This document covers hardware limits, per-state tile budgets, and pipeline
workflows for artists and developers adding tile assets to Nuke Raider.

---

## Hardware limits

| Property | Value |
|----------|-------|
| Total VRAM tile slots | 256 (tiles 0–255) |
| Sprite (OBJ) pool | Slots 0–63 (64 slots) |
| BG loader pool | Slots 143–254 (112 slots) |
| BG font slots (reserved) | Slots 64–142 — DO NOT allocate (GBDK printf font + HUD font) |
| Sentinel slot | 255 — reserved, never allocated |
| Palette depth | 4 colors per palette (2-bit indexed) |
| OAM sprites max | 40 total / 10 per scanline |
| Tile size | 8×8 pixels |
| BG tilemap size (hardware) | 32×32 tiles (wraps — ring buffer) |

---

## Per-state tile budget

Budgets are checked automatically by `make tile-check`. Values reflect
post-Increment-3 slot allocations.

| State | Sprite assets | Sprite used / 64 | Sprite free | BG assets | BG used / 112 | BG free |
|-------|--------------|-------------------|-------------|-----------|---------------|---------|
| playing | player(16) + bullet(1) + turret(2) | 19 | 45 | track(9) | 9 | 103 |
| overmap | overmap_car(2) | 2 | 62 | overmap_bg(5) | 5 | 107 |
| hub | dialog_arrow(1) | 1 | 63 | drifter(16)+mechanic(16)+trader(16)+border(8) | 56 | 56 |

> **Note:** HUD font (15 tiles, slots 128–142) is self-managed by `hud.c` and
> is excluded from loader budget accounting.

---

## How to add a new sprite asset

1. **Draw in Aseprite** — 8×8 tiles, indexed mode, 4-color palette (DMG or CGB).
2. **Export PNG** — File → Export As → `assets/sprites/<name>.png`.
3. **Run pipeline** — `python3 tools/png_to_tiles.py assets/sprites/<name>.png src/<name>_tiles.c`
   This generates `src/<name>_tiles.c` with `<name>_tile_data[]` and `<name>_tile_data_count`.
4. **Add to `bank-manifest.json`** — add an entry for `src/<name>_tiles.c` before writing the C file.
5. **Add `tile_asset_t` enum value** — add `TILE_ASSET_<NAME>` to the enum in `src/loader.h` and update `TILE_ASSET_COUNT`.
6. **Add registry entry** — add a `tile_registry_entry_t` row in `src/loader.c`:`loader_registry_tbl[]` with `is_sprite = 1u`.
7. **Add to state manifest** — add `TILE_ASSET_<NAME>` to the appropriate `k_<state>_assets[]` array in `src/loader.c`.
8. **Add symbol to `check_tile_budget.py`** — add the `_count` symbol name to the matching state in `STATE_MANIFESTS`.
9. **Run `make tile-check`** — verify the state stays within budget.

No slot number to pick — the loader assigns slots automatically at state load time.

---

## How to add a new background tileset

1. **Draw tiles in Tiled or Aseprite** — export as indexed PNG, 4-color palette, dimensions multiple of 8.
2. **Run pipeline** — `python3 tools/png_to_tiles.py assets/<name>.png src/<name>_tiles.c`
3. **Add to `bank-manifest.json`** — add entry for `src/<name>_tiles.c`.
4. **Add `tile_asset_t` enum value** — add `TILE_ASSET_<NAME>` in `src/loader.h`, update `TILE_ASSET_COUNT`.
5. **Add registry entry** — add row in `loader_registry_tbl[]` with `is_sprite = 0u`.
6. **Add to state manifest** and `check_tile_budget.py` `STATE_MANIFESTS`.
7. **Run `make tile-check`** — unique tile count must fit within BG slot budget (112 slots).

---

## Map creation constraints

### Background tilemap — hardware ring buffer

The GBC hardware BG tilemap is **32×32 tiles** and wraps (ring buffer). The camera
streams rows/columns into VRAM as the player moves — the tilemap appears infinite
but only 32 rows × 32 columns are in VRAM at any time.

| Map type | Constraint |
|----------|-----------|
| Track maps | Can exceed 32×32 (camera streams rows/cols dynamically) |
| Overmap | Hard limit: **32×32 tiles** (entire map fits in one tilemap) |
| Finish line | Must be **≥ 4 tiles from the map edge** in the finish direction (N/S/E/W) |

### Map ROM budget

| Map size | ROM cost |
|----------|----------|
| Formula | 1 byte per tile |
| 32×32 | 1 KB |
| 64×256 | 16 KB |

### Tiled workflow

`assets/maps/*.tmx` is the **authoritative source** for all map tile data.
**Never edit generated `src/*_map.c` files directly** — they are overwritten on
the next build. To place a tile (e.g. `TILE_REPAIR`), add it in Tiled, then
run `make clean && make` to regenerate.

#### Required TMX map properties

Every track TMX must have these root-level properties or `tmx_to_c.py` will error:

| Property | Type | Example | Notes |
|----------|------|---------|-------|
| `lap_count` | integer | `3` | Number of laps; `1` for combat/one-shot tracks |
| `map_type` | string | `race` | `race` or any other string (treated as combat) |

#### Required objectgroups

| Objectgroup | Required | Notes |
|-------------|----------|-------|
| `start` | yes | Exactly one object — player spawn position |
| `finish` | yes | Exactly one object — must have `direction` property: `N`, `S`, `E`, or `W` |
| `checkpoints` | no | Each object needs `direction` (N/S/E/W, default S) and `index` (int) |
| `enemies` | no | Object `name` = type (`turret`); optional `dir` property for fixed facing |
| `powerups` | no | Object `name` = type (`heal`) |

Use `assets/maps/track_template.tmx` as the starting scaffold for new tracks — it includes all required properties and objectgroups pre-filled.

#### Build pipeline (3 steps, all automated by `make`)

1. **Rotation manifest** — `tmx_to_c.py --emit-rotation-manifest` scans all TMX files for rotated/flipped tile variants; outputs `build/track_rotation_manifest.json`.
2. **Tile data + ID-map + meta header** — `png_to_tiles.py` generates base tiles + rotation variants (`src/track_tiles.c`), the ID-map (`build/track_tile_id_map.json`), and `src/track_tileset_meta.h`. Total tiles (base + rotations) must not exceed **192** (one VRAM bank).
3. **Per-track map arrays** — separate `tmx_to_c.py --id-map` call per TMX file; uses the ID-map to resolve rotated GIDs into correct C tile indices.

`src/track_tileset_meta.h` is fully generated — **never edit it by hand**.

---

## What breaks the build

| Problem | Effect |
|---------|--------|
| State sprite tiles > 64 | `make tile-check` exits non-zero |
| State BG tiles > 112 | `make tile-check` exits non-zero |
| Any state's runtime load exceeds pool | `loader_alloc_slots()` calls `disable_interrupts(); while(1){}` — game freezes on boot |
| PNG not indexed to 4 colors | `png_to_tiles.py` exits with error |
| Tile dimensions not multiples of 8 | `png_to_tiles.py` exits with error |
| Editing `src/*_map.c` directly | Changes silently overwritten on next `make` |

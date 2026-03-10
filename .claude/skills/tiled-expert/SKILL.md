---
name: tiled-expert
description: Use when reading, writing, or parsing Tiled map files (.tmx, .tsx, .json) — map structure, Global Tile IDs, GID flip flags, tile layer data encoding (CSV/base64/zlib), layer types, object types, tileset firstgid, custom properties, or converting Tiled exports for use in game code.
---

# Tiled Expert

## Overview

[Tiled](https://www.mapeditor.org/) is a 2D level editor that saves maps as **TMX** (XML) or **JSON**. This skill covers both formats with emphasis on JSON, which is easier to parse in game code.

**Canonical docs:** https://doc.mapeditor.org/en/stable/reference/json-map-format/

---

## Critical Concept: Global Tile IDs (GIDs)

GIDs identify tiles across all tilesets in a map. **GID 0 = empty cell.**

**Calculating local tile ID from GID:**
1. Sort tilesets by `firstgid` descending
2. Find the tileset where `tileset.firstgid <= gid`
3. `local_id = gid - tileset.firstgid`

**Flip/rotation flags in the top 4 bits of each 32-bit GID:**

| Bit | Hex Mask     | Meaning                                    |
|-----|--------------|--------------------------------------------|
| 32  | `0x80000000` | Horizontal flip                            |
| 31  | `0x40000000` | Vertical flip                              |
| 30  | `0x20000000` | Diagonal flip / 60° rotation (hex)         |
| 29  | `0x10000000` | 120° rotation (hexagonal only)             |

**Always mask out flags before using the GID** — even on non-hexagonal maps, clear bit 29:

```c
#define GID_FLAGS_MASK 0xF0000000u
#define GID_FLIP_H     0x80000000u
#define GID_FLIP_V     0x40000000u
#define GID_FLIP_D     0x20000000u

uint32_t flags  = gid & GID_FLAGS_MASK;
uint32_t raw_gid = gid & ~GID_FLAGS_MASK;  /* actual tile GID */
```

---

## JSON Format

### Map Root Object

| Field          | Type    | Notes                                              |
|----------------|---------|----------------------------------------------------|
| `type`         | string  | `"map"`                                            |
| `width`        | int     | Map width in tiles                                 |
| `height`       | int     | Map height in tiles                                |
| `tilewidth`    | int     | Tile width in pixels                               |
| `tileheight`   | int     | Tile height in pixels                              |
| `orientation`  | string  | `"orthogonal"`, `"isometric"`, `"staggered"`, `"hexagonal"` |
| `renderorder`  | string  | `"right-down"` (default), `"right-up"`, `"left-down"`, `"left-up"` |
| `infinite`     | bool    | If true, use `chunks` instead of `data` in tile layers |
| `layers`       | array   | Array of Layer objects                             |
| `tilesets`     | array   | Array of Tileset objects                           |
| `properties`   | array   | Custom Property objects                            |
| `nextlayerid`  | int     | Auto-increment counter for layer IDs               |
| `nextobjectid` | int     | Auto-increment counter for object IDs              |
| `version`      | string  | JSON format version                                |
| `tiledversion` | string  | Tiled app version that saved the file              |

---

### Layer Types

All layers share these base fields:

| Field       | Type   | Notes                                                 |
|-------------|--------|-------------------------------------------------------|
| `id`        | int    | Unique layer ID                                       |
| `name`      | string | Layer name                                            |
| `type`      | string | `"tilelayer"`, `"objectgroup"`, `"imagelayer"`, `"group"` |
| `visible`   | bool   | Editor visibility                                     |
| `opacity`   | double | 0.0–1.0                                              |
| `offsetx`   | double | Pixel offset X (default 0)                            |
| `offsety`   | double | Pixel offset Y (default 0)                            |
| `parallaxx` | double | Parallax factor X (default 1.0, since 1.5)            |
| `parallaxy` | double | Parallax factor Y (default 1.0, since 1.5)            |
| `tintcolor` | string | Hex color multiplier `"#RRGGBB"` or `"#AARRGGBB"`    |
| `properties`| array  | Custom Property objects                               |
| `x`, `y`   | int    | Always 0 (use offsetx/offsety instead)                |

#### tilelayer — additional fields

| Field         | Type          | Notes                                               |
|---------------|---------------|-----------------------------------------------------|
| `width`       | int           | Layer width in tiles                                |
| `height`      | int           | Layer height in tiles                               |
| `data`        | array/string  | GID array (CSV) or base64 string; absent if infinite|
| `encoding`    | string        | `"csv"` (default) or `"base64"`                     |
| `compression` | string        | `""`, `"zlib"`, `"gzip"`, or `"zstd"`               |
| `chunks`      | array         | Chunk objects (infinite maps only)                  |

**Tile order:** row-major, left-to-right, top-to-bottom.
**Index formula:** `tile[y * width + x]`

#### objectgroup — additional fields

| Field       | Type   | Notes                                      |
|-------------|--------|--------------------------------------------|
| `objects`   | array  | Array of Object instances                  |
| `draworder` | string | `"topdown"` (default) or `"index"`         |
| `color`     | string | Layer color in editor                      |

#### imagelayer — additional fields

| Field             | Type   | Notes                             |
|-------------------|--------|-----------------------------------|
| `image`           | string | Image file path                   |
| `imagewidth`      | int    | Image width in pixels (since 1.11)|
| `imageheight`     | int    | Image height in pixels            |
| `transparentcolor`| string | Hex transparent color             |
| `repeatx`         | bool   | Tile horizontally (since 1.8)     |
| `repeaty`         | bool   | Tile vertically (since 1.8)       |

#### group — additional fields

| Field    | Type  | Notes                        |
|----------|-------|------------------------------|
| `layers` | array | Nested layers of any type    |

---

### Tile Layer Data Encoding

**CSV (simplest — recommended for game code):**
```json
{ "encoding": "csv", "data": [1, 2, 0, 3, ...] }
```
`data` is a JSON array of uint32 GIDs. GID 0 = empty.

**Base64 uncompressed:**
```json
{ "encoding": "base64", "data": "AQIDBA==" }
```
Decode base64 → interpret as **little-endian uint32 array**, one entry per tile.

**Base64 + zlib:**
```json
{ "encoding": "base64", "compression": "zlib", "data": "..." }
```
Decode base64 → decompress (zlib inflate) → interpret as little-endian uint32 array.

Same pattern for `"gzip"` and `"zstd"`.

---

### Object Fields

| Field       | Type    | Notes                                              |
|-------------|---------|-----------------------------------------------------|
| `id`        | int     | Unique object ID                                   |
| `name`      | string  | Object name                                        |
| `type`      | string  | Object type/class (game-defined, e.g. `"enemy"`)   |
| `x`, `y`   | double  | Position in pixels from map origin                 |
| `width`     | double  | Width in pixels (rectangles, ellipses)             |
| `height`    | double  | Height in pixels                                   |
| `rotation`  | double  | Clockwise rotation in degrees (default 0)          |
| `visible`   | bool    | Editor visibility                                  |
| `gid`       | int     | GID if this is a tile object (optional)            |
| `ellipse`   | bool    | Present and true if object is an ellipse           |
| `point`     | bool    | Present and true if object is a point              |
| `polygon`   | array   | Array of `{x, y}` points (relative to object pos) |
| `polyline`  | array   | Array of `{x, y}` points (open path)               |
| `template`  | string  | Path to `.tx` template file                        |
| `properties`| array   | Custom Property objects                            |

**Shape determination:**
- Has `gid` → tile object
- Has `ellipse: true` → ellipse
- Has `point: true` → point
- Has `polygon` → polygon
- Has `polyline` → polyline
- Otherwise → rectangle (default)

---

### Tileset Fields

| Field             | Type   | Notes                                                 |
|-------------------|--------|-------------------------------------------------------|
| `firstgid`        | int    | First GID assigned to this tileset in this map        |
| `source`          | string | Path to external `.tsj`/`.tsx` file (if external)     |
| `name`            | string | Tileset name                                          |
| `tilewidth`       | int    | Tile width in pixels                                  |
| `tileheight`      | int    | Tile height in pixels                                 |
| `tilecount`       | int    | Total number of tiles                                 |
| `columns`         | int    | Columns in the tileset image (0 for image collection) |
| `image`           | string | Path to tileset image                                 |
| `imagewidth`      | int    | Image width in pixels                                 |
| `imageheight`     | int    | Image height in pixels                                |
| `margin`          | int    | Margin from image edge to first tile (pixels)         |
| `spacing`         | int    | Spacing between tiles (pixels)                        |
| `tiles`           | array  | Per-tile data (animations, properties, collision)     |
| `properties`      | array  | Custom Property objects                               |

**External tilesets:** When `source` is present, the tileset data lives in a separate `.tsj` (JSON) or `.tsx` (XML) file. Load and merge using `firstgid`.

**Tile position in image (single-image tileset):**
```
col = local_id % columns
row = local_id / columns
pixel_x = margin + col * (tilewidth + spacing)
pixel_y = margin + row * (tileheight + spacing)
```

---

### Custom Properties

Each property object:

| Field          | Type   | Notes                                                  |
|----------------|--------|--------------------------------------------------------|
| `name`         | string | Property key                                           |
| `type`         | string | `"string"`, `"int"`, `"float"`, `"bool"`, `"color"`, `"file"`, `"object"`, `"class"` |
| `value`        | any    | The property value                                     |
| `propertytype` | string | Custom enum/class type name (since 1.8)                |

Color values: `"#AARRGGBB"` hex string.

---

### Chunk (Infinite Maps)

| Field    | Type          | Notes                        |
|----------|---------------|------------------------------|
| `x`      | int           | Chunk origin in tiles        |
| `y`      | int           | Chunk origin in tiles        |
| `width`  | int           | Chunk width in tiles (16)    |
| `height` | int           | Chunk height in tiles (16)   |
| `data`   | array/string  | Same encoding as finite maps |

---

## TMX Format (XML)

Same structure as JSON, mapped to XML elements. Key differences:

| JSON                    | TMX XML                             |
|-------------------------|-------------------------------------|
| Root map object         | `<map>` element                     |
| `layers` array          | `<layer>`, `<objectgroup>`, etc. as children of `<map>` |
| `tilesets` array        | `<tileset>` children of `<map>`     |
| `properties` array      | `<properties><property .../></properties>` |
| `data` field            | `<data encoding="..." compression="...">` |
| Layer type via `type`   | Different element names (`<layer>` vs `<objectgroup>`) |

**TMX data element — CSV example:**
```xml
<layer id="1" name="Ground" width="20" height="15">
  <data encoding="csv">
1,2,3,0,1,...
  </data>
</layer>
```

**TSX (external tileset):** Same as TMX `<tileset>` element, saved as a standalone file. Referenced from TMX via `<tileset firstgid="1" source="terrain.tsx"/>`.

---

## Practical Parsing Pattern (C)

```c
/* Resolve GID to tileset + local tile ID */
int find_tileset(Tileset *tilesets, int count, uint32_t raw_gid) {
    /* tilesets sorted by firstgid ascending */
    int best = -1;
    for (int i = 0; i < count; i++) {
        if (tilesets[i].firstgid <= (int)raw_gid) best = i;
        else break;
    }
    return best; /* local_id = raw_gid - tilesets[best].firstgid */
}

/* Decode tile layer entry */
void decode_tile(uint32_t gid, uint32_t *raw_gid_out, int *flip_h, int *flip_v) {
    *flip_h = (gid & 0x80000000u) != 0;
    *flip_v = (gid & 0x40000000u) != 0;
    *raw_gid_out = gid & ~0xF0000000u;
}
```

**Prefer CSV export from Tiled for simplest parsing** — no base64 decode, no decompression, direct JSON integer array.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using GID directly as tile index | Always subtract `tileset.firstgid` to get local ID |
| Forgetting GID 0 = empty cell | Check `raw_gid == 0` before looking up tileset |
| Not clearing flip bits before tileset lookup | Mask with `& ~0xF0000000u` first |
| Assuming tileset is embedded | Check for `source` field; load external `.tsj`/`.tsx` separately |
| Tile index formula wrong | `tile[y * layer_width + x]` — use layer `width`, not map `width` |
| Parsing base64 as string | It's binary data: base64 → bytes → uint32 little-endian array |
| `encoding: "csv"` → expecting a string | **CSV in JSON is a JSON array of integers**, not a comma-separated string. Only base64 produces a string. |
| Object `type` vs `class` | Pre-1.9: `type` field. Since 1.9: `class` field. Check both. |

---

## Quick Reference: Layer Type Identification (JSON)

```
layer.type == "tilelayer"    → tile grid; read layer.data[]
layer.type == "objectgroup"  → objects; read layer.objects[]
layer.type == "imagelayer"   → background image; read layer.image
layer.type == "group"        → container; recurse layer.layers[]
```

---

## Map Conversion for Game Code

### Project Scripts (Wasteland Racer)

| Script | Purpose | Run |
|--------|---------|-----|
| `tools/tmx_to_c.py` | Converts `track.tmx` → `src/track_map.c` | `python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c` |
| `assets/maps/create_assets.py` | Generates `tileset.png`, `track.tsx`, `track.tmx` from hardcoded shape | `python3 assets/maps/create_assets.py` |
| `tests/test_tmx_to_c.py` | Unit tests for the converter | `python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v` |

**Permissions:** You may read, run, edit, and create Python scripts in `tools/` and `assets/maps/`. Run tests after any change.

---

### How `tmx_to_c.py` Works

The project uses **TMX (XML)** with **CSV encoding** — not JSON. GIDs must be decoded carefully: flip flags live in the top 4 bits, `firstgid` is read from `<tileset>`, and GID 0 is an empty cell (maps to 0).

```python
import xml.etree.ElementTree as ET

GID_CLEAR_FLAGS = 0x0FFFFFFF

def gid_to_tile_id(gid: int, firstgid: int) -> int:
    if gid == 0:
        return 0           # empty cell → 0 (matches track.c != 0u check)
    gid &= GID_CLEAR_FLAGS  # strip H/V/D flip bits
    return gid - firstgid

tileset_el = root.find('tileset')
firstgid = int(tileset_el.get('firstgid', '1')) if tileset_el is not None else 1
raw      = data_el.text.strip()
tile_ids = [gid_to_tile_id(int(x), firstgid) for x in raw.split(',') if x.strip()]
```

Output format (`src/track_map.c`):
```c
/* GENERATED — do not edit by hand. Source: assets/maps/track.tmx */
#include "track.h"
const uint8_t track_map[MAP_TILES_H * MAP_TILES_W] = {
    /* row  0 */ 0,0,0,...,
    ...
};
```

---

### Adding a New Converter

When adding support for new map types (e.g. multi-layer, JSON export, object layers):

1. Create `tools/<name>_to_c.py` following the same pattern
2. Write `tests/test_<name>_to_c.py` first (TDD)
3. Run `python3 -m unittest discover -s tests -p "test_<name>_to_c.py" -v`
4. Emit a `/* GENERATED */` header and `#include` in all output `.c` files

**CSV in TMX is a plain comma-separated text string** inside the `<data>` element — not a JSON array. Split on `','` after stripping whitespace.

---

### Common Conversion Mistakes

| Mistake | Fix |
|---------|-----|
| Using Tiled IDs directly as tile indices | Tiled is 1-based; subtract 1 for 0-indexed GB tiles |
| Parsing base64 TMX data as text | Decode base64 → zlib decompress → uint32 LE array |
| Using map `width` as row stride | Use `layer` `width` attribute, not map-level `width` |
| Editing `src/track_map.c` by hand | It's generated — edit `assets/maps/track.tmx` and re-run the converter |
| Forgetting to run tests after converter changes | `python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v` |
| Ignoring GID flip flags | Mask with `& 0x0FFFFFFF` before subtracting `firstgid`; raw H/V/D flip bits corrupt the tile index |
| Hardcoding `- 1` as tile offset | Read `firstgid` from `<tileset firstgid="...">` element; maps may use any firstgid |
| GID 0 underflows to 255 (uint8) | Check `gid == 0` before subtracting; return 0 (empty sentinel matches `track.c`'s `!= 0u`) |

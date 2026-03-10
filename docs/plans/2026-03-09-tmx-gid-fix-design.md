# Design: Harden tmx_to_c.py Against Silent GID Corruption

**Issue:** [#41](https://github.com/MatthieuGagne/gmb-wasteland-racer/issues/41)
**Date:** 2026-03-09

## Problem

`tools/tmx_to_c.py` silently produces corrupt tile data in three cases:

1. **Flip flags** — Tiled encodes H/V/D flip in bits 28–31 of each GID. The converter reads raw GIDs as Python ints, so a flipped tile (e.g. `0x80000001`) produces a massive corrupted value after `- 1`.
2. **Empty cells (GID 0)** — `int("0") - 1 = -1`. Python writes `-1` to the C array; the uint8_t wraps to 255, which `track.c` interprets as an on-track tile.
3. **Hardcoded `- 1` offset** — firstgid is always 1 today, but the code assumes it instead of reading it from the `<tileset>` element.

## Design

### Approach: `gid_to_tile_id()` helper (selected)

Extract GID → tile-ID conversion into a pure function. This makes each fix a named, independently-testable step.

```python
GID_CLEAR_FLAGS = 0x0FFFFFFF

def gid_to_tile_id(gid: int, firstgid: int) -> int:
    """Convert a Tiled GID to a 0-indexed GB tile ID.

    - GID 0 (empty cell) → 0  (matches track.c's `!= 0u` check)
    - Strips flip flags (bits 28-31) before subtracting firstgid
    """
    if gid == 0:
        return 0
    gid &= GID_CLEAR_FLAGS
    return gid - firstgid
```

`firstgid` is read from the `<tileset>` element:
```python
firstgid = int(root.find('tileset').get('firstgid', '1'))
```

The CSV parse line becomes:
```python
tile_ids = [gid_to_tile_id(int(x), firstgid) for x in raw.split(',') if x.strip()]
```

The `if x.strip()` guard handles trailing commas Tiled sometimes emits.

### Empty Cell Sentinel

`track.c:21` checks `track_map[...] != 0u` for on-track detection, so **0 = empty/off-track**. GID 0 → 0 is correct. No change to `track.c` needed.

## Files Changed

| File | Change |
|------|--------|
| `tools/tmx_to_c.py` | Add `GID_CLEAR_FLAGS` constant, `gid_to_tile_id()` helper, read `firstgid`, update comprehension |
| `tests/test_tmx_to_c.py` | Add direct unit tests for `gid_to_tile_id()` + integration tests with new TMX fixtures |
| `.claude/skills/tiled-expert/SKILL.md` | Update "How `tmx_to_c.py` Works" code block; add 3 rows to Common Conversion Mistakes |

## Test Plan

**Direct unit tests on `gid_to_tile_id()`** (no file I/O):
- Horizontally-flipped GID (`0x80000001`, firstgid=1) → `0`
- Vertically-flipped GID (`0x40000002`, firstgid=1) → `1`
- GID 0, any firstgid → `0`
- firstgid=2, GID 3 → `1`
- Normal GID 1, firstgid=1 → `0`

**Integration tests** (new TMX fixtures piped through `_convert()`):
- TMX with flipped tile → correct index in output C
- TMX with GID 0 cell → `0` in output (not `-1` or `255`)
- TMX with `firstgid="2"` → indices offset by 2 correctly

**Existing tests must still pass** (AC4).

## Out of Scope

- Multi-layer support
- JSON map format support
- Changes to map art or game logic

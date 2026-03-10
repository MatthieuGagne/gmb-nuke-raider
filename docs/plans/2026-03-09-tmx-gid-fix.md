# tmx_to_c GID Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three silent GID corruption bugs in `tools/tmx_to_c.py`: flip flags, empty cell underflow, and hardcoded `firstgid`.

**Architecture:** Extract a pure `gid_to_tile_id(gid, firstgid)` helper that centralises all GID → tile-ID logic. The converter reads `firstgid` from the `<tileset>` XML element and passes it into the helper. Tests hit the helper directly (fast, no I/O) plus three integration fixtures.

**Tech Stack:** Python 3, `xml.etree.ElementTree`, `unittest`, `pytest` (`python3 -m pytest`)

**Branch:** `design/tmx-gid-fix` (already created; all commits go here)

---

### Task 1: Write failing unit tests for `gid_to_tile_id()`

**Files:**
- Modify: `tests/test_tmx_to_c.py:1-9` (add import of `gid_to_tile_id`)
- Modify: `tests/test_tmx_to_c.py` (add new test class at end of file)

**Step 1: Add the import**

In `tests/test_tmx_to_c.py`, change the import line (line 9):

```python
import tmx_to_c as conv
from tmx_to_c import gid_to_tile_id
```

**Step 2: Add unit test class at the end of the file (before `if __name__ == '__main__':`)**

```python
class TestGidToTileId(unittest.TestCase):

    def test_normal_tile_firstgid_1(self):
        # GID 1 with firstgid=1 → tile index 0
        self.assertEqual(gid_to_tile_id(1, 1), 0)

    def test_normal_tile_firstgid_2(self):
        # GID 3 with firstgid=2 → tile index 1
        self.assertEqual(gid_to_tile_id(3, 2), 1)

    def test_empty_cell_returns_zero(self):
        # GID 0 = empty cell → always 0 regardless of firstgid
        self.assertEqual(gid_to_tile_id(0, 1), 0)
        self.assertEqual(gid_to_tile_id(0, 2), 0)

    def test_hflip_stripped(self):
        # GID with H-flip bit set (0x80000001) and firstgid=1 → tile 0
        self.assertEqual(gid_to_tile_id(0x80000001, 1), 0)

    def test_vflip_stripped(self):
        # GID with V-flip bit set (0x40000002) and firstgid=1 → tile 1
        self.assertEqual(gid_to_tile_id(0x40000002, 1), 1)

    def test_all_flags_stripped(self):
        # GID with all flip bits set (0xF0000003) and firstgid=1 → tile 2
        self.assertEqual(gid_to_tile_id(0xF0000003, 1), 2)
```

**Step 3: Run tests to verify they fail**

```bash
python3 -m unittest tests.test_tmx_to_c.TestGidToTileId -v
```

Expected: `ERROR` — `ImportError: cannot import name 'gid_to_tile_id'`

---

### Task 2: Implement `gid_to_tile_id()` and update the converter

**Files:**
- Modify: `tools/tmx_to_c.py`

**Step 1: Add constant and helper after the docstring/imports (after line 11)**

```python
# Top 4 bits of a 32-bit GID encode H/V/D flip and hex rotation — never tile data.
GID_CLEAR_FLAGS = 0x0FFFFFFF


def gid_to_tile_id(gid: int, firstgid: int) -> int:
    """Convert a Tiled GID to a 0-indexed GB tile ID.

    GID 0 (empty cell) maps to 0, matching track.c's `!= 0u` on-track check.
    Flip flags (bits 28-31) are stripped before subtracting firstgid.
    """
    if gid == 0:
        return 0
    gid &= GID_CLEAR_FLAGS
    return gid - firstgid
```

**Step 2: Read `firstgid` and use the helper inside `tmx_to_c()`**

Replace this block in `tmx_to_c()`:

```python
    # Tiled uses 1-based tile IDs; subtract 1 for 0-indexed GB tile values.
    raw      = data_el.text.strip()
    tile_ids = [int(x) - 1 for x in raw.split(',')]
```

With:

```python
    tileset_el = root.find('tileset')
    firstgid = int(tileset_el.get('firstgid', '1')) if tileset_el is not None else 1

    raw      = data_el.text.strip()
    tile_ids = [gid_to_tile_id(int(x), firstgid) for x in raw.split(',') if x.strip()]
```

**Step 3: Run unit tests — expect PASS**

```bash
python3 -m unittest tests.test_tmx_to_c.TestGidToTileId -v
```

Expected: all 6 tests `PASSED`

**Step 4: Run full test suite — existing tests must still pass**

```bash
python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v
```

Expected: all tests `PASSED`

**Step 5: Commit**

```bash
git add tools/tmx_to_c.py tests/test_tmx_to_c.py
git commit -m "fix: strip GID flip flags, handle empty cells, read firstgid in tmx_to_c"
```

---

### Task 3: Add integration tests for flip, empty cell, and non-1 firstgid

**Files:**
- Modify: `tests/test_tmx_to_c.py` (add TMX fixtures + integration test class)

**Step 1: Add TMX fixture strings after `MINIMAL_TMX`**

```python
# 1×1 map: tile 1 with H-flip (GID = 0x80000001 = 2147483649)
# After stripping flags: GID 1, firstgid=1 → tile index 0
HFLIP_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal"
     width="1" height="1" tilewidth="8" tileheight="8">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="1" height="1">
  <data encoding="csv">
2147483649
  </data>
 </layer>
</map>
"""

# 2×1 map: empty cell (GID 0) then tile 1 (GID 1)
# Expected: tile values 0, 0
EMPTY_CELL_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal"
     width="2" height="1" tilewidth="8" tileheight="8">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="2" height="1">
  <data encoding="csv">
0,1
  </data>
 </layer>
</map>
"""

# 2×1 map: firstgid=2 — GIDs 2 and 3 → tile indices 0 and 1
FIRSTGID_2_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal"
     width="2" height="1" tilewidth="8" tileheight="8">
 <tileset firstgid="2" source="track.tsx"/>
 <layer id="1" name="Track" width="2" height="1">
  <data encoding="csv">
2,3
  </data>
 </layer>
</map>
"""
```

**Step 2: Add integration test class**

```python
class TestGidIntegration(unittest.TestCase):

    def _convert(self, tmx_text):
        # Re-use the same _convert helper — extract to module level if preferred,
        # but for now duplicate since unittest doesn't share helpers across classes cleanly.
        with tempfile.NamedTemporaryFile('w', suffix='.tmx', delete=False) as tf:
            tf.write(tmx_text)
            tmx_path = tf.name
        out_path = tmx_path.replace('.tmx', '.c')
        try:
            conv.tmx_to_c(tmx_path, out_path)
            with open(out_path) as f:
                return f.read()
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_hflip_tile_produces_correct_index(self):
        # Flipped tile 1 (GID 0x80000001) with firstgid=1 → tile value 0 in output
        result = self._convert(HFLIP_TMX)
        self.assertIn('/* row  0 */ 0,', result)

    def test_empty_cell_produces_zero_not_underflow(self):
        # GID 0 → 0; must NOT produce -1 or 255
        result = self._convert(EMPTY_CELL_TMX)
        self.assertIn('0,0', result)
        self.assertNotIn('-1', result)
        self.assertNotIn('255', result)

    def test_firstgid_2_offsets_correctly(self):
        # GID 2 → 0, GID 3 → 1
        result = self._convert(FIRSTGID_2_TMX)
        self.assertIn('/* row  0 */ 0,1,', result)
```

**Step 3: Run integration tests**

```bash
python3 -m unittest tests.test_tmx_to_c.TestGidIntegration -v
```

Expected: all 3 tests `PASSED`

**Step 4: Run full suite one more time**

```bash
python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v
```

Expected: all tests `PASSED`

**Step 5: Commit**

```bash
git add tests/test_tmx_to_c.py
git commit -m "test: integration tests for GID flip, empty cell, and firstgid=2"
```

---

### Task 4: Update the tiled-expert skill

**Files:**
- Modify: `.claude/skills/tiled-expert/SKILL.md`

**Step 1: Update "How `tmx_to_c.py` Works" code block (lines ~340-354)**

Replace the code block inside that section:

Old:
```python
raw      = data_el.text.strip()
tile_ids = [int(x) - 1 for x in raw.split(',')]  # 1-based → 0-based
```

New:
```python
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

**Step 2: Add three rows to "Common Conversion Mistakes" table (around line 383)**

Add after the existing rows:

```markdown
| Ignoring GID flip flags | Mask with `& 0x0FFFFFFF` before subtracting `firstgid`; raw H/V/D flip bits corrupt the tile index |
| Hardcoding `- 1` as tile offset | Read `firstgid` from `<tileset firstgid="...">` element; maps may use any firstgid |
| GID 0 underflows to 255 (uint8) | Check `gid == 0` before subtracting; return 0 (empty sentinel matches `track.c`'s `!= 0u`) |
```

**Step 3: Commit**

```bash
git add .claude/skills/tiled-expert/SKILL.md
git commit -m "docs: update tiled-expert skill with corrected tmx_to_c pattern and GID pitfalls"
```

---

### Task 5: Push branch and open PR

**Step 1: Push**

```bash
gh auth setup-git 2>/dev/null; git push -u origin design/tmx-gid-fix
```

**Step 2: Open PR**

```bash
gh pr create \
  --title "fix: harden tmx_to_c.py against silent GID corruption and empty cells" \
  --body "$(cat <<'EOF'
Fixes #41.

## Changes
- Add `gid_to_tile_id(gid, firstgid)` helper that strips flip flags (bits 28–31), handles GID 0 (empty cell → 0), and uses `firstgid` from the `<tileset>` element
- Read `firstgid` from XML instead of hardcoding `- 1`
- New direct unit tests for each case + integration tests with flipped-tile, empty-cell, and firstgid=2 fixtures
- Update tiled-expert skill with corrected code pattern and new pitfall rows

## Test plan
- [ ] `python3 -m unittest discover -s tests -p "test_tmx_to_c.py" -v` — all tests pass
- [ ] Manually verify `python3 tools/tmx_to_c.py assets/maps/track.tmx /tmp/out.c` produces correct output

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

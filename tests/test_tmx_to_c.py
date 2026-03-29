#!/usr/bin/env python3
"""Unit tests for tools/tmx_to_c.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import tmx_to_c as conv
from tmx_to_c import gid_to_tile_id

# 3×2 map: Tiled IDs 1,2,1 / 2,1,2  →  GB values 0,1,0 / 1,0,1
# Includes a "start" object at pixel (88, 720) and a "finish" object at pixel y=8 (row 1).
MINIMAL_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal"
     width="3" height="2" tilewidth="8" tileheight="8"
     nextlayerid="4" nextobjectid="3">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="3" height="2">
  <data encoding="csv">
1,2,1,
2,1,2
  </data>
 </layer>
 <objectgroup id="2" name="start">
  <object id="1" x="88" y="720">
   <point/>
  </object>
 </objectgroup>
 <objectgroup id="3" name="finish">
  <object id="2" x="0" y="8" width="24" height="8"/>
 </objectgroup>
</map>
"""


class TestTmxToC(unittest.TestCase):

    def _convert(self, tmx_text):
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

    def test_generated_header_comment(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('GENERATED', result)
        self.assertIn('do not edit by hand', result)

    def test_subtracts_one_from_tile_ids(self):
        result = self._convert(MINIMAL_TMX)
        # IDs 1,2,1 → 0,1,0 and 2,1,2 → 1,0,1
        self.assertIn('0,1,0', result)
        self.assertIn('1,0,1', result)

    def test_includes_track_header(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('#include "track.h"', result)

    def test_defines_track_map_array(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('track_map[MAP_TILES_H * MAP_TILES_W]', result)

    def test_wrong_encoding_raises(self):
        bad = MINIMAL_TMX.replace('encoding="csv"', 'encoding="base64"')
        with self.assertRaises(ValueError):
            self._convert(bad)

    def test_start_layer_emits_track_start_x(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('track_start_x = 88', result)

    def test_start_layer_emits_track_start_y(self):
        result = self._convert(MINIMAL_TMX)
        self.assertIn('track_start_y = 720', result)

    def test_missing_start_layer_raises(self):
        import re
        no_start = re.sub(
            r'\s*<objectgroup[^>]*name="start".*?</objectgroup>',
            '', MINIMAL_TMX, flags=re.DOTALL
        )
        with self.assertRaises(ValueError):
            self._convert(no_start)


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
 <objectgroup name="start">
  <object id="10" x="0" y="0" width="8" height="8"/>
 </objectgroup>
 <objectgroup name="finish">
  <object id="11" x="0" y="8" width="160" height="8"/>
 </objectgroup>
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
 <objectgroup name="start">
  <object id="10" x="0" y="0" width="8" height="8"/>
 </objectgroup>
 <objectgroup name="finish">
  <object id="11" x="0" y="8" width="160" height="8"/>
 </objectgroup>
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
 <objectgroup name="start">
  <object id="10" x="0" y="0" width="8" height="8"/>
 </objectgroup>
 <objectgroup name="finish">
  <object id="11" x="0" y="8" width="160" height="8"/>
 </objectgroup>
</map>
"""


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
        # GID 0 → 0; must NOT produce tile value -1 or 255 in the data array.
        # Note: the generated output legitimately contains "#pragma bank 255",
        # so we only check the array body (everything after the opening brace).
        result = self._convert(EMPTY_CELL_TMX)
        self.assertIn('0,0', result)
        self.assertNotIn('-1', result)
        # Extract only the array body to avoid matching "#pragma bank 255"
        array_start = result.find('{')
        array_body = result[array_start:] if array_start != -1 else result
        self.assertNotIn('255', array_body)

    def test_firstgid_2_offsets_correctly(self):
        # GID 2 → 0, GID 3 → 1
        result = self._convert(FIRSTGID_2_TMX)
        self.assertIn('/* row  0 */ 0,1,', result)


class TestFinishLineParsing(unittest.TestCase):
    def _make_tmx_with_finish(self, finish_y_px, finish_name='finish'):
        """Return a minimal TMX string with configurable objectgroup name."""
        tile_row = ','.join(['1'] * 20)
        csv_data = ('\n' + tile_row + ',') * 100
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.0"
     orientation="orthogonal" renderorder="right-down"
     width="20" height="100" tilewidth="8" tileheight="8"
     infinite="0" nextlayerid="4" nextobjectid="3">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="20" height="100">
  <data encoding="csv">
{csv_data}
  </data>
 </layer>
 <objectgroup id="2" name="start">
  <object id="1" x="88" y="720" width="8" height="8"/>
 </objectgroup>
 <objectgroup id="3" name="{finish_name}">
  <object id="2" x="0" y="{finish_y_px}" width="160" height="8"/>
 </objectgroup>
</map>"""

    def test_finish_line_y_parsed_correctly(self):
        import tempfile, os
        tmx_content = self._make_tmx_with_finish(40)  # row 5 = 40/8
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmx', delete=False) as f:
            f.write(tmx_content)
            tmx_path = f.name
        out_path = tmx_path.replace('.tmx', '_out.c')
        try:
            from tools.tmx_to_c import tmx_to_c
            tmx_to_c(tmx_path, out_path)
            with open(out_path) as f:
                content = f.read()
            self.assertIn('track_finish_line_y = 5', content)
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_finish_line_y_row_zero(self):
        import tempfile, os
        tmx_content = self._make_tmx_with_finish(0)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmx', delete=False) as f:
            f.write(tmx_content)
            tmx_path = f.name
        out_path = tmx_path.replace('.tmx', '_out.c')
        try:
            from tools.tmx_to_c import tmx_to_c
            tmx_to_c(tmx_path, out_path)
            with open(out_path) as f:
                content = f.read()
            self.assertIn('track_finish_line_y = 0', content)
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_missing_finish_raises(self):
        import tempfile, os
        tmx_content = self._make_tmx_with_finish(40, finish_name='notfinish')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmx', delete=False) as f:
            f.write(tmx_content)
            tmx_path = f.name
        out_path = tmx_path.replace('.tmx', '_out.c')
        try:
            from tools.tmx_to_c import tmx_to_c
            with self.assertRaises(ValueError):
                tmx_to_c(tmx_path, out_path)
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


class TestTmxToCPrefix(unittest.TestCase):

    def _convert_prefix(self, tmx_text, prefix):
        import tempfile, os
        with tempfile.NamedTemporaryFile('w', suffix='.tmx', delete=False) as tf:
            tf.write(tmx_text)
            tmx_path = tf.name
        out_path = tmx_path.replace('.tmx', '.c')
        try:
            conv.tmx_to_c(tmx_path, out_path, prefix=prefix)
            with open(out_path) as f:
                return f.read()
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_prefix_renames_symbols(self):
        src = self._convert_prefix(MINIMAL_TMX, prefix='track2')
        self.assertIn('const uint8_t track2_map[', src)
        self.assertIn('const int16_t track2_start_x', src)
        self.assertIn('const int16_t track2_start_y', src)
        self.assertIn('const uint8_t track2_finish_line_y', src)
        # Default "track_" prefix must NOT appear
        self.assertNotIn('const uint8_t track_map[', src)

    def test_default_prefix_is_track(self):
        src = self._convert_prefix(MINIMAL_TMX, prefix='track')
        self.assertIn('const uint8_t track_map[', src)


if __name__ == '__main__':
    unittest.main()

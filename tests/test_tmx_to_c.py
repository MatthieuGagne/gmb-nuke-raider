#!/usr/bin/env python3
"""Unit tests for tools/tmx_to_c.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import tmx_to_c as conv

# 3×2 map: Tiled IDs 1,2,1 / 2,1,2  →  GB values 0,1,0 / 1,0,1
# Includes a "start" object at pixel (88, 720).
MINIMAL_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal"
     width="3" height="2" tilewidth="8" tileheight="8"
     nextlayerid="3" nextobjectid="2">
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


if __name__ == '__main__':
    unittest.main()

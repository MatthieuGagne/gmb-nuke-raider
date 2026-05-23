#!/usr/bin/env python3
"""Unit tests for tools/emit_manifest.py"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


class TestBFS(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def test_bfs_direct_right(self):
        em = self._em()
        path = em.bfs([1, 1, 1], 3, 1, 0, 0, 2, 0)
        self.assertEqual(path, ['right', 'right'])

    def test_bfs_direct_left(self):
        em = self._em()
        path = em.bfs([1, 1, 1], 3, 1, 2, 0, 0, 0)
        self.assertEqual(path, ['left', 'left'])

    def test_bfs_blocked_returns_none(self):
        em = self._em()
        path = em.bfs([1, 0, 1], 3, 1, 0, 0, 2, 0)
        self.assertIsNone(path)

    def test_bfs_around_corner(self):
        em = self._em()
        # 2x2: (0,0)=road, (1,0)=wall, (0,1)=road, (1,1)=road
        path = em.bfs([1, 0, 1, 1], 2, 2, 0, 0, 1, 1)
        self.assertEqual(path, ['down', 'right'])

    def test_bfs_same_tile_returns_empty(self):
        em = self._em()
        path = em.bfs([1], 1, 1, 0, 0, 0, 0)
        self.assertEqual(path, [])

    def test_bfs_direct_down(self):
        em = self._em()
        # 1x3 vertical grid
        path = em.bfs([1, 1, 1], 1, 3, 0, 0, 0, 2)
        self.assertEqual(path, ['down', 'down'])


class TestParseNoi(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def _write_noi(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.noi', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_wram_symbol_extracted(self):
        em = self._em()
        path = self._write_noi("DEF _cam_scx_shadow 0xC0B6\n")
        result = em.parse_noi(path)
        os.unlink(path)
        self.assertEqual(result.get('_cam_scx_shadow'), '0xc0b6')

    def test_rom_address_ignored(self):
        em = self._em()
        path = self._write_noi("DEF _some_func 0x04567\n")
        result = em.parse_noi(path)
        os.unlink(path)
        self.assertNotIn('_some_func', result)

    def test_missing_file_returns_empty(self):
        em = self._em()
        result = em.parse_noi('/tmp/nonexistent_emit_manifest_test.noi')
        self.assertEqual(result, {})

    def test_multiple_symbols(self):
        em = self._em()
        content = "DEF _px 0xC123\nDEF _hp 0xC124\nDEF _func 0x01234\n"
        path = self._write_noi(content)
        result = em.parse_noi(path)
        os.unlink(path)
        self.assertIn('_px', result)
        self.assertIn('_hp', result)
        self.assertNotIn('_func', result)


class TestParseTsx(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    _TSX = '''<?xml version="1.0"?>
<tileset name="track" tilewidth="8" tileheight="8" tilecount="3" columns="3">
 <tile id="0"><properties><property name="type" value="TILE_WALL"/></properties></tile>
 <tile id="1"><properties><property name="type" value="TILE_ROAD"/></properties></tile>
 <tile id="2"><properties><property name="type" value="TILE_SAND"/></properties></tile>
</tileset>'''

    def test_tile_types_parsed(self):
        em = self._em()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tsx', delete=False) as f:
            f.write(self._TSX)
            path = f.name
        result = em.parse_tsx_tile_types(path)
        os.unlink(path)
        self.assertEqual(result[0], 'TILE_WALL')
        self.assertEqual(result[1], 'TILE_ROAD')
        self.assertEqual(result[2], 'TILE_SAND')


class TestParseDefine(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def _write_c(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_parse_integer_with_u_suffix(self):
        em = self._em()
        path = self._write_c("#define TRAVEL_FRAMES_PER_TILE 4u\n")
        self.assertEqual(em.parse_define(path, 'TRAVEL_FRAMES_PER_TILE'), 4)
        os.unlink(path)

    def test_parse_with_inline_comment(self):
        em = self._em()
        path = self._write_c("#define PR_CONFIG_ROWS 4u   /* rows 0-3 */\n")
        self.assertEqual(em.parse_define(path, 'PR_CONFIG_ROWS'), 4)
        os.unlink(path)

    def test_parse_missing_returns_none(self):
        em = self._em()
        path = self._write_c("/* no define */\n")
        self.assertIsNone(em.parse_define(path, 'MISSING'))
        os.unlink(path)

    def test_parse_does_not_match_prefix(self):
        em = self._em()
        path = self._write_c("#define PR_CONFIG_ROWS_EXTRA 99u\n")
        self.assertIsNone(em.parse_define(path, 'PR_CONFIG_ROWS'))
        os.unlink(path)


if __name__ == '__main__':
    unittest.main()

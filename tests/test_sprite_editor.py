import unittest
import tempfile
import os
import struct

from tools.sprite_editor.model import Palette, TileSheet


class TestPalette(unittest.TestCase):

    def test_default_has_4_colors(self):
        p = Palette()
        self.assertEqual(len(p.colors), 4)

    def test_set_color_stores_5bit_rgb(self):
        p = Palette()
        p.set_color(1, 31, 0, 15)
        self.assertEqual(p.colors[1], (31, 0, 15))

    def test_get_color_rgb888_max_red(self):
        p = Palette()
        p.set_color(0, 31, 0, 0)
        r, g, b = p.get_color_rgb888(0)
        self.assertEqual(r, 255)
        self.assertEqual(g, 0)
        self.assertEqual(b, 0)

    def test_get_color_rgb888_zero_is_black(self):
        p = Palette()
        p.set_color(0, 0, 0, 0)
        self.assertEqual(p.get_color_rgb888(0), (0, 0, 0))

    def test_get_color_rgb888_mid_value(self):
        # 20 * 255 // 31 = 164
        p = Palette()
        p.set_color(2, 20, 10, 5)
        r, g, b = p.get_color_rgb888(2)
        self.assertEqual(r, (20 * 255) // 31)
        self.assertEqual(g, (10 * 255) // 31)
        self.assertEqual(b, (5 * 255) // 31)

    def test_palette_save_creates_file(self):
        p = Palette()
        p.set_color(1, 20, 10, 5)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'test.pal')
            p.save(path)
            self.assertTrue(os.path.exists(path))

    def test_palette_roundtrip(self):
        p = Palette()
        p.set_color(0, 1, 2, 3)
        p.set_color(1, 20, 10, 5)
        p.set_color(2, 0, 31, 15)
        p.set_color(3, 31, 31, 31)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'test.pal')
            p.save(path)
            p2 = Palette()
            p2.load(path)
        self.assertEqual(p2.colors[0], (1, 2, 3))
        self.assertEqual(p2.colors[1], (20, 10, 5))
        self.assertEqual(p2.colors[2], (0, 31, 15))
        self.assertEqual(p2.colors[3], (31, 31, 31))


class TestTileSheet(unittest.TestCase):

    def test_initial_all_pixels_zero(self):
        ts = TileSheet()
        for y in range(TileSheet.HEIGHT):
            for x in range(TileSheet.WIDTH):
                self.assertEqual(ts.get_pixel(x, y), 0)

    def test_set_get_pixel(self):
        ts = TileSheet()
        ts.set_pixel(5, 3, 2)
        self.assertEqual(ts.get_pixel(5, 3), 2)

    def test_set_pixel_marks_dirty(self):
        ts = TileSheet()
        self.assertFalse(ts.dirty)
        ts.set_pixel(0, 0, 1)
        self.assertTrue(ts.dirty)

    def test_clear_resets_pixels(self):
        ts = TileSheet()
        ts.set_pixel(0, 0, 3)
        ts.clear()
        self.assertEqual(ts.get_pixel(0, 0), 0)

    def test_clear_clears_dirty_flag(self):
        ts = TileSheet()
        ts.set_pixel(0, 0, 1)
        ts.clear()
        self.assertFalse(ts.dirty)

    def test_dimensions(self):
        self.assertEqual(TileSheet.WIDTH, 32)
        self.assertEqual(TileSheet.HEIGHT, 32)

    def test_save_creates_file(self):
        ts = TileSheet()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'out.png')
            ts.save_png(path)
            self.assertTrue(os.path.exists(path))

    def test_save_writes_png_signature(self):
        ts = TileSheet()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'out.png')
            ts.save_png(path)
            with open(path, 'rb') as f:
                sig = f.read(8)
        self.assertEqual(sig, b'\x89PNG\r\n\x1a\n')

    def test_save_clears_dirty_flag(self):
        ts = TileSheet()
        ts.set_pixel(0, 0, 1)
        self.assertTrue(ts.dirty)
        with tempfile.TemporaryDirectory() as d:
            ts.save_png(os.path.join(d, 'out.png'))
        self.assertFalse(ts.dirty)

    def test_save_png_is_valid_indexed_png(self):
        """Verify IHDR declares color type 3 (indexed), bit depth 2."""
        ts = TileSheet()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'out.png')
            ts.save_png(path)
            with open(path, 'rb') as f:
                data = f.read()
        # Skip signature (8) + IHDR length (4) + type (4)
        ihdr_data = data[16:29]  # 13 bytes of IHDR
        width, height, bit_depth, color_type = struct.unpack('>IIBB', ihdr_data[:10])
        self.assertEqual(width, 32)
        self.assertEqual(height, 32)
        self.assertEqual(bit_depth, 2)
        self.assertEqual(color_type, 3)


    def test_png_roundtrip_pixels(self):
        ts = TileSheet()
        ts.set_pixel(0, 0, 1)
        ts.set_pixel(31, 31, 3)
        ts.set_pixel(15, 8, 2)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'rt.png')
            ts.save_png(path)
            ts2 = TileSheet()
            ts2.load_png(path)
        self.assertEqual(ts2.get_pixel(0, 0), 1)
        self.assertEqual(ts2.get_pixel(31, 31), 3)
        self.assertEqual(ts2.get_pixel(15, 8), 2)
        self.assertEqual(ts2.get_pixel(1, 0), 0)  # unset pixel stays 0

    def test_png_roundtrip_palette(self):
        ts = TileSheet()
        ts.palette.set_color(1, 20, 10, 5)
        ts.palette.set_color(3, 31, 31, 31)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'rt.png')
            ts.save_png(path)
            ts2 = TileSheet()
            ts2.load_png(path)
        self.assertEqual(ts2.palette.colors[1], (20, 10, 5))
        self.assertEqual(ts2.palette.colors[3], (31, 31, 31))

    def test_load_clears_dirty_flag(self):
        ts = TileSheet()
        ts.set_pixel(0, 0, 2)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'rt.png')
            ts.save_png(path)
            ts2 = TileSheet()
            ts2.set_pixel(0, 0, 1)  # make ts2 dirty
            ts2.load_png(path)
        self.assertFalse(ts2.dirty)


if __name__ == '__main__':
    unittest.main()

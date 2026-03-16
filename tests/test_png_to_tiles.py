"""Tests for tools/png_to_tiles.py"""
import io
import struct
import tempfile
import unittest
import zlib

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.png_to_tiles import load_png_pixels, encode_2bpp, png_to_c


# ── Minimal PNG helpers ────────────────────────────────────────────────────

def _chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)


def _make_indexed_png(width, height, pixel_indices):
    """Create a 2-bit indexed PNG. pixel_indices: flat list of 0-3."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 2, 3, 0, 0, 0))
    plte = _chunk(b'PLTE', bytes([255,255,255, 170,170,170, 85,85,85, 0,0,0]))
    raw  = b''
    for row in range(height):
        raw += b'\x00'              # filter type None
        for col in range(0, width, 4):
            byte = 0
            for k in range(4):
                byte = (byte << 2) | (pixel_indices[row * width + col + k] if col + k < width else 0)
            raw += bytes([byte])
    idat = _chunk(b'IDAT', zlib.compress(raw))
    iend = _chunk(b'IEND', b'')
    return sig + ihdr + plte + idat + iend


def _make_rgb_png(width, height, pixels_rgb):
    """Create an 8-bit RGB PNG. pixels_rgb: flat list of (R,G,B)."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw  = b''
    for row in range(height):
        raw += b'\x00'
        for col in range(width):
            r, g, b = pixels_rgb[row * width + col]
            raw += bytes([r, g, b])
    idat = _chunk(b'IDAT', zlib.compress(raw))
    iend = _chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


# ── Tests ──────────────────────────────────────────────────────────────────

class TestLoadPngPixels(unittest.TestCase):

    def test_indexed_single_tile_all_index2(self):
        """8×8 indexed PNG with all pixels=2 → 64 pixels each equal to 2."""
        data = _make_indexed_png(8, 8, [2] * 64)
        pixels, w, h = load_png_pixels(data)
        self.assertEqual(w, 8)
        self.assertEqual(h, 8)
        self.assertEqual(pixels, [2] * 64)

    def test_rgb_off_track_color_maps_to_index2(self):
        """OFF_TRACK RGB (34,85,34) → index 2 (luminance≈64)."""
        data = _make_rgb_png(8, 8, [(34, 85, 34)] * 64)
        pixels, w, h = load_png_pixels(data)
        self.assertEqual(pixels, [2] * 64)

    def test_rgb_road_color_maps_to_index1(self):
        """ROAD RGB (136,136,136) → index 1 (luminance=136)."""
        data = _make_rgb_png(8, 8, [(136, 136, 136)] * 64)
        pixels, w, h = load_png_pixels(data)
        self.assertEqual(pixels, [1] * 64)

    def test_too_many_colors_raises(self):
        """RGB PNG with 5 distinct luminance values raises ValueError."""
        # Five grey shades with distinct luminance after quantisation
        colors = [(0,0,0), (50,50,50), (100,100,100), (150,150,150), (220,220,220)]
        flat = [colors[i % 5] for i in range(8 * 8)]
        data = _make_rgb_png(8, 8, flat)
        with self.assertRaises(ValueError):
            load_png_pixels(data)


class TestEncode2bpp(unittest.TestCase):

    def test_single_tile_all_index2(self):
        """8×8 pixels all=2 → 16 bytes: (0x00,0xFF)×8."""
        pixels = [2] * 64
        result = encode_2bpp(pixels, 8, 8)
        expected = bytes([0x00, 0xFF] * 8)
        self.assertEqual(result, expected)

    def test_single_tile_all_index1(self):
        """8×8 pixels all=1 → 16 bytes: (0xFF,0x00)×8."""
        pixels = [1] * 64
        result = encode_2bpp(pixels, 8, 8)
        expected = bytes([0xFF, 0x00] * 8)
        self.assertEqual(result, expected)

    def test_two_tile_strip(self):
        """16×8 strip: left tile all-index2, right tile all-index1."""
        pixels = []
        for _ in range(8):
            pixels += [2] * 8 + [1] * 8
        result = encode_2bpp(pixels, 16, 8)
        tile0 = bytes([0x00, 0xFF] * 8)
        tile1 = bytes([0xFF, 0x00] * 8)
        self.assertEqual(result, tile0 + tile1)


class TestPngToC(unittest.TestCase):

    def test_c_file_contains_array_name(self):
        """Generated C source contains the requested array name."""
        data = _make_indexed_png(8, 8, [2] * 64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'my_tiles', bank=255)
        with open(c_path) as f:
            src = f.read()
        self.assertIn('my_tiles[]', src)
        self.assertIn('my_tiles_count', src)
        self.assertIn('0x00', src)

    def test_count_symbol_value(self):
        """16×8 PNG (2 tiles) produces count symbol = 2."""
        data = _make_indexed_png(16, 8, [1] * 128)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'tiles', bank=255)
        with open(c_path) as f:
            src = f.read()
        self.assertIn('tiles_count = 2', src)

    def test_bank_ref_uses_volatile_at_255(self):
        """volatile __at(255) emitted for autobanked files — no BANKREF function."""
        data = _make_indexed_png(8, 8, [1] * 64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'my_tiles', bank=255)
        with open(c_path) as f:
            src = f.read()
        self.assertIn('volatile __at(255) uint8_t __bank_my_tiles;', src)
        self.assertNotIn('BANKREF(my_tiles)', src)
        self.assertNotIn('__func_my_tiles', src)

    def test_bank_ref_uses_volatile_at_explicit_bank(self):
        """volatile __at(N) emitted for explicit bank N — no BANKREF function."""
        data = _make_indexed_png(8, 8, [1] * 64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'my_tiles', bank=2)
        with open(c_path) as f:
            src = f.read()
        self.assertIn('volatile __at(2) uint8_t __bank_my_tiles;', src)
        self.assertNotIn('BANKREF(my_tiles)', src)


if __name__ == '__main__':
    unittest.main()

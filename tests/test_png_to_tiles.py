"""Tests for tools/png_to_tiles.py"""
import io
import struct
import tempfile
import unittest
import zlib

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.png_to_tiles import load_png_pixels, encode_2bpp, png_to_c, apply_transform, rasterize_polygon


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

    def test_bank_ref_uses_bankref_for_autobank(self):
        """BANKREF(sym) emitted for --bank 255 (autobank) — bankpack resolves real bank at link time."""
        data = _make_indexed_png(8, 8, [1] * 64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
            pf.write(data)
            png_path = pf.name
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
            c_path = cf.name
        png_to_c(png_path, c_path, 'my_tiles', bank=255)
        with open(c_path) as f:
            src = f.read()
        self.assertIn('BANKREF(my_tiles)', src)
        self.assertNotIn('volatile __at(255)', src)

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

    def test_bank_ref_uses_volatile_at_bank2(self):
        """volatile __at(2) still emitted for explicit --bank 2."""
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
        self.assertNotIn('BANKREF', src)


class TestApplyTransform(unittest.TestCase):

    def make_8x8_gradient(self):
        """Returns an 8×8 pixel grid with unique values for each cell."""
        return [[r * 8 + c for c in range(8)] for r in range(8)]

    def test_identity(self):
        """flags=0 returns the original pixel grid unchanged."""
        pixels = self.make_8x8_gradient()
        self.assertEqual(apply_transform(pixels, 0), pixels)

    def test_h_flip(self):
        """flags=4 (H-flip) mirrors columns left↔right."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 4)
        self.assertEqual(result[0][0], pixels[0][7])
        self.assertEqual(result[0][7], pixels[0][0])

    def test_v_flip(self):
        """flags=2 (V-flip) mirrors rows top↔bottom."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 2)
        self.assertEqual(result[0][0], pixels[7][0])
        self.assertEqual(result[7][0], pixels[0][0])

    def test_180(self):
        """flags=6 (H+V) is equivalent to 180° rotation."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 6)
        self.assertEqual(result[0][0], pixels[7][7])
        self.assertEqual(result[7][7], pixels[0][0])

    def test_transpose(self):
        """flags=1 (D) swaps rows and columns."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 1)
        self.assertTrue(all(result[r][c] == pixels[c][r] for r in range(8) for c in range(8)))

    def test_90cw(self):
        """flags=5 (D+H) is 90° CW rotation."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 5)
        for r in range(8):
            for c in range(8):
                self.assertEqual(result[r][c], pixels[7-c][r])

    def test_270cw(self):
        """flags=3 (D+V) is 270° CW rotation."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 3)
        for r in range(8):
            for c in range(8):
                self.assertEqual(result[r][c], pixels[c][7-r])

    def test_anti_transpose(self):
        """flags=7 (D+H+V) is anti-transpose."""
        pixels = self.make_8x8_gradient()
        result = apply_transform(pixels, 7)
        for r in range(8):
            for c in range(8):
                self.assertEqual(result[r][c], pixels[7-c][7-r])


class TestRasterizePolygon(unittest.TestCase):

    def test_full_tile_polygon_is_all_passable(self):
        """Polygon covering the whole 8×8 tile → all rows 0xFF."""
        poly = [(0,0),(8,0),(8,8),(0,8)]
        rows = rasterize_polygon(poly)
        self.assertEqual(rows, [0xFF]*8)

    def test_empty_polygon_is_all_solid(self):
        """Empty polygon list → all rows 0x00 (no inside pixels)."""
        rows = rasterize_polygon([])
        self.assertEqual(rows, [0x00]*8)

    def test_lower_left_triangle(self):
        """Lower-left triangle: poly=(0,0),(8.001,8),(0,8).
        Pixel (ox, oy) is passable if ox <= oy (below-left of diagonal).
        LSB = leftmost pixel (ox=0), bit ox set means passable.
        Row oy: passable columns 0..oy → mask = (1<<(oy+1))-1
        Note: diagonal is shifted by 0.001 so pixel centers on y=x are clearly inside."""
        poly = [(0,0),(8.001,8),(0,8)]
        rows = rasterize_polygon(poly)
        for oy in range(8):
            expected = (1 << (oy + 1)) - 1
            self.assertEqual(rows[oy], expected,
                             f"row {oy}: expected 0x{expected:02X} got 0x{rows[oy]:02X}")

    def test_upper_right_triangle(self):
        """Upper-right triangle: passable columns ox >= (7-oy) per row.
        Bit ox set means passable. Row oy: passable cols (7-oy)..7.
        Triangle above the anti-diagonal x+y=8: vertices (8,0),(8,8),(0,8)."""
        poly = [(8,0),(8,8),(0,8)]
        rows = rasterize_polygon(poly)
        for oy in range(8):
            passable_start = 7 - oy
            expected = 0
            for ox in range(passable_start, 8):
                expected |= (1 << ox)
            self.assertEqual(rows[oy], expected,
                             f"row {oy}: expected 0x{expected:02X} got 0x{rows[oy]:02X}")

    def test_single_pixel_center_inside(self):
        """Tiny square around pixel (3,4) center (3.5,4.5) → only bit 3 of row 4 set."""
        poly = [(3,4),(4,4),(4,5),(3,5)]
        rows = rasterize_polygon(poly)
        for oy in range(8):
            if oy == 4:
                self.assertEqual(rows[oy], 1 << 3)
            else:
                self.assertEqual(rows[oy], 0x00)


class TestMetaHeaderCollisionMask(unittest.TestCase):
    """Integration: png_to_c emits track_collision_mask in meta header."""

    def _make_minimal_tsx(self, path):
        """Write a minimal track.tsx with 1 TILE_WALL and 1 TILE_ROAD tile."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.8" name="track" tilewidth="8" tileheight="8" tilecount="2" columns="2">
 <image source="tileset.png" width="16" height="8"/>
 <tile id="0">
  <properties><property name="type" value="TILE_WALL"/></properties>
 </tile>
 <tile id="1">
  <properties><property name="type" value="TILE_ROAD"/></properties>
 </tile>
</tileset>'''
        with open(path, 'w') as f:
            f.write(content)

    def _make_tsx_with_objectgroup(self, path):
        """TSX with tile 0 having a full-tile objectgroup polygon (passable)."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.8" name="track" tilewidth="8" tileheight="8" tilecount="2" columns="2">
 <image source="tileset.png" width="16" height="8"/>
 <tile id="0">
  <properties><property name="type" value="TILE_WALL"/></properties>
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="0">
    <polygon points="0,0 8,0 8,8 0,8"/>
   </object>
  </objectgroup>
 </tile>
 <tile id="1">
  <properties><property name="type" value="TILE_ROAD"/></properties>
 </tile>
</tileset>'''
        with open(path, 'w') as f:
            f.write(content)

    def test_wall_no_objectgroup_produces_all_zero_mask(self):
        """TILE_WALL with no objectgroup → all 0x00 mask rows (R4)."""
        png_data = _make_indexed_png(16, 8, [0]*128)
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            png_path = os.path.join(d, 't.png')
            tsx_path = os.path.join(d, 't.tsx')
            c_path   = os.path.join(d, 't.c')
            id_path  = os.path.join(d, 'id.json')
            hdr_path = os.path.join(d, 'meta.h')
            with open(png_path, 'wb') as f: f.write(png_data)
            self._make_minimal_tsx(tsx_path)
            # rotation manifest: no rotations
            mf_path = os.path.join(d, 'mf.json')
            with open(mf_path, 'w') as f: json.dump({"rotations":{}}, f)
            png_to_c(png_path, c_path, 'tiles', bank=255,
                     rotation_manifest=mf_path, tsx_path=tsx_path,
                     id_map_out=id_path, meta_header_out=hdr_path)
            with open(hdr_path) as f: src = f.read()
        # C index 0 = Tiled tile 0 (TILE_WALL) → expect 8 zero bytes
        self.assertIn('track_collision_mask', src)
        # All 8 mask bytes for index 0 must be 0x00
        self.assertIn('0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00', src)

    def test_road_no_objectgroup_produces_all_ff_mask(self):
        """TILE_ROAD with no objectgroup → all 0xFF mask rows (R4)."""
        png_data = _make_indexed_png(16, 8, [0]*128)
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            png_path = os.path.join(d, 't.png')
            tsx_path = os.path.join(d, 't.tsx')
            c_path   = os.path.join(d, 't.c')
            id_path  = os.path.join(d, 'id.json')
            hdr_path = os.path.join(d, 'meta.h')
            with open(png_path, 'wb') as f: f.write(png_data)
            self._make_minimal_tsx(tsx_path)
            mf_path = os.path.join(d, 'mf.json')
            with open(mf_path, 'w') as f: json.dump({"rotations":{}}, f)
            png_to_c(png_path, c_path, 'tiles', bank=255,
                     rotation_manifest=mf_path, tsx_path=tsx_path,
                     id_map_out=id_path, meta_header_out=hdr_path)
            with open(hdr_path) as f: src = f.read()
        # C index 1 = Tiled tile 1 (TILE_ROAD) → expect 8 0xFF bytes
        self.assertIn('0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF', src)

    def test_wall_with_full_objectgroup_produces_all_ff_mask(self):
        """TILE_WALL with full-tile polygon → rasterized as all 0xFF (polygon overrides type default)."""
        png_data = _make_indexed_png(16, 8, [0]*128)
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            png_path = os.path.join(d, 't.png')
            tsx_path = os.path.join(d, 't.tsx')
            c_path   = os.path.join(d, 't.c')
            id_path  = os.path.join(d, 'id.json')
            hdr_path = os.path.join(d, 'meta.h')
            with open(png_path, 'wb') as f: f.write(png_data)
            self._make_tsx_with_objectgroup(tsx_path)
            mf_path = os.path.join(d, 'mf.json')
            with open(mf_path, 'w') as f: json.dump({"rotations":{}}, f)
            png_to_c(png_path, c_path, 'tiles', bank=255,
                     rotation_manifest=mf_path, tsx_path=tsx_path,
                     id_map_out=id_path, meta_header_out=hdr_path)
            with open(hdr_path) as f: src = f.read()
        self.assertIn('0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF', src)


if __name__ == '__main__':
    unittest.main()

import struct
import zlib


_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack('>I', len(data))
    crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


class Palette:
    """4-color CGB palette stored as 5-bit RGB tuples."""

    def __init__(self):
        # Default: black, dark-grey, light-grey, white (5-bit)
        self.colors = [(0, 0, 0), (10, 10, 10), (21, 21, 21), (31, 31, 31)]

    def set_color(self, index, r5, g5, b5):
        """Set palette entry `index` to 5-bit RGB values (0–31 each)."""
        assert 0 <= index < 4
        assert all(0 <= c <= 31 for c in (r5, g5, b5))
        self.colors[index] = (r5, g5, b5)

    def get_color_rgb888(self, index):
        """Return (r, g, b) in 0–255 range for the given palette index."""
        r5, g5, b5 = self.colors[index]
        return (
            (r5 * 255) // 31,
            (g5 * 255) // 31,
            (b5 * 255) // 31,
        )


class TileSheet:
    """4×4 grid of 8×8 tiles — 32×32 pixels total, 4-color indexed."""

    COLS = 4
    ROWS = 4
    TILE_SIZE = 8
    WIDTH = COLS * TILE_SIZE   # 32
    HEIGHT = ROWS * TILE_SIZE  # 32

    def __init__(self):
        self.palette = Palette()
        self.pixels = [[0] * self.WIDTH for _ in range(self.HEIGHT)]
        self.dirty = False

    def set_pixel(self, x, y, color_index):
        """Paint pixel (x, y) with palette index 0–3."""
        self.pixels[y][x] = color_index
        self.dirty = True

    def get_pixel(self, x, y):
        return self.pixels[y][x]

    def clear(self):
        """Reset all pixels to index 0 and clear dirty flag."""
        self.pixels = [[0] * self.WIDTH for _ in range(self.HEIGHT)]
        self.dirty = False

    def save_png(self, path):
        """Write a 2-bit indexed PNG (color type 3) to `path`."""
        # IHDR: width=32, height=32, bit_depth=2, color_type=3
        ihdr_data = struct.pack('>IIBBBBB', 32, 32, 2, 3, 0, 0, 0)
        ihdr = _make_chunk(b'IHDR', ihdr_data)

        # PLTE: 4 × RGB888
        plte_data = b''
        for r5, g5, b5 in self.palette.colors:
            plte_data += bytes([
                (r5 * 255) // 31,
                (g5 * 255) // 31,
                (b5 * 255) // 31,
            ])
        plte = _make_chunk(b'PLTE', plte_data)

        # tRNS: index 0 transparent, rest opaque
        trns = _make_chunk(b'tRNS', bytes([0, 255, 255, 255]))

        # IDAT: pack 4 pixels per byte (2 bpp), prepend filter byte 0 per row
        raw = b''
        for y in range(self.HEIGHT):
            raw += b'\x00'  # filter type None
            for x in range(0, self.WIDTH, 4):
                byte = (
                    (self.pixels[y][x]     << 6) |
                    (self.pixels[y][x + 1] << 4) |
                    (self.pixels[y][x + 2] << 2) |
                     self.pixels[y][x + 3]
                )
                raw += bytes([byte])
        idat = _make_chunk(b'IDAT', zlib.compress(raw))

        iend = _make_chunk(b'IEND', b'')

        with open(path, 'wb') as f:
            f.write(_PNG_SIGNATURE + ihdr + plte + trns + idat + iend)
        self.dirty = False

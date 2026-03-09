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

    def save(self, path):
        """Write palette to a plain-text .pal file (4 lines of 'r5 g5 b5')."""
        with open(path, 'w') as f:
            for r5, g5, b5 in self.colors:
                f.write(f'{r5} {g5} {b5}\n')

    def load(self, path):
        """Load palette from a plain-text .pal file."""
        with open(path, 'r') as f:
            for i, line in enumerate(f):
                if i >= 4:
                    break
                r5, g5, b5 = (int(v) for v in line.split())
                self.set_color(i, r5, g5, b5)


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

    def load_png(self, path):
        """Load a 2-bit indexed PNG from `path`, restoring pixels and palette."""
        with open(path, 'rb') as f:
            data = f.read()

        pos = 8  # skip PNG signature
        plte_colors = None
        idat_raw = b''

        while pos < len(data):
            length = struct.unpack('>I', data[pos:pos + 4])[0]
            chunk_type = data[pos + 4:pos + 8]
            chunk_data = data[pos + 8:pos + 8 + length]
            pos += 12 + length  # length(4) + type(4) + data(N) + crc(4)

            if chunk_type == b'PLTE':
                plte_colors = []
                for i in range(0, len(chunk_data), 3):
                    r8, g8, b8 = chunk_data[i], chunk_data[i + 1], chunk_data[i + 2]
                    # Convert RGB888 → 5-bit (round-trip inverse of save)
                    r5 = (r8 * 31 + 127) // 255
                    g5 = (g8 * 31 + 127) // 255
                    b5 = (b8 * 31 + 127) // 255
                    plte_colors.append((r5, g5, b5))
            elif chunk_type == b'IDAT':
                idat_raw += chunk_data
            elif chunk_type == b'IEND':
                break

        if plte_colors:
            for i, (r5, g5, b5) in enumerate(plte_colors[:4]):
                self.palette.set_color(i, r5, g5, b5)

        # Decompress and unpack 2-bpp pixels
        raw = zlib.decompress(idat_raw)
        row_bytes = 1 + self.WIDTH // 4  # filter byte + 8 data bytes
        for y in range(self.HEIGHT):
            row_start = y * row_bytes + 1  # +1 to skip filter byte
            for bx in range(self.WIDTH // 4):
                byte = raw[row_start + bx]
                x = bx * 4
                self.pixels[y][x]     = (byte >> 6) & 3
                self.pixels[y][x + 1] = (byte >> 4) & 3
                self.pixels[y][x + 2] = (byte >> 2) & 3
                self.pixels[y][x + 3] =  byte        & 3

        self.dirty = False

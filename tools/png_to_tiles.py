#!/usr/bin/env python3
"""PNG tileset → GB 2bpp C array converter.

Usage:
    python3 tools/png_to_tiles.py <tileset.png> <out.c> <array_name>

Reads a PNG tileset (one or more 8×8 tiles, left-to-right strip).
Writes a C source file defining:
    const uint8_t <array_name>[];        -- 2bpp tile data
    const uint8_t <array_name>_count;    -- number of tiles

Supported PNG formats:
    - Color type 3 (indexed), bit depth 2: pixel index used directly (0–3).
    - Color type 3 (indexed), bit depth 8: pixel index used directly (0–3).
    - Color type 2 (RGB), bit depth 8: luminance quantised to GB index 0–3.

Rejects PNGs with more than 4 distinct colour values.
"""
import struct
import sys
import zlib


def _parse_chunks(data):
    """Yield (chunk_type, chunk_data) for each PNG chunk."""
    pos = 8  # skip signature
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        ctype  = data[pos + 4:pos + 8]
        cdata  = data[pos + 8:pos + 8 + length]
        pos   += 12 + length
        yield ctype, cdata
        if ctype == b'IEND':
            break


def _lum_to_index(r, g, b):
    """Convert RGB888 to GB palette index 0–3 (0=white, 3=black)."""
    L = (299 * r + 587 * g + 114 * b + 500) // 1000
    return min(3, max(0, round((255 - L) / 85)))


def load_png_pixels(data):
    """Parse PNG bytes and return (pixel_list, width, height).

    pixel_list: flat list of GB palette indices (0–3), row-major.
    Raises ValueError if PNG has >4 distinct colour values.
    """
    ihdr = None
    plte = None
    idat = b''

    for ctype, cdata in _parse_chunks(data):
        if ctype == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', cdata)
        elif ctype == b'PLTE':
            plte = cdata
        elif ctype == b'IDAT':
            idat += cdata

    width, height, bit_depth, color_type = ihdr[0], ihdr[1], ihdr[2], ihdr[3]
    raw = zlib.decompress(idat)

    pixels = []

    if color_type == 3 and bit_depth == 2:
        # 2-bit indexed: 4 pixels per byte, 2 bits each (MSB first)
        bytes_per_row = (width + 3) // 4  # rounded up
        # Account for filter byte per row
        row_stride = 1 + bytes_per_row
        for y in range(height):
            row_start = y * row_stride + 1  # +1 skip filter byte
            col = 0
            for bx in range(bytes_per_row):
                byte = raw[row_start + bx]
                for shift in (6, 4, 2, 0):
                    if col < width:
                        pixels.append((byte >> shift) & 3)
                        col += 1

    elif color_type == 3 and bit_depth == 8:
        # 8-bit indexed: 1 byte per pixel, value is the palette index directly
        row_stride = 1 + width
        for y in range(height):
            row_start = y * row_stride + 1  # +1 skip filter byte
            for x in range(width):
                idx = raw[row_start + x]
                if idx > 3:
                    raise ValueError(
                        f"Indexed PNG has palette index {idx} at ({x},{y}) — max is 3. "
                        "Reduce palette to 4 colours."
                    )
                pixels.append(idx)

    elif color_type == 2 and bit_depth == 8:
        # 8-bit RGB: 3 bytes per pixel
        row_stride = 1 + width * 3
        lum_set = set()
        rgb_rows = []
        for y in range(height):
            row_start = y * row_stride + 1
            row = []
            for x in range(width):
                off = row_start + x * 3
                r, g, b = raw[off], raw[off + 1], raw[off + 2]
                lum = (299 * r + 587 * g + 114 * b + 500) // 1000
                lum_set.add(lum)
                row.append((r, g, b))
            rgb_rows.append(row)
        if len(lum_set) > 4:
            raise ValueError(
                f"PNG has {len(lum_set)} distinct luminance values (max 4). "
                "Reduce colours to <=4 grey shades."
            )
        for row in rgb_rows:
            for r, g, b in row:
                pixels.append(_lum_to_index(r, g, b))
    else:
        raise ValueError(
            f"Unsupported PNG format: color_type={color_type}, bit_depth={bit_depth}. "
            "Expected indexed 2-bit (type 3) or RGB 8-bit (type 2)."
        )

    return pixels, width, height


def encode_2bpp(pixels, width, height):
    """Convert flat pixel index list to GB 2bpp bytes.

    Returns bytes: 16 bytes per 8×8 tile, left-to-right, top-to-bottom.
    """
    if width % 8 != 0 or height % 8 != 0:
        raise ValueError(f"Image dimensions {width}x{height} must be multiples of 8.")

    result = bytearray()
    tiles_x = width // 8

    for tx in range(tiles_x):
        for ty in range(height // 8):
            for row in range(8):
                y = ty * 8 + row
                low_byte  = 0
                high_byte = 0
                for col in range(8):
                    x = tx * 8 + col
                    v = pixels[y * width + x]
                    bit_pos = 7 - col
                    low_byte  |= (v & 1)       << bit_pos
                    high_byte |= ((v >> 1) & 1) << bit_pos
                result += bytes([low_byte, high_byte])

    return bytes(result)


def png_to_c(png_path, out_path, array_name):
    """Convert PNG file to a C source file with the 2bpp array."""
    with open(png_path, 'rb') as f:
        data = f.read()

    pixels, width, height = load_png_pixels(data)
    raw_2bpp = encode_2bpp(pixels, width, height)
    n_tiles = (width // 8) * (height // 8)

    lines = [
        f"/* Auto-generated by tools/png_to_tiles.py from {png_path} -- do not edit manually */",
        "#pragma bank 255",
        "#include <stdint.h>",
        "#include \"banking.h\"",
        "",
        f"BANKREF({array_name})",
        f"const uint8_t {array_name}[] = {{",
    ]

    tile_bytes = 16
    for t in range(n_tiles):
        hex_vals = ', '.join(f'0x{b:02X}' for b in raw_2bpp[t * tile_bytes:(t + 1) * tile_bytes])
        lines.append(f"    /* tile {t} */ {hex_vals},")

    lines += [
        "};",
        "",
        f"const uint8_t {array_name}_count = {n_tiles}u;",
        "",
    ]

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <tileset.png> <out.c> <array_name>", file=sys.stderr)
        sys.exit(1)
    _, png_path, out_path, array_name = sys.argv
    try:
        png_to_c(png_path, out_path, array_name)
        print(f"Wrote {out_path}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

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


def _paeth(a, b, c):
    """Paeth predictor (PNG spec section 9.4)."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _defilter_rows(raw, width, bytes_per_row):
    """Apply PNG row filters to decompressed IDAT data.

    raw: decompressed IDAT bytes (filter byte + data per row)
    width: image width in pixels (unused here but documents intent)
    bytes_per_row: number of data bytes per row (after filter byte)

    Returns flat bytes of defiltered row data (no filter bytes).
    PNG filter types: 0=None, 1=Sub, 2=Up, 3=Average, 4=Paeth
    """
    row_stride = 1 + bytes_per_row
    n_rows = len(raw) // row_stride
    out = bytearray()
    prev = bytes(bytes_per_row)  # previous row (all zeros for first row)

    for y in range(n_rows):
        ftype = raw[y * row_stride]
        row = bytearray(raw[y * row_stride + 1 : y * row_stride + 1 + bytes_per_row])

        if ftype == 0:    # None
            pass
        elif ftype == 1:  # Sub
            for i in range(1, bytes_per_row):
                row[i] = (row[i] + row[i - 1]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(bytes_per_row):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(bytes_per_row):
                a = row[i - 1] if i > 0 else 0
                row[i] = (row[i] + (a + prev[i]) // 2) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(bytes_per_row):
                a = row[i - 1] if i > 0 else 0
                b = prev[i]
                c = prev[i - 1] if i > 0 else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF
        else:
            raise ValueError(f"Unknown PNG filter type {ftype} on row {y}")

        out.extend(row)
        prev = bytes(row)

    return bytes(out)


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
        defiltered = _defilter_rows(raw, width, bytes_per_row)
        for y in range(height):
            row_start = y * bytes_per_row
            col = 0
            for bx in range(bytes_per_row):
                byte = defiltered[row_start + bx]
                for shift in (6, 4, 2, 0):
                    if col < width:
                        pixels.append((byte >> shift) & 3)
                        col += 1

    elif color_type == 3 and bit_depth == 8:
        # 8-bit indexed: 1 byte per pixel, value is the palette index directly
        bytes_per_row = width
        defiltered = _defilter_rows(raw, width, bytes_per_row)
        for y in range(height):
            row_start = y * bytes_per_row
            for x in range(width):
                idx = defiltered[row_start + x]
                if idx > 3:
                    raise ValueError(
                        f"Indexed PNG has palette index {idx} at ({x},{y}) — max is 3. "
                        "Reduce palette to 4 colours."
                    )
                pixels.append(idx)

    elif color_type == 2 and bit_depth == 8:
        # 8-bit RGB: 3 bytes per pixel
        bytes_per_row = width * 3
        defiltered = _defilter_rows(raw, width, bytes_per_row)
        lum_set = set()
        rgb_rows = []
        for y in range(height):
            row_start = y * bytes_per_row
            row = []
            for x in range(width):
                off = row_start + x * 3
                r, g, b = defiltered[off], defiltered[off + 1], defiltered[off + 2]
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


def png_to_c(png_path, out_path, array_name, bank):
    """Convert PNG file to a C source file with the 2bpp array."""
    with open(png_path, 'rb') as f:
        data = f.read()

    pixels, width, height = load_png_pixels(data)
    raw_2bpp = encode_2bpp(pixels, width, height)
    n_tiles = (width // 8) * (height // 8)

    lines = [
        f"/* Auto-generated by tools/png_to_tiles.py from {png_path} -- do not edit manually */",
        f"#pragma bank {bank}",
        "#include <stdint.h>",
        "#include \"banking.h\"",
        "",
        # Bank reference generation:
        # --bank 255 (autobank): use BANKREF(sym) so bankpack rewrites ___bank_sym to
        #   the real assigned bank at link time. This is required when bank-0 code
        #   (loader.c) uses BANK(sym) to actually switch banks — volatile __at(255)
        #   would make BANK() return 255 (wrong after bankpack assigns a real bank).
        # --bank N (explicit): use volatile __at(N) — hardcodes N at compile time,
        #   correct for explicit bank assignment.
        *(
            [
                "/* Bank reference: BANKREF(name) emits a CODE stub; bankpack rewrites",
                "   ___bank_name to the actual assigned bank at link time.",
                "   Required for autobank (255) so BANK(name) returns the real bank. */",
                f"BANKREF({array_name})",
            ] if bank == 255 else [
                f"/* Bank reference: volatile __at({bank}) hardcodes bank number {bank}.",
                "   Correct for explicit bank assignment where BANK(sym) = N. */",
                f"volatile __at({bank}) uint8_t __bank_{array_name};",
            ]
        ),
        "",
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
    import argparse
    parser = argparse.ArgumentParser(description="Convert PNG to GBDK C tile array")
    parser.add_argument("png_path")
    parser.add_argument("out_path")
    parser.add_argument("array_name")
    parser.add_argument("--bank", type=int, required=True,
                        help="ROM bank number for #pragma bank (use 255 for autobank)")
    args = parser.parse_args()
    try:
        png_to_c(args.png_path, args.out_path, args.array_name, bank=args.bank)
        print(f"Wrote {args.out_path}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

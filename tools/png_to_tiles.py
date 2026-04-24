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


def apply_transform(pixels, flags):
    """Apply Tiled rotation flags to an 8×8 pixel grid (list of lists).

    flags: 3-bit value (H=bit2, V=bit1, D=bit0)
    Returns a new 8×8 list of lists.
    """
    d = (flags >> 0) & 1
    v = (flags >> 1) & 1
    h = (flags >> 2) & 1
    if d:
        pixels = [[pixels[c][r] for c in range(8)] for r in range(8)]
    if h:
        pixels = [[pixels[r][7-c] for c in range(8)] for r in range(8)]
    if v:
        pixels = [[pixels[7-r][c] for c in range(8)] for r in range(8)]
    return pixels


def parse_tsx_types(tsx_path):
    """Parse tile type custom properties from a Tiled TSX file.

    Returns dict mapping 0-indexed tile ID → type string (e.g. 'TILE_ROAD').
    """
    import xml.etree.ElementTree as ET
    types = {}
    tree = ET.parse(tsx_path)
    root = tree.getroot()
    for tile_elem in root.findall("tile"):
        tile_id = int(tile_elem.get("id"))
        props = tile_elem.find("properties")
        if props is not None:
            for prop in props.findall("property"):
                if prop.get("name") == "type":
                    types[tile_id] = prop.get("value")
    return types


def _point_in_polygon(px, py, polygon):
    """Even-odd ray casting. Returns True if (px,py) is inside polygon."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def rasterize_polygon(polygon):
    """Rasterize a polygon to an 8-byte collision mask.

    polygon: list of (x,y) float/int pairs in tile-local coords (0..8).
    Returns list of 8 uint8 values, one per row.
    Bit ox (LSB=left) of row oy is 1 (passable) if pixel center
    (ox+0.5, oy+0.5) is inside the polygon.
    Empty polygon → all 0x00.
    """
    rows = []
    for oy in range(8):
        mask = 0
        for ox in range(8):
            if polygon and _point_in_polygon(ox + 0.5, oy + 0.5, polygon):
                mask |= (1 << ox)
        rows.append(mask)
    return rows


def parse_tsx_collisions(tsx_path):
    """Parse per-tile collision polygons from Tiled TSX <objectgroup> elements.

    Returns dict mapping 0-indexed tile ID → list of (x,y) tuples.
    Tiles with no <objectgroup> are absent from the dict.
    Only the first <polygon> inside the first <object> is used.
    """
    import xml.etree.ElementTree as ET
    collisions = {}
    tree = ET.parse(tsx_path)
    root = tree.getroot()
    for tile_elem in root.findall("tile"):
        tile_id = int(tile_elem.get("id"))
        og = tile_elem.find("objectgroup")
        if og is None:
            continue
        obj = og.find("object")
        if obj is None:
            continue
        obj_x = float(obj.get("x", 0))
        obj_y = float(obj.get("y", 0))
        poly_elem = obj.find("polygon")
        if poly_elem is None:
            w = float(obj.get("width", 8))
            h = float(obj.get("height", 8))
            polygon = [(obj_x, obj_y),
                       (obj_x + w, obj_y),
                       (obj_x + w, obj_y + h),
                       (obj_x, obj_y + h)]
        else:
            points_str = poly_elem.get("points", "")
            polygon = []
            for pt in points_str.split():
                px_s, py_s = pt.split(",")
                polygon.append((obj_x + float(px_s), obj_y + float(py_s)))
        collisions[tile_id] = polygon
    return collisions


def png_to_c(png_path, out_path, array_name, bank,
             rotation_manifest=None, tsx_path=None,
             id_map_out=None, meta_header_out=None):
    """Convert PNG file to a C source file with the 2bpp array."""
    import json

    with open(png_path, 'rb') as f:
        data = f.read()

    pixels, width, height = load_png_pixels(data)
    raw_2bpp = encode_2bpp(pixels, width, height)
    n_tiles = (width // 8) * (height // 8)

    # --- Rotation variants (optional) ---
    if rotation_manifest is not None:
        with open(rotation_manifest) as f:
            manifest = json.load(f)
        # Build 2D pixel grid for each base tile.
        # encode_2bpp writes tiles column-major (outer=tx, inner=ty), so
        # tile_idx maps as: tx = tile_idx // tiles_tall, ty = tile_idx % tiles_tall.
        tiles_x = width // 8
        tiles_tall = height // 8
        base_tile_pixels = []
        for tile_idx in range(n_tiles):
            tx = tile_idx // tiles_tall
            ty = tile_idx % tiles_tall
            grid = []
            for row in range(8):
                row_pixels = []
                for col in range(8):
                    x = tx * 8 + col
                    y = ty * 8 + row
                    row_pixels.append(pixels[y * width + x])
                grid.append(row_pixels)
            base_tile_pixels.append(grid)

        # Build base_remap: Tiled uses row-major GIDs but encode_2bpp writes
        # tiles column-major. For multi-row tilesets this diverges, so we store
        # an explicit row-major→column-major index mapping for tmx_to_c.py.
        base_remap = {}
        if tiles_tall > 1:
            for row_idx in range(n_tiles):
                col_in_ts = row_idx % tiles_x
                row_in_ts = row_idx // tiles_x
                col_major_idx = col_in_ts * tiles_tall + row_in_ts
                base_remap[str(row_idx)] = col_major_idx

        id_map = {"base_count": n_tiles, "base_remap": base_remap, "variants": {}}
        variant_tiles = []  # list of (key, tile_2bpp_bytes)

        for base_id_str, flag_list in sorted(manifest["rotations"].items(),
                                              key=lambda x: int(x[0])):
            base_id = int(base_id_str)
            # base_id is row-major (Tiled GID offset); base_tile_pixels is
            # indexed by column-major C index — remap before lookup.
            col_major_src = int(base_remap.get(str(base_id), base_id))
            base_pixels_grid = base_tile_pixels[col_major_src]
            for flags in sorted(flag_list):
                rotated = apply_transform(base_pixels_grid, flags)
                # Flatten 2D grid to encode
                flat = [rotated[r][c] for r in range(8) for c in range(8)]
                tile_bytes_data = encode_2bpp(flat, 8, 8)
                assigned_id = n_tiles + len(variant_tiles)
                key = f"{base_id}:{flags}"
                id_map["variants"][key] = assigned_id
                variant_tiles.append((key, tile_bytes_data))

        total_tiles = n_tiles + len(variant_tiles)
        if total_tiles > 192:
            print(f"ERROR: VRAM budget exceeded: {n_tiles} base + "
                  f"{len(variant_tiles)} rotated = {total_tiles} tiles; limit 192",
                  file=sys.stderr)
            sys.exit(1)
    else:
        id_map = None
        variant_tiles = []
        total_tiles = n_tiles

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

    # Variant tiles (rotated)
    for key, tile_bytes_data in variant_tiles:
        base_id = int(key.split(":")[0])
        flags = int(key.split(":")[1])
        assigned_id = id_map["variants"][key]
        hex_vals = ', '.join(f'0x{b:02X}' for b in tile_bytes_data)
        lines.append(f"    /* tile {assigned_id} (rot from {base_id}, flags={flags}) */ {hex_vals},")

    lines += [
        "};",
        "",
        f"const uint8_t {array_name}_count = {total_tiles}u;",
        "",
    ]

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

    if id_map_out is not None and id_map is not None:
        with open(id_map_out, "w") as f:
            json.dump(id_map, f, indent=2)

    if meta_header_out is not None and tsx_path is not None and id_map is not None:
        tsx_types = parse_tsx_types(tsx_path)
        tsx_collisions = parse_tsx_collisions(tsx_path)
        lut_entries = []
        mask_rows = []   # flat: 8 bytes per tile, in LUT order
        _tiles_x = width // 8
        _tiles_tall = height // 8

        def _mask_for_tiled_idx(tiled_idx, flags=0):
            """Return 8-byte mask list for a given Tiled tile id + transform flags."""
            type_str = tsx_types.get(tiled_idx, "TILE_ROAD")
            if tiled_idx in tsx_collisions:
                poly = tsx_collisions[tiled_idx]
            elif type_str == "TILE_WALL":
                poly = []          # no objectgroup + TILE_WALL → all 0x00
            else:
                poly = [(0,0),(8,0),(8,8),(0,8)]  # no objectgroup + non-wall → all 0xFF
            rows = rasterize_polygon(poly)
            if flags != 0:
                grid = [[1 if (rows[r] >> c) & 1 else 0 for c in range(8)] for r in range(8)]
                grid = apply_transform(grid, flags)
                rows = [sum(grid[r][c] << c for c in range(8)) for r in range(8)]
            return rows

        for i in range(n_tiles):
            tiled_idx = (i % _tiles_tall) * _tiles_x + (i // _tiles_tall)
            t = tsx_types.get(tiled_idx, "TILE_ROAD")
            lut_entries.append(f"    {t},  /* {i} */")
            mask_rows.extend(_mask_for_tiled_idx(tiled_idx))

        for key, _ in variant_tiles:
            base_id = int(key.split(":")[0])
            flags   = int(key.split(":")[1])
            t = tsx_types.get(base_id, "TILE_ROAD")
            idx = id_map["variants"][key]
            lut_entries.append(f"    {t},  /* {idx} (rotated from {base_id}) */")
            mask_rows.extend(_mask_for_tiled_idx(base_id, flags))

        lut_len = len(lut_entries)

        mask_lines = []
        for tile_i in range(lut_len):
            hex_vals = ", ".join(f"0x{mask_rows[tile_i*8 + r]:02X}" for r in range(8))
            mask_lines.append(f"    /* tile {tile_i} */ {hex_vals},")

        header_lines = [
            "/* generated by png_to_tiles.py — do not edit */",
            "#ifndef TRACK_TILESET_META_H",
            "#define TRACK_TILESET_META_H",
            f"#define TRACK_TILE_LUT_LEN {lut_len}u",
            f"static const uint8_t track_tile_type_lut[TRACK_TILE_LUT_LEN] = {{",
        ] + lut_entries + [
            "};",
            "/* Per-tile 8x8 collision bitmask: 8 bytes per tile, LSB=leftmost pixel.",
            "   1=passable, 0=solid. Index: tile_idx*8+row_y.",
            "   On SDCC (GBC): const → placed in ROM bank with track.c.",
            "   On gcc (host tests): non-const → writable by track_test_set_collision_mask(). */",
            "#ifdef __SDCC",
            f"static const uint8_t track_collision_mask[TRACK_TILE_LUT_LEN * 8u] = {{",
            "#else",
            f"static uint8_t track_collision_mask[TRACK_TILE_LUT_LEN * 8u] = {{",
            "#endif",
        ] + mask_lines + [
            "};",
            "#endif /* TRACK_TILESET_META_H */",
        ]
        with open(meta_header_out, "w") as f:
            f.write("\n".join(header_lines) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert PNG to GBDK C tile array")
    parser.add_argument("png_path")
    parser.add_argument("out_path")
    parser.add_argument("array_name")
    parser.add_argument("--bank", type=int, required=True,
                        help="ROM bank number for #pragma bank (use 255 for autobank)")
    parser.add_argument("--rotation-manifest", metavar="PATH",
                        help="Path to track_rotation_manifest.json")
    parser.add_argument("--tsx", metavar="PATH",
                        help="Path to track.tsx for tile type properties")
    parser.add_argument("--id-map-out", metavar="PATH",
                        help="Output path for track_tile_id_map.json")
    parser.add_argument("--meta-header-out", metavar="PATH",
                        help="Output path for track_tileset_meta.h")
    args = parser.parse_args()
    try:
        png_to_c(args.png_path, args.out_path, args.array_name, bank=args.bank,
                 rotation_manifest=args.rotation_manifest,
                 tsx_path=args.tsx,
                 id_map_out=args.id_map_out,
                 meta_header_out=args.meta_header_out)
        print(f"Wrote {args.out_path}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

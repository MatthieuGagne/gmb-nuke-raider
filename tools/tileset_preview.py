#!/usr/bin/env python3
"""Generate a visual HTML reference of all tileset tiles with their types."""

import xml.etree.ElementTree as ET
import base64
import io
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent.parent
TSX  = ROOT / "assets/maps/track.tsx"
PNG  = ROOT / "assets/maps/tileset.png"
OUT  = ROOT / "build/tileset_preview.html"

# Parse TSX for tile types
tree = ET.parse(TSX)
ts   = tree.getroot()
cols   = int(ts.get("columns"))
tw     = int(ts.get("tilewidth"))
th     = int(ts.get("tileheight"))
tcount = int(ts.get("tilecount"))

tile_types = {}
for tile in ts.findall("tile"):
    tid  = int(tile.get("id"))
    prop = tile.find(".//property[@name='type']")
    if prop is not None:
        tile_types[tid] = prop.get("value")

# Crop each tile to its own data URI
img   = Image.open(PNG).convert("RGBA")
scale = 6  # display at 48×48 px

TYPE_COLORS = {
    "TILE_ROAD":   "#4caf50",
    "TILE_WALL":   "#f44336",
    "TILE_SAND":   "#ff9800",
    "TILE_OIL":    "#9c27b0",
    "TILE_BOOST":  "#2196f3",
    "TILE_FINISH": "#00bcd4",
}

def tile_data_uri(tid):
    col, row = tid % cols, tid // cols
    tile = img.crop((col*tw, row*th, col*tw+tw, row*th+th))
    tile = tile.resize((tw*scale, th*scale), Image.NEAREST)
    buf = io.BytesIO()
    tile.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

cells = []
for tid in range(tcount):
    ttype   = tile_types.get(tid, "TILE_WALL")
    color   = TYPE_COLORS.get(ttype, "#888")
    missing = " ⚠" if tid not in tile_types else ""
    uri     = tile_data_uri(tid)
    cells.append(f"""
      <div class="tile">
        <img src="{uri}" width="{tw*scale}" height="{th*scale}" style="image-rendering:pixelated;border:2px solid {'#f44336' if missing else '#444'}">
        <div class="label" style="color:{color}">{ttype.replace('TILE_','')}{missing}</div>
        <div class="id">id {tid} ({tid%cols},{tid//cols})</div>
      </div>""")

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Tileset Preview</title>
<style>
  body  {{ background:#1e1e1e; color:#ccc; font-family:monospace; padding:16px; }}
  h1    {{ color:#fff; margin-bottom:16px; }}
  .grid {{ display:flex; flex-wrap:wrap; gap:16px; }}
  .tile {{ display:flex; flex-direction:column; align-items:center; gap:4px; }}
  .label {{ font-size:11px; font-weight:bold; }}
  .id    {{ font-size:9px; color:#888; }}
</style>
</head>
<body>
<h1>Tileset Preview — {tcount} tiles ({cols} cols × {tcount//cols} rows)</h1>
<div class="grid">{''.join(cells)}
</div>
</body>
</html>"""

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(html)
print(f"Written: {OUT}")

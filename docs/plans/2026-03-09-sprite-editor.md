# Sprite Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a GTK3 Python sprite editor for drawing 4×4 grids of 8×8 CGB tiles and exporting indexed PNGs.

**Architecture:** Pure-Python model (`TileSheet` + `Palette`) handles all data and PNG I/O with no GTK dependency; a GTK3 view layer wires a Cairo drawing area and palette sliders to the model. Dirty-state tracking lives in the model so the view can prompt on discard.

**Tech Stack:** Python 3.12, GTK3 (PyGObject/gi), PyCairo, `struct` + `zlib` (no Pillow).

**GitHub issue:** #13

---

### Task 1: Scaffold package directories + Makefile test-tools target

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/sprite_editor/__init__.py`
- Create: `assets/sprites/.gitkeep`
- Modify: `Makefile`

**Step 1: Create package markers and assets dir**

```bash
mkdir -p tools/sprite_editor assets/sprites
touch tools/__init__.py tools/sprite_editor/__init__.py assets/sprites/.gitkeep
```

**Step 2: Add test-tools target to Makefile**

Add after the existing `test:` target:

```makefile
test-tools:
	PYTHONPATH=. python3 -m unittest tests.test_sprite_editor -v
```

Also add `test-tools` to the `.PHONY` line:

```makefile
.PHONY: all clean test test-tools
```

**Step 3: Create a minimal test file to verify the target runs**

Create `tests/test_sprite_editor.py`:

```python
import unittest

class TestPlaceholder(unittest.TestCase):
    def test_placeholder(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
```

**Step 4: Run to verify target works**

```bash
make test-tools
```

Expected output: `Ran 1 test in 0.000s` with `OK`.

**Step 5: Commit**

```bash
git add tools/__init__.py tools/sprite_editor/__init__.py assets/sprites/.gitkeep \
        Makefile tests/test_sprite_editor.py
git commit -m "feat: scaffold sprite editor package + make test-tools target"
```

---

### Task 2: Palette class

**Files:**
- Create: `tools/sprite_editor/model.py`
- Modify: `tests/test_sprite_editor.py`

**Step 1: Write the failing tests**

Replace `tests/test_sprite_editor.py` with:

```python
import unittest
import tempfile
import os

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


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run to verify they fail**

```bash
make test-tools
```

Expected: `ModuleNotFoundError: No module named 'tools.sprite_editor.model'`

**Step 3: Implement Palette in model.py**

Create `tools/sprite_editor/model.py`:

```python
import struct
import zlib


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
```

**Step 4: Run tests to verify pass**

```bash
make test-tools
```

Expected: `Ran 5 tests in ...` with `OK`.

**Step 5: Commit**

```bash
git add tools/sprite_editor/model.py tests/test_sprite_editor.py
git commit -m "feat: Palette class with 5-bit RGB storage and RGB888 conversion"
```

---

### Task 3: TileSheet basic operations

**Files:**
- Modify: `tools/sprite_editor/model.py`
- Modify: `tests/test_sprite_editor.py`

**Step 1: Add failing tests for TileSheet**

Append to the test class section in `tests/test_sprite_editor.py` (before `if __name__ == '__main__':`):

```python
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
```

**Step 2: Run to verify they fail**

```bash
make test-tools
```

Expected: `AttributeError: module ... has no attribute 'TileSheet'`

**Step 3: Add TileSheet to model.py**

Append after the `Palette` class:

```python
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
```

**Step 4: Run tests**

```bash
make test-tools
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add tools/sprite_editor/model.py tests/test_sprite_editor.py
git commit -m "feat: TileSheet with set/get pixel, clear, and dirty tracking"
```

---

### Task 4: PNG save

**Files:**
- Modify: `tools/sprite_editor/model.py`
- Modify: `tests/test_sprite_editor.py`

**Step 1: Add failing tests**

Append to `TestTileSheet` in `tests/test_sprite_editor.py`:

```python
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
```

Also add `import struct` at the top of `tests/test_sprite_editor.py` (after `import os`).

**Step 2: Run to verify they fail**

```bash
make test-tools
```

Expected: `AttributeError: 'TileSheet' object has no attribute 'save_png'`

**Step 3: Add PNG helpers and save_png to model.py**

Add these helpers at module level (between imports and `class Palette:`):

```python
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack('>I', len(data))
    crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc
```

Add `save_png` method to `TileSheet` (after `clear`):

```python
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
```

**Step 4: Run tests**

```bash
make test-tools
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add tools/sprite_editor/model.py tests/test_sprite_editor.py
git commit -m "feat: TileSheet.save_png writes 2-bit indexed PNG with PLTE and tRNS"
```

---

### Task 5: PNG load and round-trip

**Files:**
- Modify: `tools/sprite_editor/model.py`
- Modify: `tests/test_sprite_editor.py`

**Step 1: Add failing tests**

Append to `TestTileSheet`:

```python
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
```

**Step 2: Run to verify they fail**

```bash
make test-tools
```

Expected: `AttributeError: 'TileSheet' object has no attribute 'load_png'`

**Step 3: Implement load_png**

Add after `save_png` in `TileSheet`:

```python
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
```

**Step 4: Run tests**

```bash
make test-tools
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add tools/sprite_editor/model.py tests/test_sprite_editor.py
git commit -m "feat: TileSheet.load_png with palette and pixel round-trip"
```

---

### Task 6: TileCanvas (GTK3 drawing area)

No unit tests — GTK requires a display. Implement and verify manually.

**Files:**
- Create: `tools/sprite_editor/view.py`

**Step 1: Create view.py with TileCanvas**

Create `tools/sprite_editor/view.py`:

```python
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

ZOOM = 8
_W = 32  # canvas pixel width
_H = 32  # canvas pixel height


class TileCanvas(Gtk.DrawingArea):
    """Cairo-based drawing area for the tile sheet at 8× zoom."""

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.active_color = 0
        self.set_size_request(_W * ZOOM, _H * ZOOM)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        self.connect('draw', self._on_draw)
        self.connect('button-press-event', self._on_click)
        self.connect('motion-notify-event', self._on_drag)

    def _on_draw(self, widget, cr):
        for y in range(_H):
            for x in range(_W):
                idx = self.model.get_pixel(x, y)
                if idx == 0:
                    # Transparent: checkerboard
                    light = ((x + y) % 2 == 0)
                    v = 0.75 if light else 0.55
                    cr.set_source_rgb(v, v, v)
                else:
                    r8, g8, b8 = self.model.palette.get_color_rgb888(idx)
                    cr.set_source_rgb(r8 / 255, g8 / 255, b8 / 255)
                cr.rectangle(x * ZOOM, y * ZOOM, ZOOM, ZOOM)
                cr.fill()

        # Tile grid overlay
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.4)
        cr.set_line_width(1)
        tile_px = 8 * ZOOM
        for i in range(5):  # 0..4 (4 tiles = 5 lines)
            cr.move_to(i * tile_px, 0)
            cr.line_to(i * tile_px, _H * ZOOM)
            cr.stroke()
            cr.move_to(0, i * tile_px)
            cr.line_to(_W * ZOOM, i * tile_px)
            cr.stroke()

    def _paint_at(self, ex, ey):
        x = int(ex / ZOOM)
        y = int(ey / ZOOM)
        if 0 <= x < _W and 0 <= y < _H:
            self.model.set_pixel(x, y, self.active_color)
            self.queue_draw()

    def _on_click(self, widget, event):
        if event.button == 1:
            self._paint_at(event.x, event.y)

    def _on_drag(self, widget, event):
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            self._paint_at(event.x, event.y)
```

**Step 2: Run existing tests (model only, must still pass)**

```bash
make test-tools
```

Expected: All pass (view.py has no unit tests, but model tests must stay green).

**Step 3: Commit**

```bash
git add tools/sprite_editor/view.py
git commit -m "feat: TileCanvas GTK3 drawing area with 8x zoom and click-to-paint"
```

---

### Task 7: PalettePanel (GTK3 color selector)

**Files:**
- Modify: `tools/sprite_editor/view.py`

**Step 1: Append PalettePanel to view.py**

```python
class PalettePanel(Gtk.Box):
    """Vertical panel: 4 color buttons + RGB sliders for the active color."""

    def __init__(self, model, canvas):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.model = model
        self.canvas = canvas
        self.active_index = 0
        self._build()

    def _build(self):
        lbl = Gtk.Label(label='<b>Palette</b>', use_markup=True)
        self.pack_start(lbl, False, False, 0)

        self.color_buttons = []
        for i in range(4):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            btn = Gtk.Button()
            btn.set_size_request(36, 36)
            btn.connect('clicked', self._select_color, i)
            self.color_buttons.append(btn)
            row.pack_start(btn, False, False, 0)
            if i == 0:
                row.pack_start(Gtk.Label(label='(transparent)'), False, False, 0)
            self.pack_start(row, False, False, 0)
            self._refresh_button(i)

        # RGB sliders
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 4)

        self.sliders = {}
        for ch in ('R', 'G', 'B'):
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            box.pack_start(Gtk.Label(label=ch), False, False, 0)
            adj = Gtk.Adjustment(value=0, lower=0, upper=31,
                                 step_increment=1, page_increment=5,
                                 page_size=0)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                              adjustment=adj)
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.connect('value-changed', self._on_slider, ch)
            self.sliders[ch] = scale
            box.pack_start(scale, True, True, 0)
            self.pack_start(box, False, False, 0)

        self._load_sliders()
        self._highlight_active()

    def _select_color(self, btn, index):
        self.active_index = index
        self.canvas.active_color = index
        self._load_sliders()
        self._highlight_active()

    def _load_sliders(self):
        r5, g5, b5 = self.model.palette.colors[self.active_index]
        self.sliders['R'].set_value(r5)
        self.sliders['G'].set_value(g5)
        self.sliders['B'].set_value(b5)

    def _on_slider(self, scale, channel):
        val = int(scale.get_value())
        r5, g5, b5 = self.model.palette.colors[self.active_index]
        if channel == 'R':
            r5 = val
        elif channel == 'G':
            g5 = val
        else:
            b5 = val
        self.model.palette.set_color(self.active_index, r5, g5, b5)
        self._refresh_button(self.active_index)
        self.canvas.queue_draw()

    def _refresh_button(self, index):
        r8, g8, b8 = self.model.palette.get_color_rgb888(index)
        rgba = Gdk.RGBA(r8 / 255, g8 / 255, b8 / 255, 1.0)
        self.color_buttons[index].override_background_color(
            Gtk.StateFlags.NORMAL, rgba)

    def _highlight_active(self):
        for i, btn in enumerate(self.color_buttons):
            relief = Gtk.ReliefStyle.NONE if i == self.active_index else Gtk.ReliefStyle.NORMAL
            btn.set_relief(relief)
```

**Step 2: Run model tests**

```bash
make test-tools
```

Expected: All pass.

**Step 3: Commit**

```bash
git add tools/sprite_editor/view.py
git commit -m "feat: PalettePanel with color buttons and 5-bit RGB sliders"
```

---

### Task 8: MainWindow + dirty-state dialog

**Files:**
- Modify: `tools/sprite_editor/view.py`

**Step 1: Append MainWindow to view.py**

```python
class MainWindow(Gtk.Window):
    """Top-level window: HeaderBar with New/Open/Save + canvas + palette."""

    def __init__(self, model):
        super().__init__(title='Sprite Editor')
        self.model = model
        self.current_path = None

        # Header bar
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.set_title('Sprite Editor')
        self.set_titlebar(hb)

        new_btn = Gtk.Button(label='New')
        new_btn.connect('clicked', self._on_new)
        open_btn = Gtk.Button(label='Open')
        open_btn.connect('clicked', self._on_open)
        save_btn = Gtk.Button(label='Save')
        save_btn.connect('clicked', self._on_save)
        hb.pack_start(new_btn)
        hb.pack_start(open_btn)
        hb.pack_end(save_btn)

        # Layout
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox.set_border_width(8)
        self.canvas = TileCanvas(model)
        self.palette = PalettePanel(model, self.canvas)
        hbox.pack_start(self.canvas, False, False, 0)
        hbox.pack_start(self.palette, False, False, 0)
        self.add(hbox)

        self.connect('delete-event', self._on_quit)

    # ── Dirty-state guard ────────────────────────────────────────────────────

    def _confirm_discard(self):
        """Return True if safe to discard; prompt user if dirty."""
        if not self.model.dirty:
            return True
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text='Unsaved changes \u2014 discard?',
        )
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_new(self, btn):
        if self._confirm_discard():
            self.model.clear()
            self.current_path = None
            self.canvas.queue_draw()
            self.palette._load_sliders()

    def _on_open(self, btn):
        if not self._confirm_discard():
            return
        dialog = Gtk.FileChooserDialog(
            title='Open PNG',
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,   Gtk.ResponseType.OK,
            ),
        )
        f = Gtk.FileFilter()
        f.set_name('PNG files')
        f.add_pattern('*.png')
        dialog.add_filter(f)
        dialog.set_current_folder('assets/sprites')
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and path:
            self.model.load_png(path)
            self.current_path = path
            self.canvas.queue_draw()
            self.palette._load_sliders()
            for i in range(4):
                self.palette._refresh_button(i)

    def _on_save(self, btn):
        if self.current_path:
            self.model.save_png(self.current_path)
            return
        dialog = Gtk.FileChooserDialog(
            title='Save PNG',
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_SAVE,   Gtk.ResponseType.OK,
            ),
        )
        dialog.set_do_overwrite_confirmation(True)
        f = Gtk.FileFilter()
        f.set_name('PNG files')
        f.add_pattern('*.png')
        dialog.add_filter(f)
        dialog.set_current_folder('assets/sprites')
        dialog.set_current_name('sprites.png')
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and path:
            self.current_path = path
            self.model.save_png(path)

    def _on_quit(self, widget, event):
        if self._confirm_discard():
            Gtk.main_quit()
            return False
        return True  # block window close
```

**Step 2: Run model tests**

```bash
make test-tools
```

Expected: All pass.

**Step 3: Commit**

```bash
git add tools/sprite_editor/view.py
git commit -m "feat: MainWindow with New/Open/Save and dirty-state discard dialog"
```

---

### Task 9: main.py + launcher script

**Files:**
- Create: `tools/sprite_editor/main.py`
- Create: `tools/run_sprite_editor.py`

**Step 1: Create main.py**

```python
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from tools.sprite_editor.model import TileSheet
from tools.sprite_editor.view import MainWindow


def run():
    model = TileSheet()
    win = MainWindow(model)
    win.show_all()
    Gtk.main()
```

**Step 2: Create tools/run_sprite_editor.py**

```python
#!/usr/bin/env python3
import sys
import os

# Ensure repo root is on the path so `tools.sprite_editor` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.sprite_editor.main import run

if __name__ == '__main__':
    run()
```

Make it executable:

```bash
chmod +x tools/run_sprite_editor.py
```

**Step 3: Run model tests (must still pass)**

```bash
make test-tools
```

Expected: All pass.

**Step 4: Smoke-test the editor**

```bash
python3 tools/run_sprite_editor.py
```

Expected: GTK3 window opens with a tile canvas and palette panel. Clicking paints pixels, sliders update colors in real time, New/Save/Open work, discard prompt appears when dirty.

> **STOP HERE** — do not commit or create a PR until the user confirms the smoke test passes in the running editor.

**Step 5: Commit (after user confirmation)**

```bash
git add tools/sprite_editor/main.py tools/run_sprite_editor.py
git commit -m "feat: sprite editor launcher and main wiring"
```

---

### Task 10: Palette save/load (`.pal` file)

**Goal:** Let users save a palette to a `.pal` file and load it into any sprite set, enabling reuse across multiple TileSheets.

**File format:** Plain text, 4 lines, each `r5 g5 b5` (space-separated integers 0–31). Example:

```
0 0 0
31 0 0
0 31 0
0 0 31
```

**Files:**
- Modify: `tools/sprite_editor/model.py`
- Modify: `tools/sprite_editor/view.py`
- Modify: `tests/test_sprite_editor.py`

**Step 1: Write failing tests**

Append to `TestPalette` in `tests/test_sprite_editor.py`:

```python
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
```

Also add `import tempfile` and `import os` at the top if not already present (they are — added in Task 4).

**Step 2: Run to verify they fail**

```bash
make test-tools
```

Expected: `AttributeError: 'Palette' object has no attribute 'save'`

**Step 3: Implement Palette.save and Palette.load**

Add after `get_color_rgb888` in `model.py`:

```python
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
```

**Step 4: Run tests**

```bash
make test-tools
```

Expected: All tests pass.

**Step 5: Add Save Pal / Load Pal buttons to PalettePanel**

In `view.py`, inside `PalettePanel._build`, append after the RGB sliders section (before `self._load_sliders()`):

```python
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep2, False, False, 4)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        load_pal_btn = Gtk.Button(label='Load Pal…')
        load_pal_btn.connect('clicked', self._on_load_pal)
        save_pal_btn = Gtk.Button(label='Save Pal…')
        save_pal_btn.connect('clicked', self._on_save_pal)
        btn_row.pack_start(load_pal_btn, True, True, 0)
        btn_row.pack_start(save_pal_btn, True, True, 0)
        self.pack_start(btn_row, False, False, 0)
```

Also add the two handlers to `PalettePanel`:

```python
    def _on_load_pal(self, btn):
        dialog = Gtk.FileChooserDialog(
            title='Load Palette',
            parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                     Gtk.STOCK_OPEN, Gtk.ResponseType.OK),
        )
        f = Gtk.FileFilter()
        f.set_name('Palette files')
        f.add_pattern('*.pal')
        dialog.add_filter(f)
        dialog.set_current_folder('assets/sprites')
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and path:
            self.model.palette.load(path)
            self._load_sliders()
            for i in range(4):
                self._refresh_button(i)
            self.canvas.queue_draw()

    def _on_save_pal(self, btn):
        dialog = Gtk.FileChooserDialog(
            title='Save Palette',
            parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.SAVE,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                     Gtk.STOCK_SAVE, Gtk.ResponseType.OK),
        )
        dialog.set_do_overwrite_confirmation(True)
        f = Gtk.FileFilter()
        f.set_name('Palette files')
        f.add_pattern('*.pal')
        dialog.add_filter(f)
        dialog.set_current_folder('assets/sprites')
        dialog.set_current_name('palette.pal')
        response = dialog.run()
        path = dialog.get_filename()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and path:
            self.model.palette.save(path)
```

**Step 6: Run model tests (must still pass)**

```bash
make test-tools
```

**Step 7: Commit**

```bash
git add tools/sprite_editor/model.py tools/sprite_editor/view.py tests/test_sprite_editor.py
git commit -m "feat: Palette.save/load for .pal file reuse across sprite sets"
```

---

### Task 11: Final integration + PR

**Step 1: Run all tests**

```bash
make test       # C unit tests (unchanged)
make test-tools # Python sprite editor tests
```

Both must pass.

**Step 2: Verify png2asset compatibility**

Draw something in the editor and save to `assets/sprites/test_tile.png`, then:

```bash
~/gbdk/bin/png2asset assets/sprites/test_tile.png -o /tmp/test_tile.c
```

Expected: No errors; `/tmp/test_tile.c` is generated.

**Step 3: Push and open PR**

```bash
git push -u origin feat/sprite-editor
gh pr create --title "feat: sprite editor desktop tool (closes #13)" \
  --body "$(cat <<'EOF'
## Summary
- Adds `tools/sprite_editor/` Python package (model, view, main)
- `model.py` is GTK-free and fully unit-tested
- `tools/run_sprite_editor.py` launches the GTK3 editor
- `make test-tools` runs all model unit tests
- Exports 2-bit indexed PNG compatible with `png2asset`
- `Palette.save/load` supports `.pal` files for reuse across sprite sets

## Test plan
- [x] `make test` passes (C tests unchanged)
- [x] `make test-tools` passes (set_pixel, set_color, PNG round-trip, palette round-trip)
- [ ] User smoke-tested the GTK editor: painting, palette sliders, save/load, discard dialog, Load Pal / Save Pal buttons

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

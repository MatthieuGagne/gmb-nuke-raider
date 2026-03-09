import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import cairo  # registers cairo.Context as a GI foreign type (requires python3-gi-cairo)

ZOOM = 8
_W = 32  # canvas pixel width
_H = 32  # canvas pixel height

PALETTE_PRESETS = {
    'Gray': [(0, 0, 0), (10, 10, 10), (21, 21, 21), (31, 31, 31)],
    'GBC':  [(0, 0, 0), (28,  4,  4), (28, 20,  0), (31, 31, 31)],
}


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


class PalettePanel(Gtk.Box):
    """Vertical panel: preset buttons, 4 colour swatches, RGB sliders."""

    def __init__(self, model, canvas):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_border_width(6)
        self.model = model
        self.canvas = canvas
        self.active_index = 0
        self._build()

    def _build(self):
        # ── Title ────────────────────────────────────────────────────────────
        self.pack_start(
            Gtk.Label(label='<b>Palette</b>', use_markup=True),
            False, False, 0)

        # ── Preset buttons ───────────────────────────────────────────────────
        preset_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for name in PALETTE_PRESETS:
            btn = Gtk.Button(label=name)
            btn.connect('clicked', self._apply_preset, name)
            preset_row.pack_start(btn, True, True, 0)
        self.pack_start(preset_row, False, False, 0)

        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            False, False, 0)

        # ── 4 equal colour swatches in a row ─────────────────────────────────
        swatch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.color_buttons = []
        for i in range(4):
            btn = Gtk.Button(label=str(i))
            btn.set_size_request(48, 48)
            btn.connect('clicked', self._select_color, i)
            self.color_buttons.append(btn)
            swatch_row.pack_start(btn, True, True, 0)
            self._refresh_button(i)
        self.pack_start(swatch_row, False, False, 0)

        # Small note about index 0
        note = Gtk.Label(label='<small><i>Color 0 = transparent for sprites (GBC hardware)</i></small>',
                         use_markup=True)
        note.set_halign(Gtk.Align.START)
        self.pack_start(note, False, False, 0)

        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            False, False, 0)

        # ── Active colour label ──────────────────────────────────────────────
        self._active_lbl = Gtk.Label(label='Editing color 0 (0–31 per channel)')
        self._active_lbl.set_halign(Gtk.Align.START)
        self.pack_start(self._active_lbl, False, False, 0)

        # ── RGB sliders ──────────────────────────────────────────────────────
        self._linking = False  # guard against recursive slider updates

        link_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._link_btn = Gtk.CheckButton(label='Link R=G=B (greyscale)')
        link_row.pack_start(self._link_btn, False, False, 0)
        self.pack_start(link_row, False, False, 0)

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

        # ── Palette file buttons ─────────────────────────────────────────────
        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            False, False, 4)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        load_pal_btn = Gtk.Button(label='Load Pal…')
        load_pal_btn.connect('clicked', self._on_load_pal)
        save_pal_btn = Gtk.Button(label='Save Pal…')
        save_pal_btn.connect('clicked', self._on_save_pal)
        btn_row.pack_start(load_pal_btn, True, True, 0)
        btn_row.pack_start(save_pal_btn, True, True, 0)
        self.pack_start(btn_row, False, False, 0)

    # ── Preset ────────────────────────────────────────────────────────────────

    def _apply_preset(self, btn, name):
        for i, (r5, g5, b5) in enumerate(PALETTE_PRESETS[name]):
            self.model.palette.set_color(i, r5, g5, b5)
            self._refresh_button(i)
        self._load_sliders()
        self.canvas.queue_draw()

    # ── Colour selection ──────────────────────────────────────────────────────

    def _select_color(self, btn, index):
        self.active_index = index
        self.canvas.active_color = index
        self._active_lbl.set_text(f'Editing color {index} (0–31 per channel)')
        self._load_sliders()
        self._highlight_active()

    def _load_sliders(self):
        r5, g5, b5 = self.model.palette.colors[self.active_index]
        self.sliders['R'].set_value(r5)
        self.sliders['G'].set_value(g5)
        self.sliders['B'].set_value(b5)

    def _on_slider(self, scale, channel):
        if self._linking:
            return
        val = int(scale.get_value())
        if self._link_btn.get_active():
            self._linking = True
            for s in self.sliders.values():
                s.set_value(val)
            self._linking = False
            r5 = g5 = b5 = val
        else:
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
            ctx = btn.get_style_context()
            if i == self.active_index:
                ctx.add_class('suggested-action')
            else:
                ctx.remove_class('suggested-action')

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

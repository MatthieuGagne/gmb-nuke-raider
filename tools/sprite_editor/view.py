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

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

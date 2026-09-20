import json
import os
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

assert os.environ['GTK_A11Y'] == 'none', 'This test must run with accessibility disabled'
marker = Path(os.environ['GRID_TEST_DIR']) / 'events.json'
events = []
app = Gtk.Application(application_id='io.github.gridclick.Fixture')

def activate(app):
    window = Gtk.ApplicationWindow(application=app, title='Grid Click Fixture', decorated=False)
    window.set_default_size(600, 400)
    area = Gtk.Box()
    area.add_css_class('grid-fixture')
    area.append(Gtk.Label(label='Grid Click\nAccessibility disabled\nClick test surface', hexpand=True, vexpand=True))
    provider = Gtk.CssProvider()
    provider.load_from_string('.grid-fixture { background: #1f3042; color: white; font-size: 22px; }')
    Gtk.StyleContext.add_provider_for_display(window.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    window.set_child(area)
    gesture = Gtk.GestureClick()
    gesture.set_button(0)
    def record(gesture, n, x, y, kind):
        events.append(dict(kind=kind, button=gesture.get_current_button(), n=n, x=x, y=y))
        marker.write_text(json.dumps(events))
    gesture.connect('pressed', lambda g, n, x, y: record(g, n, x, y, 'press'))
    gesture.connect('released', lambda g, n, x, y: record(g, n, x, y, 'release'))
    area.add_controller(gesture)
    window.present()

app.connect('activate', activate)
app.run(None)

"""Small Wayland-only GTK fixture. Its button writes a marker for integration tests."""
import os
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

app = Gtk.Application(application_id='io.github.haplinux.TestApp')

def activate(app):
    window = Gtk.ApplicationWindow(application=app, title='HAP Integration Fixture')
    window.set_default_size(640, 420)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                  margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
    window.set_child(box)
    button = Gtk.Button(label='Activate test target')
    button.connect('clicked', lambda *_: Path(os.environ['HAP_TEST_MARKER']).write_text('activated'))
    box.append(button)
    box.append(Gtk.CheckButton(label='Test checkbox'))
    box.append(Gtk.Entry(placeholder_text='Editable text'))
    disabled = Gtk.Button(label='Disabled target')
    disabled.set_sensitive(False)
    box.append(disabled)
    window.present()

app.connect('activate', activate)
app.run(None)

import json
import os
from pathlib import Path
import subprocess
import time
from gi.repository import Gio, GLib

connection = Gio.bus_get_sync(Gio.BusType.SESSION)
directory = Path(os.environ['GRID_TEST_DIR'])
marker = directory / 'events.json'

def shell(method, signature='()', values=()):
    return connection.call_sync('org.gnome.Shell', '/io/github/gridclick/Test', 'io.github.gridclick.Test',
        method, GLib.Variant(signature, values), None, Gio.DBusCallFlags.NONE, 5000, None).unpack()

def state():
    return json.loads(shell('State')[0])

def key(value, pressed):
    shell('Key', '(ub)', (value, pressed))
    time.sleep(.04)

def stroke(value):
    key(value, True)
    key(value, False)

def shortcut():
    key(0xffeb, True)
    key(0xffe1, True)
    stroke(ord('g'))
    key(0xffe1, False)
    key(0xffeb, False)
    assert state()['overlay'] and state()['grab'], state()

def events():
    return json.loads(marker.read_text()) if marker.exists() else []

def select_target():
    r = state()['frame']
    target = (r['x'] + r['width'] * .6, r['y'] + r['height'] * .6)
    for _ in range(4):
        cells = state()['grid']['cells']
        cell = next(c for c in cells if c['x'] <= target[0] < c['x'] + c['width'] and c['y'] <= target[1] < c['y'] + c['height'])
        stroke(ord(cell['key'].lower()))
    return state()['grid']['point']

fixture = subprocess.Popen(['/usr/bin/python3', 'tests/fixture.py'])
try:
    for _ in range(60):
        try:
            if state()['frame']:
                break
        except GLib.Error:
            pass
        time.sleep(.2)
    assert state()['frame'], 'Fixture window did not open'
    shell('Prepare')
    time.sleep(1)
    shortcut()
    initial = state()['grid']
    assert len(initial['monitors']) == 2, initial
    shell('Capture', '(s)', (str(directory / 'grid.png'),))
    stroke(ord('q'))
    assert state()['grid']['area']['width'] == initial['area']['width'] / 3
    stroke(0xff08)
    assert state()['grid']['point'] == initial['point']
    stroke(0xff09)
    assert state()['grid']['index'] != initial['index']
    stroke(0xff09)
    assert state()['grid']['index'] == initial['index']
    stroke(0xff1b)
    assert not state()['overlay'] and not state()['grab'] and not events()
    print('PASS: shortcut, grid refinement, undo, monitor switching, Escape without clicks', flush=True)

    for trigger, button, count in [(0xff0d, 1, 1), (ord(' '), 1, 2), (ord('r'), 3, 1)]:
        time.sleep(.5)
        previous = len(events())
        shortcut()
        point = select_target()
        stroke(0xff53)  # Right: one logical pixel.
        assert state()['grid']['point'] == [point[0] + 1, point[1]]
        point = state()['grid']['point']
        shell('Capture', '(s)', (str(directory / 'refined.png'),))
        stroke(trigger)
        for _ in range(40):
            if len(events()) >= previous + count * 2 and not state()['clicking']:
                break
            time.sleep(.05)
        actual = events()[previous:]
        assert len(actual) == count * 2, actual
        assert [e['kind'] for e in actual] == ['press', 'release'] * count, actual
        assert all(e['button'] == button for e in actual), actual
        if count == 2:
            assert actual[-1]['n'] == 2, actual
        final = state()
        assert not final['overlay'] and not final['grab'], final
        assert all(abs(final['pointer'][i] - point[i]) <= 1 for i in (0, 1)), (final, point)
        r = final['frame']
        assert abs(actual[0]['x'] + r['x'] - point[0]) <= 1, actual
        assert abs(actual[0]['y'] + r['y'] - point[1]) <= 1, actual
        print(f'PASS: real Wayland button={button}, clicks={count}, correct application coordinates, GTK_A11Y=none', flush=True)
finally:
    fixture.terminate()
    fixture.wait(timeout=5)

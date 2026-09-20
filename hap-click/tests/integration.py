"""Run only on the isolated test D-Bus session created by integration.sh."""
import json
import os
from pathlib import Path
import subprocess
import time
from gi.repository import Gio, GLib

BUS = 'io.github.haplinux.Controller'
connection = Gio.bus_get_sync(Gio.BusType.SESSION)

def call(method, signature, args):
    return connection.call_sync(BUS, '/io/github/haplinux/Controller', BUS, method,
        GLib.Variant(signature, args), None, Gio.DBusCallFlags.NONE, 10000, None).unpack()

def shell(method, signature='()', args=()):
    return connection.call_sync('org.gnome.Shell', '/io/github/haplinux/Test',
        'io.github.haplinux.Test', method, GLib.Variant(signature, args), None,
        Gio.DBusCallFlags.NONE, 3000, None).unpack()

def state():
    return json.loads(shell('State')[0])

def key(keyval, pressed):
    shell('Key', '(ub)', (keyval, pressed))
    time.sleep(.05)

def stroke(keyval):
    key(keyval, True)
    key(keyval, False)

def shortcut():
    key(0xffeb, True)  # Super_L
    key(0xffe1, True)  # Shift_L
    stroke(ord('f'))
    key(0xffe1, False)
    key(0xffeb, False)

def wait_hints():
    for _ in range(70):
        result = state()
        if result.get('hints'):
            return result
        time.sleep(.1)
    raise AssertionError(f'No overlay hints: {result}')

fixture = subprocess.Popen(['/usr/bin/python3', 'tests/demo.py'])
try:
    payload = None
    for attempt in range(30):
        time.sleep(.3)
        try:
            payload = json.loads(call('Scan', '(us)', (fixture.pid, 'HAP Integration Fixture'))[0])
            if payload['hints']:
                break
        except GLib.Error as error:
            if attempt == 29:
                raise
    assert payload and payload['hints'], payload
    names = [hint['name'] for hint in payload['hints']]
    assert 'Disabled target' not in names, names
    selected = next(h for h in payload['hints'] if h['name'] == 'Activate test target')
    assert call('Activate', '(ss)', (payload['session'], selected['label'])) == (True,)
    for _ in range(30):
        if Path(os.environ['HAP_TEST_MARKER']).exists():
            break
        time.sleep(.1)
    assert Path(os.environ['HAP_TEST_MARKER']).read_text() == 'activated'
    print(f'PASS: real GTK4 Wayland scan ({len(names)} hints), disabled filtering, AT-SPI Action')
    try:
        call('Activate', '(ss)', (payload['session'], selected['label']))
        raise AssertionError('Replayed session accepted')
    except GLib.Error:
        print('PASS: replay rejected')
    payload = json.loads(call('Scan', '(us)', (fixture.pid, 'HAP Integration Fixture'))[0])
    call('Cancel', '(s)', (payload['session'],))
    try:
        call('Activate', '(ss)', (payload['session'], payload['hints'][0]['label']))
        raise AssertionError('Cancelled session accepted')
    except GLib.Error:
        print('PASS: cancellation rejected subsequent activation')
    Path(os.environ['HAP_TEST_MARKER']).unlink()
    shell('Prepare', '(s)', ('HAP Integration Fixture',))
    time.sleep(1)
    shortcut()
    result = wait_hints()
    assert result['overlay'] and result['grab'], result
    print(f"PASS: real GNOME global shortcut, modal overlay ({len(result['hints'])} labels)")
    stroke(0xff1b)  # Escape
    assert not state()['overlay'] and not state()['grab']
    assert not Path(os.environ['HAP_TEST_MARKER']).exists()
    print('PASS: real Escape releases overlay and keyboard grab without action')
    shortcut()
    result = wait_hints()
    selected = next(h for h in result['hints'] if h['name'] == 'Activate test target')
    assert len(selected['label']) > 1, 'Fixture must exercise multi-letter hints'
    stroke(ord(selected['label'][0].lower()))
    assert state()['prefix'] == selected['label'][0]
    stroke(0xff08)  # Backspace
    assert state()['prefix'] == ''
    assert all(h['visible'] for h in state()['hints'])
    print('PASS: prefix filtering and Backspace restores hints')
    for letter in selected['label']:
        stroke(ord(letter.lower()))
    for _ in range(30):
        if Path(os.environ['HAP_TEST_MARKER']).exists():
            break
        time.sleep(.1)
    assert Path(os.environ['HAP_TEST_MARKER']).read_text() == 'activated'
    assert not state()['overlay'] and not state()['grab']
    print('PASS: real hint key -> overlay cleanup -> AT-SPI Action -> GTK clicked signal')
finally:
    fixture.terminate()
    fixture.wait(timeout=5)

# Exercise the real file manager, not just a standalone GTK button.
folder = Path(os.environ['HAP_TEST_DIR']) / 'HAP Files Fixture'
child = folder / 'HAP Open Target'
child.mkdir(parents=True)
(folder / 'AAA Other Folder').mkdir()
(folder / 'ZZZ Other Folder').mkdir()
files = subprocess.Popen(['nautilus', '--new-window', str(folder)])
try:
    time.sleep(5)
    shell('Prepare', '(s)', (folder.name,))
    time.sleep(1)
    shortcut()
    result = wait_hints()
    selected = next(h for h in result['hints'] if h['name'].startswith(child.name))
    print('Files selection:', selected, result['appId'], flush=True)
    shell('Capture', '(s)', (str(folder.parent / 'before.png'),))
    for letter in selected['label']:
        stroke(ord(letter.lower()))
    for _ in range(30):
        result = state()
        if result['focus'] == child.name:
            break
        time.sleep(.1)
    shell('Capture', '(s)', (str(folder.parent / 'after.png'),))
    assert result['focus'] == child.name, result
    assert abs(result['pointer'][0] - (selected['x'] + 12)) <= 1, (selected, result)
    assert abs(result['pointer'][1] - (selected['y'] + 10)) <= 1, (selected, result)
    assert not result['overlay'] and not result['grab'], result
    print('PASS: real Nautilus hint keys open the selected folder')
finally:
    files.terminate()
    files.wait(timeout=5)

if os.environ.get('HAP_TEST_CODE'):
    exec(compile(Path('tests/code_geometry.py').read_text(), 'tests/code_geometry.py', 'exec'))

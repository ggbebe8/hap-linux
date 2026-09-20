# Runs inside the isolated integration session, using its helpers.
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
profile = Path(os.environ['HAP_TEST_DIR']) / 'code-profile'
log = (profile.parent / 'code.log').open('w')
code = subprocess.Popen(['/usr/share/code/code', '--no-sandbox', '--disable-gpu',
    '--ozone-platform=wayland', '--force-renderer-accessibility', '--disable-extensions',
    '--skip-welcome', '--skip-release-notes', '--user-data-dir=' + str(profile),
    '--shared-data-dir=' + str(profile.parent / 'code-shared'),
    '--extensions-dir=' + str(profile.parent / 'code-extensions'),
    '--disable-workspace-trust', '--disable-updates', '--password-store=basic', '--locale=en',
    '--new-window'], stdout=log, stderr=log)
try:
    for _ in range(150):
        windows = json.loads(shell('Windows')[0])
        window = next((w for w in windows if 'Visual Studio Code' in w['title']), None)
        if window:
            break
        time.sleep(.2)
    assert window, windows
    shell('Prepare', '(s)', (window['title'],))
    time.sleep(8)
    window = next(w for w in json.loads(shell('Windows')[0]) if w['pid'] == window['pid'])
    shell('Resize')
    time.sleep(3)
    for _ in range(20):
        current = state()
        payload = json.loads(call('Scan', '(us)', (window['pid'], current['focus']))[0])
        if any(h['name'].startswith('Toggle Panel') for h in payload['hints']):
            break
        time.sleep(.5)
    assert any(h['name'].startswith('Toggle Panel') for h in payload['hints']), payload
    call('Cancel', '(s)', (payload['session'],))
    shortcut()
    result = wait_hints()
    shell('Capture', '(s)', (str(profile.parent / 'code-hints.png'),))
    selected = next(h for h in result['hints'] if h['name'].startswith('Toggle Panel'))
    assert selected['pointer'], selected
    for letter in selected['label']:
        stroke(ord(letter.lower()))
    time.sleep(1)
    after = state()
    assert abs(after['pointer'][0] - selected['x'] - 12) <= 1, (selected, after)
    assert abs(after['pointer'][1] - selected['y'] - 10) <= 1, (selected, after)
    shell('Capture', '(s)', (str(profile.parent / 'code-panel.png'),))
    # Inspect the panel directly: its tabs need not expose a clickable Action.
    Atspi.init()
    desktop = Atspi.get_desktop(0)
    app = next(desktop.get_child_at_index(i) for i in range(desktop.get_child_count())
               if desktop.get_child_at_index(i).get_process_id() == window['pid'])
    pending, found = [app], False
    while pending:
        node = pending.pop()
        if node.get_name() == 'Output':
            found = node.get_state_set().contains(Atspi.StateType.SHOWING)
            if found:
                break
        pending.extend(node.get_child_at_index(i) for i in range(node.get_child_count()))
    assert found, 'The actual Output panel tab was not visible after the hint click'
    print('PASS: real VSCode hint location matches pointer and opens the panel')
finally:
    code.terminate()
    code.wait(timeout=10)
    log.close()

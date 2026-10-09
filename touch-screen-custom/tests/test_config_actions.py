from unittest.mock import Mock, patch
import pytest
from touchgesture.config import ConfigError, load_config
from touchgesture.actions import ActionExecutor, UInputExecutor
from touchgesture.cli import main


@pytest.mark.parametrize('text', [
    'dry_run: yesplease', 'dry_run: false\ndry_run: true',
    'recognition:\n  dominance_ratio: 1', 'recognition:\n  min_point_distance: .nan',
    'recognition:\n  min_point_distnce: 8', 'device:\n  auto_detect: false',
    'gestures: []', 'gestures:\n - name: bad\n   sequence: [DOWM, RIGHT]\n   action: {type: key, keys: [CTRL, W]}',
    'gestures:\n - name: bad\n   sequence: [DOWN, RIGHT]\n   action: {type: key, keys: [NOPE]}',
    'gestures:\n - name: bad\n   sequence: [DOWN, RIGHT]\n   action: {type: command, command: " "}',
    '[]', 'null', 'device: null',
])
def test_invalid_config(tmp_path, text):
    p = tmp_path/'bad.yaml'
    p.write_text(text)
    with pytest.raises(ConfigError):
        load_config(p)


def test_missing_explicit_config(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path/'missing')


def test_dry_run_opens_nothing():
    gestures = load_config()['gestures']
    gestures += [{'name':'cmd','action': {'type':'command','command':'echo hello'}}]
    with patch('touchgesture.actions.UInput') as uinput, patch('touchgesture.actions.subprocess.Popen') as popen:
        executor = ActionExecutor(gestures, True)
        for gesture in gestures:
            executor.execute(gesture)
        executor.close()
        uinput.assert_not_called()
        popen.assert_not_called()


def test_command_no_implicit_shell():
    gesture = {'name':'test','action':{'type':'command','command': "notify-send 'gesture detected'"}}
    with patch('touchgesture.actions.subprocess.Popen') as popen:
        ex = ActionExecutor([gesture],False)
        ex.execute(gesture)
        assert popen.call_args.args[0] == ['notify-send','gesture detected']
        assert 'shell' not in popen.call_args.kwargs


def test_key_chord_released_in_reverse():
    from evdev import ecodes as e
    with patch('touchgesture.actions.UInput') as factory, patch('touchgesture.actions.time.sleep'):
        backend = UInputExecutor(['CTRL','W'])
        backend.send(['CTRL','W'])
        writes = [c.args for c in factory.return_value.write.call_args_list]
        assert writes == [(e.EV_KEY,e.KEY_LEFTCTRL,1),(e.EV_KEY,e.KEY_W,1),(e.EV_KEY,e.KEY_W,0),(e.EV_KEY,e.KEY_LEFTCTRL,0)]
        backend.close()
        factory.return_value.close.assert_called_once()


def test_partial_press_released_on_error():
    from evdev import ecodes as e
    with patch('touchgesture.actions.UInput') as factory, patch('touchgesture.actions.time.sleep'):
        factory.return_value.write.side_effect = [None,OSError('failed'),None]
        backend = UInputExecutor(['CTRL','W'])
        with pytest.raises(OSError):
            backend.send(['CTRL','W'])
        assert factory.return_value.write.call_args.args == (e.EV_KEY,e.KEY_LEFTCTRL,0)


def test_cli_check_config_no_hardware():
    with patch('touchgesture.cli.select_device') as select:
        assert main(['--check-config']) == 0
        select.assert_not_called()


def test_virtual_keyboard_has_udev_keyboard_capabilities():
    from evdev import ecodes as e
    with patch('touchgesture.actions.UInput') as factory, patch('touchgesture.actions.time.sleep'):
        UInputExecutor(['CTRL','W'])
        assert set(range(1,32)).issubset(factory.call_args.args[0][e.EV_KEY])

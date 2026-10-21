from unittest.mock import Mock, patch
import pytest
from evdev import InputEvent, ecodes as e
from touchgesture.input import StrokeRecorder, TwoFingerRecorder
from touchgesture.config import load_config, ConfigError
from touchgesture.recognition import recognize, match
from touchgesture.rotation import DisplayState, rotate_points


def frame(changes, ms):
    sec, usec = divmod(ms*1000, 1000000)
    return [InputEvent(sec,usec,e.EV_ABS,code,value) for code,value in changes] + [InputEvent(sec,usec,e.EV_SYN,e.SYN_REPORT,0)]


def down(slot,tid,x,y):
    return [(e.ABS_MT_SLOT,slot),(e.ABS_MT_TRACKING_ID,tid),(e.ABS_MT_POSITION_X,x),(e.ABS_MT_POSITION_Y,y)]


def move(slot,x,y):
    return [(e.ABS_MT_SLOT,slot),(e.ABS_MT_POSITION_X,x),(e.ABS_MT_POSITION_Y,y)]


def lift(slot):
    return [(e.ABS_MT_SLOT,slot),(e.ABS_MT_TRACKING_ID,-1)]


def swipe(mode='valid',rotation=0):
    # Screen-space paths, mapped back to raw coordinates for portrait tests.
    def xy(x,y):
        return (y,1000-x) if rotation == 90 else (x,y)
    start2 = 300 if mode == 'late' else 50
    events = frame(down(0,1,*xy(300,200)),0)
    events += frame(down(1,2,*xy(600,200)),start2)
    if mode == 'third':
        events += frame(down(2,3,*xy(800,200))+lift(2),start2+10)
    if mode == 'replacement':
        events += frame(lift(1)+down(1,3,*xy(600,200)),start2+10)
    end1 = (600,500) if mode == 'diagonal' else (300,500)
    end2 = (600,200) if mode == 'stationary' else ((600,0) if mode == 'opposite' else (600,500))
    if mode == 'short':
        end1,end2 = (300,220),(600,220)
    events += frame(move(0,*xy(*end1))+move(1,*xy(*end2)),start2+150)
    events += frame(lift(0),start2+200)
    events += frame(lift(1),2000 if mode == 'slow_release' else start2+250)
    return events


def record(events,held=False):
    single = StrokeRecorder(lambda x,y:(x/1000,y/1000))
    single.blocked = held
    pair = TwoFingerRecorder(single)
    singles, pairs = [],[]
    for event in events:
        a = single.feed(event)
        b = pair.feed(event)
        if a is not None:
            singles.append(a)
        if b is not None:
            pairs.append(b)
    return singles,pairs


def cfg():
    config = load_config()
    config['device']['rotation'] = 0
    config['recognition'].update(distance_mode='normalized',min_point_distance=.005,
                                simplify_epsilon=.015,min_segment_distance=.08,min_total_distance=.18)
    return config


def detect(pair,rotation=0):
    config = cfg()
    results = [recognize(rotate_points(p,DisplayState(0,'test',rotation//90),config),config['recognition']) for p in pair]
    if any(r.reason for r in results) or results[0].sequence != results[1].sequence:
        return None
    return match(results[0],config['gestures'],fingers=2)


@pytest.mark.parametrize('rotation',[0,90])
def test_both_down_and_rotated(rotation):
    singles,pairs = record(swipe(rotation=rotation))
    assert not singles and len(pairs) == 1
    assert detect(pairs[0],rotation)['action']['keys'] == ['CTRL','Q']


@pytest.mark.parametrize('mode',['late','third','replacement','slow_release'])
def test_invalid_contacts_cancel(mode):
    assert record(swipe(mode)) == ([],[])


@pytest.mark.parametrize('mode',['stationary','opposite','diagonal','short'])
def test_both_fingers_must_match(mode):
    singles,pairs = record(swipe(mode))
    assert not singles and len(pairs) == 1
    assert detect(pairs[0]) is None


def test_startup_held_contacts_ignored():
    assert record(swipe(),held=True) == ([],[])


def test_no_action_until_last_finger_released():
    events = swipe()
    assert record(events[:-3]) == ([],[])


def test_recovers_after_cancel_and_emits_once():
    singles,pairs = record(swipe('third')+swipe())
    assert not singles and len(pairs) == 1


def test_one_finger_down_does_not_close_window():
    events = frame(down(0,1,300,200),0)+frame(move(0,300,500),100)+frame(lift(0),200)
    singles,pairs = record(events)
    assert not pairs
    config = cfg()
    assert match(recognize(singles[0],config['recognition']),config['gestures']) is None


def test_cli_two_finger_alt_f4():
    from touchgesture.cli import main
    dev = Mock()
    dev.read_loop.return_value = iter(swipe(rotation=90))
    rec = StrokeRecorder(lambda x,y:(x/1000,y/1000))
    rec.blocked = False
    config = cfg()
    config['device']['rotation'] = 90
    with patch('touchgesture.cli.load_config',return_value=config), \
         patch('touchgesture.cli.select_device',return_value=dev), \
         patch('touchgesture.cli.describe',return_value='test'), \
         patch('touchgesture.cli.initialize_recorder',return_value=rec), \
         patch('touchgesture.cli.ActionExecutor') as executor:
        assert main(['--dry-run','--no-preview']) == 1  # simulated disconnect
        executor.return_value.execute.assert_called_once()
        assert executor.return_value.execute.call_args.args[0]['name'] == 'close_window'


@pytest.mark.parametrize('fingers',['0','3','true','"2"'])
def test_invalid_finger_config(tmp_path,fingers):
    p = tmp_path/'config.yaml'
    p.write_text(f'gestures:\n - name: test\n   fingers: {fingers}\n   sequence: [DOWN]\n   action: {{type: key, keys: [ALT, F4]}}\n')
    with pytest.raises(ConfigError,match='fingers'):
        load_config(p)


def test_same_sequence_allowed_for_different_finger_counts(tmp_path):
    p = tmp_path/'config.yaml'
    p.write_text('gestures:\n - name: one\n   sequence: [DOWN]\n   action: {type: key, keys: [W]}\n - name: two\n   fingers: 2\n   sequence: [DOWN]\n   action: {type: key, keys: [ALT, F4]}\n')
    assert len(load_config(p)['gestures']) == 2

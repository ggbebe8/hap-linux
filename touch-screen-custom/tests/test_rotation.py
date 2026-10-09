from unittest.mock import Mock, patch
import pytest
from evdev import AbsInfo, ecodes as e
from touchgesture.config import load_config, ConfigError
from touchgesture.input import axes, is_touchscreen, supported
from touchgesture.recognition import Point, recognize, match
from touchgesture.rotation import DisplayState, StrokeOrientation, parse_state, rotate_points


def payload(transform=1, serial=1):
    return {'data': [serial,
        [[['eDP-1','vendor','panel','serial'], [], {'is-builtin': {'type':'b','data':True}}]],
        [[0,0,1.0,transform,True,[['eDP-1','vendor','panel','serial']],{}]], {}]}


def normalized():
    cfg = load_config()
    cfg['recognition'].update(distance_mode='normalized', min_point_distance=.005,
                             simplify_epsilon=.015, min_segment_distance=.08, min_total_distance=.18)
    return cfg


@pytest.mark.parametrize('transform,raw', [
    (0,[(.2,.2),(.2,.6),(.6,.6)]),
    (1,[(.2,.8),(.6,.8),(.6,.4)]),
    (2,[(.8,.8),(.8,.4),(.4,.4)]),
    (3,[(.8,.2),(.4,.2),(.4,.6)]),
    (4,[(.8,.2),(.8,.6),(.4,.6)]),
    (5,[(.2,.2),(.6,.2),(.6,.6)]),
    (6,[(.2,.8),(.2,.4),(.6,.4)]),
    (7,[(.8,.8),(.4,.8),(.4,.4)]),
])
@pytest.mark.parametrize('reverse_vertical,name', [(False,'close_tab'),(True,'next_tab')])
def test_gesture_in_every_orientation(transform,raw,reverse_vertical,name):
    cfg = normalized()
    points = [Point(x,y,i*.1) for i,(x,y) in enumerate(raw)]
    rotated = rotate_points(points,DisplayState(1,'eDP-1',transform),cfg)
    if reverse_vertical:
        # Reflect screen Y, then map back to raw coordinates to test UP.
        from touchgesture.rotation import MATRICES
        a,b,c,d,e_,f = MATRICES[transform]
        targets = [(p.x,1-p.y,p.t) for p in rotated]
        inverse = [Point(a*(x-c)+d*(y-f),b*(x-c)+e_*(y-f),t) for x,y,t in targets]
        rotated = rotate_points(inverse,DisplayState(1,'eDP-1',transform),cfg)
    result = recognize(rotated,cfg['recognition'])
    assert match(result,cfg['gestures'])['name'] == name


def test_pixel_dimensions_rotate():
    cfg = load_config()
    assert rotate_points([Point(1,0,0)],DisplayState(0,'manual',1),cfg) == [Point(1200,1920,0)]


def test_builtin_selected_even_with_external_primary():
    data = payload()
    data['data'][2].insert(0,[0,0,1.0,0,True,[['HDMI-1','v','p','s']],{}])
    assert parse_state(data).connector == 'eDP-1'
    assert parse_state(data,'HDMI-1').transform == 0


def test_ambiguous_or_inactive_display_rejected():
    data = payload()
    with pytest.raises(RuntimeError):
        parse_state(data,'missing')
    data['data'][1][0][2] = {}
    data['data'][2].append([0,0,1.0,0,True,[['HDMI-1','v','p','s']],{}])
    with pytest.raises(RuntimeError):
        parse_state(data)


def test_single_external_display():
    data = payload()
    data['data'][1][0][2] = {}
    assert parse_state(data).transform == 1


def test_mid_stroke_rotation_cancelled_then_next_stroke_succeeds():
    a,b = DisplayState(1,'eDP-1',0),DisplayState(2,'eDP-1',1)
    reader = Mock(side_effect=[a,b,b,b])
    orientation = StrokeOrientation(normalized(),reader)
    orientation.begin()
    assert orientation.finish([Point(.2,.2,0)]) is None
    orientation.begin()
    assert orientation.finish([Point(.2,.8,0)]) == [Point(pytest.approx(.2),.2,0)]


def test_read_failure_cancels_without_stale_rotation():
    reader = Mock(side_effect=[DisplayState(1,'eDP-1',0),RuntimeError('offline')])
    orientation = StrokeOrientation(normalized(),reader)
    orientation.begin()
    assert orientation.finish([Point(.2,.2,0)]) is None


def test_manual_mode_never_queries_dbus():
    cfg = normalized()
    cfg['device']['rotation'] = 270
    reader = Mock()
    orientation = StrokeOrientation(cfg,reader)
    orientation.begin()
    assert orientation.finish([Point(.2,.3,0)]) == [Point(.3,.8,0)]
    reader.assert_not_called()


@pytest.mark.parametrize('mode',['auto',0,90,180,270])
def test_rotation_config(tmp_path,mode):
    p = tmp_path/'settings.yaml'
    p.write_text(f'device:\n  rotation: {mode}\n  display_connector: eDP-1\n')
    assert str(load_config(p)['device']['rotation']) == str(mode)


def test_invalid_rotation(tmp_path):
    p = tmp_path/'settings.yaml'
    p.write_text('device:\n  rotation: 45\n')
    with pytest.raises(ConfigError):
        load_config(p)


def test_real_evdev_capability_shape_regression():
    class Device:
        def capabilities(self,absinfo=True):
            codes = [e.ABS_MT_SLOT,e.ABS_MT_TRACKING_ID,e.ABS_MT_POSITION_X,e.ABS_MT_POSITION_Y]
            return {e.EV_ABS:[(c,AbsInfo(0,0,1000,0,0,0)) for c in codes] if absinfo else codes,
                    e.EV_KEY:[e.BTN_TOUCH]}
        def input_props(self):
            return [e.INPUT_PROP_DIRECT]
    assert is_touchscreen(Device()) and supported(Device())
    assert axes(Device()) == (e.ABS_MT_POSITION_X,e.ABS_MT_POSITION_Y)


def test_cli_follows_rotation_between_strokes():
    from evdev import InputEvent
    from touchgesture.cli import main
    from touchgesture.input import StrokeRecorder
    events = []
    tick = 0
    for tid,coords in [(1,[(200,200),(200,600),(600,600)]),
                       (2,[(200,800),(600,800),(600,400)])]:
        events.append(InputEvent(0,tick,e.EV_ABS,e.ABS_MT_TRACKING_ID,tid))
        for x,y in coords:
            events.extend([InputEvent(0,tick,e.EV_ABS,e.ABS_MT_POSITION_X,x),
                           InputEvent(0,tick,e.EV_ABS,e.ABS_MT_POSITION_Y,y),
                           InputEvent(0,tick,e.EV_SYN,e.SYN_REPORT,0)])
            tick += 100000
        events.extend([InputEvent(0,tick,e.EV_ABS,e.ABS_MT_TRACKING_ID,-1),
                       InputEvent(0,tick,e.EV_SYN,e.SYN_REPORT,0)])
        tick += 100000
    dev = Mock()
    dev.read_loop.return_value = iter(events)
    rec = StrokeRecorder(lambda x,y:(x/1000,y/1000))
    rec.blocked = False
    cfg = normalized()
    a,b = DisplayState(1,'eDP-1',0),DisplayState(2,'eDP-1',1)
    with patch('touchgesture.cli.load_config',return_value=cfg), \
         patch('touchgesture.cli.select_device',return_value=dev), \
         patch('touchgesture.cli.describe',return_value='test screen'), \
         patch('touchgesture.cli.initialize_recorder',return_value=rec), \
         patch('touchgesture.cli.ActionExecutor') as executor, \
         patch.object(StrokeOrientation,'current',side_effect=[a,a,a,b,b]):
        # The simulated device disconnects after both strokes (exit 1).
        assert main(['--dry-run','--no-preview']) == 1
        calls = executor.return_value.execute.call_args_list
        assert [call.args[0]['name'] for call in calls] == ['close_tab','close_tab']
        dev.close.assert_called_once()

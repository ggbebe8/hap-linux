from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from touchgesture.config import load_config, ConfigError
from touchgesture.preview import GesturePreview
from touchgesture.recognition import Point
from touchgesture.rotation import DisplayState, StrokeOrientation


def setup(dry_run=False):
    cfg = load_config()
    cfg['device']['rotation'] = 0
    cfg['recognition'].update(distance_mode='normalized', min_point_distance=.005,
                             simplify_epsilon=.015,min_segment_distance=.08,min_total_distance=.18)
    ui = Mock()
    preview = GesturePreview(cfg,ui,dry_run)
    orientation = StrokeOrientation(cfg)
    orientation.begin()
    single = SimpleNamespace(contacts={0:object()},blocked=False,points=[])
    pair = SimpleNamespace(ended=False,blocked=False,tracks={},started_at=0)
    return preview,ui,single,pair,orientation


def test_live_match_then_extra_corner_hides_then_lift_hides():
    p,ui,single,pair,o = setup()
    single.points = [Point(0,0,0),Point(0,.3,.1),Point(.3,.3,.2)]
    p.update(.2,single,pair,o,o)
    assert ui.show.call_args.args[0] == ('탭 닫기', '↓→')
    assert ui.show.call_args.args[1] == pytest.approx(1.3)
    single.points.append(Point(.3,.6,.3))
    p.update(.3,single,pair,o,o)
    assert ui.show.call_args.args == ()
    single.contacts = {}
    p.update(.31,single,pair,o,o)
    assert ui.show.call_args.args == ()


def test_diagonal_and_short_path_no_preview():
    p,ui,single,pair,o = setup()
    for t,pts in [(0,[Point(0,0,0),Point(.02,0,0)]),(.1,[Point(0,0,0),Point(.3,.3,.1)])]:
        single.points = pts
        p.update(t,single,pair,o,o)
        assert ui.show.call_args.args == ()


def test_dry_run_shows_only_action_and_arrows():
    p,ui,single,pair,o = setup(True)
    single.points = [Point(0,0,0),Point(0,.3,.1),Point(.3,.3,.2)]
    p.update(.2,single,pair,o,o)
    assert ui.show.call_args.args[0] == ('탭 닫기', '↓→')


def test_two_finger_preview_and_first_lift():
    p,ui,single,pair,o = setup()
    single.contacts[1] = object()
    single.blocked = True
    pair.tracks = {1:[Point(.2,.1,0),Point(.2,.5,.2)],2:[Point(.5,.1,0),Point(.5,.5,.2)]}
    p.update(.2,single,pair,o,o)
    assert ui.show.call_args.args[0] == ('현재 창 닫기', '↓')
    pair.ended = True
    p.update(.21,single,pair,o,o)
    assert ui.show.call_args.args == ()


def test_rotation_change_rejects_preview():
    p,ui,single,pair,o = setup()
    single.points = [Point(0,0,0),Point(0,.3,.1),Point(.3,.3,.2)]
    o.current = lambda:DisplayState(1,'manual',1)
    p.update(.2,single,pair,o,o)
    assert ui.show.call_args.args == ()


def test_cancel_hides_even_between_throttled_frames():
    p,ui,single,pair,o = setup()
    single.points = [Point(0,0,0),Point(0,.3,.1),Point(.3,.3,.2)]
    p.update(.2,single,pair,o,o)
    single.blocked = True
    p.update(.201,single,pair,o,o)
    assert ui.show.call_args.args == ()


@pytest.mark.parametrize('text',['preview: yesplease', 'gestures:\n - name: x\n   label: 123\n   sequence: [DOWN]\n   action: {type: key, keys: [W]}'])
def test_invalid_preview_config(tmp_path,text):
    path = tmp_path/'config.yaml'
    path.write_text(text)
    with pytest.raises(ConfigError):
        load_config(path)


def test_last_move_before_hold_is_not_throttled_away():
    p,ui,single,pair,o = setup()
    single.points = [Point(0,0,0),Point(0,.3,.1),Point(.07,.3,.2)]
    p.update(.2,single,pair,o,o)
    assert ui.show.call_args.args == ()
    single.points.append(Point(.2,.3,.205))
    p.update(.205,single,pair,o,o)
    assert ui.show.call_args.args[0] == ('탭 닫기', '↓→')


def test_cli_preview_precedes_release_and_action():
    from unittest.mock import patch
    from evdev import InputEvent, ecodes as e
    from touchgesture.input import StrokeRecorder
    from touchgesture.cli import main
    preview,_,_,_,_ = setup()
    config = preview.cfg
    config['dry_run'] = False
    events = [InputEvent(0,0,e.EV_ABS,e.ABS_MT_TRACKING_ID,1)]
    for t,x,y in [(0,100,100),(100000,100,400),(200000,400,400)]:
        events += [InputEvent(0,t,e.EV_ABS,e.ABS_MT_POSITION_X,x),
                   InputEvent(0,t,e.EV_ABS,e.ABS_MT_POSITION_Y,y),
                   InputEvent(0,t,e.EV_SYN,e.SYN_REPORT,0)]
    events += [InputEvent(0,300000,e.EV_ABS,e.ABS_MT_TRACKING_ID,-1),
               InputEvent(0,300000,e.EV_SYN,e.SYN_REPORT,0)]
    device = Mock()
    device.read_loop.return_value = iter(events)
    recorder = StrokeRecorder(lambda x,y:(x/1000,y/1000))
    recorder.blocked = False
    journal = []
    with patch('touchgesture.cli.load_config',return_value=config), \
         patch('touchgesture.cli.select_device',return_value=device), \
         patch('touchgesture.cli.describe',return_value='test'), \
         patch('touchgesture.cli.initialize_recorder',return_value=recorder), \
         patch('touchgesture.cli.OverlayPreview') as ui, \
         patch('touchgesture.cli.ActionExecutor') as executor:
        executor.return_value.dry_run = False
        executor.return_value.execute.side_effect = lambda g:journal.append('execute')
        ui.return_value.show.side_effect = lambda *args:journal.append('show' if args else 'hide')
        assert main([]) == 1  # simulated device disconnect
    assert 'show' in journal
    assert journal.index('show') < len(journal)-1
    assert journal[-2:] == ['hide','execute']


def test_previous_tab_preview_disappears_when_path_changes():
    p,ui,single,pair,o = setup()
    single.points = [Point(.6,.6,0),Point(.6,.3,.1),Point(.3,.3,.2)]
    p.update(.2,single,pair,o,o)
    assert ui.show.call_args.args[0] == ('이전 탭', '↑←')
    single.points.append(Point(.3,.6,.3))
    p.update(.3,single,pair,o,o)
    assert ui.show.call_args.args == ()

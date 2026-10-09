import pytest
from evdev import InputEvent, ecodes as e
from touchgesture.input import StrokeRecorder


def event(typ, code, value, t=0):
    return InputEvent(0, t, typ, code, value)


def frame(rec, changes, t=0):
    for code, value in changes:
        rec.feed(event(e.EV_ABS, code, value, t))
    return rec.feed(event(e.EV_SYN, e.SYN_REPORT, 0, t))


def recorder():
    r = StrokeRecorder(lambda x,y:(x,y))
    frame(r, [])
    return r


def down(r, slot=0, tid=1, t=0):
    return frame(r, [(e.ABS_MT_SLOT,slot),(e.ABS_MT_TRACKING_ID,tid),(e.ABS_MT_POSITION_X,100),(e.ABS_MT_POSITION_Y,100)],t)


def test_coherent_frame_and_lift():
    r = recorder()
    assert down(r) is None
    assert frame(r, [(e.ABS_MT_POSITION_Y,300)],100000) is None
    assert frame(r, [(e.ABS_MT_POSITION_X,300)],200000) is None
    pts = frame(r, [(e.ABS_MT_TRACKING_ID,-1)],300000)
    assert [(p.x,p.y) for p in pts] == [(100,100),(100,300),(300,300),(300,300)]
    assert pts[-1].t == .3
    assert frame(r, []) is None


def test_multitouch_cancels_until_all_up():
    r = recorder()
    down(r)
    down(r,1,2)
    assert frame(r,[(e.ABS_MT_TRACKING_ID,-1)]) is None
    frame(r,[(e.ABS_MT_SLOT,0),(e.ABS_MT_POSITION_X,500)])
    assert frame(r,[(e.ABS_MT_TRACKING_ID,-1)]) is None
    down(r)
    assert frame(r,[(e.ABS_MT_TRACKING_ID,-1)]) is not None


def test_transient_second_contact_same_frame():
    r = recorder()
    down(r)
    frame(r,[(e.ABS_MT_SLOT,1),(e.ABS_MT_TRACKING_ID,2),(e.ABS_MT_TRACKING_ID,-1)])
    assert frame(r,[(e.ABS_MT_SLOT,0),(e.ABS_MT_TRACKING_ID,-1)]) is None


def test_replaced_contact_not_joined():
    r = recorder()
    down(r)
    frame(r,[(e.ABS_MT_TRACKING_ID,-1),(e.ABS_MT_TRACKING_ID,2),(e.ABS_MT_POSITION_X,300),(e.ABS_MT_POSITION_Y,300)])
    assert frame(r,[(e.ABS_MT_TRACKING_ID,-1)]) is None


def test_startup_held_contact_discarded():
    r = StrokeRecorder(lambda x,y:(x,y))
    down(r)
    assert frame(r,[(e.ABS_MT_TRACKING_ID,-1)]) is None


def test_dropped_events_fail_closed():
    r = recorder()
    down(r)
    with pytest.raises(RuntimeError, match='SYN_DROPPED'):
        r.feed(event(e.EV_SYN,e.SYN_DROPPED,0))


def test_long_stroke_memory_bounded():
    r = recorder()
    down(r)
    frame(r,[(e.ABS_MT_POSITION_X,300)],2000000)
    assert r.blocked and not r.points
    assert frame(r,[(e.ABS_MT_TRACKING_ID,-1)],2100000) is None


def test_single_touch():
    r = StrokeRecorder(lambda x,y:(x,y),multitouch=False)
    frame(r,[])
    frame(r,[(e.ABS_X,10),(e.ABS_Y,20)])
    r.feed(event(e.EV_KEY,e.BTN_TOUCH,1))
    frame(r,[])
    frame(r,[(e.ABS_Y,200)],100000)
    r.feed(event(e.EV_KEY,e.BTN_TOUCH,0,200000))
    pts = frame(r,[],200000)
    assert pts[0].x == 10 and pts[-1].y == 200


def test_slot_coordinates_persist_across_contacts():
    r = recorder()
    down(r)
    frame(r,[(e.ABS_MT_TRACKING_ID,-1)])
    # Kernel need not resend an axis whose value has not changed.
    frame(r,[(e.ABS_MT_TRACKING_ID,2),(e.ABS_MT_POSITION_Y,200)])
    pts = frame(r,[(e.ABS_MT_TRACKING_ID,-1)])
    assert pts[0].x == 100 and pts[0].y == 200


def test_coordinate_mapping_with_nonzero_ranges_and_rotation():
    from types import SimpleNamespace
    from touchgesture.config import load_config
    from touchgesture.input import make_transform
    class Device:
        def capabilities(self, absinfo=True):
            return {e.EV_ABS: [e.ABS_X,e.ABS_Y]}
        def absinfo(self, code):
            return SimpleNamespace(min=100,max=1100 if code == e.ABS_X else 2100)
    cfg = load_config()
    assert make_transform(Device(),cfg)(600,1100) == (960,600)
    cfg['recognition']['distance_mode'] = 'normalized'
    cfg['device']['swap_axes'] = True
    cfg['device']['invert_y'] = True
    assert make_transform(Device(),cfg)(100,2100) == (1,1)


def test_startup_queries_slots_and_discards_existing_contact(monkeypatch):
    from types import SimpleNamespace
    from touchgesture.config import load_config
    from touchgesture.input import initialize_recorder
    class Device:
        fd = 123
        def capabilities(self, absinfo=True):
            return {e.EV_ABS: [e.ABS_MT_SLOT,e.ABS_MT_POSITION_X,e.ABS_MT_POSITION_Y]}
        def absinfo(self, code):
            if code == e.ABS_MT_SLOT:
                return SimpleNamespace(min=0,max=1,value=1)
            return SimpleNamespace(min=0,max=1000,value=100)
    values = {e.ABS_MT_TRACKING_ID:[-1,4], e.ABS_MT_POSITION_X:[10,20],e.ABS_MT_POSITION_Y:[30,40]}
    def ioctl(fd,request,buf,mutate):
        assert fd == 123 and mutate
        for i,v in enumerate(values[buf[0]],1):
            buf[i] = v
    monkeypatch.setattr('fcntl.ioctl',ioctl)
    rec = initialize_recorder(Device(),load_config())
    assert rec.blocked and rec.slot == 1
    assert rec.positions[0] == (10,30)
    assert rec.contacts[1].tracking == 4
    assert frame(rec,[(e.ABS_MT_TRACKING_ID,-1)]) is None
    assert not rec.blocked


class SelectionDevice:
    def __init__(self, name, multitouch=False, pen=False):
        from unittest.mock import Mock
        from types import SimpleNamespace
        self.name = name
        self.path = '/dev/input/test'
        self.close = Mock()
        self.absinfo = lambda code: SimpleNamespace(min=0, max=1000)
        self.caps = {e.EV_ABS: [e.ABS_X, e.ABS_Y], e.EV_KEY: [e.BTN_TOUCH]}
        if multitouch:
            self.caps[e.EV_ABS] += [e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y,
                                    e.ABS_MT_SLOT, e.ABS_MT_TRACKING_ID]
        if pen:
            self.caps[e.EV_KEY] += [e.BTN_TOOL_PEN, e.BTN_TOOL_RUBBER, e.BTN_STYLUS]

    def capabilities(self, absinfo=True):
        assert absinfo is False
        return self.caps

    def input_props(self):
        return [e.INPUT_PROP_DIRECT]


def test_surface_touch_selected_without_pen_even_with_same_name(monkeypatch):
    from touchgesture.input import select_device
    touch = SelectionDevice('ELAN9038:00 04F3:2A1C', multitouch=True)
    pen = SelectionDevice(touch.name, pen=True)
    monkeypatch.setattr('touchgesture.input.devices', lambda: [pen, touch])
    assert select_device({}) is touch
    pen.close.assert_called_once()
    touch.close.assert_not_called()


@pytest.mark.parametrize('multitouch,pen,expected', [
    (False,False,True), (False,True,False), (True,False,True), (True,True,True),
])
def test_touch_and_pen_capabilities(multitouch,pen,expected):
    from touchgesture.input import is_touchscreen
    assert is_touchscreen(SelectionDevice('device',multitouch,pen)) is expected


def test_two_real_touchscreens_still_require_selection(monkeypatch):
    from touchgesture.input import select_device
    devices = [SelectionDevice('screen1',True), SelectionDevice('screen2',True)]
    monkeypatch.setattr('touchgesture.input.devices', lambda: devices)
    with pytest.raises(RuntimeError, match='Found 2 matching touchscreens'):
        select_device({})
    for dev in devices:
        dev.close.assert_called_once()

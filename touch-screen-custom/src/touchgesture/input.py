"""Passive Linux input acquisition and frame-based type B stroke recording."""
import logging
from dataclasses import dataclass
from evdev import InputDevice, ecodes as e, list_devices
from .recognition import Point

log = logging.getLogger(__name__)


def axes(dev):
    codes = dev.capabilities(absinfo=False).get(e.EV_ABS, [])
    if e.ABS_MT_POSITION_X in codes and e.ABS_MT_POSITION_Y in codes:
        return e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y
    return e.ABS_X, e.ABS_Y


def is_touchscreen(dev):
    caps = dev.capabilities(absinfo=False)
    codes = caps.get(e.EV_ABS, [])
    # A screen's pen node also reports DIRECT, X/Y and BTN_TOUCH. Those
    # capabilities alone do not distinguish it from a single-touch screen.
    # Keep devices with finger MT axes, including combined touch/pen nodes.
    multitouch = e.ABS_MT_POSITION_X in codes and e.ABS_MT_POSITION_Y in codes
    pen_keys = {e.BTN_TOOL_PEN, e.BTN_TOOL_RUBBER, e.BTN_STYLUS, e.BTN_STYLUS2}
    if not multitouch and pen_keys.intersection(caps.get(e.EV_KEY, [])):
        return False
    x, y = axes(dev)
    return e.INPUT_PROP_DIRECT in dev.input_props() and x in codes and y in codes


def supported(dev):
    codes = dev.capabilities(absinfo=False).get(e.EV_ABS, [])
    if e.ABS_MT_POSITION_X in codes:
        return e.ABS_MT_SLOT in codes and e.ABS_MT_TRACKING_ID in codes
    return e.BTN_TOUCH in dev.capabilities(absinfo=False).get(e.EV_KEY, [])


def devices():
    result = []
    # glob includes inaccessible event nodes, unlike list_devices on some versions.
    from glob import glob
    for path in sorted(set(list_devices()) | set(glob('/dev/input/event*'))):
        try:
            result.append(InputDevice(path))
        except OSError as exc:
            log.warning("Cannot open %s: %s", path, exc)
    return result


def describe(dev):
    touch = is_touchscreen(dev)
    text = f"{dev.path}: {dev.name} | touchscreen: {'yes' if touch else 'no'}"
    if touch:
        x, y = (dev.absinfo(code) for code in axes(dev))
        text += f" | INPUT_PROP_DIRECT | X: {x.min}..{x.max}, Y: {y.min}..{y.max} | supported: {supported(dev)}"
    return text


def select_device(cfg):
    if cfg.get("path"):
        dev = InputDevice(cfg["path"])
        if not is_touchscreen(dev) or not supported(dev):
            dev.close()
            raise RuntimeError("Selected device is not a supported direct touchscreen (type B or single-touch)")
        return dev
    opened = devices()
    candidates = []
    try:
        for dev in opened:
            if is_touchscreen(dev):
                log.info("Detected touchscreen: %s", describe(dev))
                if supported(dev) and cfg.get("name_contains", "").lower() in dev.name.lower():
                    candidates.append(dev)
        if len(candidates) != 1:
            raise RuntimeError(f"Found {len(candidates)} matching touchscreens; set device.path or name_contains. Check input permissions with --list-devices.")
        chosen = candidates[0]
    except BaseException:
        for dev in opened:
            dev.close()
        raise
    for dev in opened:
        if dev is not chosen:
            dev.close()
    return chosen


@dataclass
class Contact:
    tracking: int
    x: float | None = None
    y: float | None = None


class StrokeRecorder:
    """Consume complete SYN_REPORT frames; never join different contacts.

    A second contact cancels until all contacts are lifted, even if the second
    finger appears and disappears within one frame. Startup waits for idle.
    """
    def __init__(self, transform, multitouch=True, slot=0, max_duration_ms=1500):
        self.transform = transform
        self.multitouch = multitouch
        self.slot = slot
        self.contacts = {}
        self.positions = {}  # MT axes persist per slot, even across contacts.
        self.blocked = True
        self.points = []
        self.identity = None
        self.single_x = self.single_y = None
        self.max_duration = max_duration_ms / 1000
        self.ended = None
        self.force_cancel = False

    def feed(self, event):
        if event.type == e.EV_SYN and event.code == e.SYN_DROPPED:
            # Caller must reopen and resync from kernel, never use stale slots.
            raise RuntimeError("SYN_DROPPED: input events lost; restart to resynchronize")
        if event.type == e.EV_ABS:
            if self.multitouch:
                if event.code == e.ABS_MT_SLOT:
                    self.slot = event.value
                elif event.code == e.ABS_MT_TRACKING_ID:
                    old = self.contacts.get(self.slot)
                    if old and old.tracking == self.identity:
                        self.ended = old
                    if event.value < 0:
                        self.contacts.pop(self.slot, None)
                    else:
                        x, y = self.positions.get(self.slot, (None, None))
                        self.contacts[self.slot] = Contact(event.value, x, y)
                        if len(self.contacts) > 1 or (self.identity is not None and self.identity != event.value):
                            self.force_cancel = True
                elif event.code in (e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y):
                    x, y = self.positions.get(self.slot, (None, None))
                    if event.code == e.ABS_MT_POSITION_X:
                        x = event.value
                    else:
                        y = event.value
                    self.positions[self.slot] = (x, y)
                    if self.slot in self.contacts:
                        self.contacts[self.slot].x = x
                        self.contacts[self.slot].y = y
            else:
                if event.code == e.ABS_X:
                    self.single_x = event.value
                elif event.code == e.ABS_Y:
                    self.single_y = event.value
        if not self.multitouch and event.type == e.EV_KEY and event.code == e.BTN_TOUCH:
            if event.value:
                self.contacts[0] = Contact(0, self.single_x, self.single_y)
            else:
                self.ended = self.contacts.pop(0, None)
        if event.type != e.EV_SYN or event.code != e.SYN_REPORT:
            return None
        t = event.timestamp()
        if not self.multitouch and 0 in self.contacts:
            self.contacts[0].x, self.contacts[0].y = self.single_x, self.single_y
        result = None
        if len(self.contacts) > 1 or self.force_cancel:
            self.blocked = True
            self.points = []
            log.debug("CANCEL: multiple/replaced contacts")
        if not self.contacts:
            if self.points and not self.blocked:
                c = self.ended
                if c is not None and c.x is not None and c.y is not None:
                    x, y = self.transform(c.x, c.y)
                else:
                    x, y = self.points[-1].x, self.points[-1].y
                self.points.append(Point(x, y, t))
                result = self.points
                log.debug("TOUCH_UP; raw path: %s", result)
            self.points = []
            self.identity = None
            self.blocked = False
        elif not self.blocked:
            c = next(iter(self.contacts.values()))
            if c.x is not None and c.y is not None:
                x, y = self.transform(c.x, c.y)
                if self.points and (t - self.points[0].t > self.max_duration or len(self.points) >= 8192):
                    log.debug("CANCEL: duration or point limit")
                    self.blocked, self.points = True, []
                else:
                    log.debug("%s x=%.4f y=%.4f", "MOVE" if self.points else "TOUCH_DOWN", x, y)
                    self.points.append(Point(x, y, t))
                    self.identity = c.tracking
        self.ended = None
        self.force_cancel = False
        return result


def make_transform(dev, cfg):
    x, y = (dev.absinfo(code) for code in axes(dev))
    if x.max <= x.min or y.max <= y.min:
        raise RuntimeError("Device has invalid coordinate ranges")
    dc = cfg["device"]
    def transform(raw_x, raw_y):
        nx, ny = (raw_x-x.min)/(x.max-x.min), (raw_y-y.min)/(y.max-y.min)
        if dc["swap_axes"]:
            nx, ny = ny, nx
        if dc["invert_x"]:
            nx = 1-nx
        if dc["invert_y"]:
            ny = 1-ny
        if cfg["recognition"]["distance_mode"] == "pixels":
            nx, ny = nx * dc["screen_width"], ny * dc["screen_height"]
        return nx, ny
    return transform


def initialize_recorder(dev, cfg):
    """Query current contacts; discard a stroke already underway at startup."""
    import array
    import fcntl
    mt = e.ABS_MT_SLOT in dev.capabilities(absinfo=False).get(e.EV_ABS, [])
    slot_info = dev.absinfo(e.ABS_MT_SLOT) if mt else None
    recorder = StrokeRecorder(make_transform(dev, cfg), mt, slot_info.value if mt else 0,
                              cfg["recognition"]["max_gesture_duration_ms"])
    if mt:
        count = slot_info.max + 1
        if slot_info.min != 0 or not 1 <= count <= 256:
            raise RuntimeError("Unsupported multitouch slot range")
        def values(code):
            buf = array.array('i', [code] + [0] * count)
            # Linux EVIOCGMTSLOTS(len): _IOC(_IOC_READ, 'E', 0x0a, len).
            request = (2 << 30) | (len(buf)*buf.itemsize << 16) | (ord('E') << 8) | 0x0a
            fcntl.ioctl(dev.fd, request, buf, True)
            return buf[1:]
        ids, xs, ys = values(e.ABS_MT_TRACKING_ID), values(e.ABS_MT_POSITION_X), values(e.ABS_MT_POSITION_Y)
        recorder.positions = {i: (xs[i], ys[i]) for i in range(count)}
        recorder.contacts = {i: Contact(tid, xs[i], ys[i]) for i, tid in enumerate(ids) if tid >= 0}
    else:
        recorder.single_x = dev.absinfo(e.ABS_X).value
        recorder.single_y = dev.absinfo(e.ABS_Y).value
        if e.BTN_TOUCH in dev.active_keys():
            recorder.contacts[0] = Contact(0, recorder.single_x, recorder.single_y)
    recorder.blocked = bool(recorder.contacts)
    return recorder


class TwoFingerRecorder:
    """Observe the primary recorder's contact state, without enabling its actions.

    Record each finger only while both are down. Finish once all fingers lift.
    Late joins, replacement contacts and a third finger cancel until idle.
    Call feed AFTER StrokeRecorder.feed for every event.
    """
    def __init__(self, recorder):
        self.recorder = recorder
        self.blocked = recorder.blocked
        self.started_at = None
        self.ids = set()
        self.tracks = {}
        self.ended = False

    def feed(self, event):
        if not self.recorder.multitouch:
            return None
        if not ((event.type == e.EV_ABS and event.code == e.ABS_MT_TRACKING_ID) or
                (event.type == e.EV_SYN and event.code == e.SYN_REPORT)):
            return None
        t = event.timestamp()
        contacts = self.recorder.contacts
        if event.type == e.EV_ABS and event.code == e.ABS_MT_TRACKING_ID:
            if event.value >= 0:
                if self.started_at is None:
                    self.started_at = t
                if self.ended or event.value in self.ids:
                    self.blocked = True
                self.ids.add(event.value)
                if len(self.ids) > 2 or (len(self.ids) == 2 and t-self.started_at > .2):
                    self.blocked = True
            else:
                self.ended = True
        if event.type != e.EV_SYN or event.code != e.SYN_REPORT:
            return None
        if self.started_at is not None and t-self.started_at > self.recorder.max_duration:
            self.blocked = True
        result = None
        if not contacts:
            if not self.blocked and len(self.tracks) == 2 and all(len(track) >= 2 for track in self.tracks.values()):
                result = []
                for track in self.tracks.values():
                    last = track[-1]
                    result.append(track + [Point(last.x, last.y, t)])
                log.debug('TWO_FINGER_UP; recorded both paths')
            self.blocked = False
            self.started_at = None
            self.ids = set()
            self.tracks = {}
            self.ended = False
        elif not self.blocked and not self.ended and len(contacts) == 2:
            if all(c.x is not None and c.y is not None for c in contacts.values()):
                for c in contacts.values():
                    track = self.tracks.setdefault(c.tracking, [])
                    if len(track) >= 8192:
                        self.blocked = True
                        self.tracks = {}
                        break
                    x, y = self.recorder.transform(c.x, c.y)
                    track.append(Point(x, y, t))
                    log.debug('TWO_FINGER_MOVE id=%d x=%.4f y=%.4f', c.tracking, x, y)
        return result

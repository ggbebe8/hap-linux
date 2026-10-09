"""Apply cached display orientation at stroke boundaries."""
from dataclasses import dataclass
import logging
from .recognition import Point

log = logging.getLogger(__name__)
# Same normalized input matrices as Mutter's meta-monitor-manager.c.
MATRICES = (
    (1, 0, 0, 0, 1, 0), (0, -1, 1, 1, 0, 0),
    (-1, 0, 1, 0, -1, 1), (0, 1, 0, -1, 0, 1),
    (-1, 0, 1, 0, 1, 0), (0, 1, 0, 1, 0, 0),
    (1, 0, 0, 0, -1, 1), (0, -1, 1, -1, 0, 1),
)


@dataclass(frozen=True)
class DisplayState:
    serial: int
    connector: str
    transform: int
    generation: int = 0


def parse_state(payload, connector=None):
    """Select an explicit output, the built-in panel, or a sole display."""
    try:
        serial, monitors, logical, _ = payload['data']
        def is_builtin(m):
            value = m[2].get('is-builtin', False)
            if isinstance(value, dict):
                return value.get('data') is True
            return getattr(value, 'value', value) is True
        builtin = {m[0][0] for m in monitors if is_builtin(m)}
        candidates = []
        for monitor in logical:
            names = [spec[0] for spec in monitor[5]]
            selected = [n for n in names if n == connector] if connector else [n for n in names if n in builtin]
            if selected:
                candidates.append((selected[0], monitor[3]))
        if not candidates and not connector and not builtin and len(logical) == 1:
            candidates = [(logical[0][5][0][0], logical[0][3])]
        if len(candidates) != 1:
            raise RuntimeError('Cannot identify active touchscreen display; set device.display_connector or use --rotation 0/90/180/270')
        name, transform = candidates[0]
        if type(transform) is not int or transform not in range(8):
            raise ValueError('invalid display transform')
        return DisplayState(serial, name, transform)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError(f'Invalid GNOME display state: {exc}') from exc


def rotate_points(points, state, cfg):
    a, b, c, d, e, f = MATRICES[state.transform]
    width, height = 1, 1
    if cfg['recognition']['distance_mode'] == 'pixels':
        width, height = cfg['device']['screen_width'], cfg['device']['screen_height']
        if state.transform % 2:
            width, height = height, width
    return [Point((a*p.x+b*p.y+c)*width, (d*p.x+e*p.y+f)*height, p.t) for p in points]


class StrokeOrientation:
    def __init__(self, cfg, reader=None):
        self.cfg = cfg
        self.reader = reader
        self.start = None
        self.last = None

    def current(self):
        mode = str(self.cfg['device']['rotation'])
        if mode == 'auto':
            if self.reader is None:
                raise RuntimeError('Automatic rotation requires a display monitor')
            return self.reader(self.cfg['device'].get('display_connector'))
        return DisplayState(0, 'manual', int(mode)//90)

    def begin(self):
        self.start = None
        try:
            self.start = self.current()
            display = (self.start.connector, self.start.transform)
            if self.last != display:
                log.info('Display: %s | rotation=%d°%s', display[0], (display[1] % 4)*90,
                         ' flipped' if display[1] >= 4 else '')
                self.last = display
        except RuntimeError as exc:
            log.warning('Stroke cancelled: %s', exc)

    def finish(self, points):
        start, self.start = self.start, None
        if start is None:
            return None
        try:
            if start != self.current():
                log.info('Stroke cancelled: display configuration changed during touch')
                return None
        except RuntimeError as exc:
            log.warning('Stroke cancelled: %s', exc)
            return None
        return rotate_points(points, start, self.cfg)

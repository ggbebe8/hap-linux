"""Read-only prediction of what releasing the current stroke would execute."""
from .recognition import match, recognize
from .rotation import rotate_points

ARROWS = {'DOWN':'↓','UP':'↑','LEFT':'←','RIGHT':'→'}


class GesturePreview:
    def __init__(self, cfg, ui, dry_run=False):
        self.cfg = cfg
        self.ui = ui
        self.dry_run = dry_run
        self.last_sample = None

    def hide(self):
        self.last_sample = None
        self.ui.show()

    def update(self, timestamp, single, pair, orientation, two_orientation):
        if not single.contacts or (pair.ended and pair.tracks):
            self.hide()
            self.last_sample = None
            return
        if not pair.blocked and len(pair.tracks) == 2 and len(single.contacts) == 2:
            tracks = list(pair.tracks.values())
            fingers, orient, started = 2, two_orientation, pair.started_at
        elif not single.blocked and single.points and len(single.contacts) == 1:
            tracks = [single.points]
            fingers, orient, started = 1, orientation, single.points[0].t
        else:
            self.hide()
            return
        remaining = self.cfg['recognition']['max_gesture_duration_ms']/1000 - (timestamp-started)
        if remaining <= 0:
            self.hide()
            return
        try:
            if orient.start is None or orient.start != orient.current():
                self.hide()
                return
        except RuntimeError:
            self.hide()
            return
        # Evaluate each changed frame, including the last move before a hold.
        # Identical coordinates need no work; the UI owns the expiry timer.
        sample = (fingers, orient.start, tuple((points[0], points[-1].x, points[-1].y) for points in tracks))
        if sample == self.last_sample:
            return
        self.last_sample = sample
        results = [recognize(rotate_points(points, orient.start, self.cfg), self.cfg['recognition']) for points in tracks]
        if any(r.reason for r in results) or any(r.sequence != results[0].sequence for r in results):
            self.hide()
            return
        gesture = match(results[0], self.cfg['gestures'], fingers=fingers)
        if gesture is None:
            self.hide()
            return
        label = gesture.get('label', gesture['name'])
        path = ''.join(ARROWS[d] for d in gesture['sequence'])
        self.ui.show((label, path), remaining)

    def close(self):
        self.ui.close()

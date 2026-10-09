"""Hardware-independent filtering, RDP simplification and exact matching."""
from dataclasses import dataclass
from math import acos, degrees, hypot


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    t: float  # monotonic seconds


@dataclass(frozen=True)
class Result:
    sequence: tuple[str, ...]
    points: tuple[Point, ...]
    reason: str = ""


def distance(a, b):
    return hypot(b.x - a.x, b.y - a.y)


def simplify(points, epsilon):
    """Iterative RDP avoids recursion limits on noisy strokes."""
    if len(points) < 3:
        return points
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        a, b = points[first], points[last]
        dx, dy = b.x - a.x, b.y - a.y
        length2 = dx * dx + dy * dy
        best, index = 0, first
        for i in range(first + 1, last):
            p = points[i]
            u = max(0, min(1, ((p.x-a.x)*dx + (p.y-a.y)*dy) / length2)) if length2 else 0
            d = hypot(p.x-a.x-u*dx, p.y-a.y-u*dy)
            if d > best:
                best, index = d, i
        if best > epsilon:
            keep.add(index)
            stack.extend(((first, index), (index, last)))
    return [points[i] for i in sorted(keep)]


def direction(a, b, ratio):
    dx, dy = b.x-a.x, b.y-a.y
    if abs(dx) > abs(dy) * ratio:
        return "RIGHT" if dx > 0 else "LEFT"
    if abs(dy) > abs(dx) * ratio:
        return "DOWN" if dy > 0 else "UP"
    return "UNKNOWN"


def recognize(raw, cfg):
    def reject(reason, points=(), seq=()):
        return Result(tuple(seq), tuple(points), reason)
    if len(raw) < 2:
        return reject("too few points")
    elapsed = raw[-1].t - raw[0].t
    if elapsed < 0 or elapsed * 1000 > cfg["max_gesture_duration_ms"]:
        return reject("stroke too slow or invalid timestamps")
    filtered = [raw[0]]
    for p in raw[1:]:
        if distance(filtered[-1], p) >= cfg["min_point_distance"]:
            filtered.append(p)
    if distance(filtered[-1], raw[-1]) > 0:
        filtered.append(raw[-1])
    points = simplify(filtered, cfg["simplify_epsilon"])
    # Merge consecutive collinear-direction segments, preserving real reversals.
    merged = []
    for p in points:
        merged.append(p)
        while len(merged) >= 3:
            a, b, c = merged[-3:]
            d = direction(a, b, cfg["dominance_ratio"])
            if d == "UNKNOWN" or d != direction(b, c, cfg["dominance_ratio"]):
                break
            merged.pop(-2)
    points = merged
    seq = [direction(a, b, cfg["dominance_ratio"]) for a, b in zip(points, points[1:])]
    if "UNKNOWN" in seq:
        return reject("ambiguous or diagonal segment", points, seq)
    lengths = [distance(a, b) for a, b in zip(points, points[1:])]
    if not lengths or min(lengths) < cfg["min_segment_distance"]:
        return reject("segment too short", points, seq)
    if sum(lengths) < cfg["min_total_distance"]:
        return reject("stroke too short", points, seq)
    for a, b, c in zip(points, points[1:], points[2:]):
        dot = (b.x-a.x)*(c.x-b.x) + (b.y-a.y)*(c.y-b.y)
        angle = degrees(acos(max(-1, min(1, dot/(distance(a, b)*distance(b, c))))))
        if not cfg["corner_min_angle_deg"] <= angle <= cfg["corner_max_angle_deg"]:
            return reject("invalid corner angle", points, seq)
    return Result(tuple(seq), tuple(points))


def match(result, gestures, fingers=1):
    if result.reason:
        return None
    return next((g for g in gestures if tuple(g["sequence"]) == result.sequence and g.get("fingers", 1) == fingers), None)

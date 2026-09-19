"""Pure, testable hint and geometry logic (no desktop dependency)."""
from dataclasses import dataclass

ALPHABET = 'ASDFJKL'


def labels(count, alphabet=ALPHABET):
    if count < 0 or len(alphabet) < 2 or len(set(alphabet)) != len(alphabet):
        raise ValueError('Invalid hint count or alphabet')
    width = 1
    while len(alphabet) ** width < count:
        width += 1
    result = []
    for number in range(count):
        word = ''
        for _ in range(width):
            word = alphabet[number % len(alphabet)] + word
            number //= len(alphabet)
        result.append(word)
    return result


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_atspi(cls, rect):
        return cls(rect.x, rect.y, rect.width, rect.height)

    def normalized(self, window):
        """Clip to the window and return its visible center as fractions."""
        if min(self.width, self.height, window.width, window.height) <= 0:
            return None
        left, top = max(self.x, window.x), max(self.y, window.y)
        right = min(self.x + self.width, window.x + window.width)
        bottom = min(self.y + self.height, window.y + window.height)
        if right <= left or bottom <= top:
            return None
        return ((left + right) / 2 - window.x) / window.width, ((top + bottom) / 2 - window.y) / window.height


def choose_window(candidates, title):
    """Candidates are (accessible, name, active). Never guess among windows."""
    exact = [item for item in candidates if item[1] == title]
    if len(exact) == 1:
        return exact[0][0]
    active = [item for item in (exact or candidates) if item[2]]
    if len(active) == 1:
        return active[0][0]
    if len(candidates) == 1:
        return candidates[0][0]
    raise RuntimeError('활성 창을 AT-SPI 창과 확실하게 연결할 수 없습니다.')


def preferred_action(names):
    for preferred in ('click', 'press', 'activate', 'jump', 'open', 'toggle', 'select'):
        for index, name in enumerate(names):
            if name.lower().rsplit('.', 1)[-1] == preferred:
                return index
    return None

"""AT-SPI calls run on the controller's single worker thread."""
import time
from dataclasses import dataclass

import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib

from .core import Rect, choose_window, labels, preferred_action

POINTER_ROLES = {
    'button', 'push button', 'toggle button', 'link', 'menu item',
    'check box', 'radio button', 'tab', 'tree item', 'list item',
    'list box', 'combo box', 'spin button', 'entry', 'text',
}


@dataclass
class Target:
    accessible: object
    action_index: int
    action_name: str
    name: str
    rect: Rect
    window_rect: Rect | None = None
    pointer: bool = False


class Accessibility:
    def __init__(self):
        Atspi.init()
        Atspi.set_timeout(150, 500)

    def scan(self, pid, title, cancelled):
        deadline = time.monotonic() + 4
        def check():
            if cancelled.is_set():
                raise RuntimeError('탐색이 취소되었습니다.')
            if time.monotonic() > deadline:
                raise TimeoutError('AT-SPI 탐색 시간이 초과되었습니다. 앱 응답을 확인하세요.')

        desktop = Atspi.get_desktop(0)
        windows = []
        for i in range(desktop.get_child_count()):
            check()
            try:
                app = desktop.get_child_at_index(i)
                if app.get_process_id() != pid:
                    continue
                for j in range(min(app.get_child_count(), 256)):
                    check()
                    win = app.get_child_at_index(j)
                    states = win.get_state_set()
                    if states.contains(Atspi.StateType.SHOWING):
                        windows.append((win, win.get_name(), states.contains(Atspi.StateType.ACTIVE)))
            except GLib.Error:
                continue
        root = choose_window(windows, title)
        component = root.get_component_iface()
        if component is None:
            raise RuntimeError('이 창은 AT-SPI Component를 제공하지 않습니다.')
        window_rect = Rect.from_atspi(component.get_extents(Atspi.CoordType.WINDOW))
        if min(window_rect.width, window_rect.height) <= 0:
            raise RuntimeError('이 앱이 유효한 창 좌표를 제공하지 않습니다.')
        stack, targets, visited, truncated = [root], [], 0, False
        while stack:
            check()
            node = stack.pop()
            visited += 1
            if visited > 4000 or len(targets) >= 500:
                truncated = True
                break
            try:
                states = node.get_state_set()
                if states.contains(Atspi.StateType.DEFUNCT):
                    continue
                # Do not prune invisible containers: some toolkits omit their state.
                if all(states.contains(s) for s in (Atspi.StateType.SHOWING, Atspi.StateType.VISIBLE, Atspi.StateType.SENSITIVE)):
                    action = node.get_action_iface()
                    component = node.get_component_iface()
                    if component is not None:
                        names = ([action.get_action_name(i) for i in range(min(action.get_n_actions(), 32))]
                                 if action is not None else [])
                        index = preferred_action(names)
                        role = (node.get_role_name() or '').strip().lower()
                        pointer = index is None and ('listitem.scroll-to' in names or role in POINTER_ROLES)
                        if pointer and 'listitem.scroll-to' in names:
                            index = names.index('listitem.scroll-to')
                        rect = Rect.from_atspi(component.get_extents(Atspi.CoordType.WINDOW))
                        if (index is not None or pointer) and rect.normalized(window_rect) is not None:
                            targets.append(Target(node, index if index is not None else -1,
                                                  names[index] if index is not None else '',
                                                  node.get_name(), rect, window_rect, pointer))
                count = node.get_child_count()
                if count > 4000:
                    truncated = True
                for i in reversed(range(min(count, 4000))):
                    check()
                    child = node.get_child_at_index(i)
                    if child is not None:
                        stack.append(child)
            except GLib.Error:
                continue
        targets.sort(key=lambda target: (target.rect.y, target.rect.x))
        hints, refs = [], {}
        for label, target in zip(labels(len(targets)), targets):
            x, y = target.rect.normalized(window_rect)
            hints.append(dict(label=label, name=target.name[:160], x=x, y=y, pointer=target.pointer))
            refs[label] = target
        return dict(hints=hints, truncated=truncated), refs

    def validate(self, target, cancelled):
        if cancelled.is_set():
            raise RuntimeError('취소된 선택입니다.')
        node = target.accessible
        node.clear_cache()
        states = node.get_state_set()
        if states.contains(Atspi.StateType.DEFUNCT) or not all(states.contains(s) for s in (Atspi.StateType.SHOWING, Atspi.StateType.SENSITIVE)):
            raise RuntimeError('선택한 요소가 사라졌거나 비활성화되었습니다.')
        rect = Rect.from_atspi(node.get_component_iface().get_extents(Atspi.CoordType.WINDOW))
        action = node.get_action_iface()
        if rect != target.rect or node.get_name() != target.name:
            raise RuntimeError('UI가 변경되었습니다. 단축키로 다시 탐색하세요.')
        if not target.pointer and (action is None or action.get_action_name(target.action_index) != target.action_name):
            raise RuntimeError('UI가 변경되었습니다. 단축키로 다시 탐색하세요.')
        return action

    def prepare_click(self, target, cancelled):
        action = self.validate(target, cancelled)
        if not target.pointer:
            raise RuntimeError('마우스 보완 처리가 허용되지 않는 요소입니다.')
        names = ([action.get_action_name(i) for i in range(min(action.get_n_actions(), 32))]
                 if action is not None else [])
        if preferred_action(names) is not None or cancelled.is_set():
            raise RuntimeError('UI가 변경되었습니다. 단축키로 다시 탐색하세요.')
        return target.rect.normalized(target.window_rect)

    def activate(self, target, cancelled):
        action = self.validate(target, cancelled)
        if target.pointer:
            raise RuntimeError('이 요소는 클릭 보완 처리가 필요합니다.')
        if cancelled.is_set() or not action.do_action(target.action_index):
            raise RuntimeError('앱이 AT-SPI Action 실행을 거부했습니다.')
        return True

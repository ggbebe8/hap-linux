import threading
import unittest
from unittest.mock import Mock, patch

from hap.accessibility import Accessibility, Atspi
from hap.core import Rect


class ScanCoordinatesTests(unittest.TestCase):
    def test_hint_and_pointer_reply_share_the_same_coordinate_space(self):
        def accessible(name, bounds, role, children=()):
            node = Mock()
            node.get_name.return_value = name
            node.get_role_name.return_value = role
            node.get_state_set.return_value.contains.side_effect = lambda s: s != Atspi.StateType.DEFUNCT
            node.get_action_iface.return_value = None
            node.get_component_iface.return_value.get_extents.side_effect = (
                lambda coord: bounds if coord == Atspi.CoordType.WINDOW else Rect(0, 0, bounds.width, bounds.height))
            node.get_child_count.return_value = len(children)
            node.get_child_at_index.side_effect = lambda i: children[i]
            return node

        button = accessible('Target', Rect(10, 20, 30, 40), 'push button')
        window = accessible('Test Window', Rect(0, 0, 100, 100), 'frame', [button])
        app = accessible('Test App', Rect(0, 0, 100, 100), 'application', [window])
        app.get_process_id.return_value = 123
        desktop = accessible('Desktop', Rect(0, 0, 100, 100), 'desktop', [app])
        backend = Accessibility.__new__(Accessibility)
        cancelled = threading.Event()
        with patch.object(Atspi, 'get_desktop', return_value=desktop):
            payload, refs = backend.scan(123, 'Test Window', cancelled)
        self.assertEqual(len(payload['hints']), 1)
        hint = payload['hints'][0]
        self.assertEqual((hint['x'], hint['y']), (.25, .4))
        self.assertEqual(backend.prepare_click(refs[hint['label']], cancelled), (hint['x'], hint['y']))
        self.assertEqual(payload['bounds'], dict(width=100, height=100))
        app.clear_cache.assert_called_once()

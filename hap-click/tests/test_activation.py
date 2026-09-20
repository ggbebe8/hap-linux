import threading
import unittest
from unittest.mock import Mock
from hap.accessibility import Accessibility, Target
from hap.core import Rect


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.node = Mock()
        from hap.accessibility import Atspi
        self.node.get_state_set.return_value.contains.side_effect = lambda state: state != Atspi.StateType.DEFUNCT
        self.node.get_component_iface.return_value.get_extents.return_value = Rect(10, 20, 30, 40)
        self.node.get_name.return_value = 'Test'
        self.action = self.node.get_action_iface.return_value
        self.action.get_action_name.return_value = 'click'
        self.action.do_action.return_value = True
        self.target = Target(self.node, 0, 'click', 'Test', Rect(10, 20, 30, 40))
        self.backend = Accessibility.__new__(Accessibility)
        self.cancelled = threading.Event()

    def test_action_runs_once(self):
        self.assertTrue(self.backend.activate(self.target, self.cancelled))
        self.action.do_action.assert_called_once_with(0)

    def test_moved_target_is_rejected(self):
        self.node.get_component_iface.return_value.get_extents.return_value = Rect(50, 20, 30, 40)
        with self.assertRaises(RuntimeError):
            self.backend.activate(self.target, self.cancelled)
        self.action.do_action.assert_not_called()

    def test_cancelled_target_is_rejected(self):
        self.cancelled.set()
        with self.assertRaises(RuntimeError):
            self.backend.activate(self.target, self.cancelled)
        self.action.do_action.assert_not_called()

    def test_replaced_target_is_rejected(self):
        self.node.get_name.return_value = 'New button'
        with self.assertRaises(RuntimeError):
            self.backend.activate(self.target, self.cancelled)
        self.action.do_action.assert_not_called()

    def test_failed_action_is_reported(self):
        self.action.do_action.return_value = False
        with self.assertRaises(RuntimeError):
            self.backend.activate(self.target, self.cancelled)

    def test_pointer_fallback_validates_without_running_scroll_action(self):
        self.target.pointer = True
        self.target.window_rect = Rect(0, 0, 100, 100)
        self.target.action_name = 'listitem.scroll-to'
        self.action.get_action_name.return_value = 'listitem.scroll-to'
        self.action.get_n_actions.return_value = 1
        self.assertEqual(self.backend.prepare_click(self.target, self.cancelled), (.25, .4))
        self.action.do_action.assert_not_called()
        with self.assertRaises(RuntimeError):
            self.backend.activate(self.target, self.cancelled)
        self.node.get_component_iface.return_value.get_extents.return_value = Rect(50, 20, 30, 40)
        with self.assertRaises(RuntimeError):
            self.backend.prepare_click(self.target, self.cancelled)

    def test_click_action_cannot_use_pointer_fallback(self):
        with self.assertRaises(RuntimeError):
            self.backend.prepare_click(self.target, self.cancelled)
        self.action.do_action.assert_not_called()

    def test_pointer_uses_window_coordinates_even_if_screen_origin_is_unknown(self):
        from hap.accessibility import Atspi
        self.target.pointer = True
        self.target.window_rect = Rect(0, 0, 100, 100)
        self.target.action_name = 'listitem.scroll-to'
        self.action.get_action_name.return_value = 'listitem.scroll-to'
        self.action.get_n_actions.return_value = 1
        def extents(coord):
            # Some Wayland toolkits cannot provide a desktop SCREEN origin.
            if coord != Atspi.CoordType.WINDOW:
                raise AssertionError('Desktop SCREEN coordinates must not be used for clicking')
            return self.target.rect
        self.node.get_component_iface.return_value.get_extents.side_effect = extents
        self.assertEqual(self.backend.prepare_click(self.target, self.cancelled), (.25, .4))

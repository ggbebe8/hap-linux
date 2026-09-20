import unittest
from hap.core import Rect, labels, choose_window, preferred_action


class CoreTests(unittest.TestCase):
    def test_labels_unique_prefix_free(self):
        for count in (0, 1, 7, 8, 49, 50, 500):
            result = labels(count)
            self.assertEqual(len(result), count)
            self.assertEqual(len(set(result)), count)
            self.assertTrue(all(not b.startswith(a) for a in result for b in result if a != b))
        self.assertEqual(labels(7), list('ASDFJKL'))

    def test_invalid_labels(self):
        for count, alphabet in ((-1, 'AS'), (5, 'A'), (2, 'AA')):
            with self.assertRaises(ValueError):
                labels(count, alphabet)

    def test_geometry_clips_and_ignores_offscreen(self):
        window = Rect(0, 0, 200, 100)
        self.assertEqual(Rect(-10, 0, 40, 20).normalized(window), (.075, .1))
        self.assertIsNone(Rect(-100, 0, 20, 20).normalized(window))
        self.assertIsNone(Rect(0, 0, 0, 20).normalized(window))
        self.assertEqual(Rect(20, 30, 20, 20).normalized(Rect(10, 20, 100, 100)), (.2, .2))

    def test_window_matching(self):
        self.assertEqual(choose_window([(1, 'A', False), (2, 'B', True)], 'A'), 1)
        self.assertEqual(choose_window([(1, 'A', False), (2, 'A', True)], 'A'), 2)
        with self.assertRaises(RuntimeError):
            choose_window([(1, 'A', False), (2, 'A', False)], 'A')
        with self.assertRaises(RuntimeError):
            choose_window([], 'A')

    def test_action_preference(self):
        self.assertEqual(preferred_action(['menu', 'click']), 1)
        self.assertEqual(preferred_action(['Press']), 0)
        self.assertIsNone(preferred_action([]))

    def test_scroll_and_unrelated_actions_are_not_clicks(self):
        for names in (['listitem.scroll-to'], ['menu.popup'], ['clipboard.cut', 'delete']):
            self.assertIsNone(preferred_action(names))
        self.assertEqual(preferred_action(['listitem.scroll-to', 'listitem.activate']), 1)


if __name__ == '__main__':
    unittest.main()

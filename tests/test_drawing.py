import unittest
import numpy as np
import cv2


class TestDrawDirectionVectors(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def test_empty_config_no_change(self):
        from carcounter.drawing import draw_direction_vectors
        draw_direction_vectors(self.frame, {})
        result = np.sum(self.frame)
        self.assertEqual(result, 0)

    def test_single_direction_drawn(self):
        from carcounter.drawing import draw_direction_vectors
        config = {"north": [[100, 200], [100, 100]]}
        draw_direction_vectors(self.frame, config)
        self.assertTrue(np.any(self.frame != 0), "Frame should have non-zero pixels after drawing")

    def test_multiple_directions_drawn(self):
        from carcounter.drawing import draw_direction_vectors
        config = {
            "north": [[100, 200], [100, 100]],
            "south": [[300, 200], [300, 300]],
        }
        draw_direction_vectors(self.frame, config)
        colored_pixels = np.sum(self.frame != 0)
        self.assertGreater(colored_pixels, 0, "Should have colored pixels for multiple directions")

    def test_ignores_incomplete_direction(self):
        from carcounter.drawing import draw_direction_vectors
        config = {"incomplete": [[100, 200]]}
        draw_direction_vectors(self.frame, config)
        result = np.sum(self.frame)
        self.assertEqual(result, 0, "Should ignore directions with less than 2 points")


if __name__ == "__main__":
    unittest.main()
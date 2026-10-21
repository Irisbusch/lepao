import unittest

from lepao.win32 import map_android_point


class MapAndroidPointTests(unittest.TestCase):
    def test_origin_stays_at_client_origin(self) -> None:
        self.assertEqual(map_android_point(10, 20, 1000, 2000, 0, 0, 500, 1000), (10, 20))

    def test_scales_android_pixels_into_the_client_area(self) -> None:
        self.assertEqual(map_android_point(0, 0, 200, 400, 50, 25, 100, 100), (100, 100))

    def test_truncates_toward_zero(self) -> None:
        self.assertEqual(map_android_point(0, 0, 10, 10, 1, 1, 3, 3), (3, 3))


if __name__ == "__main__":
    unittest.main()

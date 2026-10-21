import unittest
from datetime import datetime

from lepao.gui import due_key, next_slot

SLOTS = ((8, 0), (17, 0))


class ScheduleTests(unittest.TestCase):
    def test_morning_is_still_today_before_eight(self) -> None:
        now = datetime(2026, 10, 21, 7, 30)
        self.assertEqual(next_slot(now, SLOTS), datetime(2026, 10, 21, 8, 0))

    def test_afternoon_comes_after_the_morning_slot(self) -> None:
        now = datetime(2026, 10, 21, 8, 0)
        self.assertEqual(next_slot(now, SLOTS), datetime(2026, 10, 21, 17, 0))

    def test_after_five_the_next_run_is_tomorrow_morning(self) -> None:
        now = datetime(2026, 10, 21, 17, 0)
        self.assertEqual(next_slot(now, SLOTS), datetime(2026, 10, 22, 8, 0))

    def test_only_the_scheduled_minute_is_due(self) -> None:
        self.assertEqual(due_key(datetime(2026, 10, 21, 8, 0, 12), SLOTS), ("2026-10-21", 8, 0))
        self.assertIsNone(due_key(datetime(2026, 10, 21, 8, 1), SLOTS))
        self.assertEqual(due_key(datetime(2026, 10, 21, 17, 0), SLOTS), ("2026-10-21", 17, 0))


if __name__ == "__main__":
    unittest.main()

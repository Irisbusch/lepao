import unittest

from lepao.screen import distance_km_from, manager_visible


class DistanceTests(unittest.TestCase):
    def test_reads_the_number_before_kilometer_label(self) -> None:
        texts = ["0.62", "GPS信号优", "公里", "平均配速", "2", "已打卡", "0.0"]
        self.assertEqual(distance_km_from(texts), 0.62)

    def test_ignores_a_screen_without_the_label(self) -> None:
        self.assertIsNone(distance_km_from(["2", "已打卡", "0.0"]))


class ManagerTests(unittest.TestCase):
    def test_secret_code_log_is_not_the_manager(self) -> None:
        texts = [
            "执行",
            "Broadcasting: Intent { act=android.telephony.action.SECRET_CODE }",
            "Broadcast completed: result=0",
        ]
        self.assertFalse(manager_visible(texts))

    def test_overview_marks_mean_the_manager_is_open(self) -> None:
        self.assertTrue(manager_visible(["LSPosed", "系统框架", "模块"]))


if __name__ == "__main__":
    unittest.main()

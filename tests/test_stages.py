import unittest

from lepao.stages import (
    ATTEMPT_LOG,
    RETRY_LOG,
    STAGES,
    attempt_from_line,
    boot_from_line,
    is_retry_line,
    km_from_line,
    stage_from_line,
)


class StageLineTests(unittest.TestCase):
    def test_known_stage_is_recognized(self) -> None:
        self.assertEqual(stage_from_line("阶段 等待公里"), "等待公里")
        self.assertIn("等待公里", STAGES)

    def test_other_logs_are_not_stages(self) -> None:
        self.assertIsNone(stage_from_line("点击路线 Android (1,2)"))
        self.assertIsNone(stage_from_line("阶段 不存在"))

    def test_reads_kilometers_from_the_wait_log(self) -> None:
        self.assertEqual(km_from_line("当前 0.62 公里"), 0.62)
        self.assertIsNone(km_from_line("等待公里数大于 2.00"))

    def test_attempt_sentence_roundtrip(self) -> None:
        self.assertEqual(attempt_from_line(ATTEMPT_LOG % 3), 3)
        self.assertIsNone(attempt_from_line("第 2 次还没进模块页"))

    def test_retry_sentence_is_exact(self) -> None:
        self.assertTrue(is_retry_line(RETRY_LOG))
        self.assertFalse(is_retry_line("重新开机「乐跑」"))

    def test_boot_lines_from_the_launcher(self) -> None:
        self.assertEqual(boot_from_line("打开 MuMu 主程序"), "打开 MuMu")
        self.assertEqual(boot_from_line("开机「乐跑」(index 1, Android 15)"), "正在开机")
        self.assertEqual(boot_from_line("设备已就绪: 127.0.0.1:16416"), "ADB 已就绪")
        self.assertIsNone(boot_from_line("点击路线"))


if __name__ == "__main__":
    unittest.main()

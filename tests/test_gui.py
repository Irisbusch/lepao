import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
import tkinter as tk

from lepao.config import WINDOW_HINTS
from lepao.gui import APP_TITLE, App, RunView, console_boot_args, install_startup, schedule_label
from lepao.win32 import GUI_TITLE
from lepao.stages import RETRY_LOG, STAGES


class RunViewTests(unittest.TestCase):
    def test_stage_marks_earlier_steps_done(self) -> None:
        view = RunView()
        view.begin()
        view.apply_line("阶段 路线模拟")
        self.assertEqual(view.states[4], "active")
        self.assertEqual(view.states[:4], ["done"] * 4)
        self.assertEqual(view.headline(), "路线模拟")

    def test_kilometers_fill_the_bar_toward_the_target(self) -> None:
        view = RunView(target_km=2.0)
        view.begin()
        view.apply_line("阶段 等待公里")
        view.apply_line("当前 0.62 公里")
        self.assertEqual(view.km, 0.62)
        self.assertAlmostEqual(view.progress(), 0.31)
        view.apply_line("当前 2.10 公里")
        self.assertEqual(view.progress(), 1.0)

    def test_retry_and_later_attempt_show_a_note(self) -> None:
        view = RunView()
        view.begin()
        view.apply_line("阶段 打开 LSPosed")
        view.apply_line("第 1 次从 KernelSU 打开 LSPosed")
        self.assertEqual(view.note, "")
        view.apply_line(RETRY_LOG)
        self.assertEqual(view.note, "正在重开 MuMu")
        view.apply_line("第 2 次从 KernelSU 打开 LSPosed")
        self.assertEqual(view.note, "第 2 次打开 LSPosed")

    def test_boot_line_is_the_headline_before_any_stage(self) -> None:
        view = RunView()
        view.begin()
        view.apply_line("连接 adb 127.0.0.1:16416")
        self.assertEqual(view.headline(), "连接 ADB")
        view.apply_line("阶段 打开 LSPosed")
        view.apply_line("启动 KernelSU...")
        self.assertEqual(view.headline(), "打开 LSPosed")

    def test_exit_codes_close_the_active_stage(self) -> None:
        view = RunView()
        view.begin()
        view.apply_line("阶段 结束")
        view.finish(0)
        self.assertEqual(view.status, "完成")
        self.assertEqual(view.states[-1], "done")
        self.assertEqual(view.headline(), "全部完成")

        failed = RunView()
        failed.begin()
        failed.apply_line("阶段 等待公里")
        failed.finish(1)
        self.assertEqual(failed.status, "失败")
        self.assertEqual(failed.states[STAGES.index("等待公里")], "failed")
        self.assertEqual(failed.headline(), "失败 · 等待公里")

        stopped = RunView()
        stopped.begin()
        stopped.apply_line("阶段 路线模拟")
        stopped.finish(1, stopped=True)
        self.assertEqual(stopped.status, "已停止")
        self.assertEqual(stopped.states[4], "active")

    def test_a_new_run_clears_the_previous_one(self) -> None:
        view = RunView()
        view.begin()
        view.apply_line("当前 1.00 公里")
        view.apply_line("阶段 结束")
        view.begin()
        self.assertIsNone(view.km)
        self.assertEqual(view.states, ["wait"] * len(STAGES))
        self.assertEqual(view.status, "运行中")


class ConsoleBootTests(unittest.TestCase):
    def test_boot_opens_a_real_console_script(self) -> None:
        argv, flags = console_boot_args()
        self.assertEqual(argv[0], "pwsh")
        self.assertNotIn("-NoProfile", argv)
        command = argv[-1]
        self.assertIn("conda activate daily", command)
        self.assertIn("pwsh -File", command)
        self.assertIn("start-mumu-lepao.ps1", command)
        self.assertFalse(flags & subprocess.CREATE_NO_WINDOW)
        self.assertTrue(flags & subprocess.CREATE_NEW_CONSOLE)


class ScheduleLabelTests(unittest.TestCase):
    def test_label_comes_from_the_slots(self) -> None:
        self.assertEqual(schedule_label(((8, 0), (17, 0))), "每天 08:00 和 17:00 自动运行")
        self.assertEqual(
            schedule_label(((8, 0), (12, 30), (17, 0))),
            "每天 08:00、12:30 和 17:00 自动运行",
        )


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        # 构造窗口时如果正好是 08:00 或 17:00，不能真的把开机脚本拉起来。
        original = App._start
        App._start = lambda *args, **kwargs: None  # type: ignore[method-assign]
        try:
            self.app = App(self.root)
        finally:
            App._start = original  # type: ignore[method-assign]
        self.root.update_idletasks()

    def tearDown(self) -> None:
        self.root.destroy()

    def test_log_lines_land_on_the_dashboard(self) -> None:
        self.app.view.begin()
        self.app.view.apply_line("阶段 等待公里")
        self.app.view.apply_line("当前 1.25 公里")
        self.app._paint()
        self.root.update_idletasks()
        self.assertEqual(self.app.headline_label.cget("text"), "等待公里")
        self.assertEqual(self.app.km_value.cget("text"), "1.25")
        self.assertEqual(self.app.status_label.cget("text"), "运行中")
        self.assertIn("08:00", self.app.auto_check.cget("text"))
        self.assertIn("17:00", self.app.auto_check.cget("text"))
        self.assertGreater(len(self.app.stepper.find_all()), 0)

    def test_close_minimizes_and_leaves_the_window_up(self) -> None:
        self.app.root.iconify = lambda: setattr(self.app, "iconified", True)
        self.app._minimize()
        self.assertTrue(self.app.root.winfo_exists())
        self.assertTrue(self.app.iconified)

    def test_title_does_not_look_like_the_emulator(self) -> None:
        title = self.app.root.title()
        self.assertEqual(title, APP_TITLE)
        self.assertEqual(title, GUI_TITLE)
        for hint in WINDOW_HINTS:
            self.assertNotIn(hint.lower(), title.lower())

    def test_stop_kills_the_clicker_after_the_launcher_exits(self) -> None:
        """启动脚本先退出时，停止仍要结束还在进程组里的点击进程。"""
        from lepao.win32 import ProcessJob, popen_in_job

        empty = ProcessJob()
        self.assertFalse(empty.alive())
        empty.close()

        proc = None
        job = None
        try:
            proc, job, assigned = popen_in_job(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertTrue(assigned)
            self.assertIsNone(proc.poll())
            self.assertTrue(job.alive())

            class Finished:
                pid = 0

                def poll(self) -> int:
                    return 0

            self.app.proc = Finished()  # type: ignore[assignment]
            self.app.job = job
            self.app.view.begin()
            self.app._stop()
            self.assertEqual(self.app.view.status, "已停止")
            self.assertIn("已停止", self.app.log.get("1.0", "end"))
            proc.wait(timeout=5)
            self.assertIsNotNone(proc.poll())
            deadline = time.time() + 2
            while job.alive() and time.time() < deadline:
                time.sleep(0.05)
            self.assertFalse(job.alive())
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            if job is not None:
                job.close()
            self.app.proc = None
            self.app.job = None


class StartupShortcutTests(unittest.TestCase):
    def test_shortcut_replaces_the_old_bat(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "lepao-gui.exe"
            target.write_bytes(b"")
            link = root / "startup" / "lepao-gui.lnk"
            legacy = link.with_name("lepao-gui.bat")
            legacy.parent.mkdir()
            legacy.write_text("old", encoding="utf-8")
            install_startup(link, target)
            self.assertTrue(link.exists())
            self.assertGreater(link.stat().st_size, 0)
            self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()

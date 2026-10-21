"""KernelSU → LSPosed → 定位 → 乐跑 的点击顺序。"""

from __future__ import annotations

import logging
import time
from typing import Any

import uiautomator2 as u2

from lepao.config import (
    ARTIFACTS,
    BOTTOM_TAB_FLOOR_RATIO,
    BOTTOM_TAB_X_RATIO,
    BOTTOM_TAB_Y_RATIO,
    DISTANCE_POLL_SEC,
    DISTANCE_TARGET_KM,
    DISTANCE_WAIT_SEC,
    HOLD_SEC,
    HOME_DX,
    HOME_DY,
    KERNELSU_PACKAGE,
    LSPOSED_LAUNCH_ATTEMPTS,
    MENU_DX,
    MENU_DY,
    MODULE_ICON_ABOVE_LABEL,
    MODULE_ICON_Y_RATIO,
    MODULE_TAB_ATTEMPTS,
    MULT_DX,
    MULT_DY,
    NAV_DX,
    NAV_DY,
    Points,
    REDUCE_TIMES,
    SCROLL_FROM_Y,
    SCROLL_PAUSE,
    SCROLL_TIMES,
    SCROLL_TO_Y,
)
from lepao.mumu import MuMuError, restart_player
from lepao.screen import Screen
from lepao.stages import ATTEMPT_LOG, MANAGER_SEEN_LOG, RETRY_LOG, STAGES
from lepao.win32 import (
    Pointer,
    WindowNotFound,
    enable_per_monitor_dpi,
    find_mumu_window,
    focus,
    mouse_click,
    window_rect,
)

log = logging.getLogger("lepao")


class AutomationError(RuntimeError):
    """流程停在预期失败上，消息可以直接给操作的人看。"""


class Session:
    def __init__(self, serial: str, device: Any | None = None) -> None:
        enable_per_monitor_dpi()
        self.serial = serial
        self.device = device if device is not None else u2.connect(serial)
        self.screen = Screen(self.device)
        self.pointer = Pointer()

    def run(
        self,
        *,
        last_only: bool,
        probe: tuple[float, float] | None = None,
        multitasking: bool = False,
        look_only: bool = False,
    ) -> None:
        if multitasking:
            log.info("只执行多任务菜单点击")
            self._go_home_via_Multitasking()
            return
        if look_only:
            width, height = self.device.window_size()
            point = probe or Points.ENTER_RUN
            log.info("Android 画面: %dx%d", width, height)
            log.info("只看这一个点，不点击，比例 (%.3f, %.3f)", point[0], point[1])
            self._look(width, height, point)
            return
        if last_only:
            width, height = self.device.window_size()
            point = probe or Points.ENTER_RUN
            log.info("Android 画面: %dx%d", width, height)
            log.info("只核对这一个点，比例 (%.3f, %.3f)", point[0], point[1])
            self._probe(width, height, point)
            return

        self._stage(STAGES[0])
        width, height = self._open_lsposed_shell()
        self._stage(STAGES[1])
        self._arm_spoofer(width, height)
        self._stage(STAGES[2])
        self._open_lepao(width, height)
        self._stage(STAGES[3])
        self._back_to_previous_app(width, height)
        self._stage(STAGES[4])
        self._Route_Simulation(width, height)
        self._stage(STAGES[5])
        self._back_to_previous_app(width, height)
        self._stage(STAGES[6])
        self._wait_until_km()
        self._stage(STAGES[7])
        self._hold(width, height, Points.HOLD_TO_PAUSE, "长按暂停", HOLD_SEC)
        self._stage(STAGES[8])
        self._finish(width, height)

    def _stage(self, name: str) -> None:
        log.info("阶段 %s", name)

    def _prepare_window(self) -> tuple[int, int]:
        hwnd, title = find_mumu_window()
        if not hwnd:
            raise AutomationError("没找到标题含「乐跑」或 MuMu 的窗口。把模拟器窗口摆到前台再跑。")
        log.info("将点击这扇窗口: %s", title)
        focus(hwnd)
        width, height = self.device.window_size()
        log.info("Android 画面: %dx%d", width, height)
        self._shot("before_click.png")
        return width, height

    def _enter_modules(self, width: int, height: int) -> None:
        log.info("点击底部「模块」（打在 MuMu 窗口上，不走 ADB）...")
        for attempt in range(MODULE_TAB_ATTEMPTS):
            self._click_bottom_module_tab(width, height)
            time.sleep(1.2)
            if self.screen.on_modules_page():
                log.info("已进入模块页")
                return
            log.info("第 %d 次还没进模块页", attempt + 1)
            self._shot(f"after_tab_{attempt + 1}.png")
        self._shot("debug_modules.png")
        raise AutomationError(
            "没进模块页。看 artifacts/after_tab_*.png。若鼠标没落在 KernelSU 窗口里，把窗口标题发我。"
        )

    def _click_bottom_module_tab(self, width: int, height: int) -> None:
        self._tap(width, height, Points.MODULES, "点击右下角三角形", 2.0)

    def _scroll_to_bottom(self, width: int, height: int) -> None:
        log.info("下滑到列表最底部...")
        for i in range(SCROLL_TIMES):
            log.info("  第 %d 次下滑", i + 1)
            self.pointer.swipe_android(
                width // 2,
                int(height * SCROLL_FROM_Y),
                width // 2,
                int(height * SCROLL_TO_Y),
                width,
                height,
            )
            time.sleep(SCROLL_PAUSE)

    def _open_lsposed_shell(self) -> tuple[int, int]:
        """点「执行」。没进管理器就关掉 MuMu 再开机重跑，进了才点底栏「模块」。"""
        for attempt in range(1, LSPOSED_LAUNCH_ATTEMPTS + 1):
            log.info(ATTEMPT_LOG, attempt)
            log.info("启动 KernelSU...")
            self.device.app_start(KERNELSU_PACKAGE)
            time.sleep(3)
            width, height = self._prepare_window()
            try:
                self._enter_modules(width, height)
            except AutomationError as exc:
                log.info("没进模块页: %s", exc)
                self._reboot_for_retry(attempt)
                continue
            self._scroll_to_bottom(width, height)
            self._tap(width, height, Points.LSPOSED_RUN, "点击底部 LSPosed 的「执行」", 3.0)
            if self._lsposed_manager_open():
                self._tap(width, height, Points.SHELL_MODULES, "点击底栏「模块」", 2.0)
                return width, height
            log.info(RETRY_LOG)
            self._reboot_for_retry(attempt)
        raise AutomationError(
            f"点了 {LSPOSED_LAUNCH_ATTEMPTS} 次「执行」，还是没进 LSPosed 管理器。"
        )

    def _reboot_for_retry(self, attempt: int) -> None:
        if attempt >= LSPOSED_LAUNCH_ATTEMPTS:
            return
        try:
            self.serial = restart_player(self.serial)
        except MuMuError as exc:
            raise AutomationError(str(exc)) from exc
        log.info("重新连接 %s", self.serial)
        self.device = u2.connect(self.serial)
        self.screen = Screen(self.device)

    def _lsposed_manager_open(self) -> bool:
        for index in range(3):
            try:
                if self.screen.lsposed_manager_open():
                    log.info(MANAGER_SEEN_LOG)
                    return True
            except Exception as exc:
                log.info("读 LSPosed 界面失败: %s", exc)
            if index < 2:
                time.sleep(1.0)
        log.info("没看到 LSPosed 管理器")
        return False

    def _arm_spoofer(self, width: int, height: int) -> None:
        log.info("点击 LocationSpoofer...")
        self._tap(width, height, Points.SPOOFER_CARD, "点击LocationSpoofer", 2.0)

        self._tap(width, height, Points.SPOOFER_PLAY, "点击右下角三角形", 2.0)
        self._tap(width, height, Points.MAP_STAR, "点击右侧栏星星", 1.0)
        self._tap(width, height, Points.CAMPUS, "点击南体", 1.0)
        self._tap(width, height, Points.FIXED_POINT, "点击定点模拟", 1.0)
        self._tap(width, height, Points.START_SPOOF, "点击开始模拟", 1.0)

    def _open_lepao(self, width: int, height: int) -> None:
        self._go_home_via_menu()
        time.sleep(1.0)
        self._tap(width, height, Points.LEPAO_ICON, "点击乐跑软件", 10.0)
        self._tap(width, height, Points.START_RUN, "点击开始乐跑", 1.0)
        self._tap(width, height, Points.ENTER_RUN, "点击进入乐跑", 1.5)
        self._tap(width, height, Points.BEGIN_RUN, "点击进入乐跑", 4.0)

    def _look(self, width: int, height: int, point: tuple[float, float]) -> None:
        """把光标停在比例点上，不点击。"""
        x = int(width * point[0])
        y = int(height * point[1])
        self.pointer.move_android(x, y, width, height)
        log.info("光标停在 Android (%d,%d)，不点击", x, y)

    def _probe(self, width: int, height: int, point: tuple[float, float]) -> None:
        """先把光标停在比例点上，方便肉眼核对，再点击。"""
        x = int(width * point[0])
        y = int(height * point[1])
        self.pointer.move_android(x, y, width, height)
        time.sleep(2.0)
        log.info("核对结束，点击 Android (%d,%d)", x, y)
        self.pointer.tap_android(x, y, width, height)
        log.info("已点击")

    def _tap(
        self,
        width: int,
        height: int,
        point: tuple[float, float],
        message: str,
        pause: float,
    ) -> None:
        x = int(width * point[0])
        y = int(height * point[1])
        log.info("%s Android (%d,%d)", message, x, y)
        self.pointer.tap_android(x, y, width, height)
        time.sleep(pause)

    def _hold(
        self,
        width: int,
        height: int,
        point: tuple[float, float],
        message: str,
        seconds: float,
        pause: float = 1.0,
    ) -> None:
        x = int(width * point[0])
        y = int(height * point[1])
        log.info("%s Android (%d,%d)，按住 %.1f 秒", message, x, y, seconds)
        self.pointer.hold_android(x, y, width, height, seconds)
        time.sleep(pause)

    def _open_android_nav(self, dx: int, dy: int, label: str) -> None:
        """点三个点 → 安卓导航键 → 菜单项。后两下按 MuMu 外框的像素偏移。"""
        hwnd, _title = find_mumu_window()
        if not hwnd:
            raise WindowNotFound("没找到 MuMu 窗口")
        focus(hwnd)
        rect = window_rect(hwnd)
        self._click_menu_item(rect.right + MENU_DX, rect.top + MENU_DY, "窗口菜单", 0.6)
        self._click_menu_item(rect.right + NAV_DX, rect.top + NAV_DY, "安卓导航键", 0.5)
        self._click_menu_item(rect.right + dx, rect.top + dy, label, 1.0)

    def _go_home_via_menu(self) -> None:
        self._open_android_nav(HOME_DX, HOME_DY, "首页")

    def _click_menu_item(self, x: int, y: int, label: str, pause: float) -> None:
        log.info("点击%s (%d,%d)", label, x, y)
        mouse_click(x, y)
        time.sleep(pause)

    def _shot(self, name: str) -> None:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.device.screenshot(str(ARTIFACTS / name))

    def _go_home_via_Multitasking(self) -> None:
        self._open_android_nav(MULT_DX, MULT_DY, "多任务")

    def _swipe_to_right(self, width: int, height: int) -> None:
        log.info("向右滑一次，宽 %s -> %s，高 %s", "50%", "75%", "50%")
        y = int(height * 0.50)
        self.pointer.swipe_android(
            int(width * 0.50),
            y,
            int(width * 0.75),
            y,
            width,
            height,
        )

    def _click_LocationSpoofer(self, width: int, height: int) -> None:
        self._tap(width, height, Points.MULT_SPOOFER, "点击多任务卡片", 1.0)

    def _wait_until_km(self, target: float = DISTANCE_TARGET_KM) -> float:
        log.info("等待公里数大于 %.2f", target)
        deadline = time.monotonic() + DISTANCE_WAIT_SEC
        while time.monotonic() < deadline:
            km = self.screen.distance_km()
            if km is None:
                log.info("没读到公里数")
            else:
                log.info("当前 %.2f 公里", km)
                if km > target:
                    return km
            time.sleep(DISTANCE_POLL_SEC)
        raise AutomationError(
            f"等了 {DISTANCE_WAIT_SEC / 3600:.0f} 小时，公里数还没有大于 {target:.2f}"
        )

    def _back_to_previous_app(self, width: int, height: int) -> None:
        self._go_home_via_Multitasking()
        self._swipe_to_right(width, height)
        self._click_LocationSpoofer(width, height)

    def _Route_Simulation(self, width: int, height: int) -> None:
        self._tap(width, height, Points.ROUTE, "点击路线", 1.0)
        self._tap(width, height, Points.ROUTE_LIBRARY, "点击路线库", 1.0)
        self._tap(width, height, Points.NANTI, "点击南体", 1.0)
        self._tap(width, height, Points.ROUTE_SIMULATION, "点击开始模拟", 1.0)
        self._tap(width, height, Points.CUSTOMIZATION, "点击自定义", 1.0)
        for _ in range(REDUCE_TIMES):
            self._tap(width, height, Points.REDUCE, "点击-0.2M/S", 1.0)
        self._tap(width, height, Points.START_ROUTE_SIMULATION, "点击开始线路模拟", 1.0)

    def _finish(self, width: int, height: int) -> None:
        self._tap(width, height, Points.FINISH_1, "点击结束", 1.0)
        self._tap(width, height, Points.FINISH_2, "点击确认结束", 1.0)
"""把 Android 坐标映射到 MuMu 客户区，再用宿主鼠标点击。

ADB input tap 打进的是安卓桌面，同一坐标会点到桌面上的图标。
所以点击和滑动都落在「乐跑」这扇窗口的画面上。
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from dataclasses import dataclass

from lepao.config import WINDOW_HINTS

log = logging.getLogger("lepao")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SW_RESTORE = 9

# 64 位 HWND 不能用 ctypes 默认的 32 位 c_int，否则窗口句柄会被截断。
user32.EnumWindows.argtypes = [
    ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM),
    wintypes.LPARAM,
]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.mouse_event.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_size_t,
]
user32.mouse_event.restype = None
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class WindowNotFound(RuntimeError):
    """屏幕上没有可点击的 MuMu 窗口。"""


@dataclass(frozen=True)
class ClientArea:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int


def enable_per_monitor_dpi() -> None:
    """客户区坐标按物理像素算。不设 DPI 感知时，高分屏上会点偏。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        ctypes.windll.shcore.SetProcessDpiAwareness.restype = ctypes.HRESULT
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def map_android_point(
    origin_x: int,
    origin_y: int,
    client_w: int,
    client_h: int,
    ax: float,
    ay: float,
    aw: int,
    ah: int,
) -> tuple[int, int]:
    """Android 像素线性映射到客户区屏幕像素，向零截断。"""
    return (
        int(origin_x + ax * client_w / aw),
        int(origin_y + ay * client_h / ah),
    )


def find_mumu_window() -> tuple[int, str]:
    """优先标题里带「乐跑」的窗口，否则取可见面积最大的 MuMu 窗口。"""
    found: list[tuple[int, int, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if any(hint.lower() in title.lower() for hint in WINDOW_HINTS):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
            if area > 0:
                found.append((area, int(hwnd), title))
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return 0, ""
    for _area, hwnd, title in found:
        if "乐跑" in title:
            return hwnd, title
    found.sort(reverse=True)
    return found[0][1], found[0][2]


def focus(hwnd: int) -> None:
    """把窗口拉到前台。SetForegroundWindow 经常被拒绝，所以先挂上前台线程。"""
    user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    user32.AttachThreadInput(cur, fg_thread, True)
    user32.AttachThreadInput(cur, target_thread, True)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.AttachThreadInput(cur, target_thread, False)
    user32.AttachThreadInput(cur, fg_thread, False)
    time.sleep(0.25)


def client_area(hwnd: int, title: str = "") -> ClientArea:
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return ClientArea(
        hwnd=hwnd,
        title=title,
        left=origin.x,
        top=origin.y,
        width=rect.right - rect.left,
        height=rect.bottom - rect.top,
    )


def window_rect(hwnd: int) -> wintypes.RECT:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect


def mouse_click(sx: int, sy: int) -> None:
    # mouse_event 已过时，但这套按下/抬起间隔是按它标定的。
    user32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def mouse_hold(sx: int, sy: int, seconds: float) -> None:
    user32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(seconds)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def mouse_swipe(sx1: int, sy1: int, sx2: int, sy2: int, steps: int = 20) -> None:
    user32.SetCursorPos(int(sx1), int(sy1))
    time.sleep(0.08)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    for i in range(1, steps + 1):
        x = int(sx1 + (sx2 - sx1) * i / steps)
        y = int(sy1 + (sy2 - sy1) * i / steps)
        user32.SetCursorPos(x, y)
        time.sleep(0.025)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


class Pointer:
    """每次点击前重新找窗口并抢焦点，避免中途点到别的程序。"""

    def focused_client(self) -> ClientArea:
        hwnd, title = find_mumu_window()
        if not hwnd:
            raise WindowNotFound("没找到 MuMu 窗口。请让「乐跑」窗口开着，不要最小化。")
        focus(hwnd)
        area = client_area(hwnd, title)
        if area.width <= 0 or area.height <= 0:
            raise WindowNotFound(f"MuMu 窗口客户区无效: {title}")
        return area

    def _map(self, ax: float, ay: float, aw: int, ah: int) -> tuple[int, int]:
        area = self.focused_client()
        sx, sy = map_android_point(area.left, area.top, area.width, area.height, ax, ay, aw, ah)
        log.info("窗口「%s」客户区 %dx%d @(%d,%d)", area.title, area.width, area.height, area.left, area.top)
        log.info("  Android (%d,%d) -> 屏幕 (%d,%d)", int(ax), int(ay), sx, sy)
        return sx, sy

    def move_android(self, ax: float, ay: float, aw: int, ah: int) -> None:
        sx, sy = self._map(ax, ay, aw, ah)
        log.info("光标停在 (%d,%d)，先看它在不在目标上", sx, sy)
        user32.SetCursorPos(sx, sy)

    def tap_android(self, ax: float, ay: float, aw: int, ah: int) -> None:
        sx, sy = self._map(ax, ay, aw, ah)
        log.info("点击窗口内 (%d,%d)", sx, sy)
        mouse_click(sx, sy)

    def hold_android(self, ax: float, ay: float, aw: int, ah: int, seconds: float) -> None:
        sx, sy = self._map(ax, ay, aw, ah)
        log.info("长按窗口内 (%d,%d) %.1f 秒", sx, sy, seconds)
        mouse_hold(sx, sy, seconds)

    def swipe_android(
        self,
        ax1: float,
        ay1: float,
        ax2: float,
        ay2: float,
        aw: int,
        ah: int,
    ) -> None:
        area = self.focused_client()
        sx1, sy1 = map_android_point(area.left, area.top, area.width, area.height, ax1, ay1, aw, ah)
        log.info("窗口「%s」客户区 %dx%d @(%d,%d)", area.title, area.width, area.height, area.left, area.top)
        log.info("  Android (%d,%d) -> 屏幕 (%d,%d)", int(ax1), int(ay1), sx1, sy1)
        hwnd, _title = find_mumu_window()
        if not hwnd:
            raise WindowNotFound("没找到 MuMu 窗口。请让「乐跑」窗口开着，不要最小化。")
        end = client_area(hwnd)
        sx2, sy2 = map_android_point(end.left, end.top, end.width, end.height, ax2, ay2, aw, ah)
        log.info("滑动窗口内 (%d,%d) -> (%d,%d)", sx1, sy1, sx2, sy2)
        mouse_swipe(sx1, sy1, sx2, sy2)

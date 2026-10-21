"""把 Android 坐标映射到 MuMu 客户区，再用宿主鼠标点击。

ADB input tap 打进的是安卓桌面，同一坐标会点到桌面上的图标。
所以点击和滑动都落在「乐跑」这扇窗口的画面上。
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass

from lepao.config import WINDOW_HINTS

log = logging.getLogger("lepao")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
CREATE_SUSPENDED = 0x00000004
TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectBasicProcessIdList = 3
JobObjectExtendedLimitInformation = 9
HWND_TOP = wintypes.HWND(0)
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ASFW_ANY = 0xFFFFFFFF
LSFW_UNLOCK = 2
WM_SYSCOMMAND = 0x0112
SC_MINIMIZE = 0xF020
# 和界面标题一致。这个窗口在前面时，点击会落进去，进不了模块页。
GUI_TITLE = "自动跑"

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
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.LockSetForegroundWindow.argtypes = [wintypes.UINT]
user32.LockSetForegroundWindow.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
user32.AllowSetForegroundWindow.restype = wintypes.BOOL
user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
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
kernel32.GetCurrentProcessId.argtypes = []
kernel32.GetCurrentProcessId.restype = wintypes.DWORD
kernel32.GetConsoleWindow.argtypes = []
kernel32.GetConsoleWindow.restype = wintypes.HWND
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.IsGUIThread.argtypes = [wintypes.BOOL]
user32.IsGUIThread.restype = wintypes.BOOL
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL


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
    """客户区坐标按物理像素算。不设 DPI 感知时，高分屏上会点偏。

    从没有控制台的界面启动时，python.exe 会先弹出自己的控制台，
    进程级设置就会失败。这时改当前线程，坐标才和 PyCharm 里一致。
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        ctypes.windll.shcore.SetProcessDpiAwareness.restype = ctypes.HRESULT
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        # -3 是 PER_MONITOR_AWARE，和上面的进程级设置是同一档。
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-3))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def allow_other_process_foreground() -> None:
    """当前进程在前台时，放开前台锁，让点击进程可以把 MuMu 拉到前面。

    不在前台时不要调。后台再调一次会把刚才的放行清掉。
    """
    fg = user32.GetForegroundWindow()
    if not fg:
        return
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    if int(pid.value) != int(kernel32.GetCurrentProcessId()):
        return
    user32.AllowSetForegroundWindow(ASFW_ANY)
    user32.LockSetForegroundWindow(LSFW_UNLOCK)


def minimize_own_console() -> None:
    """收起 python.exe 自己弹出的控制台。

    藏掉这个窗口会让后面的点击失效，所以只最小化，不隐藏。
    从 PyCharm 跑时没有单独的控制台，这里什么也不做。
    """
    hwnd = kernel32.GetConsoleWindow()
    if hwnd:
        user32.ShowWindow(hwnd, SW_MINIMIZE)


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


def _ensure_message_queue() -> None:
    """没有消息队列时，AttachThreadInput 会失败，光标就不动。"""
    user32.IsGUIThread(True)
    msg = wintypes.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)


def _thread_id(hwnd: int) -> int:
    if not hwnd:
        return 0
    pid = wintypes.DWORD()
    return int(user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) or 0)


def _hwnd_with_title(title: str) -> int:
    found = 0

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        nonlocal found
        if _window_title(hwnd) == title:
            found = int(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found


def _step_aside_gui() -> None:
    """「自动跑」盖住模拟器时，模块点击会落进这个窗口。先收进任务栏。"""
    hwnd = _hwnd_with_title(GUI_TITLE)
    if not hwnd or user32.IsIconic(hwnd):
        return
    log.info("把「自动跑」收进任务栏，避免挡住点击")
    user32.ShowWindow(hwnd, SW_MINIMIZE)
    time.sleep(0.05)
    if not user32.IsIconic(hwnd):
        user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_MINIMIZE, 0)
        time.sleep(0.15)


def _set_topmost(hwnd: int, top: bool) -> None:
    # 不激活。激活会把前台换掉，刚才接上的输入队列就对不上。
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST if top else HWND_NOTOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


def focus(hwnd: int) -> None:
    """把 MuMu 拉到前台。拉不动时，点击会再把它盖到「自动跑」上面。"""
    _ensure_message_queue()
    _step_aside_gui()
    user32.ShowWindow(hwnd, SW_RESTORE)
    place = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, place)
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    fg_thread = _thread_id(fg)
    target_thread = _thread_id(hwnd)
    if fg_thread and fg_thread != cur:
        user32.AttachThreadInput(cur, fg_thread, True)
    if target_thread and target_thread not in (cur, fg_thread):
        user32.AttachThreadInput(cur, target_thread, True)
    brought = bool(user32.SetForegroundWindow(hwnd))
    user32.BringWindowToTop(hwnd)
    if target_thread and target_thread not in (cur, fg_thread):
        user32.AttachThreadInput(cur, target_thread, False)
    if fg_thread and fg_thread != cur:
        user32.AttachThreadInput(cur, fg_thread, False)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, place)
    time.sleep(0.15)
    now = user32.GetForegroundWindow()
    if int(now or 0) != int(hwnd):
        if not brought:
            log.info("普通切前台被拒绝，点击时会把 MuMu 盖在前台窗口上面")
        log.info("前台仍是「%s」，点击时会把 MuMu 盖在上面", _window_title(now))


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


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


@contextmanager
def _foreground_input():
    """接到前台窗口的输入队列上再移动光标。

    前台还是「自动跑」时，后台进程单独调用 SetCursorPos 会返回成功，光标却不动。
    让开失败时，把 MuMu 盖在上面再点，点击才不会进界面窗口。
    """
    _ensure_message_queue()
    _step_aside_gui()
    hwnd, _title = find_mumu_window()
    fg = user32.GetForegroundWindow()
    pinned = bool(hwnd) and bool(fg) and _window_title(fg) == GUI_TITLE
    if pinned:
        log.info("前台仍是「自动跑」，点击时把 MuMu 盖在上面")
        _set_topmost(hwnd, True)
    cur = kernel32.GetCurrentThreadId()
    fg_thread = _thread_id(fg)
    mumu_thread = _thread_id(hwnd)
    attached: list[int] = []
    for tid, label, owner in (
        (fg_thread, "前台", fg),
        (mumu_thread, "MuMu", hwnd),
    ):
        if not tid or tid == cur or tid in attached:
            continue
        if user32.AttachThreadInput(cur, tid, True):
            attached.append(tid)
            continue
        log.info("没能接到%s「%s」的输入", label, _window_title(owner))
    try:
        yield
    finally:
        for tid in attached:
            user32.AttachThreadInput(cur, tid, False)
        if pinned:
            _set_topmost(hwnd, False)


def _cursor_near(x: int, y: int, tolerance: int = 2) -> bool:
    pos = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(pos)):
        return False
    return abs(pos.x - x) <= tolerance and abs(pos.y - y) <= tolerance


def _virtual_absolute(x: int, y: int) -> tuple[int, int]:
    """把屏幕像素换成跨所有显示器的 0..65535。不带 VIRTUALDESK 时到不了副屏。"""
    origin_x = user32.GetSystemMetrics(76)
    origin_y = user32.GetSystemMetrics(77)
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)
    ax = int(round((x - origin_x) * 65535 / max(width - 1, 1)))
    ay = int(round((y - origin_y) * 65535 / max(height - 1, 1)))
    return max(0, min(65535, ax)), max(0, min(65535, ay))


def _move_by_absolute(x: int, y: int) -> bool:
    ax, ay = _virtual_absolute(x, y)
    user32.mouse_event(
        MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
        ax,
        ay,
        0,
        0,
    )
    time.sleep(0.02)
    return _cursor_near(x, y)


_INPUT_HWND = 0
_INPUT_PROC = None


def _input_window() -> int:
    """本进程自己的小窗口。前台进程才被允许移动光标时，用它来当前台。"""
    global _INPUT_HWND, _INPUT_PROC
    if _INPUT_HWND and user32.IsWindow(_INPUT_HWND):
        return _INPUT_HWND
    _ensure_message_queue()

    wndproc = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    def _proc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _INPUT_PROC = wndproc(_proc)

    class _WndClass(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", wndproc),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    instance = kernel32.GetModuleHandleW(None)
    klass = _WndClass()
    klass.lpfnWndProc = _INPUT_PROC
    klass.hInstance = instance
    klass.lpszClassName = "LepaoInput"
    user32.RegisterClassW.argtypes = [ctypes.POINTER(_WndClass)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.RegisterClassW(ctypes.byref(klass))
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    # 放在主屏角落，2 像素，盖不住副屏上的 MuMu。
    hwnd = user32.CreateWindowExW(
        0x00000080,
        "LepaoInput",
        "lepao",
        0x80000000,
        0,
        0,
        2,
        2,
        None,
        None,
        instance,
        None,
    )
    _INPUT_HWND = int(hwnd or 0)
    if not _INPUT_HWND:
        log.info("没能建立点击窗口，光标可能继续不动")
    return _INPUT_HWND


def _take_foreground() -> None:
    """后台进程的 SetCursorPos 会被丢掉。把自己变成前台后再移。"""
    hwnd = _input_window()
    if not hwnd:
        return
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 2, 2, SWP_SHOWWINDOW)
    brought = bool(user32.SetForegroundWindow(hwnd))
    if not brought:
        # 系统只允许收到过按键的进程切前台。点一下 Alt 再试。
        user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
        user32.keybd_event.restype = None
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 0x0002, 0)
        brought = bool(user32.SetForegroundWindow(hwnd))
    log.info("改由点击进程当前台再移光标，切前台=%s", brought)


def _park_input_window() -> None:
    if _INPUT_HWND and user32.IsWindow(_INPUT_HWND):
        user32.ShowWindow(_INPUT_HWND, SW_HIDE)


def _move_to(x: int, y: int) -> bool:
    x, y = int(x), int(y)
    for _attempt in range(3):
        user32.SetCursorPos(x, y)
        time.sleep(0.02)
        if _cursor_near(x, y):
            return True
    if _move_by_absolute(x, y):
        return True
    _take_foreground()
    user32.SetCursorPos(x, y)
    time.sleep(0.02)
    if _cursor_near(x, y):
        return True
    if _move_by_absolute(x, y):
        return True
    pos = wintypes.POINT()
    if user32.GetCursorPos(ctypes.byref(pos)):
        log.info(
            "光标现在在 (%d,%d)，目标是 (%d,%d)，前台是「%s」",
            pos.x,
            pos.y,
            x,
            y,
            _window_title(user32.GetForegroundWindow()),
        )
    else:
        log.info("光标没移到 (%d,%d)", x, y)
    return False


def _put_cursor(sx: int, sy: int) -> None:
    _move_to(sx, sy)


def _nudge(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)
    if not _cursor_near(x, y):
        _move_by_absolute(x, y)


def mouse_click(sx: int, sy: int) -> None:
    # mouse_event 已过时，但这套按下/抬起间隔是按它标定的。
    try:
        with _foreground_input():
            _put_cursor(sx, sy)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.06)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    finally:
        _park_input_window()


def mouse_hold(sx: int, sy: int, seconds: float) -> None:
    try:
        with _foreground_input():
            _put_cursor(sx, sy)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(seconds)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    finally:
        _park_input_window()


def mouse_swipe(sx1: int, sy1: int, sx2: int, sy2: int, steps: int = 20) -> None:
    try:
        with _foreground_input():
            _put_cursor(sx1, sy1)
            time.sleep(0.08)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            for i in range(1, steps + 1):
                x = int(sx1 + (sx2 - sx1) * i / steps)
                y = int(sy1 + (sy2 - sy1) * i / steps)
                _nudge(x, y)
                time.sleep(0.025)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    finally:
        _park_input_window()


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
        with _foreground_input():
            _put_cursor(sx, sy)

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


# 进程组用单独的一份 kernel32，避免改到上面已经设好参数类型的那份。
_job_kernel = ctypes.WinDLL("kernel32", use_last_error=True)


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobBasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JobExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimit),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JobProcessIdList(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", ctypes.c_size_t * 32),
    ]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", wintypes.LONG),
        ("tpDeltaPri", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
    ]


_job_kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
_job_kernel.CreateJobObjectW.restype = wintypes.HANDLE
_job_kernel.SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
]
_job_kernel.SetInformationJobObject.restype = wintypes.BOOL
_job_kernel.QueryInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
]
_job_kernel.QueryInformationJobObject.restype = wintypes.BOOL
_job_kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_job_kernel.AssignProcessToJobObject.restype = wintypes.BOOL
_job_kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
_job_kernel.TerminateJobObject.restype = wintypes.BOOL
_job_kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_job_kernel.OpenProcess.restype = wintypes.HANDLE
_job_kernel.CloseHandle.argtypes = [wintypes.HANDLE]
_job_kernel.CloseHandle.restype = wintypes.BOOL
_job_kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_job_kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_job_kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)]
_job_kernel.Thread32First.restype = wintypes.BOOL
_job_kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)]
_job_kernel.Thread32Next.restype = wintypes.BOOL
_job_kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_job_kernel.OpenThread.restype = wintypes.HANDLE
_job_kernel.ResumeThread.argtypes = [wintypes.HANDLE]
_job_kernel.ResumeThread.restype = wintypes.DWORD


class ProcessJob:
    """一次运行里的 pwsh 和 python 放进同一个进程组，停止时一起结束。

    启动脚本如果先退出，python 会改挂到别的进程下面，只杀 pwsh 就杀不到它。
    关掉进程组句柄时，组里还活着的进程也会结束。
    """

    def __init__(self) -> None:
        handle = _job_kernel.CreateJobObjectW(None, None)
        if not handle:
            raise OSError("没能创建进程组")
        info = _JobExtendedLimit()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _job_kernel.SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            _job_kernel.CloseHandle(handle)
            raise OSError("没能设置进程组")
        self._handle: int | None = handle

    def assign(self, pid: int) -> bool:
        if not self._handle:
            return False
        process = _job_kernel.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if not process:
            return False
        try:
            return bool(_job_kernel.AssignProcessToJobObject(self._handle, process))
        finally:
            _job_kernel.CloseHandle(process)

    def alive(self) -> bool:
        if not self._handle:
            return False
        info = _JobProcessIdList()
        ok = _job_kernel.QueryInformationJobObject(
            self._handle,
            JobObjectBasicProcessIdList,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        )
        if not ok and ctypes.get_last_error() != 234:
            return False
        return info.NumberOfAssignedProcesses > 0

    def terminate(self) -> bool:
        if not self._handle:
            return False
        return bool(_job_kernel.TerminateJobObject(self._handle, 1))

    def close(self) -> None:
        handle = self._handle
        self._handle = None
        if handle:
            _job_kernel.CloseHandle(handle)


def resume_suspended(pid: int) -> bool:
    """CREATE_SUSPENDED 启动后，把这个进程的线程放行。"""
    snapshot = _job_kernel.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if not snapshot or int(snapshot) == ctypes.c_void_p(-1).value:
        return False
    resumed = False
    try:
        entry = _ThreadEntry()
        entry.dwSize = ctypes.sizeof(_ThreadEntry)
        found = _job_kernel.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.th32OwnerProcessID == pid:
                thread = _job_kernel.OpenThread(THREAD_SUSPEND_RESUME, False, entry.th32ThreadID)
                if thread:
                    if _job_kernel.ResumeThread(thread) != 0xFFFFFFFF:
                        resumed = True
                    _job_kernel.CloseHandle(thread)
            found = _job_kernel.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        _job_kernel.CloseHandle(snapshot)
    return resumed


def popen_in_job(args: list[str], **kwargs: object) -> tuple[subprocess.Popen[str], ProcessJob, bool]:
    """先挂起再放进进程组，然后才恢复运行。这样子进程也会留在组里。"""
    flags = int(kwargs.pop("creationflags", 0)) | CREATE_SUSPENDED
    proc = subprocess.Popen(args, creationflags=flags, **kwargs)
    job: ProcessJob | None = None
    try:
        job = ProcessJob()
        assigned = job.assign(proc.pid)
        if not resume_suspended(proc.pid):
            raise OSError("进程挂起后没能恢复")
    except Exception:
        resume_suspended(proc.pid)
        if job is not None:
            job.terminate()
        if proc.poll() is None:
            proc.kill()
        if job is not None:
            job.close()
        raise
    return proc, job, assigned

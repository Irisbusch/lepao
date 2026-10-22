"""标定过的比例坐标，以及仓库路径。

坐标是 Android 画面宽高的比例，不是屏幕像素。换分辨率时比例仍可用，
像素偏移只出现在 MuMu 窗口自己的菜单上。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = REPO_ROOT / "artifacts"

KERNELSU_PACKAGE = "me.weishu.kernelsu"
WINDOW_HINTS = ("乐跑", "MuMu", "mumu", "模拟器")

# 首页中间那张「模块」卡片。底栏的「模块」在更下面，不计入。
HOME_CARD_MIN_Y = 400
HOME_CARD_MAX_Y_RATIO = 0.75

MODULE_TAB_ATTEMPTS = 3
LSPOSED_LAUNCH_ATTEMPTS = 8
DISTANCE_TARGET_KM = 2.0
DISTANCE_POLL_SEC = 15.0
DISTANCE_WAIT_SEC = 3 * 60 * 60
REDUCE_TIMES = 4
# 本地时间。窗口开着时，到点跑整套开机流程。
SCHEDULE_TIMES = ((8, 0), (17, 0))
HOLD_SEC = 4.0
SCROLL_TIMES = 3
SCROLL_FROM_Y = 0.75
SCROLL_TO_Y = 0.30
SCROLL_PAUSE = 0.45

# MuMu 外框菜单。dx 加在窗口右缘上，dy 加在窗口顶缘上。
# 「首页」在弹出的二级菜单里，二级菜单开在窗口右侧，所以 dx 为正。
MENU_DX, MENU_DY = -240, 20
NAV_DX, NAV_DY = -180, 285
HOME_DX, HOME_DY = 200, 420
MULT_DX, MULT_DY = 200, 400


class Points:
    """Android 画面比例坐标，按当前这套界面标定。"""
    SETTING = (0.15, 0.93)
    ACCESSIBILITY = (0.50, 0.93)
    LEPAO_ACCESSIBILITY = (0.50, 0.55)
    LEPAO_ACCESSIBILITY_1 = (0.70, 0.45)
    ADMIT = (0.50, 0.80)

    MODULES = (0.70, 0.55)

    LSPOSED_RUN = (0.22, 0.52)
    SHELL_MODULES = (0.375, 0.94)
    SPOOFER_CARD = (0.42, 0.32)
    SPOOFER_PLAY = (0.87, 0.92)
    MAP_STAR = (0.91, 0.25)
    CAMPUS = (0.50, 0.50)
    FIXED_POINT = (0.50, 0.80)
    START_SPOOF = (0.80, 0.92)
    LEPAO_ICON = (0.85, 0.50)
    START_RUN = (0.50, 0.65)
    ENTER_RUN = (0.70, 0.90)
    BEGIN_RUN = (0.50, 0.95)
    MULT_SPOOFER = (0.25, 0.35)
    ROUTE = (0.40, 0.93)
    ROUTE_LIBRARY = (0.90, 0.53)
    NANTI = (0.40, 0.53)
    ROUTE_SIMULATION = (0.80, 0.80)
    CUSTOMIZATION = (0.83, 0.45)
    REDUCE = (0.40, 0.75)
    START_ROUTE_SIMULATION = (0.50, 0.90)
    HOLD_TO_PAUSE = (0.50, 0.93)
    FINISH_1 = (0.75, 0.93)
    FINISH_2 = (0.70, 0.60)



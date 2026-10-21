"""用 uiautomator2 读界面。它不负责点击。"""

from __future__ import annotations

import logging
import re
from typing import Any

from lepao.config import HOME_CARD_MAX_Y_RATIO, HOME_CARD_MIN_Y

log = logging.getLogger("lepao")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")
_MANAGER_MARKS = ("系统框架", "com.android.shell", "Xposed API")


def manager_visible(texts: list[str]) -> bool:
    blob = "\n".join(texts)
    return any(mark in blob for mark in _MANAGER_MARKS)


def distance_km_from(texts: list[str]) -> float | None:
    """公里数是「公里」前面最近的那个数字。打卡次数和后面的 0.0 不算。"""
    for index, text in enumerate(texts):
        if text != "公里":
            continue
        for previous in reversed(texts[:index]):
            if _NUMBER.fullmatch(previous):
                return float(previous)
    return None


def center_of(info: dict[str, Any]) -> tuple[int, int, int]:
    bounds = info.get("bounds") or {}
    left = bounds.get("left", 0)
    top = bounds.get("top", 0)
    right = bounds.get("right", 0)
    bottom = bounds.get("bottom", 0)
    return (left + right) // 2, (top + bottom) // 2, bottom


class Screen:
    def __init__(self, device: Any) -> None:
        self.device = device

    def module_nodes(self) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for selector in (self.device(text="模块"), self.device(description="模块")):
            try:
                count = selector.count
            except Exception:
                count = 0
            for i in range(count):
                try:
                    info = selector[i].info
                except Exception:
                    continue
                cx, cy, bottom = center_of(info)
                key = (cx, cy, info.get("text"))
                if key in seen:
                    continue
                seen.add(key)
                nodes.append({
                    "text": (info.get("text") or "").strip(),
                    "cx": cx,
                    "cy": cy,
                    "bottom": bottom,
                })
        return nodes

    def visible_texts(self) -> list[str]:
        xml = self.device.dump_hierarchy()
        return [
            text.strip()
            for text in re.findall(r'(?:text|content-desc)="([^"]+)"', xml)
            if text.strip()
        ]

    def lsposed_manager_open(self) -> bool:
        """管理器概览上有「系统框架」。执行结果页只有 SECRET_CODE 广播日志。"""
        return manager_visible(self.visible_texts())

    def distance_km(self) -> float | None:
        return distance_km_from(self.visible_texts())

    def on_modules_page(self) -> bool:
        """首页有「工作中」「管理器版本」和中部那张模块卡片。这些消失就算进了模块页。"""
        device = self.device
        if device(textContains="工作中").exists(timeout=0.3) or device(text="管理器版本").exists(timeout=0.3):
            log.info("  仍在首页（看到工作中/管理器版本）")
            return False
        if device(text="LSPosed").exists(timeout=0.3) or device(textContains="LSPosed").exists(timeout=0.2):
            return True
        if device(textContains="没有安装模块").exists(timeout=0.2) or device(text="执行").exists(timeout=0.2):
            return True

        home_card = False
        try:
            for i in range(device(text="模块").count):
                _cx, cy, _bottom = center_of(device(text="模块")[i].info)
                if HOME_CARD_MIN_Y < cy < int(device.window_size()[1] * HOME_CARD_MAX_Y_RATIO):
                    home_card = True
        except Exception:
            pass
        if not home_card:
            log.info("  首页模块卡片已消失，当作已进模块页")
            return True
        log.info("  首页卡片还在")
        return False

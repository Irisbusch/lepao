"""界面和流程共用的句子。改这里时，日志和窗口会一起变。"""

from __future__ import annotations

import re

STAGES = (
    "打开乐跑无障碍功能",
    "打开 LSPosed",
    "定位模拟",
    "打开乐跑",
    "切回模拟器",
    "路线模拟",
    "回到乐跑",
    "等待公里",
    "长按暂停",
    "结束",
)

ATTEMPT_LOG = "第 %d 次从 KernelSU 打开 LSPosed"
RETRY_LOG = "停在执行结果页，关闭 MuMu 后重开"
MANAGER_SEEN_LOG = "看到 LSPosed 管理器"

# 开机脚本写到标准输出的句子。顺序要先匹配更长的那句。
BOOT_MARKS = (
    ("执行界面流程", "进入界面流程"),
    ("启动 KernelSU", "启动 KernelSU"),
    ("设备已就绪", "ADB 已就绪"),
    ("连接 adb", "连接 ADB"),
    ("开机", "正在开机"),
    ("打开 MuMu", "打开 MuMu"),
)

_KM = re.compile(r"当前\s+([0-9]+(?:\.[0-9]+)?)\s+公里")
_ATTEMPT = re.compile(r"第\s+([0-9]+)\s+次从 KernelSU 打开 LSPosed")


def stage_from_line(line: str) -> str | None:
    if not line.startswith("阶段 "):
        return None
    name = line.removeprefix("阶段 ").strip()
    if name not in STAGES:
        return None
    return name


def km_from_line(line: str) -> float | None:
    found = _KM.search(line)
    if found is None:
        return None
    return float(found.group(1))


def attempt_from_line(line: str) -> int | None:
    found = _ATTEMPT.search(line)
    if found is None:
        return None
    return int(found.group(1))


def is_retry_line(line: str) -> bool:
    return line.strip() == RETRY_LOG


def boot_from_line(line: str) -> str | None:
    for needle, label in BOOT_MARKS:
        if needle in line:
            return label
    return None

"""关掉整个 MuMu，再只打开「乐跑」。路径来自仓库根目录的 config.json。"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from lepao.config import REPO_ROOT

log = logging.getLogger("lepao")


class MuMuError(RuntimeError):
    """MuMu 没按预期关掉或开起来。"""


def _settings() -> dict[str, Any]:
    path = REPO_ROOT / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _manager(exe: str, args: list[str]) -> str:
    completed = subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    output = completed.stdout or ""
    if completed.returncode != 0 and "{" not in output:
        detail = (completed.stderr or output).strip()
        raise MuMuError(f"MuMuManager 失败: {' '.join(args)}\n{detail}")
    return output


def _players(exe: str) -> dict[str, Any]:
    text = _manager(exe, ["info", "-v", "all"])
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise MuMuError(f"MuMu 信息里没有 JSON:\n{text}")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise MuMuError(f"MuMu 信息不是对象:\n{text}")
    return data


def _player(exe: str, name: str) -> dict[str, Any]:
    players = _players(exe)
    for item in players.values():
        if isinstance(item, dict) and item.get("name") == name:
            return item
    names = ", ".join(
        str(item.get("name")) for item in players.values() if isinstance(item, dict)
    )
    raise MuMuError(f"没有名为「{name}」的实例。当前有: {names}")


def _wait_all_stopped(exe: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            players = _players(exe)
        except (MuMuError, json.JSONDecodeError) as exc:
            log.info("  读 MuMu 状态失败: %s", exc)
            time.sleep(2)
            continue
        running = [
            item
            for item in players.values()
            if isinstance(item, dict)
            and (item.get("is_process_started") or item.get("is_android_started"))
        ]
        if not running:
            log.info("  全部实例已退出")
            return
        names = ", ".join(str(item.get("name")) for item in running)
        log.info("  仍在运行: %s", names)
        time.sleep(2)
    raise MuMuError(f"等待全部实例关机超过 {timeout:.0f} 秒")


def _host_processes(install_root: Path) -> list[tuple[int, str]]:
    command = (
        "$root = $env:MUMU_ROOT.ToLower(); "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith($root) } | "
        "ForEach-Object { '{0}`t{1}' -f $_.ProcessId, $_.Name }"
    )
    env = os.environ.copy()
    env["MUMU_ROOT"] = str(install_root)
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    found: list[tuple[int, str]] = []
    for line in (completed.stdout or "").splitlines():
        pid_text, _, name = line.strip().partition("\t")
        if pid_text.isdigit() and name:
            found.append((int(pid_text), name))
    return found


def _quit_host(install_root: Path) -> None:
    """关掉主程序窗口和播放器进程。服务进程留下，否则接下来无法开机。"""
    keep = {"mumunxservice.exe"}
    targets = [(pid, name) for pid, name in _host_processes(install_root) if name.lower() not in keep]
    if not targets:
        log.info("MuMu 主程序已经不在")
        return
    log.info("退出 MuMu 主程序: %s", ", ".join(sorted({name for _, name in targets})))
    for pid, name in targets:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log.info("  已结束 %s (%s)", name, pid)
    time.sleep(1)
    left = [name for _, name in _host_processes(install_root) if name.lower() not in keep]
    if left:
        raise MuMuError(f"MuMu 主程序还在: {', '.join(sorted(set(left)))}")


def _wait_player(exe: str, name: str, timeout: float, started: bool) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            last = _player(exe, name)
        except (MuMuError, json.JSONDecodeError) as exc:
            log.info("  读 MuMu 状态失败: %s", exc)
            time.sleep(2)
            continue
        android = bool(last.get("is_android_started"))
        process = bool(last.get("is_process_started"))
        log.info("  进程=%s  Android=%s", process, android)
        if started and android:
            return last
        if not started and not android and not process:
            return last
        time.sleep(2)
    state = "开机" if started else "关机"
    raise MuMuError(f"等待「{name}」{state}超过 {timeout:.0f} 秒")


def _wait_adb(adb: str, serial: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        subprocess.run(
            [adb, "connect", serial],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        devices = subprocess.run(
            [adb, "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
        if f"{serial}\tdevice" in devices or f"{serial}    device" in devices:
            log.info("设备已就绪: %s", serial)
            return
        time.sleep(2)
    raise MuMuError(f"Android 已启动，但 adb 还没变成 device。端口 {serial}")


def restart_player(serial: str) -> str:
    """关掉全部实例和 MuMu 主程序，再只开机「乐跑」并连上 ADB。"""
    settings = _settings()
    exe = str(settings["mumu_manager"])
    name = str(settings["player_name"])
    timeout = float(settings["timeout_sec"])
    adb_timeout = float(settings["adb_ready_timeout_sec"])
    install_root = Path(exe).resolve().parent.parent
    player = _player(exe, name)
    index = str(player["index"])

    log.info("关闭全部 MuMu 实例")
    _manager(exe, ["control", "--vmindex", "all", "shutdown"])
    _wait_all_stopped(exe, timeout)
    _quit_host(install_root)

    log.info("重新开机「%s」(index %s)", name, index)
    _manager(exe, ["control", "--vmindex", index, "launch"])
    _manager(exe, ["control", "--vmindex", index, "show_window"])
    player = _wait_player(exe, name, timeout, started=True)

    host = str(player.get("adb_host_ip") or "127.0.0.1")
    port = player.get("adb_port")
    new_serial = f"{host}:{port}" if port else serial
    _wait_adb(str(settings["adb"]), new_serial, adb_timeout)
    return new_serial

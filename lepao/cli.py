"""命令行入口。"""

from __future__ import annotations

import argparse
import logging

from lepao.flow import AutomationError, Session
from lepao.win32 import WindowNotFound, minimize_own_console

log = logging.getLogger("lepao")


def _probe_point(args: argparse.Namespace) -> tuple[float, float] | None | int:
    if args.x is None and args.y is None:
        return None
    if args.x is None or args.y is None:
        log.error("--x 和 --y 要一起给，例如 --look --x 0.50 --y 0.90")
        return 2
    if not args.last and not args.look:
        log.error("--x/--y 只在 --last 或 --look 下使用")
        return 2
    return (args.x, args.y)


def _check_mode(args: argparse.Namespace) -> int | None:
    chosen = [name for name in ("last", "look", "multitasking") if getattr(args, name)]
    if len(chosen) > 1:
        log.error("--last、--look、--multitasking 只能选一个")
        return 2
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lepao",
        description="在 MuMu「乐跑」窗口上完成 KernelSU 到乐跑的界面操作。点击打在窗口客户区，uiautomator2 只读界面。",
    )
    parser.add_argument("serial", help="ADB 序列号，例如 127.0.0.1:16416")
    parser.add_argument("--last", action="store_true", help="只核对一个点：光标先停下，再点击")
    parser.add_argument("--look", action="store_true", help="只把光标停在一个点上，不点击")
    parser.add_argument("--x", type=float, help="与 --last 或 --look 合用，宽度比例，例如 0.50")
    parser.add_argument("--y", type=float, help="与 --last 或 --look 合用，高度比例，例如 0.90")
    parser.add_argument("--multitasking", action="store_true", help="只点三个点、安卓导航键、多任务")
    return parser


def main(argv: list[str] | None = None) -> int:
    # 开机脚本拉起的是 python.exe，它会自带一个控制台。先收起来，免得挡住 MuMu。
    minimize_own_console()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    mode_error = _check_mode(args)
    if mode_error is not None:
        return mode_error
    probe = _probe_point(args)
    if isinstance(probe, int):
        return probe
    try:
        Session(args.serial).run(
            last_only=args.last,
            probe=probe,
            multitasking=args.multitasking,
            look_only=args.look,
        )
    except (AutomationError, WindowNotFound) as exc:
        log.error("%s", exc)
        return 1
    except Exception:
        log.exception("执行失败")
        return 1
    log.info("操作完成")
    return 0

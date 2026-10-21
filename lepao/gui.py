"""乐跑的窗口。开着时，到点新开一个终端，跑跟手敲一样的两条命令。

先 conda activate daily，再 pwsh -File 开机脚本。终端要加载配置文件，conda 才在。
不要挂起，不要藏窗口，不要把输出接走，否则点击进程算后台程序，光标不会动。
窗口不要置顶，置顶会挡住 MuMu，鼠标点不到模拟器。
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

from lepao.config import DISTANCE_TARGET_KM, REPO_ROOT, SCHEDULE_TIMES
from lepao.win32 import ProcessJob
from lepao.stages import (
    MANAGER_SEEN_LOG,
    STAGES,
    attempt_from_line,
    boot_from_line,
    is_retry_line,
    km_from_line,
    stage_from_line,
)

SCRIPT = REPO_ROOT / "start-mumu-lepao.ps1"
LAUNCHER = REPO_ROOT / "lepao-gui.exe"
APP_TITLE = "自动跑"


def console_boot_args() -> tuple[list[str], int]:
    """现在运行和到点运行都走这条。跟手敲的两条命令一样。

    新开一个普通 pwsh，加载配置文件，然后：
    conda activate daily
    pwsh -File start-mumu-lepao.ps1
    不要 -NoProfile，否则没有 conda。不要挂起，不要接管道，不要 CREATE_NO_WINDOW。
    这个终端由 lepao 自己最小化。
    """
    script = str(SCRIPT)
    command = (
        "conda activate daily; "
        "if (-not $?) { exit 1 }; "
        f"pwsh -File '{script}'; "
        "exit $LASTEXITCODE"
    )
    return ["pwsh", "-Command", command], subprocess.CREATE_NEW_CONSOLE


BG = "#101114"
CARD = "#181b22"
EDGE = "#2c313c"
ACCENT = "#d6f25c"
INK = "#15180d"
GREEN = "#3ddc97"
AMBER = "#ffbf47"
RED = "#ff5c7a"
TEXT = "#f3f5f7"
MUTED = "#939aab"
DIM = "#6a7180"
TRACK = "#2a303a"
LOG_BG = "#0c0e12"

UI = "Microsoft YaHei UI"
MONO = "Consolas"


def next_slot(now: datetime, slots: tuple[tuple[int, int], ...] = SCHEDULE_TIMES) -> datetime:
    """下一个还没到的时刻。已经过了今天的点，就排到明天。"""
    candidates: list[datetime] = []
    for hour, minute in slots:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates)


def due_key(
    now: datetime,
    slots: tuple[tuple[int, int], ...] = SCHEDULE_TIMES,
) -> tuple[str, int, int] | None:
    """当前这一分钟如果是设定时刻，返回当天的标记。同一分钟只应触发一次。"""
    slot = (now.hour, now.minute)
    if slot not in slots:
        return None
    return (now.date().isoformat(), slot[0], slot[1])


def schedule_label(slots: tuple[tuple[int, int], ...] = SCHEDULE_TIMES) -> str:
    parts = [f"{hour:02d}:{minute:02d}" for hour, minute in slots]
    if len(parts) <= 1:
        text = parts[0] if parts else ""
    elif len(parts) == 2:
        text = f"{parts[0]} 和 {parts[1]}"
    else:
        text = "、".join(parts[:-1]) + f" 和 {parts[-1]}"
    return f"每天 {text} 自动运行"


def startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_link() -> Path:
    return startup_dir() / "lepao-gui.lnk"


def startup_enabled() -> bool:
    folder = startup_dir()
    return startup_link().exists() or (folder / "lepao-gui.bat").exists()


def install_startup(link: Path | None = None, target: Path | None = None) -> None:
    """登录时打开 exe。顺手去掉旧的 bat，避免两个一起启动。"""
    link = link or startup_link()
    target = target or LAUNCHER
    if not target.exists():
        raise FileNotFoundError(str(target))
    link.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $shell.CreateShortcut('{link}'); "
        f"$shortcut.TargetPath = '{target}'; "
        f"$shortcut.WorkingDirectory = '{target.parent}'; "
        "$shortcut.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    link.with_name("lepao-gui.bat").unlink(missing_ok=True)


def remove_startup(link: Path | None = None) -> None:
    link = link or startup_link()
    link.unlink(missing_ok=True)
    link.with_name("lepao-gui.bat").unlink(missing_ok=True)


class RunView:
    """窗口上那一块状态。喂日志就行，不创建控件。"""

    def __init__(self, target_km: float = DISTANCE_TARGET_KM) -> None:
        self.target_km = target_km
        self.reset()

    def reset(self) -> None:
        self.states = ["wait"] * len(STAGES)
        self.km: float | None = None
        self.boot = "准备启动"
        self.note = ""
        self.status = "空闲"

    def begin(self) -> None:
        self.reset()
        self.status = "运行中"

    def apply_line(self, line: str) -> None:
        stage = stage_from_line(line)
        if stage is not None:
            index = STAGES.index(stage)
            for i in range(index):
                if self.states[i] != "failed":
                    self.states[i] = "done"
            self.states[index] = "active"
            for i in range(index + 1, len(self.states)):
                self.states[i] = "wait"
            self.note = ""
            return
        km = km_from_line(line)
        if km is not None:
            self.km = km
            return
        attempt = attempt_from_line(line)
        if attempt is not None:
            if attempt > 1:
                self.note = f"第 {attempt} 次打开 LSPosed"
            return
        if is_retry_line(line):
            self.note = "正在重开 MuMu"
            return
        if MANAGER_SEEN_LOG in line:
            self.note = ""
            return
        boot = boot_from_line(line)
        if boot is not None and self.active_name() is None:
            self.boot = boot

    def active_name(self) -> str | None:
        for name, state in zip(STAGES, self.states):
            if state == "active":
                return name
        return None

    def headline(self) -> str:
        if self.status == "完成":
            return "全部完成"
        if self.status == "已停止":
            name = self.active_name()
            return f"已停在 · {name}" if name else "已停止"
        failed = next((name for name, state in zip(STAGES, self.states) if state == "failed"), None)
        if self.status == "失败":
            return f"失败 · {failed}" if failed else f"失败 · {self.boot}"
        name = self.active_name()
        if name:
            return name
        if self.status == "空闲":
            return "等待运行"
        return self.boot

    def finish(self, code: int, *, stopped: bool = False) -> None:
        if stopped:
            self.status = "已停止"
            return
        if code == 0:
            self.states = ["done" if state == "active" else state for state in self.states]
            self.status = "完成"
            self.note = ""
            return
        self.states = ["failed" if state == "active" else state for state in self.states]
        self.status = "失败"

    def progress(self) -> float:
        if self.km is None or self.target_km <= 0:
            return 0.0
        return min(max(self.km / self.target_km, 0.0), 1.0)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x700")
        self.root.minsize(880, 620)
        self.root.configure(bg=BG)
        self.view = RunView()
        self.started_at: datetime | None = None
        self.proc: subprocess.Popen[str] | None = None
        self.job: ProcessJob | None = None
        self.fired: set[tuple[str, int, int]] = set()
        self.lines: queue.Queue[tuple[str, int | None, int]] = queue.Queue()
        self.generation = 0
        self.stopped = False
        self.auto_var = tk.BooleanVar(value=True)
        self.login_var = tk.BooleanVar(value=startup_enabled())

        self._build()
        self._paint()
        self.root.protocol("WM_DELETE_WINDOW", self._minimize)
        self._tick()
        self.root.after(100, self._drain)
        self.root.after(80, self._dark_caption)

    def _build(self) -> None:
        tk.Frame(self.root, bg=ACCENT, height=3).pack(fill="x")

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(16, 6))
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", anchor="w")
        tk.Label(titles, text="乐跑", bg=BG, fg=TEXT, font=(UI, 22, "bold")).pack(anchor="w")
        tk.Label(
            titles,
            text="步道乐跑 · 到点自动跑完",
            bg=BG,
            fg=MUTED,
            font=(UI, 10),
        ).pack(anchor="w", pady=(2, 0))
        clock_box = tk.Frame(header, bg=BG)
        clock_box.pack(side="right", anchor="e")
        self.clock_label = tk.Label(clock_box, text="00:00:00", bg=BG, fg=TEXT, font=(MONO, 32))
        self.clock_label.pack(anchor="e")
        self.next_label = tk.Label(clock_box, text="", bg=BG, fg=MUTED, font=(UI, 10))
        self.next_label.pack(anchor="e")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(8, 18))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=CARD, highlightthickness=1, highlightbackground=EDGE)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        tk.Label(left, text="流程", bg=CARD, fg=MUTED, font=(UI, 10)).pack(anchor="w", padx=18, pady=(14, 0))
        self.stepper = tk.Canvas(left, width=268, height=480, bg=CARD, highlightthickness=0, bd=0)
        self.stepper.pack(fill="both", expand=True, padx=6, pady=(2, 12))
        self.stepper.bind("<Configure>", lambda _event: self._paint_stepper())

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_km(right)
        self._build_controls(right)
        self._build_log(right)

    def _build_km(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=EDGE)
        card.pack(fill="x")
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=18, pady=(16, 0))
        self.headline_label = tk.Label(top, text="等待运行", bg=CARD, fg=TEXT, font=(UI, 20, "bold"))
        self.headline_label.pack(side="left")
        self.status_label = tk.Label(
            top,
            text="空闲",
            bg="#22262f",
            fg=MUTED,
            font=(UI, 10),
            padx=10,
            pady=3,
        )
        self.status_label.pack(side="right")
        self.note_label = tk.Label(card, text=" ", bg=CARD, fg=AMBER, font=(UI, 10), anchor="w")
        self.note_label.pack(fill="x", padx=18, pady=(4, 0))

        numbers = tk.Frame(card, bg=CARD)
        numbers.pack(fill="x", padx=18, pady=(8, 0))
        self.km_value = tk.Label(numbers, text="—", bg=CARD, fg=TEXT, font=(MONO, 36))
        self.km_value.pack(side="left")
        tk.Label(
            numbers,
            text=f"/ {DISTANCE_TARGET_KM:.2f} 公里",
            bg=CARD,
            fg=MUTED,
            font=(UI, 12),
        ).pack(side="left", padx=(10, 0), pady=(14, 0))
        self.elapsed_label = tk.Label(numbers, text="", bg=CARD, fg=MUTED, font=(MONO, 12))
        self.elapsed_label.pack(side="right", pady=(16, 0))

        bar_row = tk.Frame(card, bg=CARD)
        bar_row.pack(fill="x", padx=18, pady=(10, 0))
        self.bar = tk.Canvas(bar_row, height=12, bg=CARD, highlightthickness=0, bd=0)
        self.bar.pack(side="left", fill="x", expand=True)
        self.percent_label = tk.Label(
            bar_row,
            text="0%",
            bg=CARD,
            fg=MUTED,
            font=(MONO, 11),
            width=5,
            anchor="e",
        )
        self.percent_label.pack(side="left", padx=(10, 0))
        self.bar.bind("<Configure>", lambda _event: self._paint_bar())
        tk.Label(
            card,
            text=f"超过 {DISTANCE_TARGET_KM:.2f} 公里后长按暂停，然后结束",
            bg=CARD,
            fg=DIM,
            font=(UI, 9),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(8, 16))

    def _build_controls(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=BG)
        box.pack(fill="x", pady=(12, 0))
        buttons = tk.Frame(box, bg=BG)
        buttons.pack(anchor="w")
        self.run_button = self._button(buttons, "现在运行", self._run_now, primary=True)
        self.run_button.pack(side="left")
        self.stop_button = self._button(buttons, "停止", self._stop, primary=False)
        self.stop_button.pack(side="left", padx=(8, 0))
        self._button(buttons, "最小化", self._minimize, primary=False).pack(side="left", padx=(8, 0))
        self._button(buttons, "退出", self._quit, primary=False).pack(side="left", padx=(8, 0))
        self.auto_check = tk.Checkbutton(
            box,
            text=schedule_label(),
            variable=self.auto_var,
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=ACCENT,
            font=(UI, 10),
            highlightthickness=0,
            bd=0,
            anchor="w",
        )
        self.auto_check.pack(anchor="w", pady=(10, 0))
        tk.Checkbutton(
            box,
            text="登录 Windows 后自动打开这个窗口",
            variable=self.login_var,
            command=self._toggle_login,
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=ACCENT,
            font=(UI, 10),
            highlightthickness=0,
            bd=0,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            box,
            text="开始运行后会收进任务栏，避免挡住模拟器。时钟继续走，到点仍会自动跑。退出才会关掉。",
            bg=BG,
            fg=DIM,
            font=(UI, 9),
            anchor="w",
        ).pack(anchor="w", pady=(6, 0))

    def _build_log(self, parent: tk.Frame) -> None:
        wrap = tk.Frame(parent, bg=LOG_BG, highlightthickness=1, highlightbackground=EDGE)
        wrap.pack(fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(
            wrap,
            height=8,
            bg=LOG_BG,
            fg="#d5dbe3",
            font=(MONO, 10),
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            wrap="word",
            state="disabled",
            highlightthickness=0,
            cursor="arrow",
        )
        scroll = tk.Scrollbar(wrap, command=self.log.yview, width=12)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("stage", foreground=ACCENT)
        self.log.tag_configure("km", foreground=GREEN)
        self.log.tag_configure("warn", foreground=AMBER)
        self.log.tag_configure("err", foreground=RED)
        self.log.tag_configure("dim", foreground=DIM)
        self.log.tag_configure("plain", foreground="#d5dbe3")

    def _button(self, parent: tk.Frame, text: str, command, *, primary: bool) -> tk.Button:
        if primary:
            bg, fg, active = ACCENT, INK, "#e7ff86"
        else:
            bg, fg, active = "#242833", TEXT, "#343b4c"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg if not primary else INK,
            relief="flat",
            bd=0,
            padx=18,
            pady=8,
            font=(UI, 11, "bold" if primary else "normal"),
            cursor="hand2",
            highlightthickness=0,
        )

    def _tick(self) -> None:
        now = datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        upcoming = next_slot(now)
        day = "今天" if upcoming.date() == now.date() else "明天"
        remaining = max(0, int((upcoming - now).total_seconds()))
        hours, rem = divmod(remaining, 3600)
        minutes, _seconds = divmod(rem, 60)
        auto_on = self.auto_var.get()
        prefix = "" if auto_on else "自动已关 · "
        self.next_label.configure(
            text=f"{prefix}下次 {day} {upcoming:%H:%M} · 还有 {hours}小时{minutes:02d}分",
            fg=MUTED if auto_on else DIM,
        )
        if self.view.status == "运行中" and self.started_at is not None:
            elapsed = int((now - self.started_at).total_seconds())
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.elapsed_label.configure(text=f"已运行 {h:02d}:{m:02d}:{s:02d}")
        if self._busy():
            from lepao.win32 import allow_other_process_foreground

            allow_other_process_foreground()
        if auto_on:
            key = due_key(now)
            if key is not None and key not in self.fired:
                self.fired.add(key)
                self._run_scheduled(f"{key[1]:02d}:{key[2]:02d}")
        self.root.after(1000, self._tick)

    def _run_now(self) -> None:
        self._start("手动开始")

    def _run_scheduled(self, label: str) -> None:
        if self._busy():
            self._write(f"{label} 到了，已有任务在跑，跳过")
            return
        self._start(f"{label} 到点，开始运行")

    def _busy(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        return self.job is not None and self.job.alive()

    def _start(self, reason: str) -> None:
        if self._busy():
            self._write("已有任务在跑")
            return
        if not SCRIPT.exists():
            self._write(f"找不到 {SCRIPT}")
            return
        self.stopped = False
        self.generation += 1
        self.view.begin()
        self.started_at = datetime.now()
        self.elapsed_label.configure(text="已运行 00:00:00")
        self._set_busy_look(True)
        self._clear_log()
        self._paint()
        self._write(reason)
        from lepao.win32 import allow_other_process_foreground

        allow_other_process_foreground()
        argv, console_flag = console_boot_args()
        generation = self.generation
        try:
            # 普通新终端。不挂起，不放进进程组，不接 stdout/stderr。
            self.job = None
            self.proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), creationflags=console_flag)
        except OSError as exc:
            self.proc = None
            self.job = None
            self.view.finish(1)
            self._set_busy_look(False)
            self._write(f"没能启动：{exc}")
            self._paint()
            return
        threading.Thread(target=self._pump, args=(self.proc, generation), daemon=True).start()
        # 按钮回调里还握着前台。先放行，再收起，点击进程才能把光标送进 MuMu。
        self._park()
        self.root.after(200, self._park)
        self._write("已打开终端：conda activate daily，然后运行开机脚本")
        self._write("已收进任务栏，避免挡住模拟器")

    def _pump(self, proc: subprocess.Popen[str], generation: int) -> None:
        # 日志在控制台里，这里通常没有管道。没有管道时也要等到退出，窗口才能收尾。
        if proc.stdout is not None:
            for line in proc.stdout:
                self.lines.put((line.rstrip("\r\n"), None, generation))
        self.lines.put(("", proc.wait(), generation))

    def _drain(self) -> None:
        try:
            while True:
                line, code, generation = self.lines.get_nowait()
                if generation != self.generation:
                    continue
                if code is None:
                    if line:
                        self.view.apply_line(line)
                        self._write(line)
                        self._paint()
                    continue
                self.view.finish(code, stopped=self.stopped)
                self.stopped = False
                self._close_job()
                self._set_busy_look(False)
                self._write(f"结束，退出码 {code}")
                self._paint()
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _close_job(self) -> None:
        job = self.job
        self.job = None
        if job is not None:
            job.close()

    def _stop(self) -> None:
        proc = self.proc
        job = self.job
        proc_running = proc is not None and proc.poll() is None
        job_running = job is not None and job.alive()
        # 启动脚本先退出时，poll 已经有值，但点击进程还在进程组里。这时候也要杀。
        if not proc_running and not job_running:
            return
        self.stopped = True
        killed = job_running and job is not None and job.terminate()
        if job_running and not killed:
            self._write("进程组没能结束，改按进程树停止")
        if proc_running and not killed and proc is not None:
            detail = _taskkill_tree(proc.pid)
            if detail:
                self._write(detail)
        self._close_job()
        self.view.finish(1, stopped=True)
        self._set_busy_look(False)
        self._write("已停止")
        self._paint()

    def _toggle_login(self) -> None:
        if self.login_var.get():
            try:
                install_startup()
            except Exception as exc:
                self.login_var.set(False)
                self._write(f"没能放入启动文件夹：{exc}")
                return
            self._write(f"已放入启动文件夹：{startup_link()}")
            return
        remove_startup()
        self._write("已取消登录后自动打开")

    def _set_busy_look(self, busy: bool) -> None:
        if busy:
            self.run_button.configure(bg="#2a3120", fg="#8a916c")
            self.stop_button.configure(bg="#3a242c", fg=RED)
            return
        self.run_button.configure(bg=ACCENT, fg=INK)
        self.stop_button.configure(bg="#242833", fg=TEXT)

    def _paint(self) -> None:
        view = self.view
        self.headline_label.configure(text=view.headline())
        self.note_label.configure(text=view.note if view.note else " ")
        if view.km is None:
            self.km_value.configure(text="—", fg=TEXT)
            self.percent_label.configure(text="0%")
        else:
            passed = view.km > view.target_km
            self.km_value.configure(text=f"{view.km:.2f}", fg=GREEN if passed else TEXT)
            self.percent_label.configure(text=f"{view.progress() * 100:.0f}%")
        colors = {
            "空闲": ("#22262f", MUTED),
            "运行中": ("#3a3014", AMBER),
            "完成": ("#143028", GREEN),
            "失败": ("#3a1822", RED),
            "已停止": ("#22262f", MUTED),
        }
        bg, fg = colors[view.status]
        self.status_label.configure(text=view.status, bg=bg, fg=fg)
        self._paint_stepper()
        self._paint_bar()

    def _paint_stepper(self) -> None:
        canvas = self.stepper
        canvas.delete("all")
        width = _canvas_size(canvas, horizontal=True)
        height = _canvas_size(canvas, horizontal=False)
        if width < 20 or height < 20:
            return
        count = len(STAGES)
        pad = 8
        gap = (height - pad * 2) / count
        cx = 22

        def center(index: int) -> float:
            return pad + gap * index + gap / 2

        for index, name in enumerate(STAGES):
            state = self.view.states[index]
            cy = center(index)
            if state == "active":
                canvas.create_rectangle(40, cy - 16, width - 8, cy + 16, fill="#22280f", outline="")
            elif state == "failed":
                canvas.create_rectangle(40, cy - 16, width - 8, cy + 16, fill="#2a161c", outline="")
        for index in range(count - 1):
            color = GREEN if self.view.states[index] == "done" else "#2a303a"
            canvas.create_line(cx, center(index) + 12, cx, center(index + 1) - 12, fill=color, width=2)
        for index, name in enumerate(STAGES):
            state = self.view.states[index]
            cy = center(index)
            radius = 7
            if state == "done":
                canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=GREEN, outline="")
                fill = "#d7efe2"
            elif state == "active":
                canvas.create_oval(cx - radius - 4, cy - radius - 4, cx + radius + 4, cy + radius + 4, outline=ACCENT)
                canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=ACCENT, outline="")
                fill = TEXT
            elif state == "failed":
                canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=RED, outline="")
                fill = RED
            else:
                canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline=DIM, width=1)
                fill = DIM
            weight = "bold" if state == "active" else "normal"
            canvas.create_text(46, cy, text=f"{index + 1:02d}   {name}", anchor="w", fill=fill, font=(UI, 11, weight))

    def _paint_bar(self) -> None:
        canvas = self.bar
        canvas.delete("all")
        width = _canvas_size(canvas, horizontal=True)
        height = _canvas_size(canvas, horizontal=False)
        if width < 8 or height < 4:
            return
        radius = (height - 2) / 2
        _pill(canvas, 0, 1, width, height - 1, radius, fill=TRACK)
        span = self.view.progress() * width
        if span < 2:
            return
        color = GREEN if self.view.km is not None and self.view.km > self.view.target_km else ACCENT
        _pill(canvas, 0, 1, max(span, height), height - 1, radius, fill=color)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _write(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n", _log_tag(message))
        rows = int(self.log.index("end-1c").split(".")[0])
        if rows > 1000:
            self.log.delete("1.0", f"{rows - 800}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _dark_caption(self) -> None:
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attr,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception:
            return

    def _park(self) -> None:
        """运行中把本窗口让开。前台还是它时，模块点击会落进来。"""
        if not self.root.winfo_exists():
            return
        from lepao.win32 import allow_other_process_foreground

        allow_other_process_foreground()
        self._minimize()

    def _minimize(self) -> None:
        """收进任务栏。时钟和正在跑的流程都继续。"""
        self.root.iconify()

    def _quit(self) -> None:
        if self._busy():
            from tkinter import messagebox

            if not messagebox.askokcancel(APP_TITLE, "正在跑，退出会停掉这次。"):
                return
        self._stop()
        self.root.destroy()


def _taskkill_tree(pid: int) -> str:
    result = subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    data = (result.stdout or b"") + (result.stderr or b"")
    return data.decode("mbcs", errors="replace").strip()


def _canvas_size(canvas: tk.Canvas, *, horizontal: bool) -> int:
    """窗口还没映射出来时，winfo 是 1，用创建时写的尺寸。"""
    actual = canvas.winfo_width() if horizontal else canvas.winfo_height()
    if actual > 1:
        return actual
    key = "width" if horizontal else "height"
    return int(canvas.cget(key))


def _pill(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, radius: float, fill: str) -> None:
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    canvas.create_polygon(
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
        smooth=True,
        fill=fill,
        outline="",
    )


def _log_tag(line: str) -> str:
    if stage_from_line(line):
        return "stage"
    if km_from_line(line) is not None:
        return "km"
    if is_retry_line(line) or "没看到" in line or "没进" in line or "重开" in line:
        return "warn"
    if any(word in line for word in ("失败", "Error", "Traceback", "找不到")):
        return "err"
    if line.startswith("  "):
        return "dim"
    return "plain"


def _claim_single_instance() -> bool:
    """第二次双击时把已经在跑的窗口还原，不再开一个时钟。"""
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\LepaoGui")
    if not handle:
        return True
    global _INSTANCE_MUTEX
    _INSTANCE_MUTEX = handle
    return kernel32.GetLastError() != 183


def _restore_existing() -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value == APP_TITLE:
            found.append(int(hwnd))
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return
    user32.ShowWindow(found[0], 9)
    user32.SetForegroundWindow(found[0])


def main() -> None:
    from lepao.win32 import enable_per_monitor_dpi

    enable_per_monitor_dpi()
    if not _claim_single_instance():
        _restore_existing()
        return
    legacy = startup_dir() / "lepao-gui.bat"
    if legacy.exists() and LAUNCHER.exists():
        try:
            install_startup()
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


_INSTANCE_MUTEX: object | None = None


if __name__ == "__main__":
    main()

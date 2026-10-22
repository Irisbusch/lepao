# lepao

打开 MuMu「乐跑」，连上 ADB，然后在模拟器窗口上走完 KernelSU 到乐跑的界面。

点击用的是 Windows 鼠标，落在 MuMu 客户区里。uiautomator2 只读界面。ADB `input tap` 会打进安卓桌面，所以不用它。

## 布局

- `start-mumu-lepao.ps1`：开机、等 Android、连接 ADB、调用 Python。KernelSU 由界面流程在无障碍之后启动。
- `config.json`：这台机器的 MuMu 路径、Python 解释器、实例名。
- `lepao/`：窗口定位（`win32.py`）、读界面（`screen.py`）、点击顺序（`flow.py`）、比例坐标（`config.py`）、关掉并重开 MuMu（`mumu.py`）。
- `kernelsu_lsposed.py`：旧入口，参数不变，转到 `python -m lepao`。
- `artifacts/`：失败时的截图。已忽略，不进版本库。

## 环境

`uiautomator2` 在 conda 环境 `daily` 里。`config.json` 的 `python` 指向这个解释器。基础环境 `E:\Anaconda3\python.exe` 没有这个包。

```powershell
& "E:\Anaconda3\envs\daily\python.exe" -m pip install -r G:\scripts\requirements.txt
```

## 用法

双击 `lepao-gui.exe` 打开窗口。可以按「现在运行」。最小化后程序继续留着，每天 08:00 和 17:00 仍会自动跑。按「退出」才会关掉。勾选「登录 Windows 后自动打开」后，开机登录就会打开。时刻在 `lepao/config.py` 的 `SCHEDULE_TIMES`。窗口标题是「自动跑」，避免和 MuMu「乐跑」抢点击。

整套开机并跑完界面：

```powershell
pwsh -File G:\scripts\start-mumu-lepao.ps1
```

模拟器已经开着、ADB 已连接时，只跑界面。序列号以 `adb devices` 为准。

```powershell
E:\Anaconda3\envs\daily\python.exe -m lepao 127.0.0.1:16416
```

光标停在一个比例点上再点击。不写 `--x` `--y` 时点的是 `Points.ENTER_RUN`。

```powershell
E:\Anaconda3\envs\daily\python.exe -m lepao 127.0.0.1:16416 --last --x 0.50 --y 0.93
```

只把光标停过去，不点击：

```powershell
E:\Anaconda3\envs\daily\python.exe -m lepao 127.0.0.1:16416 --look --x 0.50 --y 0.93
```

点「执行」后如果停在广播日志页，会关掉全部 MuMu 实例和主程序，再只开机「乐跑」重跑。最多 `LSPOSED_LAUNCH_ATTEMPTS` 次。

旧命令仍然可用：

```powershell
E:\Anaconda3\envs\daily\python.exe G:\scripts\kernelsu_lsposed.py 127.0.0.1:16416
```

运行时鼠标会被抢走。「乐跑」窗口留在屏幕上，不要最小化。

换一台机器时，改 `config.json`。界面点偏时，改 `lepao/config.py` 里的 `Points`。

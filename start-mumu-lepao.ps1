<#
.SYNOPSIS
    打开 MuMu「乐跑」，连接 ADB，再跑界面流程。界面流程里先打开无障碍，再启动 KernelSU。
.DESCRIPTION
    机器相关路径在仓库根目录的 config.json。参数可以覆盖配置。
.EXAMPLE
    pwsh -File G:\scripts\start-mumu-lepao.ps1
.EXAMPLE
    pwsh -File G:\scripts\start-mumu-lepao.ps1 -PlayerName "乐跑" -TimeoutSec 180
#>

param(
    [string]$PlayerName,
    [int]$TimeoutSec,
    [int]$AdbReadyTimeoutSec,
    [string]$Manager,
    [string]$Adb,
    [string]$VmsRoot,
    [string]$Python
)

$ErrorActionPreference = "Stop"
# 窗口把这条管道当 UTF-8 读。不设的话，中文会按系统 ANSI 码页出去，日志里就是乱码。
$utf8 = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $utf8
try { [Console]::OutputEncoding = $utf8 } catch {}

$RepoRoot = Split-Path -Parent $PSCommandPath
$ConfigPath = Join-Path $RepoRoot "config.json"
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "找不到配置: $ConfigPath"
}
$Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $PSBoundParameters.ContainsKey("PlayerName")) { $PlayerName = [string]$Config.player_name }
if (-not $PSBoundParameters.ContainsKey("TimeoutSec")) { $TimeoutSec = [int]$Config.timeout_sec }
if (-not $PSBoundParameters.ContainsKey("AdbReadyTimeoutSec")) { $AdbReadyTimeoutSec = [int]$Config.adb_ready_timeout_sec }
if (-not $PSBoundParameters.ContainsKey("Manager")) { $Manager = [string]$Config.mumu_manager }
if (-not $PSBoundParameters.ContainsKey("Adb")) { $Adb = [string]$Config.adb }
if (-not $PSBoundParameters.ContainsKey("VmsRoot")) { $VmsRoot = [string]$Config.vms_root }
if (-not $PSBoundParameters.ContainsKey("Python")) { $Python = [string]$Config.python }

function Invoke-MuMu {
    param([string[]]$MuMuArgs)

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Manager
    $psi.Arguments = ($MuMuArgs -join " ")
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    $process = [System.Diagnostics.Process]::Start($psi)
    $output = $process.StandardOutput.ReadToEnd()
    $err = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if ($process.ExitCode -ne 0 -and -not $output) {
        throw "MuMuManager 失败: $($MuMuArgs -join ' ') `n$err"
    }
    return $output
}

function Get-JsonObject {
    param([string]$Text)
    $start = $Text.IndexOf("{")
    $end = $Text.LastIndexOf("}")
    if ($start -lt 0 -or $end -lt $start) {
        throw "输出里没有 JSON:`n$Text"
    }
    return $Text.Substring($start, $end - $start + 1) | ConvertFrom-Json
}

function Get-Players {
    return Get-JsonObject (Invoke-MuMu -MuMuArgs @("info", "-v", "all"))
}

function Get-Player {
    param($Players, [string]$Index)
    return $Players.$Index
}

function Wait-AndroidReady {
    param([string]$Index)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        Start-Sleep -Seconds 2
        $player = Get-Player (Get-Players) $Index
        Write-Host ("  进程={0}  Android={1}" -f $player.is_process_started, $player.is_android_started)
        if ($player.is_android_started -eq $true) {
            return
        }
    } while ((Get-Date) -lt $deadline)
    throw "等待「$PlayerName」开机超过 $TimeoutSec 秒"
}

function Get-AdbHostPort {
    param($Target)
    $vmConfig = Join-Path $VmsRoot ("MuMuPlayer-{0}-{1}\configs\vm_config.json" -f $Target.android_version, $Target.index)
    if (-not (Test-Path -LiteralPath $vmConfig)) {
        throw "找不到虚拟机配置: $vmConfig"
    }
    return (Get-Content -LiteralPath $vmConfig -Raw -Encoding UTF8 | ConvertFrom-Json).vm.nat.port_forward.adb.host_port
}

function Wait-AdbDevice {
    param([string]$Serial)
    Write-Host "连接 adb $Serial"
    $deadline = (Get-Date).AddSeconds($AdbReadyTimeoutSec)
    $devices = ""
    do {
        & $Adb connect $Serial 2>&1 | Out-Null
        $devices = & $Adb devices 2>&1 | Out-String
        if ($devices -match [regex]::Escape($Serial) + "\s+device") {
            Write-Host "设备已就绪: $Serial"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    Write-Warning "Android 已启动，但 adb 还没变成 device。端口 $Serial"
    exit 1
}

if (-not (Test-Path -LiteralPath $Manager)) {
    throw "找不到 MuMuManager: $Manager"
}
if (-not (Test-Path -LiteralPath $Adb)) {
    throw "找不到 adb: $Adb"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "找不到 Python: $Python 。config.json 的 python 需要指向已安装 uiautomator2 的解释器。"
}

Write-Host "打开 MuMu 主程序"
Invoke-MuMu -MuMuArgs @("main", "launch") | Out-Null
Start-Sleep -Seconds 2

$players = Get-Players
$target = $null
foreach ($property in $players.PSObject.Properties) {
    if ($property.Value.name -eq $PlayerName) {
        $target = $property.Value
        break
    }
}
if (-not $target) {
    $names = @($players.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value.name)" }) -join ", "
    $raw = $players | ConvertTo-Json -Depth 3 -Compress
    throw "没有名为「$PlayerName」的实例。当前有: $names`n原始: $raw"
}

$index = [string]$target.index
Write-Host "开机「$PlayerName」(index $index, Android $($target.android_version))"
Invoke-MuMu -MuMuArgs @("control", "--vmindex", $index, "launch") | Out-Null
Invoke-MuMu -MuMuArgs @("control", "--vmindex", $index, "show_window") | Out-Null
Wait-AndroidReady -Index $index

$port = Get-AdbHostPort -Target $target
if (-not $port) {
    throw "无法获取 ADB 端口"
}
$serial = "127.0.0.1:$port"
Wait-AdbDevice -Serial $serial

Write-Host "执行界面流程..."
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RepoRoot;$($env:PYTHONPATH)"
} else {
    $env:PYTHONPATH = $RepoRoot
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
# 用配置里的 python.exe，不要换成 pythonw。pythonw 没有控制台，前台还是「自动跑」时
# 系统会丢掉 SetCursorPos，光标进不了 MuMu，停止也等不到它退出。
# 这个控制台由 lepao 自己最小化，不挡模拟器。

Push-Location $RepoRoot
try {
    & $Python -m lepao $serial
    if ($LASTEXITCODE -ne 0) {
        throw "界面流程失败，退出码 $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "全部完成"
exit 0

# TabDock installer for Windows 10/11: venv + autostart at log on (Task Scheduler) + firewall rule for home networks.
#   .\install-windows.ps1              install / update and (re)start
#   .\install-windows.ps1 -Port 9000   use another port
#   .\install-windows.ps1 -Status      is it running, and the address for the tablet
#   .\install-windows.ps1 -Uninstall   stop and remove the autostart (data\ is kept)
# Run in PowerShell from the TabDock folder. If scripts are blocked: powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
param([int]$Port = 8787, [switch]$Status, [switch]$Uninstall)
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$Me = [Security.Principal.WindowsIdentity]::GetCurrent().Name      # COMPUTER\user (USERDOMAIN can be wrong in remote sessions)
$Dir = $PSScriptRoot
$Task = "TabDock"
$Rule = "TabDock"
function Say($t) { Write-Host "> $t" -ForegroundColor Cyan }
function Warn($t) { Write-Host "! $t" -ForegroundColor Yellow }
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Stop-TabDock {
    Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
    $run = Join-Path $env:LOCALAPPDATA "TabDock\run.json"
    if (Test-Path $run) {
        $p = Get-Content $run -Raw | ConvertFrom-Json
        foreach ($id in @($p.runner, $p.server, $p.tray)) { if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }
    }
}

function Firewall($cmd) {
    # the rule needs administrator rights: Windows asks once (UAC) when this window is not elevated
    if ($admin) { Invoke-Expression $cmd } else { Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", $cmd }
}

if ($Uninstall) {
    Stop-TabDock
    Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
    Firewall "Remove-NetFirewallRule -DisplayName '$Rule' -ErrorAction SilentlyContinue"
    Say "Автозапуск удалён. Данные остались в $Dir\data"
    exit 0
}

$py = Join-Path $Dir ".venv\Scripts\python.exe"
if ($Status) {
    Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue | Select-Object TaskName, State | Format-Table
    if (Test-Path $py) { & $py (Join-Path $Dir "server.py") --port $Port --print-url }
    exit 0
}

# 1. Python 3.9+ (python.org or Microsoft Store), venv, packages
$base = $null
foreach ($c in @("py -3", "python")) {
    try {
        $exe = & ([scriptblock]::Create("$c -c `"import sys; print(sys.executable if sys.version_info >= (3, 9) else '')`"")) 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe) -and $exe -notmatch "WindowsApps\\python.exe$") { $base = $exe; break }
    } catch { }
}
if (-not $base) {
    $cand = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($cand) { $base = $cand.FullName }
}
if (-not $base) {
    Warn "Нужен Python 3.9 или новее: https://www.python.org/downloads/windows/ (галочка «Add python.exe to PATH»)"
    Warn "или в терминале: winget install Python.Python.3.12 — и запустите установщик ещё раз."
    exit 1
}
if (-not (Test-Path $py)) { Say "Создаю venv"; & $base -m venv (Join-Path $Dir ".venv") }
Say "Ставлю зависимости Python"
& $py -m pip install -q --disable-pip-version-check --only-binary=:all: -r (Join-Path $Dir "requirements.txt")
if ($LASTEXITCODE -ne 0) { Warn "pip не смог поставить зависимости (нет интернета?)"; exit 1 }

# 2. Firewall: the port only for private (home) networks; in a public Wi-Fi the dock stays closed
Say "Открываю порт $Port для домашних сетей"
Firewall "Remove-NetFirewallRule -DisplayName '$Rule' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName '$Rule' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private,Domain | Out-Null; New-NetFirewallRule -DisplayName '$Rule' -Direction Inbound -Protocol UDP -LocalPort 5353 -Action Allow -Profile Private,Domain | Out-Null"
$cat = (Get-NetConnectionProfile | Select-Object -First 1).NetworkCategory
if ("$cat" -eq "Public") { Warn "Сеть помечена как «Общедоступная»: планшет компьютер не увидит. Параметры → Сеть и Интернет → свойства сети → «Частная сеть»." }

# 3. Autostart: Task Scheduler, at log on, in your own session (a Windows service could not see the desktop, music, keys)
Stop-TabDock
$pyw = Join-Path $Dir ".venv\Scripts\pythonw.exe"
$action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$Dir\dock\windows\run.py`" --port $Port" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $Me
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $Me -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $Task -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "TabDock — док для планшета или телефона" -Force | Out-Null
Start-ScheduledTask -TaskName $Task
Say "TabDock запущен и будет стартовать при входе в Windows"

# 4. Wait for it and show the address
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://localhost:$Port/api/hello" | Out-Null; $ok = $true; break } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ok) { Warn "Сервер не ответил. Журнал: $env:LOCALAPPDATA\TabDock\logs\tabdock.log"; exit 1 }
Say "Готово! Панель TabDock на этом компьютере: http://localhost:$Port (там QR-код)"
Say "Планшет или телефон: в приложении TabDock нажмите «Сканировать QR-код», затем «Разрешить» в панели."
Say "Значок TabDock — в области уведомлений (справа внизу, может быть под стрелкой ^)."
Start-Process "http://localhost:$Port/"

@echo off
chcp 65001 >nul
setlocal
set "TRIPILOT_BATCH=%~f0"
set "TRIPILOT_ROOT=%~dp0"
set "TRIPILOT_ACTION=%~1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$text=[IO.File]::ReadAllText($env:TRIPILOT_BATCH,[Text.Encoding]::UTF8); $body=$text.Substring($text.IndexOf([Environment]::NewLine+'#==POWERSHELL==')+([Environment]::NewLine+'#==POWERSHELL==').Length); & ([scriptblock]::Create($body))"
set "RESULT=%ERRORLEVEL%"
if /I not "%~1"=="check" pause
exit /b %RESULT%
#==POWERSHELL==

$ErrorActionPreference = 'Stop'
$repo = Join-Path $env:TRIPILOT_ROOT 'final_project_cs'
$stateDir = Join-Path $env:TRIPILOT_ROOT '.tmp\local-services'
$stateFile = Join-Path $stateDir 'processes.json'
$action = $env:TRIPILOT_ACTION
function Open-Port([int]$port) {
    $c = New-Object Net.Sockets.TcpClient
    try { return ($c.ConnectAsync('127.0.0.1', $port).Wait(500) -and $c.Connected) }
    catch { return $false } finally { $c.Dispose() }
}
function Save-State { ConvertTo-Json -InputObject @($script:owned) -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding UTF8 }
function Stop-Owned {
    if (-not (Test-Path -LiteralPath $stateFile)) { Write-Host '이 배치가 실행한 로컬 개발 프로세스 기록이 없습니다.'; return }
    $remaining = @()
    foreach ($entry in @(Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json | Sort-Object -Property Order -Descending)) {
        $p = Get-Process -Id $entry.Id -ErrorAction SilentlyContinue
        if (-not $p) { continue }
        if ($p.StartTime.ToUniversalTime().Ticks.ToString() -ne $entry.StartTicks) { Write-Warning "PID 재사용으로 제외: $($entry.Name)"; continue }
        & taskkill.exe /PID $entry.Id /T /F | Out-Host
        if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $entry.Id -ErrorAction SilentlyContinue)) { $remaining += $entry }
    }
    $script:owned = $remaining; Save-State
    if ($remaining.Count) { throw '종료하지 못한 프로세스가 있습니다. 기록을 유지했습니다.' }
    Write-Host '이 배치가 켠 로컬 개발 프로세스를 종료했습니다. 공유 DB와 기존 실행 프로세스는 유지했습니다.'
}
try {
    if ($action -eq 'stop') { Stop-Owned; exit 0 }
    if ($action -and $action -ne 'check') { throw '사용법: triPilot-실행.bat [check] / triPilot-종료.bat' }
    $starter = Join-Path $env:USERPROFILE '.acop-ops\start-acop.ps1'
    $web = Join-Path $repo 'frontend\apps\web'
    $admin = Join-Path $repo 'frontend\apps\admin'
    foreach ($path in @($starter, (Join-Path $repo 'app\ops_entrypoint.py'), (Join-Path $web 'node_modules\next\dist\bin\next'), (Join-Path $admin 'node_modules\next\dist\bin\next'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw "필요한 파일이 없습니다: $path" }
    }
    $python = (Get-Command python -ErrorAction Stop).Source
    $node = (Get-Command node -ErrorAction Stop).Source
    $plans = @(
        @{Name='고객 API·감시·알림·연결'; Port=8042; Exe='powershell.exe'; Args=('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $starter); Dir=$repo},
        @{Name='운영 API'; Port=8070; Exe=$python; Args='-m app.ops_entrypoint'; Dir=$repo},
        @{Name='고객 웹앱'; Port=3100; Exe=$node; Args='node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3100'; Dir=$web},
        @{Name='관리자 웹앱'; Port=3300; Exe=$node; Args='node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3300'; Dir=$admin}
    )
    if ($action -eq 'check') {
        foreach ($plan in $plans) { Write-Host "$($plan.Name): $($plan.Port) 준비됨" }
        Write-Host '설정 점검만 완료했습니다. 프로세스 실행·종료는 하지 않았습니다.'; exit 0
    }
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    $script:owned = @()
    if (Test-Path -LiteralPath $stateFile) { $script:owned = @(Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json) }
    $env:PYTHONPATH = Join-Path $env:TRIPILOT_ROOT 'final_project_sample'
    $env:ACOP_OPS_API_BASE_URL = 'http://127.0.0.1:8042'
    $env:ADMIN_OPS_API_URL = 'http://127.0.0.1:8070'
    $env:NEXT_PUBLIC_API_BASE = 'http://127.0.0.1:8042'
    $env:NEXT_PUBLIC_DATA_MODE = 'live'
    $env:NEXT_PUBLIC_ADMIN_DATA_MODE = 'live'
    $env:NEXT_DIST_DIR = '.next-batch'
    $run = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $order = 0
    foreach ($plan in $plans) {
        $order++
        if (Open-Port $plan.Port) { Write-Host "$($plan.Name): 이미 포트가 열려 있어 새로 실행하지 않습니다. 기존 프로세스는 종료 대상에 넣지 않습니다."; continue }
        $p = Start-Process -FilePath $plan.Exe -ArgumentList $plan.Args -WorkingDirectory $plan.Dir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir "$run-$($plan.Port).out.log") -RedirectStandardError (Join-Path $stateDir "$run-$($plan.Port).err.log")
        $script:owned += @{Name=$plan.Name; Id=$p.Id; StartTicks=$p.StartTime.ToUniversalTime().Ticks.ToString(); Order=$order}
        Save-State
        $ready = $false
        for ($i=0; $i -lt 180; $i++) {
            if ($p.HasExited) { throw "$($plan.Name) 실행이 종료됐습니다. .tmp\local-services 로그를 확인하세요." }
            if (Open-Port $plan.Port) { $ready=$true; break }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) { throw "$($plan.Name) 포트가 열리지 않았습니다. 종료 배치로 정리한 뒤 로그를 확인하세요." }
        Write-Host "$($plan.Name): 포트 열림 $($plan.Port)"
    }
    Write-Host '고객 웹앱: http://127.0.0.1:3100'
    Write-Host '관리자 웹앱: http://127.0.0.1:3300'
    Write-Host '포트 기동 확인입니다. 관리자 로그인 계정·외부 API 설정은 기존 비공개 설정을 사용합니다.'
    Write-Host '종료하려면 프로젝트 루트의 triPilot-종료.bat를 실행하세요. 공유 DB는 유지합니다.'
    exit 0
} catch { Write-Host "실패: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

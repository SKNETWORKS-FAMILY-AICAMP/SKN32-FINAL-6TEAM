@setlocal & set "TRIPILOT_BATCH=%~f0" & set "TRIPILOT_ROOT=%~dp0" & set "TRIPILOT_ACTION=%~1" & powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$text=[IO.File]::ReadAllText($env:TRIPILOT_BATCH,[Text.Encoding]::UTF8); $body=($text -split '(?m)^#==POWERSHELL==\r?$',2)[1]; & ([scriptblock]::Create($body))" && exit /b 0 || exit /b 1
#==POWERSHELL==

$ErrorActionPreference = 'Stop'
$repo = Join-Path $env:TRIPILOT_ROOT 'final_project_cs'
$stateDir = Join-Path $env:TRIPILOT_ROOT '.tmp\local-services'
$stateFile = Join-Path $stateDir 'processes.json'
$action = $env:TRIPILOT_ACTION
$pollMilliseconds = 500
function Open-Port([int]$port) {
    $c = New-Object Net.Sockets.TcpClient
    try { return ($c.ConnectAsync('127.0.0.1', $port).Wait(500) -and $c.Connected) }
    catch { return $false } finally { $c.Dispose() }
}
function Test-ListenerOwned($plan, $process) {
    $listeners = @(Get-NetTCPConnection -LocalPort $plan.Port -State Listen -ErrorAction Stop)
    if (-not $listeners.Count) { return $false }
    foreach ($listener in $listeners) {
        $currentId = [int]$listener.OwningProcess
        $visited = [Collections.Generic.HashSet[int]]::new()
        while ($currentId -ne $process.Id) {
            if (-not $visited.Add($currentId)) { return $false }
            $child = Get-Process -Id $currentId -ErrorAction Stop
            if ($child.StartTime.ToUniversalTime() -lt $process.StartTime.ToUniversalTime()) { return $false }
            $info = Get-CimInstance Win32_Process -Filter "ProcessId=$currentId" -ErrorAction Stop
            if (-not $info -or -not $info.ParentProcessId) { return $false }
            $currentId = [int]$info.ParentProcessId
        }
    }
    return $true
}
function Test-AppResponse($plan) {
    $response = $null
    try {
        $request = [Net.HttpWebRequest]::Create("http://127.0.0.1:$($plan.Port)$($plan.HealthPath)")
        $request.Proxy = $null
        $request.AllowAutoRedirect = $false
        $request.Timeout = $pollMilliseconds
        $request.ReadWriteTimeout = $pollMilliseconds
        $response = $request.GetResponse()
        if ([int]$response.StatusCode -ne 200) { return $false }
        if (-not $plan.HealthApp) { return $true }
        $reader = [IO.StreamReader]::new($response.GetResponseStream())
        try { $health = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        if ($health.status -ne 'ok') { return $false }
        return ($plan.HealthApp -eq 'customer' -or $health.app -eq $plan.HealthApp)
    } catch { return $false } finally { if ($response) { $response.Dispose() } }
}
function Save-State { ConvertTo-Json -InputObject @($script:owned) -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding UTF8 }
function Stop-Owned {
    if (-not (Test-Path -LiteralPath $stateFile)) { Write-Host '이 배치가 실행한 로컬 개발 프로세스 기록이 없습니다.'; return }
    $remaining = @()
    $entries = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    foreach ($entry in @($entries | Sort-Object -Property Order -Descending)) {
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
    foreach ($path in @((Join-Path $repo 'app\ops_entrypoint.py'), (Join-Path $web 'node_modules\next\dist\bin\next'), (Join-Path $admin 'node_modules\next\dist\bin\next'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw "필요한 파일이 없습니다: $path" }
    }
    $python = (Get-Command python -ErrorAction Stop).Source
    $node = (Get-Command node -ErrorAction Stop).Source
    $apiPlan = @{Name='고객 API'; Port=8042; Exe=$python; Args='-m uvicorn app.presentation.api.app:app --host 127.0.0.1 --port 8042 --reload'; Dir=$repo}
    if (Test-Path -LiteralPath $starter) {
        $apiPlan = @{Name='고객 API·감시·알림·연결'; Port=8042; Exe='powershell.exe'; Args=('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $starter); Dir=$repo}
        Write-Host '고객 API: 기존 개인 시작 스크립트 경로를 유지합니다.'
    } else {
        Write-Host '고객 API: README 기본 uvicorn을 사용합니다. 감시·알림 작업자는 별도 기동이 필요합니다.'
    }
    $plans = @(
        $apiPlan,
        @{Name='운영 API'; Port=8070; Exe=$python; Args='-m app.ops_entrypoint --host 127.0.0.1 --port 8070'; Dir=$repo},
        @{Name='고객 웹앱'; Port=3100; Exe=$node; Args='node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3100'; Dir=$web},
        @{Name='관리자 웹앱'; Port=3300; Exe=$node; Args='node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3300'; Dir=$admin}
    )
    foreach ($plan in $plans) { $plan.HealthPath = '/'; $plan.HealthApp = $null }
    $plans[0].HealthPath = '/health'; $plans[0].HealthApp = 'customer'
    $plans[1].HealthPath = '/health'; $plans[1].HealthApp = 'ops'
    if ($action -eq 'check') {
        foreach ($plan in $plans) { Write-Host "$($plan.Name): $($plan.Port) 준비됨" }
        Write-Host '설정 점검만 완료했습니다. 프로세스 실행·종료는 하지 않았습니다.'; exit 0
    }
    foreach ($plan in $plans) {
        if (Open-Port $plan.Port) { throw "포트 충돌: $($plan.Name) $($plan.Port). 기존 listener는 재사용하거나 종료하지 않습니다." }
    }
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    $script:owned = @()
    if (Test-Path -LiteralPath $stateFile) { $script:owned = @(Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json | ForEach-Object { $_ }) }
    $env:PYTHONPATH = Join-Path $env:TRIPILOT_ROOT 'final_project_sample'
    $env:ACOP_OPS_API_BASE_URL = 'http://127.0.0.1:8042'
    $env:ADMIN_OPS_API_URL = 'http://127.0.0.1:8070'
    $env:NEXT_PUBLIC_API_BASE = 'http://127.0.0.1:8042'
    $env:NEXT_PUBLIC_DATA_MODE = 'live'
    $env:NEXT_PUBLIC_ADMIN_DATA_MODE = 'live'
    $env:NEXT_DIST_DIR = '.next-batch'
    $run = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $order = 0
    $running = @()
    foreach ($plan in $plans) {
        $order++
        if (Open-Port $plan.Port) { throw "포트 충돌: $($plan.Name) $($plan.Port). 기존 listener는 종료하지 않습니다." }
        $p = Start-Process -FilePath $plan.Exe -ArgumentList $plan.Args -WorkingDirectory $plan.Dir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir "$run-$($plan.Port).out.log") -RedirectStandardError (Join-Path $stateDir "$run-$($plan.Port).err.log")
        $script:owned += @{Name=$plan.Name; Id=$p.Id; StartTicks=$p.StartTime.ToUniversalTime().Ticks.ToString(); Order=$order}
        $running += @{Plan=$plan; Process=$p; StartTicks=$p.StartTime.ToUniversalTime().Ticks.ToString()}
        Save-State
        $ready = $false
        for ($i=0; $i -lt 180; $i++) {
            if ($p.HasExited) { throw "$($plan.Name) 실행이 종료됐습니다. .tmp\local-services 로그를 확인하세요." }
            if (Open-Port $plan.Port) {
                if (-not (Test-ListenerOwned $plan $p)) { throw "$($plan.Name): 비소유 listener 충돌" }
                if (Test-AppResponse $plan) { $ready=$true; break }
            }
            Start-Sleep -Milliseconds $pollMilliseconds
        }
        if (-not $ready) { throw "$($plan.Name) 준비 실패. 종료 배치로 정리한 뒤 로그를 확인하세요." }
        Write-Host "$($plan.Name): 소유 listener와 HTTP 준비 확인 $($plan.Port)"
    }
    foreach ($entry in $running) {
        $p = $entry.Process
        $p.Refresh()
        if ($p.HasExited -or $p.StartTime.ToUniversalTime().Ticks.ToString() -ne $entry.StartTicks) { throw "$($entry.Plan.Name): 최종 생존 확인 실패. 소유 기록을 유지했습니다." }
        if (-not (Open-Port $entry.Plan.Port) -or -not (Test-ListenerOwned $entry.Plan $p) -or -not (Test-AppResponse $entry.Plan)) { throw "$($entry.Plan.Name): 최종 준비 확인 실패. 소유 기록을 유지했습니다." }
    }
    foreach ($entry in $running) {
        $entry.Process.Refresh()
        if ($entry.Process.HasExited) { throw "$($entry.Plan.Name): 최종 HTTP 확인 중 프로세스 종료" }
    }
    Write-Host '고객 웹앱: http://127.0.0.1:3100'
    Write-Host '관리자 웹앱: http://127.0.0.1:3300'
    Write-Host '소유 프로세스·HTTP 준비 확인입니다. 로그인·tenant·DB·예약 OFF 저장 확인은 별도입니다.'
    Write-Host '종료하려면 프로젝트 루트의 triPilot-종료.bat를 실행하세요. 공유 DB는 유지합니다.'
    exit 0
} catch { Write-Host "실패: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

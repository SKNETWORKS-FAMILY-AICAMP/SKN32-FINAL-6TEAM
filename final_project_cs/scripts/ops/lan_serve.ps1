# triPilot — 같은 공유기에 붙은 다른 기기(폰 등)에서 웹앱을 보게 서버 둘을 연다.
#
#   API 서버(고객용)   0.0.0.0:8043   — 폰의 브라우저가 이 PC 의 **공유기 주소**로 부른다
#   웹앱(Next 개발)     0.0.0.0:3110   — 폰은 http://<이 PC 주소>:3110 을 연다
#
# ★평소 쓰는 서버(127.0.0.1:8042 · 3100)는 건드리지 않는다 — 포트를 달리해 **따로** 띄운다. 같은 DB 를 쓴다(API 는 상태 없는 프로세스라 둘이 떠도 된다).
# ★주소는 실행할 때마다 이 PC 에서 읽는다(공유기가 바꿀 수 있다). 파일에 적지 않는다.
# ★폰에서 안 열리면 거의 윈도 방화벽이다 — 관리자 PowerShell 에서 `scripts\\ops\\lan_firewall.ps1` 을 한 번 실행한다(이 스크립트는 방화벽을 건드리지 않는다).
# ★http 라서 폰 브라우저가 **위치 · 복사** 기능을 막을 수 있다(안전한 연결 https 에서만 허락하는 기능). 화면 확인에는 영향이 없다.
# 멈추려면 이 창에서 Ctrl+C — 여기서 띄운 둘이 같이 내려간다.
param(
  [int]$WebPort = 3110,
  [int]$ApiPort = 8043,
  [string]$Ip = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)          # scripts\ops → 저장소 루트
$webDir = Join-Path $repo 'frontend\apps\web'
if (-not (Test-Path (Join-Path $repo 'app\presentation\api\app.py'))) { throw "저장소 구조가 다르다 — $repo" }
if (-not (Test-Path (Join-Path $webDir 'node_modules'))) { throw "웹앱 의존성이 없다 — frontend\apps\web 에서 npm ci 를 먼저" }

function Test-Open([int]$Port) {
  $c = New-Object System.Net.Sockets.TcpClient
  try { $c.ConnectAsync('127.0.0.1', $Port).Wait(700) -and $c.Connected } catch { $false } finally { $c.Dispose() }
}
function Say([string]$Text) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Text) }
function Get-LanIp {
  # 기본 게이트웨이가 있는 어댑터의 사설 IPv4 — VPN 어댑터(게이트웨이 없음)는 건너뛴다
  foreach ($c in (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' })) {
    foreach ($a in $c.IPv4Address) {
      if ($a.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)') { return $a.IPAddress }
    }
  }
  return $null
}

if (-not $Ip) { $Ip = Get-LanIp }
if (-not $Ip) { throw '공유기에 연결된 사설 주소를 못 찾았다 — Wi-Fi/랜선 연결을 확인하거나 -Ip 로 직접 준다' }
foreach ($p in @($WebPort, $ApiPort)) { if (Test-Open $p) { throw "$p 번 포트를 이미 누가 쓰고 있다 — -WebPort / -ApiPort 로 다른 번호를 준다" } }

# 방화벽 · 네트워크 종류 — 읽기만 한다(고치지 않는다)
$allowed = $false
try {
  foreach ($f in (Get-NetFirewallPortFilter -Protocol TCP | Where-Object { $_.LocalPort -in @("$WebPort", "$ApiPort") })) {
    $r = $f | Get-NetFirewallRule
    if ($r.Direction -eq 'Inbound' -and $r.Action -eq 'Allow' -and $r.Enabled -eq 'True') { $allowed = $true }
  }
} catch { }

$origin = "http://${Ip}:$WebPort"
$mine = @()
try {
  # 1) API — 0.0.0.0 에 연다. CORS 는 이 웹 주소만 더 허락한다(기본 허용 목록을 덮으니 로컬 주소도 같이 둔다)
  $env:ACOP_WEB_ALLOWED_ORIGINS = "http://127.0.0.1:$WebPort,http://localhost:$WebPort,$origin"
  $mine += Start-Process python -ArgumentList @('-m', 'uvicorn', 'app.presentation.api.app:app', '--host', '0.0.0.0', '--port', $ApiPort) `
    -WorkingDirectory $repo -PassThru -NoNewWindow
  # 2) 웹앱 — 주소는 **브라우저가 부를 주소**라 폰 입장의 이 PC 주소여야 한다(127.0.0.1 은 폰 자신이다). 빌드 폴더를 따로 써 평소 개발 서버의 .next 를 안 건드린다
  $env:NEXT_PUBLIC_API_BASE = "http://${Ip}:$ApiPort"
  $env:NEXT_DIST_DIR = '.next-lan'
  $env:NEXT_ALLOWED_DEV_ORIGINS = $Ip
  $mine += Start-Process node -ArgumentList @('node_modules/next/dist/bin/next', 'dev', '--hostname', '0.0.0.0', '--port', $WebPort) `
    -WorkingDirectory $webDir -PassThru -NoNewWindow

  foreach ($p in @($ApiPort, $WebPort)) {
    $ok = $false
    foreach ($i in 1..120) { if (Test-Open $p) { $ok = $true; break }; Start-Sleep -Milliseconds 500 }
    if (-not $ok) { throw "$p 번이 60초 안에 안 열렸다 — 위 로그를 본다" }
  }
  Write-Host ''
  Say "열렸다 — 같은 공유기의 폰 브라우저에서:  $origin"
  Say "(API 는 http://${Ip}:$ApiPort — 웹앱이 알아서 부른다. 처음 화면은 첫 요청 때 컴파일해 몇 초 걸린다)"
  if (-not $allowed) {
    Write-Host ''
    Say '★이 PC 의 방화벽에 이 포트를 허락하는 규칙이 안 보인다 — 폰에서 안 열리면 관리자 PowerShell 에서:'
    Write-Host ('      powershell -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $PSScriptRoot 'lan_firewall.ps1'))
  }
  Write-Host ''
  Say '멈추려면 Ctrl+C'
  # 둘 중 하나라도 죽으면 알리고 나머지도 내린다
  while (($mine | Where-Object { -not $_.HasExited }).Count -eq $mine.Count) { Start-Sleep -Seconds 2 }
  Say '서버 하나가 멈췄다 — 둘 다 내린다'
} finally {
  foreach ($p in $mine) { try { & taskkill /T /F /PID $p.Id 2>$null | Out-Null } catch { } }
}

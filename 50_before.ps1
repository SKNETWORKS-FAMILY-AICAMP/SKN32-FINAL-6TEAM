# 50번 방 ①② — merge 전 상태 기록. 작업트리를 바꾸지 않는다(git fetch 만 한다). 커밋하지 않는다.
#   저장소 루트에서:  powershell -ExecutionPolicy Bypass -File .\50_before.ps1
#   -SkipReg : 회귀 before 를 건너뛴다(약 10분). merge 뒤 --json 대조를 하려면 돌려야 한다.
param([switch]$SkipReg)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$BASE = "201dad5"          # 우리가 근거로 적어 둔 develop (9/21 merge eb3f3ad)
$EXPECT_HEAD = "7e913e8"   # role-mobility
$D = "_50"; New-Item -ItemType Directory -Force -Path $D | Out-Null
$LOG = "$D/50_before.txt"; Remove-Item -ErrorAction SilentlyContinue $LOG

function W([object[]]$lines) { foreach ($l in $lines) { Write-Host "$l"; "$l" | Out-File -Encoding utf8 -Append $LOG } }
function G([string]$title, [string[]]$argv, [string]$to = "") {
    W ""; W "===== $title ====="; W "  git $($argv -join ' ')"
    $out = & git -c core.quotepath=off --no-pager @argv 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    if ($to) { $out | Out-File -Encoding utf8 "$D/$to"; W "  → $D/$to ($(@($out).Count)줄)" } else { W $out }
    W "  (종료코드 $code)"
    return $code
}

W "50번 merge 전 기록 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') · 기기 $env:COMPUTERNAME"
W "$(git --version)"

# ── 여는 조건 ──
$br = (git rev-parse --abbrev-ref HEAD).Trim()
$dirty = @(git status --porcelain --untracked-files=no)
W "브랜치 $br · 추적 파일 변경 $($dirty.Count)건"
if ($br -ne "role-mobility") { W "! role-mobility 가 아니다 — 멈춘다"; exit 1 }
if ($dirty.Count) { W $dirty; W "! 추적 파일에 변경이 있다 — 멈춘다(커밋하거나 되돌린 뒤 다시)"; exit 1 }
if (Test-Path .git/MERGE_HEAD) { W "! 진행 중인 merge 가 있다 — 멈춘다"; exit 1 }

# ① 받기 전 상태
G "① HEAD" @("log","--oneline","-1") | Out-Null
$head = (git rev-parse --short HEAD).Trim()
if (-not $head.StartsWith($EXPECT_HEAD)) { W "! HEAD $head ≠ 기록 $EXPECT_HEAD — 계속하되 27 의 git 줄과 다르다" }
G "① fetch" @("fetch","origin") | Out-Null
$dev = (git rev-parse --short origin/develop).Trim()
$devFull = (git rev-parse origin/develop).Trim()
$devFull | Out-File -Encoding ascii "$D/develop_hash.txt"
W ""; W "origin/develop = $dev  (전체 해시 → $D/develop_hash.txt · 50_merge.ps1 이 이 해시를 merge 한다)"
G "① 201dad5 가 HEAD 의 조상인가 (0 = 예)" @("merge-base","--is-ancestor",$BASE,"HEAD") | Out-Null
G "① merge-base HEAD origin/develop" @("merge-base","--short","HEAD","origin/develop") | Out-Null
G "① HEAD 가 이미 develop 을 다 담았나 — develop 에만 있는 커밋 수" @("rev-list","--count","HEAD..origin/develop") | Out-Null
G "① 사이 커밋 $BASE..origin/develop" @("log","--oneline","--date=format:%m-%d %H:%M","--format=%h %ad %an | %s","$BASE..origin/develop") | Out-Null
G "① 사이 커밋 (merge 제외 · 파일 목록)" @("log","--no-merges","--name-status","--format=--- %h %an | %s","$BASE..origin/develop") "commits_name_status.txt" | Out-Null

# ② 바뀐 파일
G "② 전체 diff --stat" @("diff","--stat=200","-M","$BASE..origin/develop") | Out-Null
$watch = @(
  "final_project_cs/app/modules/travel_ops/mobility.py",
  "final_project_cs/app/tools/read_tools.py",
  "final_project_cs/app/infrastructure/travel/",
  ":(glob)**/test_transit_source_assembly.py",
  "final_project_cs/app/core/",
  "final_project_cs/app/application/controller.py",
  ":(glob)**/project.yaml",
  "final_project_cs/app/modules/travel_ops/__init__.py",
  "final_project_cs/app/modules/travel_ops/itinerary_team.py",
  ":(glob)**/*schema*",
  ":(glob)**/*contract*"
)
G "② 우리가 읽는 팀 파일 --stat" (@("diff","--stat=200","-M","$BASE..origin/develop","--") + $watch) | Out-Null
G "② 우리가 읽는 팀 파일 전체 diff" (@("diff","-M","$BASE..origin/develop","--") + $watch) "watched.diff" | Out-Null
G "② 우리 자리를 팀이 건드렸나 (0줄이어야 한다)" @("diff","--stat=200","-M","$BASE..origin/develop","--",
  "final_project_cs/app/modules/travel_ops/mobility_engine/","tests/mobility/","scripts/","modules/","docs/mobility/","config/mobility/","requirements-mobility.txt",".gitignore") | Out-Null
G "② 충돌 미리보기 (작업트리 안 바꿈 · 1 = 충돌 있음)" @("merge-tree","--write-tree","--name-only","HEAD","origin/develop") | Out-Null
G "② develop 의 Team 에 넘기는 상태 키" @("grep","-n","TEAM_STATE_KEYS","origin/develop","--","final_project_cs/app/application/controller.py") | Out-Null

W ""; W "①② 기록 끝 → $LOG · $D/watched.diff · $D/commits_name_status.txt"
if ($SkipReg) { W "회귀 before 건너뜀(-SkipReg)"; exit 0 }
W "회귀 before 시작 (약 10분) → $D/reg_before.txt"
& powershell -ExecutionPolicy Bypass -File .\50_reg.ps1 -Tag before
W "회귀 before 종료코드 $LASTEXITCODE"

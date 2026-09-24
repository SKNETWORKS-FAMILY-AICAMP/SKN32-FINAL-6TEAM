# 50번 방 — 회귀·점검 한 벌. merge 전(-Tag before) · 후(-Tag after) 에 같은 것을 돌린다. 커밋하지 않는다.
#   저장소 루트에서:  powershell -ExecutionPolicy Bypass -File .\50_reg.ps1 -Tag before
# 31b_after.ps1 과 같은 묶음 · 같은 인자(--gh-url none — 라우터 상태가 결과에 안 들어간다).
# 더한 것 둘: [0] 자기완결에 팀 travel_ops/__init__ import 확인 · 팀 시험 test_transit_source_assembly(pytest 있으면).
param([Parameter(Mandatory=$true)][ValidateSet("before","after")][string]$Tag)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "final_project_cs"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$D   = "_50"; New-Item -ItemType Directory -Force -Path $D | Out-Null
$LOG = "$D/reg_$Tag.txt"
$JD  = "$D/json_$Tag"
Remove-Item -ErrorAction SilentlyContinue $LOG
Remove-Item -ErrorAction SilentlyContinue -Recurse $JD
New-Item -ItemType Directory -Force -Path $JD | Out-Null
$script:sum = @()

function L([object[]]$lines) { foreach ($l in $lines) { "$l" | Out-File -Encoding utf8 -Append $LOG } }
L "50번 회귀 [$Tag] — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') · 기기 $env:COMPUTERNAME"
L "git $(git --no-pager log --oneline -1)"
L "MERGE_HEAD $(if (Test-Path .git/MERGE_HEAD) { Get-Content .git/MERGE_HEAD } else { '(없음)' })"

function Run([string]$label, [string[]]$argv) {
    Write-Host ""; Write-Host "===== $label =====" -ForegroundColor Cyan
    L ""; L "===== $label ====="; L "  python $($argv -join ' ')"
    $out = & python @argv 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $out | Select-Object -Last 6 | ForEach-Object { Write-Host "  $_" }
    L $out; L "  (종료코드 $code)"
    $key = ($out | Select-String "기대 대조|통과|실패|판정 |차이 |passed|failed|OK" | Select-Object -Last 1)
    $script:sum += [pscustomobject]@{ 항목 = $label; rc = $code; 마지막 = "$key".Trim() }
}

# ── [0] 자기완결 — final_project_cs 만 보고 엔진·팀장 Team 이 들리는가 ──
Write-Host ""; Write-Host "===== [0] 자기완결 =====" -ForegroundColor Yellow
Push-Location final_project_cs
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$imp = & python -c "import app.modules.travel_ops.mobility_engine.runtime as R; import app.modules.travel_ops.mobility_engine.verify_time as V; from app.modules.travel_ops import MobilityTeam as T; print('import OK ·', R.__name__, '·', hasattr(V,'Verifier'), '· 팀장 MobilityTeam', T.__module__)" 2>&1 | ForEach-Object { "$_" }
$c0 = $LASTEXITCODE
# 팀 시험 — 소스 슬롯 조립(transit/route). pytest 가 없으면 건너뛴다.
$tt = Get-ChildItem -Recurse -Filter test_transit_source_assembly.py -ErrorAction SilentlyContinue | Select-Object -First 1
if ($tt) {
    $rel = Resolve-Path -Relative $tt.FullName
    $pt = & python -m pytest -q $rel 2>&1 | ForEach-Object { "$_" }
    $c1 = $LASTEXITCODE
} else { $pt = @("test_transit_source_assembly.py 를 못 찾음"); $c1 = -1 }
Pop-Location
$env:PYTHONPATH = "final_project_cs"
$imp | ForEach-Object { Write-Host "  $_" }
L ""; L "===== [0] 자기완결 ====="; L $imp; L "  (종료코드 $c0)"
L ""; L "===== 팀 시험 test_transit_source_assembly ====="; L $pt; L "  (종료코드 $c1)"
$script:sum += [pscustomobject]@{ 항목 = "[0] 자기완결"; rc = $c0; 마지막 = "$($imp | Select-Object -Last 1)" }
$script:sum += [pscustomobject]@{ 항목 = "팀 시험 transit 조립"; rc = $c1; 마지막 = "$($pt | Select-Object -Last 1)" }

$VT = @("-m", "app.modules.travel_ops.mobility_engine.verify_time")
$T  = "tests/mobility"
Run "규칙표 구조"       @("scripts/rules_check.py")
Run "자전거 단위 16"    @("$T/test_bike_unit.py")
# ── 회귀 9묶음 = 123 ──
Run "회귀 bike 14"      ($VT + @("--cases","$T/bike_legs_v1.json","--check-expect","--gh-url","none","--bike-fixture","$T/bike_gh_fixture_v1.json","--json","$JD/bike.json"))
Run "회귀 alt 5"        ($VT + @("--cases","$T/alt_legs_v1.json","--check-expect","--gh-url","none","--allow-router-down","--json","$JD/alt.json"))
Run "회귀 real 32"      ($VT + @("--cases","$T/real_legs_v1.json","--check-expect","--gh-url","none","--json","$JD/real.json"))
Run "회귀 issue 9"      ($VT + @("--cases","$T/issue_legs_v1.json","--check-expect","--gh-url","none","--json","$JD/issue.json"))
Run "회귀 bus 11"       ($VT + @("--cases","$T/bus_legs_v1.json","--check-expect","--gh-url","none","--json","$JD/bus.json"))
Run "회귀 mixed 6"      ($VT + @("--cases","$T/mixed_legs_v1.json","--check-expect","--gh-url","none","--json","$JD/mixed.json"))
Run "회귀 multi 6"      ($VT + @("--cases","$T/multi_legs_v1.json","--check-expect","--gh-url","none","--json","$JD/multi.json"))
Run "회귀 car 12"       ($VT + @("--cases","$T/car_legs_v1.json","--gh-url","fixture:$T/car_routes_fixture_v1.json","--check-expect","--json","$JD/car.json"))
Run "회귀 synthetic 28" ($VT + @("--cases","$T/synthetic_legs_v1.json","--timetable","$T/mini_timetable_v2.jsonl","--check-expect","--gh-url","none","--json","$JD/synthetic.json"))
# ── 단위·불변식·자기점검 ──
Run "택시 요금 31"      @("$T/test_car_fare.py")
Run "불변식 자체점검 10" @("$T/test_selfcheck_invariants.py")
Run "탐침 9,776 · 376"  @("scripts/selfcheck_mobility.py","--seeds","$T/*.json")
# ── 계약 점검 ──
Run "check_fold 12"     @("$T/contract/check_fold.py")
Run "어댑터 30"         @("$T/contract/check_adapter.py")
Run "런타임 26"         @("$T/contract/check_runtime.py")
Run "라우팅 13"         @("$T/contract/check_routing.py")

L ""; L "===== 요약 [$Tag] ====="
$tbl = $script:sum | Format-Table -AutoSize -Wrap | Out-String -Width 220
L $tbl
Write-Host $tbl
$bad = @($script:sum | Where-Object { $_.rc -ne 0 -and $_.항목 -ne "팀 시험 transit 조립" }).Count
L "종료코드 0 아닌 항목(팀 시험 제외): $bad"
Write-Host "종료코드 0 아닌 항목(팀 시험 제외): $bad  · 기록 $LOG" -ForegroundColor $(if ($bad) { "Red" } else { "Green" })
Write-Host "정본: 회귀 123 · 탐침 9,776 · 판단불가 376 · 어댑터 30 · 런타임 26 · 라우팅 13 · check_fold 12 · bike 16"
exit $bad

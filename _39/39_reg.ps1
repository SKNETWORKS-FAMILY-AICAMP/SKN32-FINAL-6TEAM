# 39_reg.ps1 — 39번 방 회귀 재실행(기기). 저장소 루트에서:  powershell -ExecutionPolicy Bypass -File _39\39_reg.ps1
# 클라우드에서 돌린 것과 같은 옵션이다(라우터 없음 · car/bike 는 픽스처). 출력은 _39\reg\ 에 남는다(미추적).
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "final_project_cs"
$out = "_39\reg"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$bundles = "real","issue","alt","bus","mixed","multi","synthetic","car","bike","judgment"
$fail = 0
foreach ($b in $bundles) {
  $extra = @("--gh-url","none","--allow-router-down")
  if ($b -eq "car")  { $extra = @("--gh-url","fixture:tests/mobility/car_routes_fixture_v1.json") }
  if ($b -eq "bike") { $extra = @("--gh-url","fixture:tests/mobility/car_routes_fixture_v1.json","--bike-fixture","tests/mobility/bike_gh_fixture_v1.json") }
  $tt = @()
  if ($b -eq "synthetic") { $tt = @("--timetable","tests/mobility/mini_timetable_v2.jsonl") }
  python -m app.modules.travel_ops.mobility_engine.verify_time --cases "tests/mobility/${b}_legs_v1.json" --check-expect @tt @extra --json "$out\$b.json" 2>&1 | Out-File -Encoding utf8 "$out\$b.txt"
  $rc = $LASTEXITCODE
  $line = (Get-Content -Encoding UTF8 "$out\$b.txt" | Select-String "기대 대조").Line
  Write-Host ("{0,-10} rc={1} :: {2}" -f $b, $rc, $line)
  if ($rc -ne 0) { $fail++ }
}
Write-Host "----"
python scripts/rules_check.py | Select-Object -Last 1
python tests/mobility/contract/check_fold.py | Select-Object -Last 1
python tests/mobility/contract/check_runtime.py | Select-Object -Last 1
python tests/mobility/contract/check_adapter.py | Select-Object -Last 1
python tests/mobility/contract/check_routing.py | Select-Object -Last 1
python tests/mobility/test_selfcheck_invariants.py | Select-Object -Last 1
python tests/mobility/test_bike_unit.py | Select-Object -Last 1
python tests/mobility/test_car_fare.py | Select-Object -Last 1
Write-Host "----"
Write-Host "회귀 묶음 실패 $fail 개 (0 이어야 초록). 자기점검(약 3분)은 39_selfcheck.ps1"

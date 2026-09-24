# 39_reg.ps1 - room 39 regression rerun (device). From repo root:  powershell -ExecutionPolicy Bypass -File _39\39_reg.ps1
# Same options as the cloud run (no router; car/bike use fixtures). Output goes to _39\reg\ (untracked). ASCII only - PowerShell reads ps1 as cp949 without BOM.
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
  $line = (Get-Content -Encoding UTF8 "$out\$b.txt" | Select-String ([regex]::Unescape("\uAE30\uB300 \uB300\uC870"))).Line
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
Write-Host "bundles failed: $fail (must be 0). selfcheck (~3 min): 39_selfcheck.ps1"

# 39_selfcheck.ps1 - selfcheck with v0.8 invariants. From repo root:  powershell -ExecutionPolicy Bypass -File _39\39_selfcheck.ps1
# Default report is now .metrics\selfcheck_report.md (untracked). Root selfcheck_report.md is no longer written.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "final_project_cs"
New-Item -ItemType Directory -Force -Path ".metrics" | Out-Null
$seeds = "tests/mobility/real_legs_v1.json","tests/mobility/issue_legs_v1.json","tests/mobility/alt_legs_v1.json","tests/mobility/bus_legs_v1.json","tests/mobility/mixed_legs_v1.json","tests/mobility/synthetic_legs_v1.json","tests/mobility/car_legs_v1.json","tests/mobility/bike_legs_v1.json"
python scripts/selfcheck_mobility.py --seeds @seeds --json .metrics/selfcheck_39.json 2>&1 | Out-File -Encoding utf8 _39\selfcheck.txt
Get-Content -Encoding UTF8 _39\selfcheck.txt | Select-Object -Last 8
# Expected: probes 9,776 / verdicts {infeasible 3272, feasible 6128, unknown 376} / findings 4 (INV-UNKNOWN 4, critical 0) - same as cloud

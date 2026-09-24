# 39_selfcheck.ps1 — 자기점검(v0.8 불변식 포함). 저장소 루트에서:  powershell -ExecutionPolicy Bypass -File _39\39_selfcheck.ps1
# ★ 기본 출력이 .metrics\selfcheck_report.md 로 바뀌었다(미추적). 저장소 루트의 selfcheck_report.md 는 더 이상 안 쓴다.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "final_project_cs"
New-Item -ItemType Directory -Force -Path ".metrics" | Out-Null
$seeds = "tests/mobility/real_legs_v1.json","tests/mobility/issue_legs_v1.json","tests/mobility/alt_legs_v1.json","tests/mobility/bus_legs_v1.json","tests/mobility/mixed_legs_v1.json","tests/mobility/synthetic_legs_v1.json","tests/mobility/car_legs_v1.json","tests/mobility/bike_legs_v1.json"
python scripts/selfcheck_mobility.py --seeds @seeds --json .metrics/selfcheck_39.json 2>&1 | Out-File -Encoding utf8 _39\selfcheck.txt
Get-Content -Encoding UTF8 _39\selfcheck.txt | Select-Object -Last 8
# 기대: 탐침 9,776 · 판정 {'infeasible': 3272, 'feasible': 6128, 'unknown': 376} · 이상 4건(INV-UNKNOWN 4 · 치명 0) — 클라우드와 같아야 한다

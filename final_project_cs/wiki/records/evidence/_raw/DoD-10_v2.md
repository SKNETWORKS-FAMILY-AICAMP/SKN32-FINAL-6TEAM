# DoD-10 재측정 원문 (수집: 구현 담당, 판정 없음)

## 재현 명령
```powershell
python -m scripts.run_daily_feedback --date 2026-08-13
python -m pytest tests\unit\voc -q
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"; & $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'feedback_analytics_reports='||count(*) from feedback_analytics_reports where tenant_id='demo'"
```

## 실제 출력
```
{"alerts": [], "metrics": {"intent_issue_count": {"prior_7_days": {}, "today": {}}, "negative_ratio": {"prior_7_days": 0.0, "today": 0.0}, "totals": {"prior_7_days": 0, "today": 0}, "unresolved_ratio": {"prior_7_days": 0.0, "today": 0.0}}, "period_end": "2026-08-13", "period_start": "2026-08-06", "tenant_id": "demo"}
........                                                                 [100%]
… warning 상세 6줄 생략
8 passed, 1 warning in 2.30s
feedback_analytics_reports=1
```

## 관측 사실
- daily feedback 출력의 `period_start`는 `2026-08-06`, `period_end`는 `2026-08-13`, `tenant_id`는 `demo`이다.
- daily feedback 출력의 `alerts`는 빈 배열이다.
- `today` totals는 `0`, `prior_7_days` totals는 `0`이다.
- `tests\unit\voc` 출력의 집계는 `8 passed, 1 warning`이다.
- `demo`의 `feedback_analytics_reports` 건수 출력값은 `1`이다.

## 확인하지 못한 것
- 실데이터가 있는 날짜의 급증 alert 출력은 확인하지 못했다.

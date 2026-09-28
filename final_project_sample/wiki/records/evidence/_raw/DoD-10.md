# DoD-10 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python -m scripts.run_daily_feedback --date 2026-08-12
python -m pytest tests/unit/voc/test_feedback.py -q
python  # SELECT count(*) FROM feedback_analytics_reports ...
```

## 실제 출력
```
{"alerts": [], "metrics": {"intent_issue_count": {"prior_7_days": {}, "today": {}}, "negative_ratio": {"prior_7_days": 0.0, "today": 0.0}, "totals": {"prior_7_days": 0, "today": 0}, "unresolved_ratio": {"prior_7_days": 0.0, "today": 0.0}}, "period_end": "2026-08-12", "period_start": "2026-08-05", "tenant_id": "demo"}
EXIT=0
....... [100%]
7 passed, 1 warning in 1.08s
EXIT=0
feedback_analytics_reports_count= 1
EXIT=0
```

## 관측 사실
- report 기간은 `2026-08-05`부터 `2026-08-12`이다.
- report tenant는 `demo`이다.
- `feedback_analytics_reports_count` 조회값은 1이다.
- VOC 단위 테스트 출력의 테스트 수는 7개이다.

## 확인하지 못한 것
- 별도 데이터가 있는 환경의 급증 alert 출력은 확인하지 못했다.

# DoD-10 v4 실측 원문

실행 시각: 2026-08-14

명령:

```text
python -m pytest tests/unit/voc -v
python -m scripts.run_daily_feedback --date 2026-08-14
```

출력 요약:

```text
collected 8 items
8 passed
{"alerts": [], "metrics": {"intent_issue_count": {"prior_7_days": {}, "today": {}}, "negative_ratio": {"prior_7_days": 0.0, "today": 0.0}, "totals": {"prior_7_days": 0, "today": 0}, "unresolved_ratio": {"prior_7_days": 0.0, "today": 0.0}}, "period_end": "2026-08-14", "period_start": "2026-08-07", "tenant_id": "demo"}
```

별도 임시 tenant 실측:

```text
tenant= raw_voc_cebb7113f41544459dfec276c863ba24
alert_report= {'tenant_id': 'raw_voc_cebb7113f41544459dfec276c863ba24', 'period_start': '2026-08-07', 'period_end': '2026-08-14', 'metrics': {'intent_issue_count': {'today': {'billing': {'raw_surge': 6}}, 'prior_7_days': {'billing': {'raw_surge': 2}}}, 'negative_ratio': {'today': 1.0, 'prior_7_days': 1.0}, 'unresolved_ratio': {'today': 1.0, 'prior_7_days': 1.0}, 'totals': {'today': 6, 'prior_7_days': 2}}, 'alerts': [{'intent': 'billing', 'issue_code': 'raw_surge', 'today': 6, 'avg7': 0.2857142857142857}]}
teardown=deleted
```

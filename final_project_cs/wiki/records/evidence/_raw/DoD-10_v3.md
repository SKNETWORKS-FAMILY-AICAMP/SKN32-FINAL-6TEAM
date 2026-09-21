# DoD-10 재측정 원문

## 재현 명령

```powershell
python -m pytest tests\unit\voc -v
python -m scripts.run_daily_feedback --date 2026-08-14
```

별도 measurement tenant에 당일 Case 6개와 이전 기간 Case 2개를 만들고 `run_daily_feedback`를 호출했다. 종료 후 해당 tenant의 연결 데이터를 삭제했다.

## 실제 출력

```text
collecting ... collected 8 items
tests/unit/voc/test_feedback.py::test_classifier_returns_all_four_fields_from_injected_llm PASSED [ 12%]
tests/unit/voc/test_feedback.py::test_classifier_fails_when_any_field_is_missing[sentiment] PASSED [ 25%]
tests/unit/voc/test_feedback.py::test_classifier_fails_when_any_field_is_missing[intent] PASSED [ 37%]
tests/unit/voc/test_feedback.py::test_classifier_fails_when_any_field_is_missing[issue_code] PASSED [ 50%]
tests/unit/voc/test_feedback.py::test_classifier_fails_when_any_field_is_missing[severity] PASSED [ 62%]
tests/unit/voc/test_feedback.py::test_surge_boundary_requires_both_conditions PASSED [ 75%]
tests/unit/voc/test_feedback.py::test_batch_is_tenant_scoped_and_idempotent PASSED [ 87%]
tests/unit/voc/test_feedback_runtime.py::test_real_cases_trigger_voc_surge_and_boundary_does_not PASSED [100%]
======================== 8 passed, 1 warning in 7.76s =========================
```

```text
{"alerts": [], "metrics": {"intent_issue_count": {"prior_7_days": {}, "today": {}}, "negative_ratio": {"prior_7_days": 0.0, "today": 0.0}, "totals": {"prior_7_days": 0, "today": 0}, "unresolved_ratio": {"prior_7_days": 0.0, "today": 0.0}}, "period_end": "2026-08-14", "period_start": "2026-08-07", "tenant_id": "demo"}
DOD10_real_case_report= {'tenant_id': 'measure_voc_19ee61da9afe4b60840cfdd78665279e', 'period_start': '2026-08-07', 'period_end': '2026-08-14', 'metrics': {'intent_issue_count': {'today': {'billing': {'measurement_surge': 6}}, 'prior_7_days': {'billing': {'measurement_surge': 2}}}, 'negative_ratio': {'today': 1.0, 'prior_7_days': 1.0}, 'unresolved_ratio': {'today': 1.0, 'prior_7_days': 1.0}, 'totals': {'today': 6, 'prior_7_days': 2}}, 'alerts': [{'intent': 'billing', 'issue_code': 'measurement_surge', 'today': 6, 'avg7': 0.2857142857142857}]}
DOD10_cleanup_tenant= measure_voc_19ee61da9afe4b60840cfdd78665279e
```

## 관측 사실

- `tests/unit/voc` 수집 항목 수는 `8`이었다.
- `demo` daily feedback 출력의 `alerts`는 빈 배열이었다.
- 별도 tenant 측정의 당일 Case 수는 `6`, 이전 기간 수는 `2`였다.
- 별도 tenant 측정 출력의 alerts 항목은 `billing`, `measurement_surge`, `today=6`, `avg7=0.2857142857142857`이었다.
- 별도 tenant 정리 출력이 남았다.

## 확인하지 못한 것

- 외부 LLM 호출은 하지 않았다.


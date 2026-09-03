# Case 상세 API의 evidence.value가 항상 {}였다

## 해결됨 (2026-09-01)

- 발견 경위: 다른 세션이 근거 되짚기(traceability) 장치를 셋으로 나눠
  확인하다("운영 화면 / 표 사이 연결 / API 응답") API 응답만 비어 있음을
  발견해 relay했다. 코드로 직접 재현·확인 후 CS 저장소에서 바로 고쳤다.
- 판정: **실재, 수정 완료.**

## 재현

`GET /v1/cases/{case_id}` (`app/presentation/api/cases.py:153`, 수정 전):

```python
"evidence": [{"source_type": "case_event", "source_id": str(e["event_id"]),
              "claim": e["event_type"], "value": {},   # ← 항상 빈 딕셔너리
              "observed_at": e["created_at"]} for e in events]
```

`repository.get_case_events()`(`app/infrastructure/db/repository.py:36-39`)는
`payload_json`을 이미 SELECT해서 `events` 각 행에 담아 오는데, 위 줄이 그걸
버리고 `{}`로 덮어썼다. 그래서 API 응답의 `evidence`는 `claim`(어떤 이벤트가
있었는지)만 말하고 `value`(그 이벤트가 실제로 기록한 내용 — 채널, 메시지,
분류 라벨, 승인 사유 등)는 항상 비어 있었다. `/ui/cases/{id}`의 Evidence
카드는 이 API가 아니라 DB를 직접 읽어 만들어서 화면 쪽은 멀쩡했다 — API로만
되짚기가 안 됐다.

## 수정

`e["value"]`를 `e["payload_json"] or {}`로 바꿨다 — 한 줄, 이미 조회돼 있던
값을 실제로 쓰게 한 것뿐이라 위험이 없다. `payload_json`이 이미 이 API
응답의 다른 자리(`answer`, `intent` 등, `case["state_json"]`에서 옴)와 같은
노출 수준(`case:read` scope, 이미 마스킹된 텍스트)이라 새로운 종류의 노출을
만들지 않는다.

## 검증

- `tests/integration/api/test_api_runtime.py::test_detail_evidence_carries_the_actual_event_payload`
  신규 — created 이벤트의 `value.channel`이 실제로 채워지는지, 전체
  evidence가 전부 `{}`는 아닌지 확인.
- `python -m pytest -q -m "not live"` → 513 → 514 passed, 회귀 0건.

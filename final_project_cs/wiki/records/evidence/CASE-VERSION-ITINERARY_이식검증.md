# Case 버전 여행 일정 관리 이식 — 검증 로그

- 날짜: 2026-09-17 · 브랜치 `role-core1` · 기준 커밋 `b9afb02` 위 작업 트리
- DB: 로컬 PostgreSQL(`acop`) — 시험마다 전용 테넌트를 만들고 끝나면 지운다
- LLM: 흉내(분류기 · 신고 추출). 감시 · Controller · Team · 적용 · 통지는 실제 코드
- 리포트: [../reports/2026-09-17_0536_Case버전_여행일정관리_이식_리포트.md](../reports/2026-09-17_0536_Case버전_여행일정관리_이식_리포트.md)

## 1. 하루 전체 대조 — 두 버전이 같은 결과

```powershell
python -m pytest tests/scenario/test_case_version_day.py -q
```

```
.....                                                                    [100%]
5 passed in 14.77s
```

`test_the_case_version_runs_the_whole_day_like_the_trip_version` 이 보는 것: 감시 Case 3건(activity 1 · mobility 2)과 고객 Case 3건(dining 2 · activity 1)이 전부 `resolved`, 두 테넌트의 일정 버전 6 · 마지막 항목(순서·제목·시각) · 버전별 통지 문구 5건이 같다, Case 버전의 버전 2~6 에 `case_id` 가 붙고 `itinerary.apply` succeeded 5건.

### 1-1. 일부러 깨뜨림 — 시험이 결과를 가르는가

적용기가 통지를 빼먹게 바꿨다(`itinerary_actions.py` 의 `outbox=[…]` → `outbox=[]`, 확인 후 원복).

```
E         Left contains 5 more items, first extra item: '오늘 오전 잠실 스카이타워 야외 전망 데크는 시야 확보가 어려울 것으로 예상되어, 같은 건물 지하 1층 아쿠아리움으로 변경됩니다.'
1 failed in 6.11s
```

원복 뒤 같은 시험: `1 passed in 5.59s`.

## 2. 시나리오 모드 — 화면 경로로 Case 엔진

```powershell
python -m pytest tests/e2e/test_scenario_mode.py tests/scenario -q
```

```
......................                                                   [100%]
22 passed in 32.61s
```

첫 실행에서 `test_the_whole_day_runs_through_cases_when_the_engine_is_case` 가 **실패했다** — 화면 「다른 안」 버튼의 문장에 분류가 `activity_other` 를 붙여 점심(식당) 항목이 activity Team 으로 갔고 `target_kind_mismatch` 로 escalated. 「클라이언트가 지정하고 서버가 확인한 항목의 종류는 분류보다 우선」 규칙을 넣고 위 결과가 나왔다(wiki `external/rest-endpoints.md` subject_ref).

## 3. 코어 규칙 · 자동 적용 가드 · 대상 연결

```powershell
python -m pytest tests/unit/core/test_case_subject_routing.py tests/integration/controller/test_auto_apply_proposals.py tests/integration/api/test_case_subject_ref.py -q
```

```
.................                                                        [100%]
17 passed in 5.35s
```

## 4. 시나리오용 여행 버전의 계산 분리(리팩터) 회귀

`trip_desk.py`·`trip_watch.py` 를 `itinerary_changes.py` 위로 옮긴 뒤, 새 판과 원본(`legacy/`)을 번갈아 돌렸다.

| 실행 | 대상 | 결과 |
|---|---|---|
| 첫 실행(새 판) | `tests/scenario` + `test_trip_api.py` + `test_scenario_mode.py` | **25 passed · 1 failed** — `test_a_repeated_message_does_not_open_a_second_case` (`duplicate` 기대, `still_fits`) |
| 새 판 → 원본 → 새 판 → 원본 | `test_trip_api.py` 전체 | 10 passed · 10 passed · 10 passed · 10 passed |
| 새 판 → 원본 → 새 판 | 첫 실행과 같은 조합 | 26 passed · 26 passed · 26 passed |

★첫 실패는 이후 **3회 재현되지 않았다**. 원본은 같은 조합으로 1회만 돌렸으므로 「이 변경과 무관」을 증명하지 못한다 — **간헐 실패 1건, 원인 미확정**으로 남긴다.

## 5. 전체(라이브 제외)

```powershell
python -m pytest -m "not live" -q
```

```
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[배송완료로 떴는데 못 받았어요-doc_01]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[주문은 3개인데 반품을 5개 신청했어요-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
3 failed, 1097 passed, 7 deselected, 36 warnings in 185.80s (0:03:05)
```

실패 3건의 원인(출력 원문): `openai.RateLimitError: Error code: 429 … 'code': 'credit_balance_exhausted'` — OpenAI 크레딧 소진. 커밋 `041813f`·`9575126` 메시지에 같은 3건이 기록돼 있다.

## 6. wiki 검사

```powershell
python program/scripts/check_wiki.py
```

첫 실행 위반 5건 중 1건이 이 작업 — `final_project_cs/wiki/teams/activity.md (304줄)` 300줄 초과. 절을 줄여 295줄로 고친 뒤 **위반 4건**(이 작업이 건드리지 않은 `acop_dojo/wiki/guide.md` · `acop_dojo/wiki/handoff-2026-09-14.md` · 허브 `wiki/travel_api_competitor_census_2026-09-11.md` · `decisions/D-017`).

## 7. 후속(2026-09-17 오후) — 운영 조립 · 실제 Gemma

### 7-1. 시험

```powershell
python -m pytest tests/scenario/test_case_version_day.py tests/unit/travel/test_trip_intake.py -q
```

```
16 passed in 10.34s
```

(그 뒤 해석기 실패 시험 1건을 더해 `test_case_version_day.py` 7건.) 새로 넣은 것:

- `test_the_interpretation_routes_correctly_even_when_the_classifier_prefix_is_wrong` — 아래 7-2 에서 실제 Gemma 가 붙인 **틀린 접두를 그대로** 내는 분류기로 하루 + 자유 재요청 + 되돌리기. 늦음·휴무 → dining, 품절 → activity, 전부 `resolved`, 일정 v8 이 v6 과 같은 모양.
- 일부러 깨뜨림: `case_engine.py` 의 `self.interpreter` 를 `None` 으로 → `1 failed, 5 passed in 9.61s`(바로 이 시험). 원복 후 통과.
- `test_a_failing_interpreter_is_recorded_and_the_case_still_routes_by_classification` — 추출기가 `TimeoutError` → `state_json.interpretation.error` 에 남고 분류 접두(dining)로 가며 `resolved` 가 아니다.
- `test_trip_intake.py` — 되돌리기 번호가 문장에 없으면 버린다 · 해석기가 신고 종류로 담당을 고른다 · 구조가 정해진 요청은 모델을 안 부른다.
- 앞서 넣은 것: `tests/e2e/test_case_version_rest.py`(REST 종단) · `tests/integration/controller/test_travel_approval_proposal_reaches_waiting.py`(승인 대기 도달) · `tests/unit/test_report_extractor_wiring.py`(운영 조립 추출기).

넓은 범위(라이브 제외, ML 시험 폴더 제외 — 다른 세션 작업):

```powershell
python -m pytest tests/unit tests/contract tests/architecture tests/integration tests/scenario tests/e2e tests/security -q -m "not live" --ignore=tests/unit/ml
```

```
3 failed, 1079 passed, 36 warnings in 85.79s
```

실패 3건은 §5 와 같은 RAG 시험(OpenAI 크레딧 소진)이다.

### 7-2. 실제 gemma4:12b — 문장별 분류·추출, 3회 × 3실행

스크립트는 세션 임시 폴더(저장소 밖)에 있다: 문장 7개를 분류기(`composition.build_classifier`)와 추출기(`composition.build_report_extractor`)에 각 3회. **3실행 × 3회 = 9회 모두 같은 값**이었다.

| 문장 | 분류(intent, issue_code) | 추출 |
|---|---|---|
| 팝업스토어 줄이 길어서 점심에 70분 늦을 것 같아요 | incident_report, **activity_time_conflict** | delay, 70 |
| 저녁 먹으려던 식당이 오늘 임시휴무래요 | incident_report, dining_other | closed |
| 라면 선물세트랑 스팸 선물세트가 품절이에요… | **other, other** | stock_out, 제품 2 |
| 다른 안으로 바꿔줘 | adjust_reject, **booking_change_request** | change |
| 화면에서 다른 안 선택 | other, other | change |
| 6번 일정으로 되돌려 주세요 | adjust_reject, **booking_change_request** | rollback, 6 (고치기 전: change) |
| 그냥 궁금한 게 있어요 | other, other | other |

한 호출 1.4~2.4초. 굵은 접두는 담당과 어긋난다 — 추출 종류는 7문장 모두 맞다.

### 7-3. 실제 gemma4:12b — 하루 전체(감시는 재생, 고객 문장만 실제 모델)

| 고객 단계 | 고치기 전(1실행) | 고친 뒤(3실행, 모두 같음) |
|---|---|---|
| 늦음 | escalated · activity · `report_delay_not_handled_by_team` | **resolved · dining** |
| 휴무 | resolved · dining | resolved · dining |
| 품절 | escalated · mobility · `report_stock_out_not_handled_by_team` | **resolved · activity** |
| 화면 버튼 다른 안 | resolved · dining | resolved · dining |
| 다른 안으로 바꿔줘 | escalated · booking_handoff · `degraded_context` | **resolved · dining** |
| 6번 일정으로 되돌려 주세요 | (재지 않음) | **resolved · dining**, v9 |
| 그냥 궁금한 게 있어요 | escalated · mobility · `report_not_understood` | escalated · dining · `report_not_understood` (의도한 결과 — 무엇을 원하는지 모르면 사람에게) |

`resolved`: 고치기 전 2/6 = 33% → 고친 뒤 6/7 = 86%(분모 = 고객 단계 수. 남은 1은 사람에게 가야 맞는 문장). 감시 Case 3건은 3실행 모두 `resolved`. 고객 단계 한 건 3.2~3.8초(화면 버튼은 추출을 건너뛰어 1.6초).

★표본은 문장 7개 · 하루 1종이다. 다른 표현·다른 언어에서 추출이 맞는지는 이것으로 말하지 못한다.

### 7-4. 전체(라이브 제외)

```powershell
python -m pytest -m "not live" -q
```

```
3 failed, 1107 passed, 7 deselected, 36 warnings in 95.22s
```

실패 3건은 §5 와 같은 RAG 시험이다. 1107 에는 이 작업 트리의 다른 세션 ML 시험(`tests/unit/ml`, 이 커밋에 없음)이 섞여 있다.

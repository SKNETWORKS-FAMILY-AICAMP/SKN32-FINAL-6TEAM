# 2026-10-26 통합 서빙 후보 v8 (live v7a + temporal·F02 + Comment9 + I06 booked-only + fix8)

- 작성: 2026-10-26 02:50 KST. 상태는 **READY_PARENT_ONLY**입니다. 후보만 만들었고 교체·push는 하지 않았습니다.
- 후보 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/integ-v8-20261026-011529-adebc095/`. 이 폴더의 `REPORT_KO.md`와 `PARENT_SWAP.json`이 정본입니다.

## 문제

live v7a(v7 + all-past 날짜 가드)에 검증된 후보 4개가 아직 반영되지 않았습니다.

- temporal·F02 (`f02-origin-…5daacb`)
- Comment9 운영시간 3파일 (`comment9-v8-…`)
- I06 booked-only (`i06-booked-only-…`)
- 시험·자료 8건 수정 (`fix8-…`)

## 수정

- 기준은 v7a source 사본입니다. 각 patch의 preimage SHA를 대조한 뒤 순서대로 적용하고 postimage SHA를 확인했습니다.
  1. temporal
  2. F02
  3. Comment9
  4. I06 최종
  5. I06 booked-only
- 제품이 아닌 21파일은 v7/v7a/fix8 트리로 3-way 했습니다. 양쪽이 같은 파일을 고친 경우는 0건입니다. all-past 3파일과 겹치는 파일도 0개입니다.
- 통합 뒤 2건을 고쳤습니다.
  - `test_plan_generation_response.py`: fixture 여행일이 2026-10-25로 고정돼 있어 10-26부터 all-past 가드에 걸렸습니다. fixture 날짜만 "KST 오늘 + 7일"로 바꿨습니다.
  - ruff F/E9 4건: 미사용 import, autouse fixture import에 noqa, `agent_read.py` 반복 변수 이름.

## 실행·결과

| 항목 | 결과 |
|---|---|
| 정확 nodeid 합집합 2214개 단일 실행 (v7a 1376 ∪ fix8 2184 ∪ I06 신규 15 ∪ fix8 짝 2) | 2214/2214 = 100%, skip 0 |
| 같은 실행의 첫 시도 (시한폭탄 수정 전) | 2175/2214, 39 실패. 원인은 test_plan_generation_response 하나이며 live v7a에서도 같은 39건이 실패 |
| ruff F/E9 (변경 .py 23개) | 0건 |
| `launch-serving.py --shadow --preflight` | RC0 |
| 빈 포트 shadow 핵심 GET | 7/7 = 100%, 로드 모듈 341개 drift 0 |
| 실 E4B (I06 명시 고정, booked-only, temporal T03, F02) | 4/4 = 100% |
| v8-over-v7a patch roundtrip | 30/30 = 100% |

## 남은 한계

- 부모의 교체와 교체 후 검증(14 GET, provenance, all-past 422)은 아직 하지 않았습니다. 공유 부하에서는 startup이 3분을 넘기므로 readiness를 약 600초로 잡아야 합니다.
- Comment9 저장 검토는 승인된 revalidate 전까지 예전 경고를 보여 줍니다.
- I06 Q1~Q3은 아직 결정되지 않았습니다.
- 시험 시한폭탄은 upstream develop과 role-manager에도 남아 있습니다.
- QA 수정 2건(chat-outdoor, chat-subject)은 넣지 않았습니다. 예상 충돌은 chat-outdoor의 decision_unit과 edit_intent이고, chat-subject의 read_requests는 `--check`로 적용됩니다. 표는 후보 REPORT에 있습니다.
- 고객 DB 쓰기 0, 원본 코드 변경 0, push 0.

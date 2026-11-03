# 2026-10-25 I06 booked-only 후보 e1309e55 — 남은 수락 완료 (READY_PARENT_ONLY, all-past 선행 통합 조건부)

- 시각: 2026-10-25 23:30–23:44 KST. 후보: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/i06-booked-only-20261025-212313-e1309e55` (이전 기록: [2026-10-25_i06-booked-only-e1309e55.md](2026-10-25_i06-booked-only-e1309e55.md) — HOLD, 고치지 않음)
- 결론: 남은 조건 3/3 = 100% 충족. `PARENT_SWAP.json` = **READY_PARENT_ONLY**. 단 이 후보에는 all-past 가드가 없어 **all-past hotfix(커밋 d2ab93a65, 제품 3파일) 선행 통합 → 재동결·재수락 후에만** 교체. 통합·교체는 하지 않았습니다.

## 문서 수정
- 이 보고서 신규, 후보 `REPORT_KO.md`에 절 추가(백업 `REPORT_KO.prev-20261025T2206.md`). wiki 계약·index 수정 0.

## 코드 검증 (제품 source 변경 0)
| 항목 | 결과 |
|---|---|
| 실 E4B 명시 고정 control (I06 fixture `이 일정은 고정해 주세요.` + 예약 완료, 정상 API→ingest claim→assemble→review→GET) | 2/2 = 100% (gugu_replay_improved_20261025 1, gugu_replay_baseline_20261025 1). 각 21/21 검사 pass |
| 저장 내용 | `items[0].locked` llm_agent claim=true, 인용 원문 span [63,77] `이 일정은 고정해 주세요.`, stored review locked=true = GET locked=true, booked=true, dropped.locked_booking=0 |
| 실모델 호출 | 2 (이번 cap 4), `tripilot-pointer:e4b-ft` digest ef0a580a…, ctx 8192, concurrency 1, done_reason=stop. lease 반환, inflight 0 |
| idle gate | 매 dispatch·모델 요청 직전. 8042 = PID 27184 v7 launcher(교체 없음 확인), counters 22/22, 활성 intake 0 |
| runtime-serving | 후보 폴더 사본 스크립트 `build_runtime_serving.py`로 생성(subprocess 0), runtime inputs 6198, 외부 drift 0 |
| `--shadow --preflight` | RC0, listen 0, 추론 0, routes 120, acop_cs 읽기 전용 |
| app closure | `190dad440dfebda911f5524c578a53ba0beed06baf9c0c0cdc127eb111455bdb` (517 파일, 동결본=startup, source drift 0) |
| 합집합 | 2174/2184 = 99.54%, 새 실패 0 (source 불변이라 기존 결과 유지) |

## all-past 선행 통합 계획 (실행 안 함)
- 원 커밋 diff를 후보 사본에 `apply --check`: 7 hunk 중 6 clean, **review.py `ensure()` hunk #4 1건 REJECT**(후보의 `_customer_inputs` 줄).
- 부모 v7a 해결 patch(`action-v7a-allpast-…/evidence/v7a-product.patch`, sha256 3f92252b…): 후보 3파일 = v7 ours 바이트 동일 → `apply --check` RC0, 결과 3/3 = v7a postimage(CRLF 정규화 후). `pipeline._agent_rows`·`agent_read.py`는 hotfix가 건드리지 않아 충돌 0. 통합할 때 `git -c core.autocrlf=false apply`.
- 통합 후 새 동결·합집합(all-past 시험 2파일 + I06 신규 15)·preflight 다시 필요.

## 해당 환경 반영
- 없음. live 8042 교체·kill·재시작 0, push 0, 등록·알림·유료·고객 DB 쓰기 0. 기준 후보 폴더 쓰기 0.

## 남은 한계
- 표본 2회(같은 fixture·temperature 0). 일반 성능으로 보지 않음.
- 설계 결정 (a)(b)(c)는 부모 기본값(현재 동작 유지)이며 사용자 확인 전.

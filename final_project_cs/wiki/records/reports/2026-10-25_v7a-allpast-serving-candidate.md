# 2026-10-25 v7a(all-past 날짜 가드) 로컬 서빙 후보 — 부모 교체 대기

- 시각: 2026-10-25 23:50 KST · 범위: 로컬 live v7 API(8042)에 all-past hotfix만 추가. 다른 후보(temporal·F02·Comment9·I06)는 섞지 않았습니다.
- 문제: v7은 모든 일정이 오늘 이전인 계획도 새로 등록할 수 있습니다(공개 review·ready, direct POST trips).
- 수정: 팀 develop `d2ab93a65e127e03154af535654bada0d9383d90`의 제품 3파일 hunk를 v7 사본에 3-way로 적용했습니다(itinerary_checks `all_dates_before_today`, review `admission_dates`/cached guard, trip_api `_create_trip` 최종 422 `all_dates_in_past`). review.py 충돌 2곳에서는 v7 고유 `_customer_inputs`를 보존했습니다. 제품 patch SHA256 `3f92252bf7701dfcad68b27d97020136c3d3827b612a3740313416b62331773b`.
- 결과: hotfix 13/13 = 100%(v7 기준 RED 6/13), v7 정확 합집합+hotfix 1376/1376 = 100%, HTTP4 4/4 = 100%, ruff F/E9 0, `--shadow --preflight` RC0, 자가종료 shadow GET 7/7 = 100%.
- 시험 조정 1건: v7 고유의 등록 후 범위 재조회 계약에 맞춰 confirm 시험의 `_trip_view` 대역에 `customer_id`만 추가했습니다. assertion은 바꾸지 않았고 v7에서도 같은 실패가 재현됩니다.
- 반영 상태: 서비스 교체 안 함(부모 전용). 프런트 3100 변경 없음. 한국어 화면은 서버 문장을 그대로 표시합니다.
- 남은 한계: 교체 후 검증(14 GET·provenance·시험 게스트 direct POST 422)은 아직 실행하지 않았습니다. 시험 게스트 발급이 사람 확인으로 막힐 수 있습니다. 기존 세션 인증 acceptance는 v6/v7 상태를 승계합니다.
- 증거: `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\action-v7a-allpast-20261025-233317-fac130f7\` — `PARENT_SWAP.json`, `REPORT_KO.md`, `evidence/`, `runtime-v7a/`, `runtime-v7a-serving/`.
- 모델 추론 0, 고객 DB 쓰기 0, 원본 코드 변경 0, push 0.

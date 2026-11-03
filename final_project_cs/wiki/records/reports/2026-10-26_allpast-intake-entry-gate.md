---
type: report
title: 전부 과거인 계획을 계획 담기 단계에서 막기(접수 읽기 끝 fatal all_dates_in_past + 웹 계획 담기 복귀) — 후보 patch
status: candidate
domain: travel
---

# 전부 과거 계획 — 계획 담기 가드 (2026-10-26 04:20 KST)

- 사용자 원문: 「전부 과거면 계획 고르는 화면으로 넘어가면 안되고 그 전에 있는 계획담기 페이지의 가드레일에 걸려서 통과 안되게 해야해」. 이전 결정 유지: 일부만 과거면 통과, 전부 오늘 이전일 때만 막음.
- 작업 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/allpast-intake-gate-20261026-032048/` (`REPORT_KO.md`, `patches/`, `ev/`).
- 원본 코드·live 8042·프런트 3100 변경 0, push 0, 서빙 교체 0, E4B 호출 0, 비교 DB 쓰기는 e2e 시험이 만든 새 tenant(`trip_api_*`)만.

## 결론

1. 원인: 글·파일·예시 계획 모두 접수 읽기(`pipeline.process`)가 끝나면 무조건 `review` 로 넘어갔고, 날짜 가드는 그 뒤 검사 줄(`date` ✕)·`ready=false`·등록 422 에만 있었다. 그래서 확인(고르는) 화면 첫 카드에서 멈췄다(x600 10/20·10/21 「차단」도 이 review 표시였다).
2. 수정: 읽기·첫 검사 직후, `review` 로 넘기기 전에 등록 가드와 같은 판정(`itinerary_checks.all_dates_before_today`, 새 `review.wholly_past`)으로 보고, 전부 과거면 기존 `fatal` 상태로 끝낸다(`fatal_code: all_dates_in_past` = 등록 거절 violations 코드, 새 상태값 없음). 웹은 이 fatal 을 받으면 계획 확인 화면을 열지 않고 「계획 담기」(`/trips/new`)로 돌아가 보낸 글·파일을 되돌리고 안내를 띄운다(ko 서버 문장 / en 「Every stop is before today. Please check the trip dates.」). 계약은 wiki `external/rest-endpoints/web-intakes.md` 에 먼저 한 문단 추가(후보 트리 안).
3. 검증: 서버 새 시험 12/12(수정 전 3/12 실패 RED), DB e2e 2/2(수정 전 1/2 실패), 웹 새 시험 7/7(수정 전 6/7 실패), 빠른 관문 실패 집합 수정 전후 동일·새 시험 12건만 추가, `npm run check` 3트리 exit 0, 실제 브라우저(가짜 API) ko/en 화면 확인.

## 남은 한계

- 「계획 짜 주기」의 짧은 글에 과거 날짜 일정만 적히면 이제 같은 문장으로 계획 담기에 남는다(전에는 읽은 일정을 버리고 계획을 짰다). 운영 기본 꺼짐(extras) 칸이며 되돌릴 수 있는 기본값으로 둔다.
- 판정은 읽기 끝의 1판(AI 1안)으로 한 번. 로딩 중 해석 답으로 미래 일정이 되살아나는 경우는 다루지 않는다. 확인 화면 진입 뒤 고객이 날짜를 모두 과거로 고친 판은 기존처럼 검사 줄·ready=false·등록 422.
- DB 관문의 고정 날짜 e2e(예: `test_intake_progress_events` PLAN 2026-10-15)는 이제 review 대신 fatal 을 받아 실제 시계에서 실패한다(4건 추가). 대기 중인 시험 시계 patch(`_pin_all_past_guard_today`, 2026-08-01)와 같은 시계로 돌리면 8/8 통과 — 함께 반영해야 한다.
- 실서버(x600·로컬 v8) 반영과 실 E4B 확인은 하지 않았다.

---
type: guide
title: 세션 인계 안내 목차
description: Codex↔Claude 세션을 넘길 때 남기는 인계 문서의 목록과 쓰는 법. 가장 최근 것이 맨 위
status: draft
domain: travel
impl_scope: cs — 세션 인계는 릴리스 대상 final_project_cs 의 작업 폴더 상태를 다룬다. final_project_sample 은 별도 참고 구현이라 해당 없다
---

# 세션 인계 안내 목차

여러 세션(Codex · Claude)이 같은 작업 폴더에서 일하고, 커밋은 사용자가 시킬 때만 한다. 그래서 **git 이력만 보면 최근 작업이 안 보인다.** 이어받는 세션은 아래 목록의 맨 위 인계부터 읽는다.

## 인계 목록 (최근 것이 위)

| 날짜 | 문서 | 무엇 |
|---|---|---|
| 2026-10-14 | [활동 판정 끼움 자리 연결](../../final_project_cs/wiki/records/reports/2026-10-13_activity_ledger_hook.md) | 한 일(끝 · 코드 커밋 2개는 role-manager 반영·양쪽 원격 포함 확인, 위키 커밋 `b76e45f7` 은 이번에 role-manager 반영): 활동 팀 `role-activity-b` 를 합치고(`7440260b`) 활동 코어 전달 사항 3번 — 관광지 휴무 · 중간에 닫힘 · 재난문자 영향을 활동 팀 판정으로 확인 화면 · 등록 판정 · 감시가 본다(`97829e58`), D-CS-013 표(`b76e45f7`). 설정 선언에 활동 팀 새 기능 `activity.submit_itinerary` 추가(없으면 활동 팀이 조립에서 빠져 시험 78개 실패). 시험: 새 9/9 · 구조·계약·단위 실패 14 · 통과 6,379(매니저 그대로에서도 9개 실패, 5개는 새 DB 프롬프트 미등록). 격리 DB 확인: 경복궁 10/20(화) 휴무 경고 · 18:00 마감 3곳 「60분만 머물 수 있어요」. 실제 웹 화면 확인 안 함. ★바로 아래 06:00 작업(미커밋)과 `intake/hours.py` · `review.py` · `itinerary_checks.py` 가 겹친다 — 합칠 때 둘 다 살린다. 남은 것: 공휴일 조건 휴무는 모름 · 활동 팀이 `ledger.state_by_content` 추가를 받아들일지 · 활동 팀 wiki 추가분(`teams/activity.md`) 옮기기 |
| 2026-10-13 06:00 | [고객이 운영시간을 직접 알려 주는 기능](../../final_project_cs/wiki/records/reports/2026-10-13_고객_운영시간_직접입력.md) | 한 일(끝 · 커밋 안 함): 확인 화면에서 운영시간을 못 찾은 일정에 고객이 여는·닫는 시각과 쉬는 요일을 넣는다(`items[n].hours`, 다른 출처가 있으면 그쪽이 이김, 장소를 바꾸면 지움, 등록 뒤엔 항목 `detail.customer_hours` 에만). 화면 읽기 「모두 확인했어요」는 못 찾은 곳이 있으면 「고칠 곳은 없어요 · 운영시간을 못 찾은 곳 n곳」. 바뀐 폴더: cs `app/.../intake/`(pipeline·hours·review·assemble·direct_schedule) · `itinerary/itinerary_checks.py` · 웹 `features/plan-check/` · `features/intake-review/model.ts` · `lib/live/`(intake·intake-review·intake-events) · `tests/live/`(stub-server · 새 spec) · 시험 2개 새로 · 시험 2개 흉내 함수 고침 · 계약 `web-intakes.md`. 시험: 단위 19/19 · DB 5/5 · 기존 확인 화면 75/75 · mock 서버 시험 75/75 · 실서버 확인 안 함. 19:40 추가: 새벽 확인(구글이 모를 때만)·대체 일정·지연 반영·대화 답·여행 화면도 알려 준 값을 씀(일정 불러올 때 장소 보기에 붙임, `itinerary.with_told_hours`) · 회귀 5235 통과·실패 0. 로컬 `.env.apikeys` 의 새 키 `ACOP_SERPAPI_API_KEY` 는 설정 코드에 칸이 들어가 해결(우회 없이 34/34 재확인) |
| 2026-10-13 01:00 | [베이스라인 TRP-BL-2026-10-13 — 작업 기준](../../program/baseline/triPilot-baseline-2026-10-13.md) | 한 일: 베이스라인을 NASA 형상 관리 계획서(SCMP) 양식의 작업 기준으로 다시 씀(커밋 `11a1dbcd` 고정, 승인란 기입 대기). 옛 검토본 본문은 [검증 현황 보고](../../program/baseline/triPilot-verification-status-2026-10-12.md)로 옮김. 알려진 문제는 [검증 현황 보고](../../program/baseline/triPilot-verification-status-2026-10-12.md) 부록으로 옮김. 01:20 해결 요청 전달: 이동(시험 실패 6·택시 요금) → 「이동 이어서」 세션이 받아 「이동경로 최적화」 세션으로 넘김(이동 담당 교대, [근거](../../final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/CLAUDE-HANDOFF-20261013-from-45290d-v1.md) §3), 모니터링·코어(도로 사건 방향 2/20·감시 회차 팀 순서 고정) → 「재난 알림 시 작업 중단 처리」 세션. 01:35 커밋 `2c737818` 기준 이동 시험: 자료 없음 97 통과·실패 0, 실제 자료 132/136(골든 4개 — 새로 만들지 사용자 결정 대기). 남은 것: 승인란 기입·태그(승인 뒤) |
| 2026-10-12 22:00 | [통합 인계 — 10-08~10-12 한 일 목록과 점검 결과](2026-10-12_2200_claude-integrated-handoff.md) | **여기부터 읽는다.** 작업 줄기별 한 일 · 왜 git 이력에 안 보이나 · 오늘 고친 것 · 남은 문제와 주인 · 커밋 전 할 일 |
| 2026-10-12 21:40 | [Claude 이어받기 — 후속 회귀·검색 시험 통과](../../final_project_cs/wiki/records/reports/2026-10-12_2130_followup-data-regression.md) | 한 일: 식당·이동 7개 해소 확인 · 후속 회귀 2,119/2,137(이동 단위 실패 18은 이동 담당 몫) · 시험용 pgdata 33개 삭제 · 베이스라인·v12·통합표 W13 갱신. 21:40 추가: 실제 벡터 계산 끝 · 검색 시험 17/17 통과. 남은 것: 이동 단위 실패 18(이동 담당 판정 — develop PR #41 은 다른 52건 수정) |
| 2026-10-12 18:00 | [코덱스 세션 작업 정리](../../final_project_cs/wiki/records/reports/2026-10-12_1800_코덱스_세션_작업_정리.md) | 10-11 저녁~10-12 오후 코덱스 세션 10개 상세 · 원격→로컬 합침 내역 |
| 2026-10-12 | [Codex → Claude 통합 인계](2026-10-12_codex-to-claude.md) | Codex 가 정리한 읽기 순서 · 검증 범위 · 미완료 범위 |

## 인계를 남기는 법

- **한 일 목록**을 남긴다 — 작업 이름 · 바뀐 폴더 · 상태(끝 / 검증만 남음 / 진행 중 / 실패) · 근거 기록 링크 · 남은 일. 「어디를 읽으라」만 적으면 받는 쪽이 무엇이 바뀌었는지 모른다.
- 커밋하지 않은 변경이 있으면 **어느 경로가 한 묶음인지** 적는다(커밋은 사용자 지시가 있을 때).
- 바깥 기계에서 도는 일(GPU 작업 대기열 · x600 서버 배포)은 **상태를 다시 확인하는 명령**을 적는다. 숫자를 현재 값처럼 옮기지 않는다.
- 규칙을 바꿨으면 루트·`final_project_cs/` 의 `CLAUDE.md` 와 `AGENTS.md` 를 **같이** 고친다(루트 `CLAUDE.md` 「함께 고친다」 절).

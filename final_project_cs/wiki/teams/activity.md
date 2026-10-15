---
type: guide
title: Activity 에이전트 팀 안내
description: 활동 검증의 책임·범위·현재 구현과 과거 개발 기록을 구분한다
status: draft
domain: travel
---

# Activity 에이전트 팀 안내

Activity 에이전트 팀은 여행지의 자연·문화·레포츠·쇼핑 활동이 일정 조건에서 가능한지 검증하고 변경안을 제시합니다. 예약 유무·실내 여부·레저 여부만으로 활동 범위를 좁히지 않습니다.

## 책임과 경계

영업·운영 조건, 날씨, 시간과 장소의 근거를 대조하고 에이전트 팀 결과를 반환합니다. 직접 쓰기 실행을 하지 않으며 [Team 계약](team-contract/index.md)과 [코드 구조 계약](code-layout.md)을 따릅니다.

## 구현과 검증

- [Activity 구현](../../app/domains/travel_ops/instances/activity/) — 현재 작업 위치
- [활동 시험](../../tests/unit/travel/activity/) — 회귀 검증 위치
- [여행별 문제 조정 결정](../../../wiki/decisions/D-017-watch-cadence-golden-time.md) — WatchBatch 책임과 계산 등록 경로

아래 기록의 과거 미구현·실측 수치는 해당 날짜의 상태입니다. 현재 완료 판단은 현재 코드와 후속 실행 기록을 대조합니다.


## 최근 외부 브랜치 검토

[2026-10-12 최신 3커밋·Claude 5.5 Sonnet 검토](../records/reports/2026-10-12_0414_Activity_최신3커밋_Sonnet55_검토.md) — 별도 최신 사본 수신, 관련 시험 480/480 통과. 확정 계약 우선순위·서빙 관문·취향 추천 연결은 보완이 필요하며 주 작업 브랜치 병합·운영 배포는 하지 않았습니다.

[2026-10-13 전달 8번 회신 — 예약 성립 판정의 설문 전달](../records/reports/2026-10-13_활동_전달8_설문전달_회신.md) — Case 상태에 칸을 더하지 않고 활동 팀이 그 예약이 속한 여행의 설문을 도구로 읽는다. 여행을 못 찾으면 필요할 때만 질문 하나를 다시 묻고 이번 문의에만 쓴다. 공용 도구(`read.booking` 의 `trip`)는 매니저 브랜치에 들어갔고, 활동 팀 쪽(여행 설문 읽기 · 다시 묻기 · 지난 답)은 [2026-10-14 구현 · 시험](../records/reports/2026-10-14_활동_전달8_활동쪽_구현.md)했습니다.

[2026-10-13 전달 사항(10-13) 회신](../records/reports/2026-10-13_활동_전달사항_1013_회신.md) — 3건 모두 코어 반영 · develop 에 올림(운영 상태 읽기 연결 · 팀 정기 작업 자리 — 새벽 3시 시간대 · 예약 → 여행 찾기). 활동 쪽 부탁: 원장 판정에도 운영 상태 싣기 · 꺼짐 경고 · `jobs.py` 등록 · 예산 「최대 3번」 재계산.

`[2026-10-14 코어]` **`jobs.py` 등록은 코어가 했다** — 웹 운영 확인 배치가 새벽 정기점검(03:00 시작 · 03:30 목표 · 08:00 멈춤)에서 1분마다 2~4곳씩 돈다(`instances/activity/jobs.py` · 부품은 `instances/activity/live_batch.py` 로 옮김, 스크립트 `scripts/activity/check_live_status.py` 는 손으로 돌리는 껍데기). 정기점검이 묻는 「오늘 남은 건수」(`remaining`)는 활동 팀에 묻지 않고 대상 목록에서 직접 센다(최근 6시간 안에 본 곳 제외). 연결 · 판정 LLM · 웹 예산은 조립이 꽂는다(팀 폴더는 인프라를 직접 열지 않는다 — DoD-22). 판정 LLM 이 꺼져 있으면 `disabled` 로 답하고 아무것도 부르지 않는다.

## 시점별 기록

[정정 전 전체 본문](../records/reports/2026-10-11_activity.md) — 날짜별 계약·검증·초안을 보존했습니다. 날짜가 붙은 결과를 오늘의 전체 통과나 운영 반영으로 읽지 않습니다. 후속 결정이 없는 계약 조항은 원문의 적용 범위를 확인합니다.

### 기존 링크 연결

<a id="왜-이것이-첫째인가"></a> [기존 절: 왜 이것이 첫째인가](../records/reports/2026-10-11_activity.md#왜-이것이-첫째인가)
<a id="무엇이-이-team-의-상품인가"></a> [기존 절: 무엇이 이 Team 의 상품인가](../records/reports/2026-10-11_activity.md#무엇이-이-team-의-상품인가)
<a id="범위--관광-분류체계로-못박는다"></a> [기존 절: 범위 — 관광 분류체계로 못박는다](../records/reports/2026-10-11_activity.md#범위--관광-분류체계로-못박는다)
<a id="-2026-09-09-레저로-좁힐까-는-잘못된-질문이었다"></a> [기존 절: ★ [2026-09-09] "레저로 좁힐까" 는 잘못된 질문이었다](../records/reports/2026-10-11_activity.md#-2026-09-09-레저로-좁힐까-는-잘못된-질문이었다)
<a id="셋을-갖는다"></a> [기존 절: 셋을 갖는다](../records/reports/2026-10-11_activity.md#셋을-갖는다)
<a id="①-검증-규칙--코드가-판정한다"></a> [기존 절: ① 검증 규칙 — 코드가 판정한다](../records/reports/2026-10-11_activity.md#①-검증-규칙--코드가-판정한다)
<a id="②-감시-소스"></a> [기존 절: ② 감시 소스](../records/reports/2026-10-11_activity.md#②-감시-소스)
<a id="-2026-09-10-감시-소스는-넓은-것부터-좁은-것으로"></a> [기존 절: ★ [2026-09-10] 감시 소스는 넓은 것부터 좁은 것으로](../records/reports/2026-10-11_activity.md#-2026-09-10-감시-소스는-넓은-것부터-좁은-것으로)
<a id="③-재계획-후보"></a> [기존 절: ③ 재계획 후보](../records/reports/2026-10-11_activity.md#③-재계획-후보)
<a id="재계획이-다른-team의-일정을-건드린다"></a> [기존 절: 재계획이 다른 Team의 일정을 건드린다](../records/reports/2026-10-11_activity.md#재계획이-다른-team의-일정을-건드린다)
<a id="manifest--실제-구현"></a> [기존 절: manifest — 실제 구현](../records/reports/2026-10-11_activity.md#manifest--실제-구현)
<a id="2026-09-25-규정-질문--activityitinerary_question"></a> [기존 절: `[2026-09-25]` 규정 질문 — `activity.itinerary_question`](../records/reports/2026-10-11_activity.md#2026-09-25-규정-질문--activityitinerary_question)
<a id="2026-09-17-case-버전의-여행-일정-관리--activityitinerary"></a> [기존 절: `[2026-09-17]` Case 버전의 여행 일정 관리 — `activity.itinerary`](../records/reports/2026-10-11_activity.md#2026-09-17-case-버전의-여행-일정-관리--activityitinerary)
<a id="business_subject--도메인이-바뀌어도-안-바꾸는-칸"></a> [기존 절: `business_subject` — 도메인이 바뀌어도 안 바꾸는 칸](../records/reports/2026-10-11_activity.md#business_subject--도메인이-바뀌어도-안-바꾸는-칸)
<a id="-2026-09-09-코드가-이-규칙을-안-지킨다"></a> [기존 절: ★ [2026-09-09] 코드가 이 규칙을 안 지킨다](../records/reports/2026-10-11_activity.md#-2026-09-09-코드가-이-규칙을-안-지킨다)
<a id="-2026-09-10-계획서가-이-규칙을-받았다--v11-4-e"></a> [기존 절: ★ [2026-09-10] 계획서가 이 규칙을 받았다 — v11 §4-E](../records/reports/2026-10-11_activity.md#-2026-09-10-계획서가-이-규칙을-받았다--v11-4-e)
<a id="-두-번-다시-이렇게-부르지-않는다"></a> [기존 절: ★ 두 번 다시 이렇게 부르지 않는다](../records/reports/2026-10-11_activity.md#-두-번-다시-이렇게-부르지-않는다)
<a id="이-team이-하지-않는-것"></a> [기존 절: 이 Team이 하지 않는 것](../records/reports/2026-10-11_activity.md#이-team이-하지-않는-것)
<a id="걸리는-것"></a> [기존 절: 걸리는 것](../records/reports/2026-10-11_activity.md#걸리는-것)
<a id="관계"></a> [기존 절: 관계](../records/reports/2026-10-11_activity.md#관계)

## 관계

- [영역 안내](index.md) — 인접 문서와 읽기 순서

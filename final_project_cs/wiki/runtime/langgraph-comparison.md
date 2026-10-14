---
type: guide
title: LangGraph 비교 실험 안내
description: 현재 흐름 제어 계약과 과거 비교 실험을 구분한다
status: draft
domain: travel
---

# LangGraph 비교 실험 안내

현재 흐름 제어는 [Controller](agentic-controller.md)와 [Case 생명주기](case-lifecycle.md)에서 확인합니다. 2026-10-03 LangGraph 비교의 결과·조건·반박·재현 명령은 아래 기록에 있습니다. 당시 속도 차이를 현재 제품 전체 지연으로 확대하지 않습니다.

## 시점별 기록

[정정 전 전체 본문](../records/reports/2026-10-11_langgraph-comparison.md) — 날짜별 계약·검증·초안을 보존했습니다. 날짜가 붙은 결과를 오늘의 전체 통과나 운영 반영으로 읽지 않습니다. 후속 결정이 없는 계약 조항은 원문의 적용 범위를 확인합니다.

### 기존 링크 연결

<a id="왜-쟀나"></a> [기존 절: 왜 쟀나](../records/reports/2026-10-11_langgraph-comparison.md#왜-쟀나)
<a id="결과"></a> [기존 절: 결과](../records/reports/2026-10-11_langgraph-comparison.md#결과)
<a id="직선-경로--접수--분류--담당--처리--종결-전이-4회"></a> [기존 절: 직선 경로 — 접수 → 분류 → 담당 → 처리 → 종결 (전이 4회)](../records/reports/2026-10-11_langgraph-comparison.md#직선-경로--접수--분류--담당--처리--종결-전이-4회)
<a id="대기재개가-든-경로--위에-대기--재개-한-번-전이-6회"></a> [기존 절: 대기·재개가 든 경로 — 위에 「대기 → 재개」 한 번 (전이 6회)](../records/reports/2026-10-11_langgraph-comparison.md#대기재개가-든-경로--위에-대기--재개-한-번-전이-6회)
<a id="디스크에-쓴-양-같은-횟수-기준"></a> [기존 절: 디스크에 쓴 양 (같은 횟수 기준)](../records/reports/2026-10-11_langgraph-comparison.md#디스크에-쓴-양-같은-횟수-기준)
<a id="코드-분량-같은-흐름을-짜는-데-든-줄-수"></a> [기존 절: 코드 분량 (같은 흐름을 짜는 데 든 줄 수)](../records/reports/2026-10-11_langgraph-comparison.md#코드-분량-같은-흐름을-짜는-데-든-줄-수)
<a id="과장하지-않기"></a> [기존 절: 과장하지 않기](../records/reports/2026-10-11_langgraph-comparison.md#과장하지-않기)
<a id="공정하게-하려고-한-것"></a> [기존 절: 공정하게 하려고 한 것](../records/reports/2026-10-11_langgraph-comparison.md#공정하게-하려고-한-것)
<a id="동작-비교--속도보다-이쪽이-중요하다"></a> [기존 절: 동작 비교 — 속도보다 이쪽이 중요하다](../records/reports/2026-10-11_langgraph-comparison.md#동작-비교--속도보다-이쪽이-중요하다)
<a id="틀린-이동을-막아-주나"></a> [기존 절: 틀린 이동을 막아 주나](../records/reports/2026-10-11_langgraph-comparison.md#틀린-이동을-막아-주나)
<a id="필요한-값이-빠졌을-때"></a> [기존 절: 필요한 값이 빠졌을 때](../records/reports/2026-10-11_langgraph-comparison.md#필요한-값이-빠졌을-때)
<a id="중간에-죽으면-어디까지-갔는지-아나"></a> [기존 절: 중간에 죽으면 어디까지 갔는지 아나](../records/reports/2026-10-11_langgraph-comparison.md#중간에-죽으면-어디까지-갔는지-아나)
<a id="되감을-수-있나"></a> [기존 절: 되감을 수 있나](../records/reports/2026-10-11_langgraph-comparison.md#되감을-수-있나)
<a id="둘이-동시에-같은-건을-고치면"></a> [기존 절: 둘이 동시에 같은 건을 고치면](../records/reports/2026-10-11_langgraph-comparison.md#둘이-동시에-같은-건을-고치면)
<a id="새-상태를-하나-더하려면"></a> [기존 절: 새 상태를 하나 더하려면](../records/reports/2026-10-11_langgraph-comparison.md#새-상태를-하나-더하려면)
<a id="많이-들어오면--처리량"></a> [기존 절: 많이 들어오면 — 처리량](../records/reports/2026-10-11_langgraph-comparison.md#많이-들어오면--처리량)
<a id="새-흐름을-하나-더하면--안-고친-자리를-누가-잡나"></a> [기존 절: 새 흐름을 하나 더하면 — 안 고친 자리를 누가 잡나](../records/reports/2026-10-11_langgraph-comparison.md#새-흐름을-하나-더하면--안-고친-자리를-누가-잡나)
<a id="한-번-191ms-까지-튀던-것"></a> [기존 절: 한 번 191ms 까지 튀던 것](../records/reports/2026-10-11_langgraph-comparison.md#한-번-191ms-까지-튀던-것)
<a id="코덱스-반박--내-비교가-어디서-기울었나"></a> [기존 절: ★코덱스 반박 — 내 비교가 어디서 기울었나](../records/reports/2026-10-11_langgraph-comparison.md#코덱스-반박--내-비교가-어디서-기울었나)
<a id="구조적으로-기운-항목--여섯"></a> [기존 절: 구조적으로 기운 항목 — 여섯](../records/reports/2026-10-11_langgraph-comparison.md#구조적으로-기운-항목--여섯)
<a id="조건이-같아야-비교되는-항목"></a> [기존 절: 조건이 같아야 비교되는 항목](../records/reports/2026-10-11_langgraph-comparison.md#조건이-같아야-비교되는-항목)
<a id="가장-강한-반론--결론-범위가-넓었다"></a> [기존 절: ★가장 강한 반론 — 결론 범위가 넓었다](../records/reports/2026-10-11_langgraph-comparison.md#가장-강한-반론--결론-범위가-넓었다)
<a id="아직-안-잰-것"></a> [기존 절: 아직 안 잰 것](../records/reports/2026-10-11_langgraph-comparison.md#아직-안-잰-것)
<a id="그래서-어떻게-하나"></a> [기존 절: 그래서 어떻게 하나](../records/reports/2026-10-11_langgraph-comparison.md#그래서-어떻게-하나)
<a id="다시-재는-법"></a> [기존 절: 다시 재는 법](../records/reports/2026-10-11_langgraph-comparison.md#다시-재는-법)
<a id="이어지는-것"></a> [기존 절: 이어지는 것](../records/reports/2026-10-11_langgraph-comparison.md#이어지는-것)

## 관계

- [영역 안내](index.md) — 인접 문서와 읽기 순서

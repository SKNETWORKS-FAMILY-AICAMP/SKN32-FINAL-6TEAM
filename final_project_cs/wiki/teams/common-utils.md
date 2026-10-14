---
type: guide
title: 여행 Team 공통 구현
description: 여행 에이전트 팀의 공통 기반(TravelTeamBase)과 팀들이 함께 쓰는 구현
status: draft
domain: travel
---

# 여행 Team 공통 구현

현재 공통 기반은 [TravelTeamBase](../../app/domains/travel_ops/instances/_shared/_base.py)입니다. Team·capability·degraded 확인, 허용 도구·예산 전달, 근거 누적, 결과·제안 구성의 공통 절차를 제공합니다. 일정 판정 공통 동작은 [itinerary_team](../../app/domains/travel_ops/instances/_shared/itinerary_team.py)에 있습니다.

업무별 판단은 각 [여행 인스턴스](code-layout.md)에 남깁니다. 공통 기반을 변경하면 이를 사용하는 에이전트 팀의 호출·근거·대기·재개 시험을 함께 확인합니다. 기존 상속 구조와 과거에 제안했던 조합형 유틸을 혼동하지 않습니다. 구현되지 않은 과거 설계를 현재 파일 경로로 안내하지 않습니다.

공유 계약 변경은 [개발 역할](../../../wiki/delivery/roles.md)의 검토 절차를 따릅니다. 프롬프트·knowledge scope·도구 권한을 편의상 한 업무에 합치지 않습니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--teams--common-utils.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="team-공통-뼈대"></a>
<a id="반복되는-네-가지"></a>
<a id="-상속이-아니라-조합이다"></a>
<a id="공통-prompt-도-합치지-않는다"></a>
<a id="-아직-없다"></a>
<a id="-2026-09-10-공통-뼈대는-생겼다--다만-조합이-아니라-상속이다"></a>
<a id="관계"></a>

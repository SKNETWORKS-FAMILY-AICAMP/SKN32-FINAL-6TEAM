---
type: guide
title: 여행 에이전트 팀
description: 현재 여행 기준과 사용 종료된 기록을 구분한다
status: draft
domain: travel
---

# 여행 에이전트 팀

Team은 **업무 요청을 판정하고 제안을 반환하는 에이전트 팀**입니다. 개발 팀원의 조직을 뜻하지 않습니다. 실제 등록·허용 도구는 [프로젝트 선언](../../config/project.yaml), 구현·시험 위치는 [코드 경로](code-layout.md)가 소유합니다.

| 에이전트 팀 | 현재 제품 범위 | 책임 문서 |
|---|---|---|
| Activity | MVP | [활동 판정](activity.md) |
| Dining | MVP | [식당 판정](dining.md)·[설계](dining-agent-design.md) |
| Mobility | MVP | [이동 판정](mobility.md) |
| Booking Handoff | MVP 다음 단계 | [예약 인계](booking-handoff.md) |
| Lodging·Flight | 확장 — 숙소 · 항공편 찾기, 일정 숙소 · 항공 항목의 「다른 후보」(예약은 링크로). `[2026-10-13]` role-manager 등록 · 일정에 항목을 만드는 웹 입구는 아직 없음 | [현재 선언](../../config/project.yaml) · [반영 기록](../records/reports/2026-10-13_숙소항공_role-manager_반영.md) |

범위는 [제품 범위](../../../wiki/product/scope.md)와 후속 확정 결정을 따릅니다. 등록·코드 존재를 기능 완료나 배포 완료로 해석하지 않습니다.

## 선택·실행·제안 경계

`TeamRegistry`는 `case_type`·`intent`와 manifest로 팀을 선택합니다. `Controller`가 작업을 실행하고 결과를 처리합니다. Team은 다른 Team을 직접 호출하거나 외부 부수효과를 직접 실행하지 않습니다. 읽기 권한과 예산은 공통 도구 경계를 따릅니다.

[Team 계약](team-contract/index.md) → [책임 경계](team-boundary.md) → [Registry](team-registry.md) → [조립](composition.md) 순서로 읽습니다. 도구 목록을 이 페이지에 복제하지 않습니다.

[플러그인 가용성과 요청 판 고정](team-plugin-lifecycle.md)은 담당 부재 시 업무 중단, 독립 기능 유지, 질문·답변 재개와 교체의 현재 로컬 구현·시험·운영 반영 상태를 구분합니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--teams--index.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 2026-10-12 목차에 더한 문서

- [dining-customer-reports.md](dining-customer-reports.md) — 고객 실시간 제보(식사 시작 시각 「영업 중인가요?」 · 일정 카드 제보 버튼 · 같은 식당 제보 공유) 설계

## 이전 절 링크

<a id="teams"></a>
<a id="읽기-순서"></a>
<a id="계약구조"></a>
<a id="여행-team"></a>
<a id="-2026-09-10-place-verification--상대는-생겼고-아직-안-붙었다"></a>
<a id="지난-도메인의-team--코드도-문서도-여기-없다"></a>
<a id="team이-하지-않는-것-셋"></a>
<a id="team의-read-도구"></a>
<a id="이-영역의-불변식"></a>
<a id="sample의-team"></a>
<a id="인접-영역"></a>
<a id="조립-선언은-따로-본다"></a>

---
type: guide
title: 여행 Team 구축 순서
description: 새 에이전트 팀을 만드는 순서 — 범위·계약 확인부터 판정·대기·재개 조건, 시험, 등록까지
status: draft
domain: travel
---

# 여행 Team 구축 순서

1. [제품 범위](../../../wiki/product/scope.md)와 [Team 계약](team-contract/index.md)에서 업무 입력·판정·결과·대기·재개 조건을 확인합니다.
2. [현재 코드 경로](code-layout.md)에 구현·시험을 배치하고 manifest의 case type·intent·capability·도구·knowledge scope를 맞춥니다.
3. 계산·외부 조회·LLM 대안 생성의 경계를 나누고 근거를 누적합니다. 생성한 대안도 같은 검증을 통과해야 합니다.
4. [Registry](team-registry.md)·[조립 선언](composition.md)에 연결하고 비활성·미설치·계약 오류 경로를 검사합니다.
5. 업무 단위 시험에 더해 실제 입력→분류→팀 선택→제안→실행 경계의 통합 시험을 확인합니다. API·MCP·고객 웹 연결과 운영 반영은 각각 증거를 남깁니다.

다른 제품의 주문·배송·반품 자료를 대조군으로 가져오지 않습니다. 원격 A2A는 [원격 계약](remote-team-a2a.md)을 따르며 계약 왕복 확인과 실제 외부 데이터 정확성을 구분합니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--teams--build-order.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="team-을-어느-순서로-만드나"></a>
<a id="계획한-순서"></a>
<a id="왜-activity-가-첫째인가"></a>
<a id="booking-handoff-는-왜-필요한가--mvp-다음"></a>
<a id="-실제로는-이-순서로-안-갔다"></a>
<a id="그-선택이-만든-것--좋은-쪽과-나쁜-쪽"></a>
<a id="business_subject"></a>
<a id="-지금-막혀-있는-것--team-순서가-아니라-그-앞이다"></a>
<a id="다음에-무엇을-만드나"></a>
<a id="관계"></a>

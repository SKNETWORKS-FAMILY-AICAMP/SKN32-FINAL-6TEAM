---
type: guide
title: 여행 도메인 조립과 정책 주입
description: 여행 도메인을 공통 엔진에 조립하고 여행 정책을 주입하는 방식
status: draft
domain: travel
---

# 여행 도메인 조립과 정책 주입

현재 제품은 여행 CS입니다. 도메인 조립은 [현재 조립 계약](../../final_project_cs/wiki/teams/composition.md)과 [TeamRegistry](../../final_project_cs/wiki/teams/team-registry.md)를 따릅니다. 에이전트 팀은 `TeamTask`·`TeamResult`·`ActionProposal` 계약으로 연결하며 Core에서 Team 내부를 직접 import하지 않습니다.

## 현재 검증하는 성질

[여행 정책 주입 시험](../../final_project_cs/tests/architecture/test_engine_accepts_travel_policies.py)은 합성 철도 패스·승차권 정책의 참조·금액·인원 상한을 같은 검증 엔진에 주입합니다. 실제 제품의 패스 기능 출시나 모든 산업의 범용성을 증명하지 않습니다. 다른 여행 정책으로 입력을 바꾸면 판정도 바뀌는지 확인합니다. [불변식 카탈로그](../../final_project_cs/wiki/quality/invariants.md)가 검사 책임을 소유합니다.

과거 Pack 교체의 소스 개수·미추적 상태·일정과 쇼핑몰 대조군은 당시 기록입니다. 현재 사업 방향을 기업용 다중 산업 플랫폼으로 확정하는 근거로 사용하지 않습니다. 현재 제공 범위는 [제품 범위](../product/scope.md)가 소유합니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--architecture--pack-model.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [별도 참고 구현체](../../final_project_sample/wiki/index.md) — 여행 제품의 완료 증거와 구분합니다.


- [여행 사양 허브](../index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="pack-모델"></a>
<a id="-pack은-이-wiki-의-낱말이지-v10-의-낱말이-아니다"></a>
<a id="구조"></a>
<a id="판정-기준"></a>
<a id="왜-pack인가"></a>
<a id="교체가-성립하는-조건"></a>
<a id="-2026-09-08-판올림이-이-구조를-시험했다"></a>
<a id="-판정--registry-등록만으로-끝난다는-그대로는-못-쓴다"></a>
<a id="-확장-판단은-만들-수-있는가가-아니다"></a>
<a id="필요-team과-착수-team을-구분한다"></a>
<a id="port-3종을-같은-원칙으로-둔다"></a>
<a id="mvp가-여기까지인-이유"></a>
<a id="teamexecutorport"></a>
<a id="성공-판정"></a>
<a id="현재-상태"></a>
<a id="pack-범위-판단"></a>
<a id="vision"></a>
<a id="관계"></a>

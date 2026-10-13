---
type: guide
title: 여행 도메인과 공통 엔진의 경계
description: 현재 여행 기준과 사용 종료된 기록을 구분한다
status: draft
domain: travel
---

# 여행 도메인과 공통 엔진의 경계

현재 업무 구현은 `app/domains/travel_ops/`와 프로젝트 선언에서 조립합니다. Core가 여행 Team 구현을 직접 import하지 않는 경계는 [구조 시험](../tests/architecture/)으로 확인합니다. 계약·팀 선택·가용성은 [현재 조립 계약](teams/composition.md)·[Registry](teams/team-registry.md)를 따릅니다.

과거 도메인 교체 과정은 기록으로 남깁니다. 현재 관문에서 이전 상품 주문·반품 자료를 대조군으로 사용하지 않습니다. [정책 주입 시험](../tests/architecture/test_engine_accepts_travel_policies.py)은 서로 다른 여행 정책의 선언·사실·상한에 따라 같은 엔진이 동작하는지 확인합니다. 이 시험만으로 모든 산업의 범용성이 증명됐다고 말하지 않습니다.

새 Team·도구·knowledge scope를 추가하면 구현·선언·프롬프트·자료·시험·현재 안내를 함께 갱신하고, 이전 자료는 현재 실행과 분리합니다. 실제 개발 경로는 [배치 안내](teams/code-layout.md)가 소유합니다.

## 과거 기록

[수정 전 문서](records/commerce_2026-10-11/wiki--domain-swap.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="도메인을-갈아-끼울-때"></a>
<a id="바꾸는-것--순서가-있다"></a>
<a id="1-도메인-테이블"></a>
<a id="2-대조-선언"></a>
<a id="-갈아-끼우지-않는-것--11행"></a>
<a id="같은-목록이-composer-에도-있다"></a>
<a id="이-목록이-sample-이-혼자-서는-근거다"></a>
<a id="복사-후-첫-검증"></a>
<a id="-2026-09-09-가드가-여행-어휘를-모른다"></a>
<a id="이-문서가-생긴-이유"></a>
<a id="원본-가이드handoff10에서-낡은-것"></a>
<a id="어느-문서를-다시-쓰나"></a>
<a id="관계"></a>

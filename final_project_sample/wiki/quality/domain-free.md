---
type: concept
title: Basement의 도메인 독립성 강제
description: basement가 업무 도메인을 모른다는 경계를 어떤 검사들이 강제하는지 설명한다.
status: draft
tags: [testing, architecture]
domain: neutral
domain_note: 코어에 도메인 어휘가 없는지 보는 가드다. 커머스 낱말은 금지 목록이다
---

## 결론

`[실측]` “basement는 도메인을 모른다”는 선언만으로 유지되지 않는다. 금지 어휘 검색, 도메인 모듈 import 금지, 예외 수 제한, 도메인 위치에 대한 양성 대조군이 함께 경계를 강제한다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:78`, `tests/architecture/test_basement_is_domain_free.py:94`, `tests/architecture/test_basement_is_domain_free.py:103`, `tests/architecture/test_basement_is_domain_free.py:108`

## 금지 어휘

`[실측]` 검사 대상은 `acop_basement` 아래의 Python 파일이며 `__pycache__` 경로는 제외된다. `tests/architecture/test_basement_is_domain_free.py:27`, `tests/architecture/test_basement_is_domain_free.py:57`

`[실측]` 금지 어휘는 다음 열 가지다. 대소문자는 구분하지 않는다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:44`

- 구독·결제: `payment`, `subscription`, `entitlement`, `refund`, `invoice`
- 커머스: `order_id`, `line_item`, `shipment`, `sku`, `cart`

`[실측]` 해당 어휘가 실행 코드의 한 줄에서 발견되면 파일 경로, 줄 번호, 잘린 원문이 문제 목록에 들어가고 최종 assertion이 실패한다. `tests/architecture/test_basement_is_domain_free.py:66`, `tests/architecture/test_basement_is_domain_free.py:78`

`[실측]` 주석, 삼중 큰따옴표로 시작하는 줄, `★`로 시작하는 줄은 검색에서 제외한다. 설명 속 도메인 어휘를 결합으로 판정하지 않기 위한 줄 단위 예외다. `tests/architecture/test_basement_is_domain_free.py:68`

## 구조적 보강

`[실측]` `from app.modules`와 `import app.modules` 문자열이 basement 파일에 있으면 별도의 테스트가 실패한다. 조립 지점이 아니라 basement가 도메인 구현을 직접 호출하는 결합을 잡는다. `tests/architecture/test_basement_is_domain_free.py:108`

`[실측]` 도메인 구현 위치에도 같은 검색을 적용해 적어도 한 파일에서 도메인 어휘가 발견되어야 통과한다. 이 양성 대조군은 검사 대상이 비었거나 어휘 목록이 현실과 동떨어져 항상 통과하는 상태를 막는다. `tests/architecture/test_basement_is_domain_free.py:94`

`[실측]` 허용 예외는 PII 마스킹 규칙 파일과 원격 Agent 데모 파일 두 건이다. 허용 목록 자체도 최대 3건으로 제한된다. `tests/architecture/test_basement_is_domain_free.py:46`, `tests/architecture/test_basement_is_domain_free.py:103`

`[실측]` 검증 엔진에는 추가 검사가 있다. 실행부에 `payment_id`, `subscription_id`, `order_id`, `amount_cents`, `total_cents`가 있으면 다른 도메인 테스트가 실패한다. `tests/architecture/test_engine_serves_another_domain.py:108`

## 재발을 막는 결함

`[실측]` 코드 주석에 따르면 2026-08-16에 구독·결제 어휘가 Core에 박혔고, 그 결과 쇼핑몰의 `order_id`가 “확인 불가 → 거부” 대상이 되었다. 도메인 독립성 검사는 이 결함의 재발 방지 장치로 작성되었다. `tests/architecture/test_basement_is_domain_free.py:12`

## 보장 범위

`[실측]` 이 게이트가 직접 보장하는 것은 목록에 든 어휘와 두 형태의 `app.modules` import 문자열이 검사 대상 코드에 없다는 점이다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:108`

`[미확보]` 목록에 없는 새 도메인 어휘, 별칭이나 동적 import, 문자열로 우회한 결합까지 탐지한다는 근거는 확보되지 않았다.

## 관계

- [아키텍처 테스트 다섯 경계](architecture-tests.md)
- [다른 도메인 실행 증거](another-domain.md)
- [제안 대조 규칙](verification.md)

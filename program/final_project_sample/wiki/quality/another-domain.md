---
type: concept
title: 다른 도메인으로 검증한 범용 엔진
description: 같은 검증 엔진에 쇼핑몰 도메인을 연결하는 테스트가 무엇을 증명하는지 설명한다.
status: draft
tags: [testing, architecture, contract]
---

## 결론

`[실측]` **같은 `verify_proposal` 엔진은 구독·결제 필드에 의존하지 않고 쇼핑몰의 주문·배송·환불·반품 규칙을 실행한다.** 테스트는 쇼핑몰 정책을 외부에서 선언해 `acop_basement.core.verification`의 `Facts`, `QuantityRule`, `VerificationPolicy`, `verify_proposal`에 주입한다. `tests/architecture/test_engine_serves_another_domain.py:15`, `tests/architecture/test_engine_serves_another_domain.py:19`, `tests/architecture/test_engine_serves_another_domain.py:47`

`[실측]` 이 테스트의 import와 실행 경로에는 `final_project_cs`가 없다. **실행 결과는 아래와 같다.**

```
python -m pytest tests/architecture/test_engine_serves_another_domain.py -q
10 passed in 0.04s          # 2026-09-02 확인
``` 따라서 허용된 확인 범위 안에서는 sample의 검증 엔진이 cs 없이 다른 도메인 규칙을 수행한다는 실행 증거가 성립한다. `tests/architecture/test_engine_serves_another_domain.py:11`, `tests/architecture/test_engine_serves_another_domain.py:15`, `tests/architecture/test_engine_serves_another_domain.py:59`

## 주입한 쇼핑몰 계약

`[실측]` 참조 규칙은 `order_id`를 `orders` 컬렉션에, `shipment_id`를 `shipments` 컬렉션에 연결한다. `tests/architecture/test_engine_serves_another_domain.py:19`

`[실측]` 환불액은 `order_id`가 가리키는 레코드의 `total_cents`와 비교하며 제안 값에 100을 곱한다. 반품 수량은 같은 주문의 `item_count`와 비교하며 배수는 1이다. `tests/architecture/test_engine_serves_another_domain.py:21`

`[실측]` `coupon_id`는 대조 수단이 없는 `opaque` 필드로 선언되고, `reason`과 `memo`는 대조 대상이 아닌 `ignored` 필드로 선언된다. `tests/architecture/test_engine_serves_another_domain.py:27`

`[실측]` 사실 집합에는 주문 `ord-1001`, 배송 `shp-77`, 주문 상한 `total_cents=5_000_000`, 수량 상한 `item_count=3`, 근거 `mev-1`이 들어간다. `tests/architecture/test_engine_serves_another_domain.py:31`, `tests/architecture/test_engine_serves_another_domain.py:35`

## 실행으로 확인하는 성질

`[실측]` 존재하는 `order_id`는 통과하고 존재하지 않는 주문은 거부된다. 엔진이 `order_id` 자체를 금지하는 것이 아니라 주입된 컬렉션의 사실과 대조한다는 증거다. `tests/architecture/test_engine_serves_another_domain.py:59`, `tests/architecture/test_engine_serves_another_domain.py:64`

`[실측]` 환불액 `70_000`은 배수 적용 후 주문 상한을 넘으므로 거부되고, `20_000`은 통과한다. 상한 검사가 쇼핑몰 정책의 필드 이름과 단위를 받아 작동한다. `tests/architecture/test_engine_serves_another_domain.py:68`, `tests/architecture/test_engine_serves_another_domain.py:74`

`[실측]` 반품 수량 5는 주문 수량 3을 넘으므로 거부되고, 수량 2는 통과한다. 동일 엔진의 수량 규칙이 금액에만 고정되지 않았다는 증거다. `tests/architecture/test_engine_serves_another_domain.py:78`, `tests/architecture/test_engine_serves_another_domain.py:84`

`[실측]` 현재 고객의 배송 `shp-77`은 통과하고 `shp-other`는 거부된다. `tests/architecture/test_engine_serves_another_domain.py:88`

`[실측]` 대조 수단이 없다고 선언한 `coupon_id`는 거부된다. 반대로 쇼핑몰 정책에 없는 `payment_id`는 “선언되지 않은 필드”로 거부된다. 다른 도메인의 어휘가 엔진에 내장되어 자동으로 통과하지 않음을 확인한다. `tests/architecture/test_engine_serves_another_domain.py:93`, `tests/architecture/test_engine_serves_another_domain.py:98`

## 하드코딩 반증

`[실측]` 두 도메인 사례가 모두 동작하는 것만으로는 엔진에 두 도메인을 함께 하드코딩했을 가능성이 남는다. 그래서 테스트는 엔진 실행부를 읽고 `payment_id`, `subscription_id`, `order_id`, `amount_cents`, `total_cents`가 없는지 별도로 검사한다. `tests/architecture/test_engine_serves_another_domain.py:108`

`[실측]` 이 검사는 주석과 일부 docstring 줄을 제외한 문자열 검사다. 지정된 다섯 어휘 이외의 모든 도메인 결합까지 부재한다고 증명하지는 않는다. `tests/architecture/test_engine_serves_another_domain.py:113`

## 2026-08-16 이전 결함

`[실측]` 코드 주석에 따르면 2026-08-16 이전에는 `order_id`가 basement의 “확인 불가 → 거부” 목록에 하드코딩되어 있었다. 그 결과 쇼핑몰의 핵심 식별자가 사실 조회를 받기도 전에 자동 거부되었다. `tests/architecture/test_engine_serves_another_domain.py:7`

`[실측]` 현재 테스트는 기존 주문의 `order_id`가 통과해야 한다는 회귀 조건을 직접 둔다. 과거와 같은 거부 목록이 다시 들어오면 이 조건이 깨진다. `tests/architecture/test_engine_serves_another_domain.py:58`

## 증명의 범위

`[실측]` 이 테스트가 실행으로 증명하는 대상은 범용 제안 검증 엔진과 주입형 정책 계약이다. `tests/architecture/test_engine_serves_another_domain.py:15`, `tests/architecture/test_engine_serves_another_domain.py:19`

`[미확보]` 이 테스트 하나만으로 sample의 모든 하위 시스템, 배포 절차, 외부 연동까지 다른 도메인에서 독립 실행된다고 단정할 근거는 없다.

## 관계

- [아키텍처 테스트 다섯 경계](architecture-tests.md)
- [도메인 독립성 게이트](domain-free.md)
- [제안 대조 규칙](verification.md)

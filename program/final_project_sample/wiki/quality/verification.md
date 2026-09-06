---
type: concept
title: 제안을 사실과 대조하는 규칙
description: 제안의 필드를 무엇과 대조하며 대조할 수 없는 필드를 어떻게 처리하는지 설명한다.
status: draft
tags: [testing, contract, data]
---

## 결론

`[실측]` 제안은 도메인이 제공한 `VerificationPolicy`와 재조회한 `Facts`에 대조된다. 대조 수단이 없는 필드와 정책에 선언되지 않은 필드는 통과시키지 않는다. `acop_basement/core/verification.py:67`, `acop_basement/core/verification.py:87`, `acop_basement/core/verification.py:119`, `acop_basement/core/verification.py:144`, `acop_basement/core/verification.py:158`

`[실측]` 결과는 `Mismatch` 목록이며 빈 목록만 통과다. 불일치를 예외로 던지지 않고 모아 반환한다. `acop_basement/core/verification.py:35`, `acop_basement/core/verification.py:119`

## 대조 입력

`[실측]` `VerificationPolicy`는 네 종류의 선언을 받는다. `references`는 제안 키와 사실 컬렉션을 연결하고, `quantities`는 수량 상한 규칙을 담고, `opaque`는 대조 수단이 없는 키를 표시하며, `ignored`는 대조 대상이 아닌 키를 표시한다. `acop_basement/core/verification.py:67`

`[실측]` `Facts`는 이름별 레코드 컬렉션, 사용 가능한 근거 ID 집합, 사실 조회 성공 여부인 `loaded`를 가진다. 컬렉션 이름은 정책에서 공급된다. `acop_basement/core/verification.py:87`

`[실측]` 검증 함수는 제안 인자 `arguments`, 제안이 든 근거 ID `rationale_evidence_ids`, `facts`, `policy`를 입력으로 받는다. `acop_basement/core/verification.py:119`

## 필드별 판정

| 필드 분류 | 대조 대상과 처리 |
|---|---|
| 참조 필드 | `[실측]` 정책이 지정한 사실 컬렉션에서 `str(value)`를 키로 찾는다. 행이 없으면 해당 고객 소유의 사실이 없는 것으로 불일치를 만든다. `acop_basement/core/verification.py:150` |
| 수량 필드 | `[실측]` 연결된 참조 레코드의 `limit_key` 값과 비교한다. 제안 값에는 정책의 `scale`을 곱해 단위를 맞춘다. `acop_basement/core/verification.py:49`, `acop_basement/core/verification.py:175` |
| `opaque` 필드 | `[실측]` 대응 데이터가 없어 확인할 수 없다는 불일치를 만들고 거부한다. 확인 불가를 허용으로 바꾸지 않는다. `acop_basement/core/verification.py:144` |
| `ignored` 필드 | `[실측]` 대조 대상이 아니므로 건너뛴다. `acop_basement/core/verification.py:140` |
| 선언되지 않은 필드 | `[실측]` 검사 규칙 없이 실행되지 않도록 불일치를 만든다. `acop_basement/core/verification.py:158` |
| 값이 `None`인 필드 | `[실측]` 현재 구현은 필드 분류와 관계없이 첫 순회에서 건너뛴다. `acop_basement/core/verification.py:140` |

## 수량 판정

`[실측]` 수량 값이 있지만 참조 대상 값이 없으면 무엇에 대한 수량인지 확인할 수 없으므로 거부한다. `acop_basement/core/verification.py:175`, `acop_basement/core/verification.py:186`

`[실측]` 제안 값과 상한은 `Decimal`로 변환한다. 변환할 수 없거나 `NaN`, `Infinity`, `-Infinity`처럼 유한하지 않은 값은 숫자가 아닌 것으로 거부한다. `acop_basement/core/verification.py:106`, `acop_basement/core/verification.py:198`

`[실측]` 참조 레코드에 상한 필드가 없거나 상한이 숫자가 아니면 상한을 모르는 것으로 거부한다. `acop_basement/core/verification.py:204`

`[실측]` 배수를 적용한 값이 상한보다 크거나 0 이하이면 거부한다. 상한과 같거나 0보다 크고 상한보다 작은 값은 이 규칙을 통과한다. `acop_basement/core/verification.py:210`

`[실측]` 참조 레코드가 없으면 수량 검사에서는 같은 문제를 다시 추가하지 않는다. 참조 필드 검사가 이미 만든 불일치를 유지한다. `acop_basement/core/verification.py:193`

## 근거와 조회 실패

`[실측]` 제안이 인용한 근거 ID가 `Facts.evidence_ids`에 없으면 `evidence_ids` 불일치를 만든다. `acop_basement/core/verification.py:167`

`[실측]` 사실 조회 자체가 실패해 `loaded=False`이면 다른 필드를 검사하지 않고 `__facts__` 불일치 한 건을 즉시 반환한다. “조회했지만 없음”과 “조회 실패”를 구분하는 처리다. `acop_basement/core/verification.py:94`, `acop_basement/core/verification.py:133`

## 단위 테스트가 확인하는 결과

`[실측]` 실제 상한이 `3_000_000` cents인 사실에 `50_000`원의 제안을 넣으면 거부되고, 원문 금액은 불일치의 digest 문자열에 남지 않는다. `tests/unit/core/test_proposal_verification.py:24`, `tests/unit/core/test_proposal_verification.py:46`

`[실측]` 존재하지 않는 결제 식별자, 다른 고객 범위의 구독 식별자, 대조할 수 없는 식별자, 대상 없는 금액, ContextPack에 없는 근거, 0 이하 값과 비유한 수는 모두 거부 조건으로 검사된다. `tests/unit/core/test_proposal_verification.py:59`, `tests/unit/core/test_proposal_verification.py:66`, `tests/unit/core/test_proposal_verification.py:74`, `tests/unit/core/test_proposal_verification.py:82`, `tests/unit/core/test_proposal_verification.py:89`, `tests/unit/core/test_proposal_verification.py:104`, `tests/unit/core/test_proposal_verification.py:111`

`[실측]` 여러 필드와 근거가 동시에 틀리면 첫 문제에서 멈추지 않고 네 종류의 불일치를 함께 반환하는 조건이 있다. `tests/unit/core/test_proposal_verification.py:122`

`[실측]` 정상 상한과 같은 제안, 부분 수량 제안, 정책의 단위에 맞는 값도 통과 조건으로 검사된다. 과잉 차단 역시 결함으로 취급한다. `tests/unit/core/test_proposal_verification.py:132`, `tests/unit/core/test_proposal_verification.py:139`, `tests/unit/core/test_proposal_verification.py:145`

`[미확보]` 단위 테스트가 주입하는 `CUSTOMER_OPS_POLICY`의 전체 필드 선언은 지정된 확인 파일에 포함되지 않아 이 문서에서 열거하지 않는다. `tests/unit/core/test_proposal_verification.py:12`

## 감사 값

`[실측]` 불일치는 필드, 이유, 기대값 digest, 실제값 digest를 가진다. digest는 값의 문자열 표현을 SHA-256으로 해시한 뒤 앞 16자를 사용하므로 원문 식별자나 금액을 직접 기록하지 않는다. `acop_basement/core/verification.py:26`, `acop_basement/core/verification.py:35`

## 관계

- [아키텍처 테스트 다섯 경계](architecture-tests.md)
- [도메인 독립성 게이트](domain-free.md)
- [다른 도메인 실행 증거](another-domain.md)

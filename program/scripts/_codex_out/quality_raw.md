===== FILE: architecture-tests.md =====
---
type: concept
title: 아키텍처 테스트가 지키는 다섯 경계
description: 아키텍처 테스트 5종이 각각 어떤 위반을 어떻게 탐지하는지 설명한다.
status: draft
tags: [testing, architecture]
---

## 결론

[실측] 다섯 테스트 파일은 도메인 독립성, 다른 도메인 수용성, export 선언의 완전성, 메시지 소비자의 멱등성 증거, UI 패키지의 격리를 각각 검사한다.

| 테스트 | 잡는 위반 | 검사 방식 |
|---|---|---|
| `test_basement_is_domain_free.py` | basement의 업무 도메인 결합 | [실측] Python 파일의 금지 어휘, 도메인 모듈 직접 import, 과도한 예외 목록을 검사한다. 반대로 도메인 구현 위치에 금지 어휘가 실제로 존재하는지도 확인한다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:57`, `tests/architecture/test_basement_is_domain_free.py:78`, `tests/architecture/test_basement_is_domain_free.py:94`, `tests/architecture/test_basement_is_domain_free.py:103`, `tests/architecture/test_basement_is_domain_free.py:108` |
| `test_engine_serves_another_domain.py` | 특정 도메인에 고정된 검증 엔진 | [실측] 쇼핑몰 정책과 사실을 범용 엔진에 주입하고 주문·배송·환불·반품 수량을 검증한다. 엔진 실행부에 다섯 도메인 어휘가 없는지도 문자열로 검사한다. `tests/architecture/test_engine_serves_another_domain.py:19`, `tests/architecture/test_engine_serves_another_domain.py:35`, `tests/architecture/test_engine_serves_another_domain.py:59`, `tests/architecture/test_engine_serves_another_domain.py:108` |
| `test_basement_manifest_covers_every_package.py` | 실제 패키지와 export 선언의 불일치 | [실측] `acop_basement` 바로 아래 디렉터리 집합과 `BASEMENT_COMPONENTS`를 양방향으로 비교한다. 실제로만 존재하면 누락, 선언에만 존재하면 stale 항목으로 실패한다. `tests/architecture/test_basement_manifest_covers_every_package.py:17`, `tests/architecture/test_basement_manifest_covers_every_package.py:20`, `tests/architecture/test_basement_manifest_covers_every_package.py:25`, `tests/architecture/test_basement_manifest_covers_every_package.py:32` |
| `test_consumer_idempotency_gate.py` | 멱등성 증거 없이 추가된 메시지 소비자 | [실측] 메시징 Python 파일에서 이름이 `Worker` 또는 `Consumer`로 끝나는 클래스를 찾고, 검증 완료 목록과 발견 목록의 차집합을 양방향으로 검사한다. `tests/architecture/test_consumer_idempotency_gate.py:12`, `tests/architecture/test_consumer_idempotency_gate.py:13`, `tests/architecture/test_consumer_idempotency_gate.py:19`, `tests/architecture/test_consumer_idempotency_gate.py:31` |
| `test_composer_ui_package_boundary.py` | UI 프로세스에 대상 런타임이나 검증 모델이 섞이는 결합 | [실측] 검사할 소스의 존재, 금지 import, Core 모델 이름의 재구현, 비어 있지 않은 의존성, 제품 배포판 포함을 각각 실패시킨다. `tests/architecture/test_composer_ui_package_boundary.py:19`, `tests/architecture/test_composer_ui_package_boundary.py:30`, `tests/architecture/test_composer_ui_package_boundary.py:36`, `tests/architecture/test_composer_ui_package_boundary.py:49`, `tests/architecture/test_composer_ui_package_boundary.py:61`, `tests/architecture/test_composer_ui_package_boundary.py:69` |

## 각 게이트의 판정 기준

[실측] 도메인 독립성 게이트의 허용 예외는 두 파일이며, 예외 수가 3개를 넘으면 실패한다. `tests/architecture/test_basement_is_domain_free.py:46`, `tests/architecture/test_basement_is_domain_free.py:103`

[실측] 다른 도메인 게이트는 10개 테스트 함수로 구성된다. 문서 작성 시 이 10개 함수를 직접 실행한 결과 모두 통과했다. 개별 판정은 기존 주문과 부분 환불의 허용, 없는 주문과 초과 환불의 거부처럼 성공과 실패 양쪽을 포함한다. `tests/architecture/test_engine_serves_another_domain.py:59`, `tests/architecture/test_engine_serves_another_domain.py:64`, `tests/architecture/test_engine_serves_another_domain.py:68`, `tests/architecture/test_engine_serves_another_domain.py:74`

[실측] manifest 게이트는 재귀적인 모든 하위 디렉터리가 아니라 `acop_basement`의 바로 아래 디렉터리를 비교하며 `__pycache__`는 제외한다. `tests/architecture/test_basement_manifest_covers_every_package.py:20`

[실측] 멱등성 증거 목록에 선언된 소비자는 `OutboxWorker` 하나다. 새 클래스뿐 아니라 코드에서 사라졌지만 목록에 남은 이름도 실패 원인이 된다. `tests/architecture/test_consumer_idempotency_gate.py:15`, `tests/architecture/test_consumer_idempotency_gate.py:31`

[실측] UI 금지 import는 `acop_basement`, `acop_composer.`, `app.`, `fastapi`, `pydantic`, `yaml`이다. 재구현 신호로 검사하는 모델 이름은 `ProjectConfig`, `TeamManifest`, `ContextPack`이다. `tests/architecture/test_composer_ui_package_boundary.py:22`, `tests/architecture/test_composer_ui_package_boundary.py:49`

## 검사 범위

[실측] 도메인 어휘와 import 검사는 AST 분석이 아니라 줄 단위 문자열 검사다. 목록에 없는 어휘나 동적으로 구성한 import까지 일반적으로 탐지한다고 단정할 수 없다. `tests/architecture/test_basement_is_domain_free.py:66`, `tests/architecture/test_composer_ui_package_boundary.py:36`

[실측] 소비자 탐지는 클래스 이름이 정규식의 `Worker` 또는 `Consumer` 접미사와 일치할 때만 이루어진다. 다른 이름 규칙의 소비자까지 탐지한다고 단정할 수 없다. `tests/architecture/test_consumer_idempotency_gate.py:13`, `tests/architecture/test_consumer_idempotency_gate.py:19`

[미확보] 다른 도메인 테스트를 제외한 네 테스트 파일의 현재 실행 결과는 이 문서의 확인 범위에 포함되지 않았다.

## 관계

- [도메인 독립성 게이트](./domain-free.md)
- [다른 도메인 실행 증거](./another-domain.md)
- [제안 대조 규칙](./verification.md)

===== FILE: domain-free.md =====
---
type: concept
title: Basement의 도메인 독립성 강제
description: basement가 업무 도메인을 모른다는 경계를 어떤 검사들이 강제하는지 설명한다.
status: draft
tags: [testing, architecture]
---

## 결론

[실측] “basement는 도메인을 모른다”는 선언만으로 유지되지 않는다. 금지 어휘 검색, 도메인 모듈 import 금지, 예외 수 제한, 도메인 위치에 대한 양성 대조군이 함께 경계를 강제한다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:78`, `tests/architecture/test_basement_is_domain_free.py:94`, `tests/architecture/test_basement_is_domain_free.py:103`, `tests/architecture/test_basement_is_domain_free.py:108`

## 금지 어휘

[실측] 검사 대상은 `acop_basement` 아래의 Python 파일이며 `__pycache__` 경로는 제외된다. `tests/architecture/test_basement_is_domain_free.py:27`, `tests/architecture/test_basement_is_domain_free.py:57`

[실측] 금지 어휘는 다음 열 가지다. 대소문자는 구분하지 않는다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:44`

- 구독·결제: `payment`, `subscription`, `entitlement`, `refund`, `invoice`
- 커머스: `order_id`, `line_item`, `shipment`, `sku`, `cart`

[실측] 해당 어휘가 실행 코드의 한 줄에서 발견되면 파일 경로, 줄 번호, 잘린 원문이 문제 목록에 들어가고 최종 assertion이 실패한다. `tests/architecture/test_basement_is_domain_free.py:66`, `tests/architecture/test_basement_is_domain_free.py:78`

[실측] 주석, 삼중 큰따옴표로 시작하는 줄, `★`로 시작하는 줄은 검색에서 제외한다. 설명 속 도메인 어휘를 결합으로 판정하지 않기 위한 줄 단위 예외다. `tests/architecture/test_basement_is_domain_free.py:68`

## 구조적 보강

[실측] `from app.modules`와 `import app.modules` 문자열이 basement 파일에 있으면 별도의 테스트가 실패한다. 조립 지점이 아니라 basement가 도메인 구현을 직접 호출하는 결합을 잡는다. `tests/architecture/test_basement_is_domain_free.py:108`

[실측] 도메인 구현 위치에도 같은 검색을 적용해 적어도 한 파일에서 도메인 어휘가 발견되어야 통과한다. 이 양성 대조군은 검사 대상이 비었거나 어휘 목록이 현실과 동떨어져 항상 통과하는 상태를 막는다. `tests/architecture/test_basement_is_domain_free.py:94`

[실측] 허용 예외는 PII 마스킹 규칙 파일과 원격 Agent 데모 파일 두 건이다. 허용 목록 자체도 최대 3건으로 제한된다. `tests/architecture/test_basement_is_domain_free.py:46`, `tests/architecture/test_basement_is_domain_free.py:103`

[실측] 검증 엔진에는 추가 검사가 있다. 실행부에 `payment_id`, `subscription_id`, `order_id`, `amount_cents`, `total_cents`가 있으면 다른 도메인 테스트가 실패한다. `tests/architecture/test_engine_serves_another_domain.py:108`

## 재발을 막는 결함

[실측] 코드 주석에 따르면 2026-08-16에 구독·결제 어휘가 Core에 박혔고, 그 결과 쇼핑몰의 `order_id`가 “확인 불가 → 거부” 대상이 되었다. 도메인 독립성 검사는 이 결함의 재발 방지 장치로 작성되었다. `tests/architecture/test_basement_is_domain_free.py:12`

## 보장 범위

[실측] 이 게이트가 직접 보장하는 것은 목록에 든 어휘와 두 형태의 `app.modules` import 문자열이 검사 대상 코드에 없다는 점이다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:108`

[미확보] 목록에 없는 새 도메인 어휘, 별칭이나 동적 import, 문자열로 우회한 결합까지 탐지한다는 근거는 확보되지 않았다.

## 관계

- [아키텍처 테스트 다섯 경계](./architecture-tests.md)
- [다른 도메인 실행 증거](./another-domain.md)
- [제안 대조 규칙](./verification.md)

===== FILE: another-domain.md =====
---
type: concept
title: 다른 도메인으로 검증한 범용 엔진
description: 같은 검증 엔진에 쇼핑몰 도메인을 연결하는 테스트가 무엇을 증명하는지 설명한다.
status: draft
tags: [testing, architecture, contract]
---

## 결론

[실측] **같은 `verify_proposal` 엔진은 구독·결제 필드에 의존하지 않고 쇼핑몰의 주문·배송·환불·반품 규칙을 실행한다.** 테스트는 쇼핑몰 정책을 외부에서 선언해 `acop_basement.core.verification`의 `Facts`, `QuantityRule`, `VerificationPolicy`, `verify_proposal`에 주입한다. `tests/architecture/test_engine_serves_another_domain.py:15`, `tests/architecture/test_engine_serves_another_domain.py:19`, `tests/architecture/test_engine_serves_another_domain.py:47`

[실측] 이 테스트의 import와 실행 경로에는 `final_project_cs`가 없다. 문서 작성 시 테스트 함수 10개를 직접 실행했으며 모두 통과했다. 따라서 허용된 확인 범위 안에서는 sample의 검증 엔진이 cs 없이 다른 도메인 규칙을 수행한다는 실행 증거가 성립한다. `tests/architecture/test_engine_serves_another_domain.py:11`, `tests/architecture/test_engine_serves_another_domain.py:15`, `tests/architecture/test_engine_serves_another_domain.py:59`

## 주입한 쇼핑몰 계약

[실측] 참조 규칙은 `order_id`를 `orders` 컬렉션에, `shipment_id`를 `shipments` 컬렉션에 연결한다. `tests/architecture/test_engine_serves_another_domain.py:19`

[실측] 환불액은 `order_id`가 가리키는 레코드의 `total_cents`와 비교하며 제안 값에 100을 곱한다. 반품 수량은 같은 주문의 `item_count`와 비교하며 배수는 1이다. `tests/architecture/test_engine_serves_another_domain.py:21`

[실측] `coupon_id`는 대조 수단이 없는 `opaque` 필드로 선언되고, `reason`과 `memo`는 대조 대상이 아닌 `ignored` 필드로 선언된다. `tests/architecture/test_engine_serves_another_domain.py:27`

[실측] 사실 집합에는 주문 `ord-1001`, 배송 `shp-77`, 주문 상한 `total_cents=5_000_000`, 수량 상한 `item_count=3`, 근거 `mev-1`이 들어간다. `tests/architecture/test_engine_serves_another_domain.py:31`, `tests/architecture/test_engine_serves_another_domain.py:35`

## 실행으로 확인하는 성질

[실측] 존재하는 `order_id`는 통과하고 존재하지 않는 주문은 거부된다. 엔진이 `order_id` 자체를 금지하는 것이 아니라 주입된 컬렉션의 사실과 대조한다는 증거다. `tests/architecture/test_engine_serves_another_domain.py:59`, `tests/architecture/test_engine_serves_another_domain.py:64`

[실측] 환불액 `70_000`은 배수 적용 후 주문 상한을 넘으므로 거부되고, `20_000`은 통과한다. 상한 검사가 쇼핑몰 정책의 필드 이름과 단위를 받아 작동한다. `tests/architecture/test_engine_serves_another_domain.py:68`, `tests/architecture/test_engine_serves_another_domain.py:74`

[실측] 반품 수량 5는 주문 수량 3을 넘으므로 거부되고, 수량 2는 통과한다. 동일 엔진의 수량 규칙이 금액에만 고정되지 않았다는 증거다. `tests/architecture/test_engine_serves_another_domain.py:78`, `tests/architecture/test_engine_serves_another_domain.py:84`

[실측] 현재 고객의 배송 `shp-77`은 통과하고 `shp-other`는 거부된다. `tests/architecture/test_engine_serves_another_domain.py:88`

[실측] 대조 수단이 없다고 선언한 `coupon_id`는 거부된다. 반대로 쇼핑몰 정책에 없는 `payment_id`는 “선언되지 않은 필드”로 거부된다. 다른 도메인의 어휘가 엔진에 내장되어 자동으로 통과하지 않음을 확인한다. `tests/architecture/test_engine_serves_another_domain.py:93`, `tests/architecture/test_engine_serves_another_domain.py:98`

## 하드코딩 반증

[실측] 두 도메인 사례가 모두 동작하는 것만으로는 엔진에 두 도메인을 함께 하드코딩했을 가능성이 남는다. 그래서 테스트는 엔진 실행부를 읽고 `payment_id`, `subscription_id`, `order_id`, `amount_cents`, `total_cents`가 없는지 별도로 검사한다. `tests/architecture/test_engine_serves_another_domain.py:108`

[실측] 이 검사는 주석과 일부 docstring 줄을 제외한 문자열 검사다. 지정된 다섯 어휘 이외의 모든 도메인 결합까지 부재한다고 증명하지는 않는다. `tests/architecture/test_engine_serves_another_domain.py:113`

## 2026-08-16 이전 결함

[실측] 코드 주석에 따르면 2026-08-16 이전에는 `order_id`가 basement의 “확인 불가 → 거부” 목록에 하드코딩되어 있었다. 그 결과 쇼핑몰의 핵심 식별자가 사실 조회를 받기도 전에 자동 거부되었다. `tests/architecture/test_engine_serves_another_domain.py:7`

[실측] 현재 테스트는 기존 주문의 `order_id`가 통과해야 한다는 회귀 조건을 직접 둔다. 과거와 같은 거부 목록이 다시 들어오면 이 조건이 깨진다. `tests/architecture/test_engine_serves_another_domain.py:58`

## 증명의 범위

[실측] 이 테스트가 실행으로 증명하는 대상은 범용 제안 검증 엔진과 주입형 정책 계약이다. `tests/architecture/test_engine_serves_another_domain.py:15`, `tests/architecture/test_engine_serves_another_domain.py:19`

[미확보] 이 테스트 하나만으로 sample의 모든 하위 시스템, 배포 절차, 외부 연동까지 다른 도메인에서 독립 실행된다고 단정할 근거는 없다.

## 관계

- [아키텍처 테스트 다섯 경계](./architecture-tests.md)
- [도메인 독립성 게이트](./domain-free.md)
- [제안 대조 규칙](./verification.md)

===== FILE: verification.md =====
---
type: concept
title: 제안을 사실과 대조하는 규칙
description: 제안의 필드를 무엇과 대조하며 대조할 수 없는 필드를 어떻게 처리하는지 설명한다.
status: draft
tags: [testing, contract, data]
---

## 결론

[실측] 제안은 도메인이 제공한 `VerificationPolicy`와 재조회한 `Facts`에 대조된다. 대조 수단이 없는 필드와 정책에 선언되지 않은 필드는 통과시키지 않는다. `acop_basement/core/verification.py:67`, `acop_basement/core/verification.py:87`, `acop_basement/core/verification.py:119`, `acop_basement/core/verification.py:144`, `acop_basement/core/verification.py:158`

[실측] 결과는 `Mismatch` 목록이며 빈 목록만 통과다. 불일치를 예외로 던지지 않고 모아 반환한다. `acop_basement/core/verification.py:35`, `acop_basement/core/verification.py:119`

## 대조 입력

[실측] `VerificationPolicy`는 네 종류의 선언을 받는다. `references`는 제안 키와 사실 컬렉션을 연결하고, `quantities`는 수량 상한 규칙을 담고, `opaque`는 대조 수단이 없는 키를 표시하며, `ignored`는 대조 대상이 아닌 키를 표시한다. `acop_basement/core/verification.py:67`

[실측] `Facts`는 이름별 레코드 컬렉션, 사용 가능한 근거 ID 집합, 사실 조회 성공 여부인 `loaded`를 가진다. 컬렉션 이름은 정책에서 공급된다. `acop_basement/core/verification.py:87`

[실측] 검증 함수는 제안 인자 `arguments`, 제안이 든 근거 ID `rationale_evidence_ids`, `facts`, `policy`를 입력으로 받는다. `acop_basement/core/verification.py:119`

## 필드별 판정

| 필드 분류 | 대조 대상과 처리 |
|---|---|
| 참조 필드 | [실측] 정책이 지정한 사실 컬렉션에서 `str(value)`를 키로 찾는다. 행이 없으면 해당 고객 소유의 사실이 없는 것으로 불일치를 만든다. `acop_basement/core/verification.py:150` |
| 수량 필드 | [실측] 연결된 참조 레코드의 `limit_key` 값과 비교한다. 제안 값에는 정책의 `scale`을 곱해 단위를 맞춘다. `acop_basement/core/verification.py:49`, `acop_basement/core/verification.py:175` |
| `opaque` 필드 | [실측] 대응 데이터가 없어 확인할 수 없다는 불일치를 만들고 거부한다. 확인 불가를 허용으로 바꾸지 않는다. `acop_basement/core/verification.py:144` |
| `ignored` 필드 | [실측] 대조 대상이 아니므로 건너뛴다. `acop_basement/core/verification.py:140` |
| 선언되지 않은 필드 | [실측] 검사 규칙 없이 실행되지 않도록 불일치를 만든다. `acop_basement/core/verification.py:158` |
| 값이 `None`인 필드 | [실측] 현재 구현은 필드 분류와 관계없이 첫 순회에서 건너뛴다. `acop_basement/core/verification.py:140` |

## 수량 판정

[실측] 수량 값이 있지만 참조 대상 값이 없으면 무엇에 대한 수량인지 확인할 수 없으므로 거부한다. `acop_basement/core/verification.py:175`, `acop_basement/core/verification.py:186`

[실측] 제안 값과 상한은 `Decimal`로 변환한다. 변환할 수 없거나 `NaN`, `Infinity`, `-Infinity`처럼 유한하지 않은 값은 숫자가 아닌 것으로 거부한다. `acop_basement/core/verification.py:106`, `acop_basement/core/verification.py:198`

[실측] 참조 레코드에 상한 필드가 없거나 상한이 숫자가 아니면 상한을 모르는 것으로 거부한다. `acop_basement/core/verification.py:204`

[실측] 배수를 적용한 값이 상한보다 크거나 0 이하이면 거부한다. 상한과 같거나 0보다 크고 상한보다 작은 값은 이 규칙을 통과한다. `acop_basement/core/verification.py:210`

[실측] 참조 레코드가 없으면 수량 검사에서는 같은 문제를 다시 추가하지 않는다. 참조 필드 검사가 이미 만든 불일치를 유지한다. `acop_basement/core/verification.py:193`

## 근거와 조회 실패

[실측] 제안이 인용한 근거 ID가 `Facts.evidence_ids`에 없으면 `evidence_ids` 불일치를 만든다. `acop_basement/core/verification.py:167`

[실측] 사실 조회 자체가 실패해 `loaded=False`이면 다른 필드를 검사하지 않고 `__facts__` 불일치 한 건을 즉시 반환한다. “조회했지만 없음”과 “조회 실패”를 구분하는 처리다. `acop_basement/core/verification.py:94`, `acop_basement/core/verification.py:133`

## 단위 테스트가 확인하는 결과

[실측] 실제 상한이 `3_000_000` cents인 사실에 `50_000`원의 제안을 넣으면 거부되고, 원문 금액은 불일치의 digest 문자열에 남지 않는다. `tests/unit/core/test_proposal_verification.py:24`, `tests/unit/core/test_proposal_verification.py:46`

[실측] 존재하지 않는 결제 식별자, 다른 고객 범위의 구독 식별자, 대조할 수 없는 식별자, 대상 없는 금액, ContextPack에 없는 근거, 0 이하 값과 비유한 수는 모두 거부 조건으로 검사된다. `tests/unit/core/test_proposal_verification.py:59`, `tests/unit/core/test_proposal_verification.py:66`, `tests/unit/core/test_proposal_verification.py:74`, `tests/unit/core/test_proposal_verification.py:82`, `tests/unit/core/test_proposal_verification.py:89`, `tests/unit/core/test_proposal_verification.py:104`, `tests/unit/core/test_proposal_verification.py:111`

[실측] 여러 필드와 근거가 동시에 틀리면 첫 문제에서 멈추지 않고 네 종류의 불일치를 함께 반환하는 조건이 있다. `tests/unit/core/test_proposal_verification.py:122`

[실측] 정상 상한과 같은 제안, 부분 수량 제안, 정책의 단위에 맞는 값도 통과 조건으로 검사된다. 과잉 차단 역시 결함으로 취급한다. `tests/unit/core/test_proposal_verification.py:132`, `tests/unit/core/test_proposal_verification.py:139`, `tests/unit/core/test_proposal_verification.py:145`

[미확보] 단위 테스트가 주입하는 `CUSTOMER_OPS_POLICY`의 전체 필드 선언은 지정된 확인 파일에 포함되지 않아 이 문서에서 열거하지 않는다. `tests/unit/core/test_proposal_verification.py:12`

## 감사 값

[실측] 불일치는 필드, 이유, 기대값 digest, 실제값 digest를 가진다. digest는 값의 문자열 표현을 SHA-256으로 해시한 뒤 앞 16자를 사용하므로 원문 식별자나 금액을 직접 기록하지 않는다. `acop_basement/core/verification.py:26`, `acop_basement/core/verification.py:35`

## 관계

- [아키텍처 테스트 다섯 경계](./architecture-tests.md)
- [도메인 독립성 게이트](./domain-free.md)
- [다른 도메인 실행 증거](./another-domain.md)
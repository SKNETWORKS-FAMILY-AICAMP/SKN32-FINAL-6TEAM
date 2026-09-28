---
type: concept
title: 아키텍처 테스트가 지키는 일곱 경계
description: 아키텍처 테스트 7종이 각각 어떤 위반을 어떻게 탐지하는지 설명한다.
status: draft
tags: [testing, architecture]
domain: neutral
domain_note: 아키텍처 가드 목록이다. 커머스 낱말은 금지 목록으로 나온다
---

## 결론

`[정정 2026-09-10]` **테스트 파일은 일곱이다** — 이 문서는 다섯을 싣고 `test_composer_package_boundary.py`·`test_records_live_in_wiki.py` 를 빠뜨렸다(표 끝에 더했다). `[실측]` 처음 다섯 테스트 파일은 도메인 독립성, 다른 도메인 수용성, export 선언의 완전성, 메시지 소비자의 멱등성 증거, UI 패키지의 격리를 각각 검사한다.

| 테스트 | 잡는 위반 | 검사 방식 |
|---|---|---|
| `test_basement_is_domain_free.py` | basement의 업무 도메인 결합 | `[실측]` Python 파일의 금지 어휘, 도메인 모듈 직접 import, 과도한 예외 목록을 검사한다. 반대로 도메인 구현 위치에 금지 어휘가 실제로 존재하는지도 확인한다. `tests/architecture/test_basement_is_domain_free.py:37`, `tests/architecture/test_basement_is_domain_free.py:57`, `tests/architecture/test_basement_is_domain_free.py:78`, `tests/architecture/test_basement_is_domain_free.py:94`, `tests/architecture/test_basement_is_domain_free.py:103`, `tests/architecture/test_basement_is_domain_free.py:108` |
| `test_engine_serves_another_domain.py` | 특정 도메인에 고정된 검증 엔진 | `[실측]` 쇼핑몰 정책과 사실을 범용 엔진에 주입하고 주문·배송·환불·반품 수량을 검증한다. 엔진 실행부에 다섯 도메인 어휘가 없는지도 문자열로 검사한다. `tests/architecture/test_engine_serves_another_domain.py:19`, `tests/architecture/test_engine_serves_another_domain.py:35`, `tests/architecture/test_engine_serves_another_domain.py:59`, `tests/architecture/test_engine_serves_another_domain.py:108` |
| `test_basement_manifest_covers_every_package.py` | 실제 패키지와 export 선언의 불일치 | `[실측]` `acop_basement` 바로 아래 디렉터리 집합과 `BASEMENT_COMPONENTS`를 양방향으로 비교한다. 실제로만 존재하면 누락, 선언에만 존재하면 stale 항목으로 실패한다. `tests/architecture/test_basement_manifest_covers_every_package.py:17`, `tests/architecture/test_basement_manifest_covers_every_package.py:20`, `tests/architecture/test_basement_manifest_covers_every_package.py:25`, `tests/architecture/test_basement_manifest_covers_every_package.py:32` |
| `test_consumer_idempotency_gate.py` | 멱등성 증거 없이 추가된 메시지 소비자 | `[실측]` 메시징 Python 파일에서 이름이 `Worker` 또는 `Consumer`로 끝나는 클래스를 찾고, 검증 완료 목록과 발견 목록의 차집합을 양방향으로 검사한다. `tests/architecture/test_consumer_idempotency_gate.py:12`, `tests/architecture/test_consumer_idempotency_gate.py:13`, `tests/architecture/test_consumer_idempotency_gate.py:19`, `tests/architecture/test_consumer_idempotency_gate.py:31` |
| `test_composer_ui_package_boundary.py` | UI 프로세스에 대상 런타임이나 검증 모델이 섞이는 결합 | `[실측]` 검사할 소스의 존재, 금지 import, Core 모델 이름의 재구현, 비어 있지 않은 의존성, 제품 배포판 포함을 각각 실패시킨다. `tests/architecture/test_composer_ui_package_boundary.py:19`, `tests/architecture/test_composer_ui_package_boundary.py:30`, `tests/architecture/test_composer_ui_package_boundary.py:36`, `tests/architecture/test_composer_ui_package_boundary.py:49`, `tests/architecture/test_composer_ui_package_boundary.py:61`, `tests/architecture/test_composer_ui_package_boundary.py:69` |
| `test_composer_package_boundary.py` | 선택 패키지가 제품 코드를 끌어오는 것 | `[실측]` 다섯 검사 — 패키지 소스가 있다 · 어느 제품도 import 하지 않는다 · **코어가 그 패키지를 import 하지 않는다**(Composer 없이도 뜬다) · 제품 쪽에서 패키지를 아는 곳은 조립부 하나 · 모듈마다 단독 import 된다 |
| `test_records_live_in_wiki.py` | 작업 기록이 제자리 밖에 생기는 것 | `[실측]` 두 검사 — **`docs/` 가 다시 생기지 않는다** · 기록이 규칙대로 `wiki/records/` 에 있다(2026-09-08 통합 게이트) |

## 각 게이트의 판정 기준

`[실측]` 도메인 독립성 게이트의 허용 예외는 두 파일이며, 예외 수가 3개를 넘으면 실패한다. `tests/architecture/test_basement_is_domain_free.py:46`, `tests/architecture/test_basement_is_domain_free.py:103`

`[실측]` 다른 도메인 게이트는 10개 테스트 함수로 구성된다. 문서 작성 시 이 10개 함수를 직접 실행한 결과 모두 통과했다. 개별 판정은 기존 주문과 부분 환불의 허용, 없는 주문과 초과 환불의 거부처럼 성공과 실패 양쪽을 포함한다. `tests/architecture/test_engine_serves_another_domain.py:59`, `tests/architecture/test_engine_serves_another_domain.py:64`, `tests/architecture/test_engine_serves_another_domain.py:68`, `tests/architecture/test_engine_serves_another_domain.py:74`

`[실측]` manifest 게이트는 재귀적인 모든 하위 디렉터리가 아니라 `acop_basement`의 바로 아래 디렉터리를 비교하며 `__pycache__`는 제외한다. `tests/architecture/test_basement_manifest_covers_every_package.py:20`

`[실측]` 멱등성 증거 목록에 선언된 소비자는 `OutboxWorker` 하나다. 새 클래스뿐 아니라 코드에서 사라졌지만 목록에 남은 이름도 실패 원인이 된다. `tests/architecture/test_consumer_idempotency_gate.py:15`, `tests/architecture/test_consumer_idempotency_gate.py:31`

`[실측]` UI 금지 import는 `acop_basement`, `acop_composer.`, `app.`, `fastapi`, `pydantic`, `yaml`이다. 재구현 신호로 검사하는 모델 이름은 `ProjectConfig`, `TeamManifest`, `ContextPack`이다. `tests/architecture/test_composer_ui_package_boundary.py:22`, `tests/architecture/test_composer_ui_package_boundary.py:49`

## 검사 범위

`[실측]` 도메인 어휘와 import 검사는 AST 분석이 아니라 줄 단위 문자열 검사다. 목록에 없는 어휘나 동적으로 구성한 import까지 일반적으로 탐지한다고 단정할 수 없다. `tests/architecture/test_basement_is_domain_free.py:66`, `tests/architecture/test_composer_ui_package_boundary.py:36`

`[실측]` 소비자 탐지는 클래스 이름이 정규식의 `Worker` 또는 `Consumer` 접미사와 일치할 때만 이루어진다. 다른 이름 규칙의 소비자까지 탐지한다고 단정할 수 없다. `tests/architecture/test_consumer_idempotency_gate.py:13`, `tests/architecture/test_consumer_idempotency_gate.py:19`

`[미확보]` 다른 도메인 테스트를 제외한 네 테스트 파일의 현재 실행 결과는 이 문서의 확인 범위에 포함되지 않았다.

## 관계

- [도메인 독립성 게이트](domain-free.md)
- [다른 도메인 실행 증거](another-domain.md)
- [제안 대조 규칙](verification.md)

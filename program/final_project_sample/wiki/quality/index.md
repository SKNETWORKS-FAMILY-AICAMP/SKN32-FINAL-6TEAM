---
type: guide
title: 무엇이 이 구조를 강제하나
description: sample이 혼자 설 수 있다는 주장을 테스트가 증명한다. 특히 다른 도메인을 물리는 테스트
status: draft
tags: [testing, architecture]
---

# 품질 — 무엇이 이 구조를 강제하나

**"basement는 도메인을 모른다"는 선언이 아니라 테스트다.** 그게 sample이 cs 없이 성립하는 근거다.

## ★ 가장 중요한 테스트

`[실측]` `tests/architecture/test_engine_serves_another_domain.py`

> 이 저장소의 목표는 "어떤 CS 플랫폼 요청이 와도 대응 가능한 범용 basement" 다.
> 그 주장은 **선언만으로는 증명되지 않는다.**

이 테스트는 **쇼핑몰 도메인 선언을 새로 만들어** `core/verification.py`를 **한 줄도 고치지 않고** 돌린다.

```python
MALL_POLICY = VerificationPolicy(
    references={"order_id": "orders", "shipment_id": "shipments"},
    quantities=(QuantityRule(field="refund_amount", reference="order_id",
                             limit_key="total_cents", scale=Decimal(100)), …),
    opaque=frozenset({"coupon_id"}),      # 아직 대조 수단이 없다
    ignored=frozenset({"reason", "memo"}),
)
```

**깨지면 basement가 특정 도메인에 묶였다는 뜻이다.**

### 실제로 한 번 묶여 있었다

`[실측]` 2026-08-16 이전 버전은 `order_id`를 basement의 **"확인 불가 → 거부"** 목록에 박아 뒀다.

**쇼핑몰의 가장 중요한 식별자가 자동으로 거부됐다.**

**이 테스트가 없었으면 안 드러났을 종류다.** 선언은 그대로였고 코드만 어긋나 있었다.

## 아키텍처 테스트 5종

`[실측]` `tests/architecture/`

| 테스트 | 무엇을 막나 |
|---|---|
| `test_basement_is_domain_free.py` | basement에 도메인 어휘가 새는 것 |
| **`test_engine_serves_another_domain.py`** | **엔진이 한 도메인에만 도는 것** |
| `test_basement_manifest_covers_every_package.py` | 배포 매니페스트 누락 |
| `test_composer_ui_package_boundary.py` | UI가 basement를 직접 만지는 것 |
| `test_consumer_idempotency_gate.py` | 중복 소비 |

## 도메인 어휘 차단 목록

```python
DOMAIN_WORDS = (
    "payment", "subscription", "entitlement", "refund", "invoice",
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

**cs와 sample이 같은 목록을 지킨다.** → [`../../../final_project_cs/wiki/quality/invariants.md](../../../final_project_cs/wiki/quality/invariants.md)

## 계약 테스트

| 폴더 | 무엇 |
|---|---|
| `tests/contract/` | 상태표·Team 계약·Core 격리·모듈 토글 |
| `tests/contracts/` | 콘솔 읽기·introspection |

`[미확보]` **두 폴더 이름이 `contract`와 `contracts`로 갈려 있다.** 왜 나뉘었는지 확인하지 않았다.

## 문서

| 문서 | 답하는 질문 |
|---|---|
| [architecture-tests.md](architecture-tests.md) | 아키텍처 테스트 5종이 각각 무엇을 잡나 |
| [domain-free.md](domain-free.md) | "basement 는 도메인을 모른다"를 무엇이 강제하나 |
| **[another-domain.md](another-domain.md)** | **같은 엔진에 다른 도메인을 물리면 도나** |
| [verification.md](verification.md) | 제안을 무엇과 대조하나 |
| [evidence.md](evidence.md) | **DoD 30건이 어디서 무엇을 증명하나.** cs 와 판정이 갈리는 항목이 있다 |
| **[domain-swap.md](domain-swap.md)** | **도메인을 갈아 끼우는 절차.** sample 이 혼자 서는 실무 방법 |
| [invariants.md](invariants.md) | **깨면 안 되는 것 12개.** 테스트 68개가 받친다 |

`[실측]` **`another-domain.md` 가 이 저장소에서 가장 중요한 문서다.** sample 이 cs 없이 성립한다는 주장의 유일한 실행 증거다.

```
python -m pytest tests/architecture/test_engine_serves_another_domain.py -q
10 passed in 0.04s          # 2026-09-02 확인
```

### 아직 안 쓴 것

| 문서 | 답할 질문 |
|---|---|
| — | 없다 |

## 관계

- [../index.md](../index.md) — 지식 지도
- [`../../../wiki/architecture/core-vs-team.md](../../../wiki/architecture/core-vs-team.md) — 강제하는 계약

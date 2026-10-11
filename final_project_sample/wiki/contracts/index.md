---
type: guide
title: 선검증 계약
description: sample에서 먼저 검증하고 cs로 이식하는 계약. validated/ 는 검증이 끝난 것
status: draft
domain: neutral
domain_note: 두 저장소의 금지 어휘 목록을 비교하는 규칙 문서다. 여행 낱말은 cs 가 더한 목록을 보이려고 나온다
---

# 선검증 계약

**여기 있는 것만 `final_project_cs`로 이식한다.**

sample의 나머지 구현은 참고이고 이식 대상이 아니다.

## 왜 sample에서 먼저 하나

계약을 릴리스 대상에서 바로 바꾸면 되돌리기 비싸다. **sample에서 형태를 확정한 뒤 옮긴다.**

| 단계 | 어디서 |
|---|---|
| 계약 설계·시행착오 | `final_project_sample` |
| 검증 완료 | `contracts/validated/` |
| 이식 | `final_project_cs` |

## 무엇을 이식했나

`[실측]`

| 대상 | 상태 |
|---|---|
| Composer 쓰기채널 | 이식 |
| Core/Team 계약 | 이식 |
| 예시 Team (Billing / Technical) | **이식 안 함** |

## ★ 이식 안 하는 것

**예시 Team 2종은 아키텍처 증거로만 남긴다.**

Core 격리 위반 0을 보여주는 자료이지, cs의 착수 목록에 없다.

**sample의 검증 상태를 cs의 릴리스 완료로 간주하지 않는다.** 이걸 혼동하면 "다 됐다"고 착각한다.

## `validated/`의 조건

여기 들어가려면 셋이 필요하다.

| 조건 | 왜 |
|---|---|
| 계약 형태가 확정됐다 | 바뀌면 cs를 또 고쳐야 한다 |
| 테스트가 있다 | 형태만 맞고 동작이 다르면 소용없다 |
| cs 이식 계획이 있다 | 언제 누가 옮기는지 |

`[미확보]` 현재 `validated/` 는 비어 있다. 이관 대상 선별이 필요하다.

## 같은 규칙을 지킨다

sample에도 cs와 같은 아키텍처 테스트가 있다. ★`[실측 2026-09-10]` **다만 금지 목록은 이제 같지 않다** — sample 은 구독·결제 5 + 커머스 5 = **10개**, cs 는 여기에 여행 5개(`booking`·`itinerary`·`lodging`·`supplier_booking`·`traveller`)를 더해 **15개**다. 아래는 sample 목록이다. **규칙(코어에 도메인 어휘가 없다)은 같고, 금지 목록은 도메인마다 누적된다.**

```python
DOMAIN_WORDS = (
    "payment", "subscription", "entitlement", "refund", "invoice",
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

`tests/architecture/test_basement_is_domain_free.py`

**두 저장소가 같은 규칙을 지키는 게 이식 가능성의 근거다.** 규칙이 다르면 옮길 때 깨진다.

## 관계

- [../index.md](../index.md) — sample의 위치
- [`../../../final_project_cs/wiki/teams/team-contract/index.md](../../../final_project_cs/wiki/teams/team-contract/index.md) — 이식된 계약
- [`../../../wiki/architecture/repository-map.md](../../../wiki/architecture/repository-map.md) — 저장소 관계
- [`../../../wiki/governance/migration.md](../../../wiki/governance/migration.md) — 이관 범위 (sample 430건 중 25건 추정)

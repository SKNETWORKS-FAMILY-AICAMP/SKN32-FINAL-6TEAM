---
type: guide
title: final_project_sample 지식 지도
description: Core/Team 계약의 참조 구현. cs가 릴리스로 나간 뒤에도 혼자 정확히 돌아야 한다
status: draft
---

# final_project_sample 지식 지도

## ★ [2026-09-01] 이 문서의 전제를 고쳤다

**전에는 이렇게 적혀 있었다.**

> 참고 구현체다. 릴리스 대상이 아니다.
> cs로 이식 확정된 것**만** 여기 문서로 남긴다.
> **안 둔다 — sample 내부 구현 설명**

**틀렸다.**

> **cs가 릴리스로 나가더라도 sample은 혼자 정확히 굴러가야 한다.**

sample은 cs에 부품을 대주고 버려지는 발판이 아니다. **Core/Team 계약의 참조 구현이고, cs가 떠난 뒤에도 그 자리에 남는다.**

그래서 **내부 구현 설명을 여기 둔다.** 그게 없으면 cs가 나가는 순간 이 저장소를 읽을 방법이 사라진다.

### 이 전제가 어긋나 있었다는 증거

`[실측]` hub(`program/wiki`)가 구현을 가리키는 횟수를 세어 봤다.

| 대상 | 참조 |
|---|---|
| `final_project_cs` | **94회 · 39개 문서** |
| `final_project_sample` | **6회** |

**hub의 Core 계약 문서 8개가 전부 cs wiki로만 내려간다.** cs가 나가면 계약을 읽으러 온 사람이 전부 남의 저장소로 떨어진다.

`check_wiki.py`가 이제 이걸 위반으로 잡는다 — **"hub 가 한 구현만 가리킨다"**.

## 무엇인가

`[실측]` 2026-09-01 측정.

```
py 337개 · 테스트 62개 파일
acop_basement/   Core. 도메인을 모른다
acop_composer/   쓰기채널. 설정을 바꾸는 유일한 경로
packages/acop_composer_ui/
```

**두 패키지로 나뉜 게 핵심이다.** basement가 실행 기반이고 composer가 그 설정을 바꾸는 통제된 입구다.

## 여전히 유효한 경고

> **sample의 예시 Team과 검증 상태를 cs의 릴리스 완료로 간주하지 않는다.**

sample에 Billing/Technical Team이 있고 Core 격리 위반이 0이다. 그건 **Team-플러그인 구조가 동작한다는 증거**일 뿐 cs의 10주 착수 목록이 아니다.

**이건 "sample이 덜 중요하다"는 뜻이 아니다.** 두 저장소가 다른 것을 증명한다는 뜻이다.

| | 무엇을 증명하나 |
|---|---|
| **sample** | **계약이 성립한다** |
| **cs** | **그 계약 위에서 도메인이 돈다** |

## 영역

| 영역 | 답하는 질문 |
|---|---|
| [contracts/](contracts/index.md) | cs로 이식할 계약은 무엇인가 |
| [runtime/](runtime/index.md) | Case가 어떻게 흘러가나 |
| [teams/](teams/index.md) | Team을 어떻게 끼우나 |
| [composer/](composer/index.md) | 설정을 누가 어떻게 바꾸나 |
| [quality/](quality/index.md) | 무엇이 이 구조를 강제하나 |
| [operations/](operations/index.md) | 어떻게 띄우나 |

`[미확보]` **잎 문서는 아직 안 썼다.** 위 영역 index만 있다. 무엇을 써야 하는지는 각 index에 적혀 있다.

## 여기도 지키는 불변식

sample에도 같은 아키텍처 테스트가 있다.

```python
DOMAIN_WORDS = (
    "payment", "subscription", "entitlement", "refund", "invoice",
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

`tests/architecture/test_basement_is_domain_free.py`

**cs와 sample이 같은 규칙을 지키는 게 이식 가능성의 근거다.** 그리고 **sample이 혼자 설 수 있는 근거이기도 하다** — basement는 도메인을 모르므로 cs가 없어도 성립한다.

## 관계

- [../../wiki/architecture/core-vs-team.md](../../wiki/architecture/core-vs-team.md) — 이 저장소가 구현하는 계약
- [../../wiki/architecture/repository-map.md](../../wiki/architecture/repository-map.md) — 저장소 관계
- [../../final_project_cs/wiki/index.md](../../final_project_cs/wiki/index.md) — 이식 대상

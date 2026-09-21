---
type: decision
title: Composer 범위 — 세 층으로 나눈다
description: 설정만으로 되는 것·재시작이 필요한 것·코드 배포가 필요한 것. 토글 전용 계약으로 전체를 대체하지 않는다
status: draft
tags: [architecture, contract, ui]
owners: [human:미배정]
domain: neutral
---

# D-CS-003 Composer 범위 — 세 층

`[실측]` `A-COP_Composer_범위재검토.md`(217줄)에서 결정 부분만 분리.

## 맥락

Composer v3가 **토글 전용**으로 설계됐다. 그걸 전체 Composer의 대체 계약으로 쓸 수 있는가.

## 결정

> **토글 전용 v3를 전체 Composer의 대체 계약으로 쓰면 안 된다.**
>
> **가능한 범위를 세 층으로 나누고, 각 층이 요구하는 것을 다르게 본다.**

## ★ 세 층

| 층 | 무엇을 바꿀 수 있나 | 대상이 하는 것 | 현재 상태 |
|---|---|---|---|
| **설정만** | 이미 설치된 구현의 인스턴스 선언 · 선언형 Team 생성 · 활성 상태 변경 · 허용된 Port 선택 | 카탈로그 조회 · 스키마 검증 · 의존성 검사 · **원자적 저장** · 감사 | **토글과 전체 YAML 저장 일부만.** 인스턴스 설정·선언형 Team 없음 |
| **재시작 필요** | 새 Registry 구성 · Team 추가·제거의 **실제 반영** · 모듈 조립 변경 · GraphStore adapter 교체 | staged 저장 → drain → 재시작 → health check → **실패 시 rollback** | YAML 저장만 가능. **재시작·health check·rollback 계약 없음** |
| **코드 배포 필요** | 새 Python Team 종류 · 새 adapter · 새 Core 계약 | 서명·호환성·테스트 확인 → 격리 설치 → 카탈로그 등록 → 재시작 → 검증 → rollback | **고정 소스와 import 경로만.** 배포 관리 기능 없음 |

**"설정만으로 된다"는 말의 전제**는 플랫폼에 **범용 런타임과 구현체가 미리 배포돼 있다**는 것이다.

선언형 Team도 **범용 실행기가 한 번 배포된 뒤부터** 설정만으로 추가할 수 있다.

## 왜 토글로는 부족한가

`[실측]` 요구사항이 **"등록 카탈로그에서 구현 종류를 고르고 UI에서 인스턴스 이름을 붙인다"**인데, 토글은 **이미 있는 것을 켜고 끄는 것**만 한다.

**없는 것을 만드는 경로가 없다.** `[2026-09-10]` **이 판단은 토글만 있던 때의 것이다** — sample Composer API 에는 지금 `GET /catalog`(구현 카탈로그 조회)과 `POST /changes`(인스턴스 선언 변경)가 있다(`final_project_sample/acop_composer/api.py:339,354`, 라우트 여덟 중 둘). 아래 「계약 제안」이 그렇게 구현됐다. cs 에 이식됐는지는 이 수정에서 확인하지 않았다.

## 계약 제안

### `GET /composer/catalog` 신설

UI가 고를 수 있는 것을 대상이 알려준다.

```
module type · Team implementation · declarative Team type · Port implementation
```

각 항목에 담을 것.

```
implementation_id (안정된 ID) · 버전 · 입력 JSON Schema
필요한 모듈과 Port · 충돌 가능한 capability
재시작 필요 여부 · 허용 tool 목록 · 배포 digest
```

**★ Python 경로는 UI 계약에 노출하지 않는다.** `implementation_id`로 가린다.

### `GET /composer/current` — 두 revision 을 구분한다

| 필드 | 뜻 |
|---|---|
| `desired_revision` | **저장된 선언**의 revision |
| `effective_revision` | **Controller가 실제 사용하는** revision |
| `activation_state` | `effective` · `pending_restart` · `failed` · `rolling_back` |

**둘을 구분하는 게 핵심이다.** 저장했다고 적용된 게 아니다. 재시작 층의 존재가 이 구분을 강제한다.

각 인스턴스도 **desired 상태와 effective 상태를 따로** 갖는다.

## UI가 하지 않는 것

> **UI는 raw 응답을 그린다. UI가 Core Pydantic 모델을 복제하지 않는다.**
>
> **입력 폼은 대상이 준 JSON Schema에서 만든다.**

**UI가 모델을 복제하면 계약이 두 곳에 생긴다.** 하나가 바뀌면 조용히 어긋난다.

## 못 하게 되는 것

- 토글 하나로 모든 구성 변경을 처리할 수 없다
- 재시작 층을 쓰려면 health check·rollback 계약을 먼저 만들어야 한다
- 코드 배포 층은 MVP 범위 밖이다

## 관계

- [D-CS-001](D-CS-001-composer-ui-removal.md) — `/ui/composer` 폐기
- [../external/rest-api.md](../external/rest-api.md) — `/composer/*` API
- [../../../wiki/architecture/pack-model.md](../../../wiki/architecture/pack-model.md) — Registry 등록형

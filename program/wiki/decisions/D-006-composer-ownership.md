---
type: decision
title: Composer 는 sample 이 만들고 UI 가 가져다 쓴다
description: 문장 두 개가 잘못 읽혀 세션마다 "UI에서 새로 만들자"는 오답이 반복됐다
status: draft
tags: [architecture, ui, contract]
owners: [human:미배정]
---

# D-006 Composer 소유권

`[실측]` `A-COP_Composer_소유권_정정.md`(2026-08-24)에서 이관.

**여러 저장소가 당사자라 중앙 허브에 둔다.**

## 맥락 — 같은 오답이 반복됐다

`[실측]` 기존 v3 설계 문서의 **문장 두 개**가 잘못 읽혔다.

> §3 표 — `final_project_sample` — 이번 v3 UI 이관 설계의 **구현 대상이 아님**
>
> §8.1 — `final_project_ui` — pip 패키지가 아니다. **아무것도 pip install하지 않아도 동작해야 하며**

**이 둘이 "UI가 Composer를 자체 구현해야 한다"로 읽힌다.**

그래서 **세션마다 "UI에서 새로 만들자"는 결론이 나왔다.**

## 결정

> **Composer 관련 기능은 `final_project_sample`에서 만든다.**
> **`final_project_ui`는 그것을 가져다 쓴다.**
>
> **UI가 Composer 로직을 처음부터 다시 만들지 않는다.**

## 무엇을 혼동했나

**import 금지 대상이 `final_project_cs`이지 sample 전체가 아니다.**

| | 규칙 |
|---|---|
| `final_project_cs` | **import 금지.** 릴리스 대상이라 결합하면 안 된다 |
| **sample 의 공용 패키지** | **허용.** 그러라고 만든 것이다 |

**"sample 은 구현 대상이 아니다"는 말은 "v3 UI 이관 작업의 대상이 아니다"였지 "sample 이 아무것도 안 만든다"가 아니었다.**

## 정정된 구조

```
acop_basement    공통 런타임
acop_composer    Composer 로직        ← sample 이 만든다
final_project_ui 이 패키지를 가져다 쓴다

cs ↔ UI 는 HTTP 로만 (인증된 /composer/* API)
```

## 무엇이 바뀌고 무엇이 그대로인가

| | |
|---|---|
| **바뀐 것** | **구현 소유권만** — 누가 만드는가 |
| 그대로 | cs import 금지 · 대상 내부 쓰기 금지 · 인증 · 감사 |

## 왜 이 방향이 맞나

**이중 구현과 계약 drift 를 막는다.**

UI 가 자체 구현하면 같은 로직이 두 곳에 생기고, 한쪽이 바뀔 때 조용히 어긋난다.

## 이 결정이 남긴 교훈

**문서 두 문장이 세션마다 같은 오답을 만들었다.**

| 원인 | 대책 |
|---|---|
| "구현 대상이 아님"이 범위 한정인지 소유권 부정인지 모호 | **범위를 명시한다** — "이번 작업의" |
| "pip install 안 해도 동작"이 의존 금지로 읽힘 | **무엇에 대한 독립인지 밝힌다** |

**애매한 문장 하나가 반복 비용을 만든다.** 이게 [문서 표준](../governance/document-standard.md)이 "경계를 명시하라"고 하는 이유다.

## 후속 조치

| # | 무엇 | 상태 |
|---|---|---|
| 1 | v3 문서의 두 문장 정정 | `[미확보]` |
| 2 | UI 규칙 정정 | `[미확보]` |
| 3 | 패키지 이름·경계 확정 | `[미확보]` → [../delivery/open-items.md](../delivery/open-items.md) |

## ★ [2026-09-06] Composer가 어디에 사는가 — 배포 형태 둘로 정리 (사용자)

| 배포 형태 | Composer 위치 | cs 와의 관계 | 릴리즈 때 |
|---|---|---|---|
| **중앙 저장 방식** | **UI 프로젝트**(설정 서비스)로 빠진다 → [D-007](D-007-central-config-store.md) | cs 는 자기 선언을 **읽기만** 한다 | cs 에 Composer 코드가 애초에 없다 |
| **pip 방식** | `acop_composer` 패키지 | **관리용 빌드의 cs 가 pip 로 설치해 라우터를 주입**하고, UI 는 그 cs 의 `/composer/*` 를 바라본다 | **패키지를 빼서 cs 에서 제거된다** |

두 형태 모두에서 성립하는 규칙 하나 — **cs 소스 안에 Composer 구현이 있으면 안 된다.** 위 "import 금지"는 이 뜻이다. 패키지가 밖에서 붙는 것(관리용 빌드)은 결합이 아니고, 소스에 복사해 넣는 것이 결합이다.

`[실측]` 지금 cs 는 후자다 — `app/application/composer_service.py`(167줄)·`app/presentation/api/composer.py`(157줄)·`composer_auth.py`(76줄)가 옛 v2 를 복사한 자체 구현이고, `app/presentation/api/app.py:8-27` 이 무조건 include 한다. 릴리즈 빌드에서 빠질 방법이 없다. **pip 방식으로 가면 이 셋을 지우고 패키지 주입으로 바꿔야 한다** — D-011 의 scope 분리·이력·복원도 그때 패키지째 따라온다. cs 작업자 몫 → [open-items](../delivery/open-items.md).

## 관계

- [`sample/wiki/composer/`](../../final_project_sample/wiki/composer/index.md) — **원본 구현.** Composer 는 여기서 만들어 cs 로 간다
- [`D-CS-001`](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) — `/ui/composer` 폐기
- [`D-CS-003`](../../final_project_cs/wiki/decisions/D-CS-003-composer-scope.md) — Composer 범위 세 층
- [../architecture/repository-map.md](../architecture/repository-map.md) — 저장소 관계

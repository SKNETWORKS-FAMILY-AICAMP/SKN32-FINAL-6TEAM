---
type: decision
title: /ui/composer 폐기
description: 인증 없이 고객 접근이 가능한 앱에 구성기가 물려 있었다. 삭제하고 별도 프로그램으로 옮겼다
status: draft
tags: [security, ui]
owners: [human:미배정]
---

# D-CS-001 `/ui/composer` 폐기

**이 저장소 안에서 끝나는 결정이다.** 여러 저장소가 당사자인 결정은 [중앙 허브](../../../wiki/decisions/index.md)에 있다.

## 맥락

Composer는 **제작 단계의 구성기**다. 모듈 토글, Port 교체, Team 추가·제거를 화면에서 한다.

이게 `/ui/composer`로 운영 UI에 붙어 있었다.

## 문제

`[실측]` **이 앱은 인증이 전혀 없이 고객이 접근할 수 있다.**

운영 UI(`/ui/cases` 등)는 고객 응대 화면이라 그렇게 설계됐다. **거기에 시스템 구성을 바꾸는 화면이 같이 물려 있었다.**

실측으로 확인했다.

## 결정

> **`/ui/composer`를 삭제한다. (2026-08-18)**

같은 기능은 별도 프로그램 `final_project_ui`가 **인증된 `/composer/*` API로만** 제공한다.

## 선택지와 이유

| 안 | 채택 | 이유 |
|---|---|---|
| **삭제하고 별도 프로그램으로** | ✅ | 경계가 확실하다. 이 앱에는 아예 없다 |
| 인증을 붙인다 | ❌ | 같은 앱에 두 등급의 권한이 섞인다 |
| 개발 환경에서만 켠다 | ❌ | 환경 플래그는 실수로 켜진다 |
| 그대로 둔다 | ❌ | — |

**"환경 플래그로 끄면 된다"를 택하지 않은 게 중요하다.** 플래그는 잘못 설정되고, 잘못 설정된 걸 알아채기 어렵다. **없으면 켜질 수 없다.**

## 결과

| 바뀐 것 | |
|---|---|
| `app/presentation/ui/` | composer 화면 제거 |
| `app/presentation/api/composer.py` | ~~남는다~~ **2026-09-06 삭제됐다** (v9 §8-D, 커밋 `f2319aa`). 같은 API는 `acop_composer` 패키지의 라우터를 **관리용 빌드(`app/entrypoint.py`)에서만** 주입한다. 고객 릴리즈 앱(`app.presentation.api.app:app`)엔 `/composer/*`가 아예 없다 → [D-CS-004](D-CS-004-composer-boundary.md) |
| `final_project_ui` | 별도 프로그램이 이 API를 쓴다 |

`wiki/records/handoff/09_Composer_GUI_계약.md` 상단에 이 사실이 적혀 있다.

## 못 하게 되는 것

- 이 저장소를 띄운 것만으로는 구성을 바꿀 수 없다
- `final_project_ui`를 따로 띄워야 한다

**불편하지만 의도된 것이다.**

## 근거

`[실측]` `final_project_cs/CLAUDE.md` §5 모듈화·Composer GUI 행

> `/ui/composer`는 폐기됨(2026-08-18) — 인증이 전혀 없이 고객 접근 가능한 이 앱에 물려 있던 것을 실측으로 확인, 삭제했다.

## 같은 종류의 결함

`[실측]` 이 저장소에서 인증 경계 문제가 두 번 있었다.

| 결함 | 원인 |
|---|---|
| 인증 전 요청이 500 | `os.getenv`로 설정을 읽음 |
| `/ui/composer` 노출 | **무엇이 어디 물려 있는지** |

**둘 다 인증 로직 자체의 버그가 아니었다.** 경계를 어디에 그었는가의 문제였다.

## 관계

- [../external/auth-boundary.md](../external/auth-boundary.md) — Trust Boundary
- [../external/rest-api.md](../external/rest-api.md) — `/composer/*` API
- [index.md](index.md) — cs 로컬 결정 목록

---
type: report
title: v3 설계 대비 구현 격차
description: 항목 11개를 대조했더니 일치 1건이었다. 토글 전용 계약이 구현되지 않았다
status: draft
tags: [architecture, api, contract]
domain: neutral
---

# v3 설계 대비 구현 격차

`[실측]` 2026-08-20 대조. HEAD `033ebc2`. 원본은 `program/research/_컴포저_설계대비_구현대조.md`.

## 판정 — 불일치

| 판정 | 건수 |
|---|---|
| 일치 | **1** |
| **불일치** | **8** |
| 미구현 | 1 |
| 설계에 없음 | 1 |

**v3 의 핵심인 `POST /composer/toggle` 토글 전용 계약이 구현되지 않았다.** 현재 구현은 전체 `ProjectConfig` 를 검증·교체하는 **v2 형** `/composer/validate`·`/composer/apply` 다.

`[실측]` **2026-09-02 확인 — `/composer/toggle` 경로 자체는 지금 존재한다.**

```
POST /auth/token      POST /composer/changes
GET  /composer/catalog POST /composer/validate
GET  /composer/current POST /composer/apply
POST /composer/toggle  GET  /health
```

`[미확보]` **경로가 생긴 것과 v3 계약을 지키는 것은 다르다.** 아래 항목별로 다시 대조하지 않았다.

## 항목별

### 유일하게 일치한 것

| 항목 | 근거 |
|---|---|
| **revision 충돌을 검사한다** | writer lock 안에서 `base_revision` 을 비교하고 다르면 `RevisionConflict`. API 는 409 (`acop_composer/service.py:115-122`, `api.py:100-104`) |

### 불일치 8건

| 항목 | 무엇이 다른가 |
|---|---|
| 대상 ID 존재 확인만 한다 | 구현은 team 의 `implementation_ref` allowlist 까지 검사 (`service.py:55-69`) |
| **Core 계약 모델을 깊이 검증하지 않는다** | `acop_composer` 가 `ProjectConfig`·`load_project_config` 를 import (`service.py:29-32`). 그 함수가 Pydantic schema 와 team class 계약까지 검사한다 |
| **한 항목의 flag 만 원자적으로 쓴다** | **전체를 YAML 로 만들어 `os.replace` 로 `project.yaml` 통째 교체** (`service.py:118-134`) |
| append-only 감사 로그 | 남기긴 하는데 `target_type`·`target_id`·old/new flag 가 아니라 **전체 config 의 `changed_fields`** (`api.py:101-106`) |
| UI 가 Core 를 import 하지 않는다 | Composer API 가 basement Core 를 직접 import (`api.py:25-27`) |
| **`acop_basement` 에 Composer 코드가 없어야 한다** | basement 의 app factory 가 **Composer router 주입을 알고 있고** Composer JWT 설정도 보유 (`presentation/api/app.py:11-17`, `core/settings.py:50-52`) |
| **`acop_composer` 는 선택 설치 패키지다** | 하나의 배포물 `final-project-sample` 에 `app*`·`acop_basement*`·`acop_composer*` 를 함께 포함 (`pyproject.toml:5-8`) |
| architecture test 가 경계를 검사한다 | `test_basement_is_domain_free.py` 는 **도메인 단어와 `app.modules` import 만** 본다. **Composer 혼입·wheel 파일 목록은 안 본다** |

## ★ 가장 큰 것 둘

**1. 전체 교체가 실제 적용 경로다.**

v3 가 금지한 **전체 `ProjectConfig` 재구성**이 지금 쓰이고 있다. 토글 하나 바꾸려고 파일 전체를 갈아끼운다.

**2. 경계를 검사하는 테스트가 없다.** ★`[정정 2026-09-10]` **지금은 있다** — `tests/architecture/test_composer_package_boundary.py` 와 `test_composer_ui_package_boundary.py` 가 생겼다. 아래는 그 전 대조 결과다.

`[실측]` 도메인 격리는 [test-basement-is-domain-free](../quality/domain-free.md) 가 강제한다. **그런데 Composer 와 basement 의 패키지 경계는 아무도 안 지킨다.**

**선언만 있고 강제가 없는 경계다.** → [../quality/architecture-tests.md](../quality/architecture-tests.md)

## 대조의 한계

`[실측]` 원본이 스스로 적어 뒀다.

```
확인 시점  2026-08-20 스냅샷
미커밋 변경  있음 (?? .pytest-tmp/)
다른 세션이 작업했을 수 있다
```

**`final_project_sample/` 안의 파일은 수정하지 않았다.**

## 관계

- [write-channel.md](write-channel.md) — 쓰기 경로
- [ui-boundary.md](ui-boundary.md) — UI 경계
- [../quality/architecture-tests.md](../quality/architecture-tests.md) — 무엇이 강제되나
- 원본: `program/research/_컴포저_설계대비_구현대조.md`

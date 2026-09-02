---
type: decision
title: 중앙 설정 저장소
description: 고객 빌드에 쓰기 코드를 안 넣으면서 릴리즈 후 구성 관리를 하려면 로컬 파일로는 안 된다
status: draft
tags: [architecture, security, contract]
owners: [human:미배정]
---

# D-007 중앙 설정 저장소

`[실측]` `A-COP_Composer_중앙설정저장소_결정.md`(2026-08-29)에서 이관.

## 맥락 — 두 요구가 충돌했다

| 요구 | 뜻 |
|---|---|
| **고객 빌드에 쓰기 코드를 넣지 않는다** | 배포본이 자기 설정을 못 고친다 |
| **릴리즈 후에도 구성을 관리한다** | 누군가는 고쳐야 한다 |

**로컬 YAML 파일 저장으로는 둘이 양립하지 않는다.** 고칠 수 있으면 쓰기 코드가 있는 것이고, 없으면 못 고친다.

## 결정

> **direct 와 central 두 모드를 모두 지원하고, UI 환경변수로 선택한다.**
>
> **수천 배포 규모에서는 central 을 쓴다.**

## 구조

```
중앙 설정 서비스 + DB
        ↓ 읽기 전용 부트스트랩
수천 개의 대상 배포본
```

**대상은 읽기만 한다.** 쓰기 코드가 배포본에 없다.

## 무엇이 바뀌나

| 무엇 | 전 | 후 |
|---|---|---|
| 저장 | YAML 파일 | **DB row + CAS** |
| 식별 | — | `deployment_id` |
| 감사 | 파일 | **append-only DB** |
| 읽기 | 로컬 | 중앙 |

## 바뀌지 않는 것

```
저장과 활성 상태 구분  (desired vs effective)
서버 판정            UI 가 아니라 대상이 검증한다
grant ceiling        권한 상한
```

**UI CRUD 계약(`/catalog`·`/changes`·`/toggle`)도 그대로다.** → [D-CS-003](../../final_project_cs/wiki/decisions/D-CS-003-composer-scope.md)

## ★ 반증 조건

`[실측]` **이 결정이 틀릴 수 있는 조건을 문서가 스스로 적었다.**

> **실제 대상이 수십 개 이하라면 중앙 운영 부담이 더 크다.**

**규모가 전제다.** 수천 대가 아니면 direct 가 낫다.

**반증 조건을 적은 게 이 문서의 좋은 점이다.** 결정을 언제 되돌릴지 미리 정해 뒀다.

## 구현 상태

`[실측]` 마이그레이션·store·config source·service app 커밋 완료. **438개 테스트 통과.**

## 아직 안 정한 것

`[미확보]`

```
HA · 백업 · 인증 · 방화벽 승인
```

**운영에 필요한 것들이 남았다.** 구현은 됐지만 운영 준비는 아니다.

## 다른 결정과의 관계

| | |
|---|---|
| 인스턴스 CRUD 금지 | **철회됨** |
| 임의 Python 경로 등록 금지 | **유지** |
| 3패키지 소유권 | **유지** → [D-006](D-006-composer-ownership.md) |

## 관계

- [D-006](D-006-composer-ownership.md) — Composer 소유권
- [`sample/wiki/composer/`](../../final_project_sample/wiki/composer/index.md) — `core/config_store.py` 가 여기 있다
- [`D-CS-003`](../../final_project_cs/wiki/decisions/D-CS-003-composer-scope.md) — 세 층 구분
- [`D-CS-001`](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) — `/ui/composer` 폐기
- [../architecture/repository-map.md](../architecture/repository-map.md) — 저장소 관계

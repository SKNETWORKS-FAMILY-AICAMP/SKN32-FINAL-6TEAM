---
type: decision
title: Team 을 코드가 아니라 선언으로 만든다
description: 네 방식을 비교했고 선언형을 권고했다. 나머지 셋은 기각이 아니라 조건부다
status: draft
tags: [architecture, contract, security]
domain: neutral
---

# D-013 Team 을 코드가 아니라 선언으로 만든다

`[실측]` 원본은 `program/plan/A-COP_Composer_범위재검토.md` §5.

**구현은 이미 있는데** (`acop_basement/teams/declarative.py`) **왜 이 방식인지가 wiki 에 없었다.**

## 결정

> **선언형 Team 을 우선 권고한다.** 나머지 셋은 조건부이거나 위험하다.

## 네 방식을 비교했다

| 방식 | 가능 | 대가와 한계 |
|---|---|---|
| 등록 구현체 선택 후 설정 입력 | 가능 | `TeamConfig` 에 설정 필드가 없다. 카탈로그와 instance schema 가 필요 |
| **템플릿에서 새 구현체 생성** | 개발 환경만 | **생성 결과가 코드다.** 검토·테스트·서명·배포·재시작이 필요. **운영 UI 에서 즉시 실행하면 안 된다** |
| **선언형 Team** | **권고** | 범용 실행기와 정책 엔진을 **한 번** 배포. 복잡한 알고리즘과 새 side effect 는 표현하기 어렵다 |
| **플러그인 디렉터리 스캔** | 조건부 | **임의 파일 import 는 원격 코드 실행과 같다.** 서명·고정 디렉터리·격리 검사·버전 고정·재시작이 필요 |

### ★ 기각 사유가 이 결정의 값이다

**네 번째가 가장 편해 보이는데 가장 위험하다.**

> **임의 파일 import 는 원격 코드 실행과 같다.**

**두 번째도 같은 함정이다** — 생성한 것이 코드면 그걸 바로 돌릴 수 없다. **UI 에서 만든 걸 UI 에서 실행하면 그 순간 임의 코드 실행이다.**

**선언형이 이긴 이유는 "만든 결과가 데이터"라서다.** → [D-005](D-005-write-gate.md)

## "코드가 전혀 없다"는 뜻이 아니다

**`DeclarativeTeamRuntime` 이라는 범용 Python 구현체를 한 번 배포한다.** 그 뒤 개별 Team 은 데이터로 만든다.

### 선언에 들어가는 것

```
instance_id · 표시 이름
capabilities · accepted_case_types
version 고정 system prompt (또는 prompt resource)
allowed_tools + 각 tool 의 read/write 등급
knowledge_scope · 필요한 ContextPack 항목
max_steps · token·비용 한도 · timeout
TeamResult 로 제한하는 output schema
생성자 · 검토자 · 승인자 · 생성 시각 · 변경 revision
```

**마지막 줄이 감사 경로다.** 누가 만들고 누가 승인했는지가 선언 안에 있다.

### 실행기가 지키는 것

| | |
|---|---|
| `TeamModule` 계약을 구현한다 | 기존 Team 과 같은 인터페이스 |
| 실행 때 선언으로 `TeamManifest` 를 만든다 | |
| **모든 tool 호출이 서버의 tool gateway 를 거친다** | → [tool-gateway](../../final_project_cs/wiki/actions/tool-gateway.md) |
| 결과를 기존 `TeamResult` 로 검증한다 | |
| **승인 필요한 side effect 는 계속 `ActionProposal` 만 반환** | 선언형이라고 예외가 아니다 |

**마지막 줄이 중요하다.** 선언으로 만든 Team 도 [D-005](D-005-write-gate.md) 를 그대로 받는다.

## 한계 — 표현 못 하는 것

`[실측]` 원본이 적어 둔 것.

> **복잡한 알고리즘과 새 side effect 는 표현하기 어렵다.**

**그러면 코드로 만들어야 하고, 그건 배포 절차를 탄다.** 선언형이 모든 Team 을 대체하지 않는다.

## 구현 상태

`[실측]` `final_project_sample/acop_basement/teams/declarative.py` 에 있다.

**계약 검사도 있다** — 카탈로그 조회·토글·선언형 Team 생성·dry-run·revision 충돌을 **실제 서버와 왕복한다.** `tests/e2e/test_composer_ui_client_contract.py`

`[실측]` **읽기 전용 선언형 Team 에 쓰기 도구를 넣는 요청**은 UI 가 자체 판정하지 않고 **서버가 422 로 거부한다.** → [sample/composer/ui-boundary.md](../../final_project_sample/wiki/composer/ui-boundary.md)

`[미확보]` **`final_project_cs` 쪽 구현 상태는 확인하지 않았다.**

## [2026-09-10] sample 구현과 대조

`[실측 git]` 이 문서가 제안한 것 중 일부는 sample 에 이미 있고, 일부는 제안보다 좁게 구현됐다.

| 이 문서 | sample 구현 |
|---|---|
| 「셋을 기각했다」(description) | `[정정]` 비교표는 셋을 **가능 · 개발 환경 한정 · 조건부**로 적었다. 기각이 아니다 |
| 선언에 `parameters` 를 넣는다 | **이미 있다** — `TeamConfig.parameters`(`final_project_sample/acop_basement/core/project_config.py:115`), 선언형만 가질 수 있다(`:118`) |
| 선언에 생성자 · 검토자 · 승인자 · 비용 한도 | **없다** — `TeamConfig` 필드는 `team_id` · `active` · `implementation_ref` · `parameters` 넷이다(같은 파일 100~125행을 읽었다) |
| 「승인 필요한 side effect 는 `ActionProposal` 만 반환」 | **더 좁다** — 실행기는 읽기 전용이라 `ActionProposal` 을 **아예 만들지 않는다**(`acop_basement/teams/declarative.py:9`) |

## 관계

- [D-005](D-005-write-gate.md) — 쓰기 권한 전제
- [D-006](D-006-composer-ownership.md) — Composer 소유
- [../../final_project_sample/wiki/teams/example-teams.md](../../final_project_sample/wiki/teams/example-teams.md) — 실행기 구현
- [../architecture/pack-model.md](../architecture/pack-model.md) — Pack 모델

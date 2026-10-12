---
type: contract
title: sample 이 깨면 안 되는 것
description: 테스트가 실제로 강제하는 규칙만 적는다. 선언만 있고 강제가 없는 것은 여기 없다
status: draft
tags: [testing, architecture, contract]
domain: neutral
---

# sample 이 깨면 안 되는 것

`[실측]` 2026-09-03. **테스트가 실제로 강제하는 것만 적는다.**

**선언만 있고 강제가 없는 규칙은 여기 두지 않는다.** 그건 불변식이 아니라 희망이다.

## 구조 — `INV-SAMPLE-ARCH-*`

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-SAMPLE-ARCH-001` | **basement 는 도메인 어휘를 쓰지 않는다** | `tests/architecture/test_basement_is_domain_free.py` (4) |
| `INV-SAMPLE-ARCH-002` | **같은 엔진이 다른 도메인을 돌린다** | `tests/architecture/test_engine_serves_another_domain.py` (10) |
| `INV-SAMPLE-ARCH-003` | 배포 매니페스트가 모든 패키지를 덮는다 | `tests/architecture/test_basement_manifest_covers_every_package.py` (2) |
| `INV-SAMPLE-ARCH-004` | UI 가 basement 를 직접 만지지 않는다 | `tests/architecture/test_composer_ui_package_boundary.py` (5) |
| `INV-SAMPLE-ARCH-005` | **Core 가 도메인 모듈을 import 하지 않는다** | `tests/contract/test_core_isolation.py::test_core_does_not_import_modules` |

**`ARCH-002` 가 이 저장소의 존재 이유다.** → [another-domain.md](another-domain.md)

**`ARCH-005` 가 Team 교체 가능성의 전부다.** Core 가 Team 을 모르지 않으면 갈아끼울 수 없다.

## 런타임 — `INV-SAMPLE-RUN-*`

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-SAMPLE-RUN-001` | **모든 messaging consumer 가 멱등임이 증명돼 있다** | `tests/architecture/test_consumer_idempotency_gate.py::test_every_messaging_consumer_is_explicitly_proven_idempotent` |
| `INV-SAMPLE-RUN-002` | 상태 전이표를 벗어나지 않는다 | `tests/contract/test_case_state_table.py` (8) |

### `RUN-001` 이 특이하다

**개별 consumer 를 테스트하는 게 아니라 "증거가 없는 consumer 가 있는지"를 센다.**

```
Guard the set of messaging consumers covered by idempotency evidence.
```

**새 consumer 를 만들고 증거를 안 붙이면 실패한다.** 빠뜨리는 것을 막는 종류의 테스트다.

## Team 계약 — `INV-SAMPLE-TEAM-*`

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-SAMPLE-TEAM-001` | Team 이 받고 돌려주는 모양이 고정돼 있다 | `tests/contract/test_team_contract.py` (2) · `test_contracts.py` (19) |
| `INV-SAMPLE-TEAM-002` | 모듈을 켜고 끌 수 있다 | `tests/contract/test_module_toggles.py` (8) |

## 보안 — `INV-SAMPLE-SEC-*`

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-SAMPLE-SEC-001` | **읽기와 쓰기 scope 가 분리돼 있다** | `tests/security/test_scope_contract.py::test_composer_scopes_are_guardrail_owned` |
| `INV-SAMPLE-SEC-002` | **MCP 도구는 읽기 셋뿐이다** | `tests/security/test_scope_contract.py::test_mcp_has_exactly_three_read_scoped_tools` |
| `INV-SAMPLE-SEC-003` | PII 가 런타임에서 가려진다 | `tests/security/test_pii_redaction_runtime.py` |

`[실측]` `SEC-001` 의 테스트가 이유를 적어 뒀다.

> `ops:introspect`(읽기) · `composer:write`(쓰기) 는 `mcp:read` 와 **분리된 scope 다** — 되돌릴 수 있지만 **반영은 그 순간 트래픽이 받는 것을 바꾼다.**

**되돌릴 수 있다고 안전한 게 아니다.** 되돌리기 전까지는 이미 나가 있다.

## 세어 보면

`[실측]` 강제하는 테스트 함수 **68개**가 위 12개 불변식을 받친다. `[2026-09-10]` 같은 네 폴더를 지금 세면 **87개**다(architecture 29 · contract 50 · contracts 5 · security 3). 68 은 그때 값이다.

```
architecture  22    contract  38
contracts      5    security   3
```

## ★ 강제되지 않는 것

`[미확보]` **선언은 있는데 테스트가 없는 경계가 하나 확인됐다.** `[정정 2026-09-10]` **지금은 테스트가 있다** — `tests/architecture/test_composer_package_boundary.py` 5건.

> `acop_composer` 와 `acop_basement` 의 **패키지 경계**

`test_basement_is_domain_free.py` 는 **도메인 단어와 `app.modules` import 만** 본다. **Composer 혼입·wheel 파일 목록은 안 본다.**

→ [../composer/design-gap.md](../composer/design-gap.md)

**여기가 다음에 불변식을 붙일 자리다.**

## 관계

- [architecture-tests.md](architecture-tests.md) — 5종이 각각 무엇을 잡나
- [domain-free.md](domain-free.md) — 도메인 격리
- [another-domain.md](another-domain.md) — 가장 중요한 테스트
- [index.md](index.md) — 품질 영역

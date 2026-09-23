---
type: guide
title: Team을 어떻게 끼우나
description: Team-플러그인 구조의 참조 구현. 예시 Team은 계약이 성립한다는 증거이지 제품이 아니다
status: draft
tags: [architecture, contract]
domain: neutral
---

# Team — 어떻게 끼우나

**sample이 증명하는 것은 "Team을 갈아끼울 수 있다"이지 "이 Team이 쓸 만하다"가 아니다.**

## ★ 혼동하면 안 되는 것

`[정정 2026-09-10]` 「sample 에 Billing·Technical Team 이 구현돼 있고 Core 격리 위반이 0」은 옛 문장이다 — 지금 sample `app/modules/customer_ops/` 에는 `feedback.py`·`feedback_team.py` 만 있다. 「위반 0」은 `tests/contract/test_core_isolation.py` 의 `test_core_does_not_import_modules` 가 보는 범위(Core 의 지정 import)이고, 이 수정에서 다시 돌리지 않았다.

**그건 구조가 동작한다는 증거일 뿐 cs의 착수 목록이 아니다.** → [../index.md](../index.md)

## 계약을 고정하는 테스트

`[실측]` `tests/contract/`

| 테스트 | 무엇을 고정 |
|---|---|
| `test_team_contract.py` | Team이 받고 돌려주는 모양 |
| `test_core_isolation.py` | Core가 Team을 import 하지 않는 것 |
| `test_case_state_table.py` | 상태표 |
| `test_module_toggles.py` | 모듈 켜고 끄기 |

**`test_core_isolation.py`가 핵심이다.** Core가 Team을 모르는 게 Team 교체 가능성의 전부다.

## 문서

| 문서 | 답하는 질문 |
|---|---|
| [team-contract.md](team-contract.md) | Team 이 무엇을 받고 무엇을 돌려주나 |
| [team-boundary.md](team-boundary.md) | Team 이 하면 안 되는 것과 무엇이 그걸 막나 |
| [team-registry.md](team-registry.md) | capability 로 어떻게 찾나. 없으면 어떻게 되나 |
| [example-teams.md](example-teams.md) | 예시 Team 이 무엇을 보여주나 |

### 아직 안 쓴 것

| 문서 | 답할 질문 |
|---|---|
| — | 없다 |

## 관계

- [../index.md](../index.md) — 지식 지도
- [`../../../wiki/architecture/core-vs-team.md](../../../wiki/architecture/core-vs-team.md) — 경계 규칙
- [`../../../wiki/architecture/pack-model.md](../../../wiki/architecture/pack-model.md) — Pack 모델

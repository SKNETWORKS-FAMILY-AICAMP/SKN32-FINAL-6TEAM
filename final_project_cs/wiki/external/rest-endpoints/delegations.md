---
type: contract
title: 위임 API
description: 호출 주체와 책임별 REST 요청·응답 계약
status: draft
domain: travel
---

# 위임 API

## 위임 — `/v1/delegations/*` `[2026-09-22]`

`[실측]` `app/domains/travel_ops/entry/delegation_api.py`. 라우터는 도메인 폴더에 있고
`composition.build_domain_routers()` 가 앱에 넣는다(여행 API 와 같은 이유 — presentation 은
도메인을 import 하지 못한다, INV-CS-ARCH-001). v11 §12 DoD-18·19.

**전에는 이 경로가 없었다.** 위임 범위 판정과 `delegations` 표는 있는데 **주고 거두는 자리가
없어** 운영자가 손으로 SQL 을 쳐야 했다 — 「위임은 언제든 철회할 수 있다」가 말뿐이었다.

| 경로 | scope | 하는 일 |
|---|---|---|
| `GET /v1/delegations` | `delegation:read` | 테넌트의 위임 전부 + **지금 맡기는 범위**(`limits`) + 집계 |
| `GET /v1/delegations/{customer_id}` | `delegation:read` | 한 고객의 상태 · 누적 사용액 · **주고 거둔 이력**(021) |
| `POST /v1/delegations/{customer_id}/grant` | `delegation:write` | 맡긴다. 다시 주면 철회가 풀린다(`regranted:true`) |
| `POST /v1/delegations/{customer_id}/revoke` | `delegation:write` | 거둔다. 판정은 **적용 순간**이라 승인 뒤에 거둬도 그 건은 열리지 않는다 |

| 규칙 | 계약 |
|---|---|
| ★**scope 를 `action:approve` 와 나눈다** | 승인은 **제안 한 건**에 "이 변경을 해도 된다" 이고, 위임은 **서 있는 권한**이다 — 한 번 주면 거둘 때까지 그 고객의 모든 자동 실행이 한계 안에서 열린다. 영향 범위가 다르면 나누는 것이 이 저장소의 방식이다(`composer:admin`·`ops:reload` 가 같은 기준으로 갈라졌다). 읽기/쓰기도 나눈다 — 현황을 보는 사람이 문을 열지는 못한다 |
| 요청 몸통 | `actor_id`(1자 이상) · `note`(1자 이상). `extra="forbid"`. **공백만 보내면 `422`** — 근거 없이 위임 상태를 바꾸지 않는다(`/v1/outbox/{id}/resolve` 와 같은 계약) |
| `404` | 다른 테넌트의 고객이거나 없는 고객. **있는지도 말하지 않는다** |
| ★`409 no_live_delegation` | 거둘 위임이 없다. **「거뒀다」고 답하지 않는다** — 200 으로 넘기면 운영자가 "눌렀으니 됐겠지" 로 간다. 이미 막혀 있다는 사실은 응답의 `state` 가 말한다 |
| 응답에 없는 것 | `external_id`·`email_hash` — 고객 식별자를 `customer_id` 밖으로 늘리지 않는다 |
| 한계 값 | 만들지 않고 **읽어서 이름표만 붙인다**(`limits[].label`·`value`). 정본은 `config/guardrails.yaml` `travel.delegation`(RULE.md §3.1). 화면이 여행 어휘를 모르고도 그릴 수 있게 하려는 것이다 |
| ★이력 | 주기·거두기가 `delegation_events`(마이그레이션 [021](../../../app/infrastructure/db/migrations/021_delegation_audit_trail.sql))에 **덧붙는다**. `delegations` 한 행은 다시 주기가 덮으므로 그것만으로는 「누가 거뒀나」가 사라진다 |

운영 화면은 `/ui/delegations` 다 — ★`[2026-09-29]` **운영 앱**(별도 프로세스, [D-CS-008](../../decisions/D-CS-008-ops-console-separate-app.md))이 이 경로를 **실제 HTTP** 로 불러(`ACOP_OPS_API_BASE_URL` · 키 `ACOP_OPS_API_KEYS`) 서버에서 그린다. 전에는 같은 프로세스 안에서 불렀다.

시험: [`tests/integration/api/test_delegation_api.py`](../../../tests/integration/api/test_delegation_api.py)(12) ·
[`tests/integration/api/test_ui_delegation_screen.py`](../../../tests/integration/api/test_ui_delegation_screen.py)(8).


## 관계

- [REST 안내](index.md) — 계약 지도

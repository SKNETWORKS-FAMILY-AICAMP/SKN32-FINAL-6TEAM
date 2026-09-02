---
type: contract
title: introspection 계약
description: 무엇이 조립돼 있나를 보여주고 얼마나 돌고 있나는 안 보여준다
status: draft
tags: [api, contract, security]
---

# `GET /introspection` 계약 v1

`[실측]` `docs/handoff/13_introspection_계약.md` 에서 이관.

**`ops:introspect` scope 로 보호되는 read-only JSON API 다.** `contract_version` 은 `1.0`.

응답은 `app.introspection.contract.snapshot()` 의 조립 메타데이터를 그대로 낸다.

| 넣는다 | 넣지 않는다 |
|---|---|
| 활성 모듈과 Port 선언 | **API key 원문** |
| Team manifest·선언 | **tenant 운영 데이터** — document·chunk·case·outbox 카운트 |
| 실제 Port 구현 이름 | |
| guardrails · LLM provider/model | |
| **마스킹된 `api_key`** | |

**"무엇이 조립돼 있나"는 보여주고 "얼마나 돌고 있나"는 안 보여준다.**

`[실측]` **운영 카운트를 뺀 게 중요하다.** 그건 tenant 의 업무량이라 조립 메타데이터가 아니다.

## 관계

- [rest-api.md](rest-api.md) — REST 경로
- [auth-boundary.md](auth-boundary.md) — scope

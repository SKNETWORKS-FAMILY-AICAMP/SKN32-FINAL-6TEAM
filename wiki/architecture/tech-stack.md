---
type: reference
title: 기술 스택
description: MVP에서 쓰는 것과 Phase 2로 미룬 것. Docker 는 지금 없다
status: draft
tags: [architecture]
owners: [human:미배정]
domain: neutral
---

# 기술 스택

`[실측]` v8 §12에서 이관. `[미확보]` **v11 에도 대응하는 절이 없다** — v11 에 `MCP`·`Docker`·`AWS` 가 나오는 곳은 「v11 이 이것들을 말하지 않는다」고 적은 한 줄(124행)뿐이다. 뺀 것인지 빠진 것인지 안 정해졌다. `[정정 2026-09-10]` 이 자리는 v10 기준으로 적혀 있었다. ★**아래 표는 기존 코드의 구현 선택이고 v11 이 정한 기술 결정이 아니다.**

★**이 문서는 도메인이 바뀌어도 안 바뀐다.**

## MVP

```
Python · FastAPI · PostgreSQL · pgvector · LangGraph
REST/OpenAPI · MCP · A2A · React
```

| 항목 | 선택 |
|---|---|
| Message Broker | **DB Outbox 로 시작**(바깥함 표에 적고 발행 일꾼이 내보낸다 — `final_project_cs/app/infrastructure/messaging/worker.py`). `[정정 2026-09-10]` 「In-Process / Outbox」로 적혀 있었다. Adapter 교체 → [D-003](../decisions/D-003-message-broker.md) |
| Graph Store | **`SqlGraphAdapter`.** 게이트 통과 시에만 교체 → [D-002](../decisions/D-002-graph-store-gate.md) |
| 임베딩 | `text-embedding-3-small` = **1536차원** |

**둘 다 Port 뒤에 있다.** 지금 선택을 나중에 바꿀 수 있게 해 둔 것이다.

## Phase 2

```
AWS · Docker (컨테이너 기반 배포)
```

## ★ 지금 Docker가 없다

`[실측]` **로컬 개발 환경에 Docker가 설치돼 있지 않다.**

```
로컬    PostgreSQL 직접 실행 (conda env pgv, 127.0.0.1:5433)
배포    그때 컨테이너화
```

`docker/compose.yml`로 DB를 띄우는 전제는 **이 기계에서 성립하지 않는다.** compose 파일은 재현용으로만 남긴다.

→ [`operations/local-setup.md`](../../final_project_cs/wiki/operations/local-setup.md) · [sample](../../final_project_sample/wiki/operations/local-setup.md)

## 바꾸면 함께 바뀌는 것

| 바꾸는 것 | 함께 |
|---|---|
| 임베딩 모델 | **DDL의 `vector(1536)`과 적재분 전체** |
| Message Broker 구현 | consumer 계약 테스트 재실행 |
| Graph Store | Projection 동기화 설계 (25~40인·일 `[추정]` — D-002 와 같은 값) |

## 관계

- [core-design.md](core-design.md) — Port 3종
- [../decisions/D-002-graph-store-gate.md](../decisions/D-002-graph-store-gate.md) — Graph Store 게이트
- [../decisions/D-003-message-broker.md](../decisions/D-003-message-broker.md) — Broker 선택
- [`data/migrations.md`](../../final_project_cs/wiki/data/migrations.md) · [sample](../../final_project_sample/wiki/operations/index.md) — 환경 주의

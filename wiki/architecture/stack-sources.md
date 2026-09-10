---
type: reference
title: A-COP 기술 스택 공식 문서
description: 활용 기술의 공식 URL과 HTTP 200 확인 결과 및 링크 제외 사유를 정리한다.
status: draft
tags: [architecture, api, documentation]
domain: neutral
---

## 결론

`[실측]` 아래 18개 공식 URL은 `2026-08-17`에 `curl`로 요청해 모두 HTTP `200`을 확인했다. RAG·GraphRAG 등 5개 항목에는 공식 사이트가 없거나 A-COP 내부 설계·구성요소이므로 링크를 걸지 않았다.

## 공식 문서

| 기술 | 역할 | 공식 URL과 확인 결과 |
|---|---|---|
| Python | 코어 1 · MVP | `[실측]`[외부]` https://www.python.org/ — HTTP 200, 2026-08-17 |
| LangGraph | 코어 1 · MVP | `[실측]`[외부]` https://langchain-ai.github.io/langgraph/ — HTTP 200, 2026-08-17 |
| PostgreSQL | 코어 1 · MVP | `[실측]`[외부]` https://www.postgresql.org/ — HTTP 200, 2026-08-17 |
| Redis | 코어 1 · Phase 2 | `[실측]`[외부]` https://redis.io/ — HTTP 200, 2026-08-17 |
| RabbitMQ | ❌ **기각** ([D-003](../decisions/D-003-message-broker.md)) | `[실측]`[외부]` https://www.rabbitmq.com/ — HTTP 200, 2026-08-17 |

★`[정정 2026-09-10]` **RabbitMQ 를 「코어 1 · Phase 2」로 적어 채택 항목처럼 보였다.** [D-003](../decisions/D-003-message-broker.md) 은 **기각**으로 기록한다 — "현재 규모에서 운영 복잡도가 불필요하다". **후보와 기각을 같은 칸에 두면 나중에 누군가 "Phase 2 에 쓰기로 했다"고 읽는다.** Redis Streams 가 프로덕션 **후보**이고 RabbitMQ 는 후보가 아니다.

| Apache AGE | 코어 1 · Phase 2 | `[실측]`[외부]` https://age.apache.org/ — HTTP 200, 2026-08-17 |
| Neo4j | 코어 1 · Phase 2 | `[실측]`[외부]` https://neo4j.com/ — HTTP 200, 2026-08-17 |
| FastAPI | 코어 2 · MVP | `[실측]`[외부]` https://fastapi.tiangolo.com/ — HTTP 200, 2026-08-17 |
| OpenAPI | 코어 2 · MVP | `[실측]`[외부]` https://www.openapis.org/ — HTTP 200, 2026-08-17 |
| MCP | 코어 2 · MVP | `[실측]`[외부]` https://modelcontextprotocol.io/ — HTTP 200, 2026-08-17 |
| A2A | 코어 2 · MVP | `[실측]`[외부]` https://a2a-protocol.org/ — HTTP 200, 2026-08-17 |
| OAuth 2.0 | 코어 2 · Phase 2 | `[실측]`[외부]` https://oauth.net/2/ — HTTP 200, 2026-08-17 |
| OpenID Connect | 코어 2 · Phase 2 | `[실측]`[외부]` https://openid.net/developers/how-connect-works/ — HTTP 200, 2026-08-17 |
| pgvector | 모델 · MVP | `[실측]`[외부]` https://github.com/pgvector/pgvector — HTTP 200, 2026-08-17 |
| pytest | 검증 & 프론트 · MVP | `[실측]`[외부]` https://docs.pytest.org/ — HTTP 200, 2026-08-17 |
| AWS | 배포 · Phase 2 | `[실측]`[외부]` https://aws.amazon.com/ — HTTP 200, 2026-08-17 |
| Docker | 배포 · Phase 2 | `[실측]`[외부]` https://www.docker.com/ — HTTP 200, 2026-08-17 |
| React | 검증 & 프론트 · MVP | `[실측]`[외부]` https://react.dev/ — HTTP 200, 2026-08-17 |

## 링크를 걸지 않은 항목

| 항목 | 이유 |
|---|---|
| RAG · GraphRAG | `[실측]` 특정 제품이 아니라 검색 증강 방식의 이름이므로 공식 사이트가 없다. |
| API Key + Scope | `[실측]` A-COP Gateway의 권한 설계이며 외부 표준이 아니다. |
| golden / holdout harness | `[실측]` 내부 평가 하네스다. **두 저장소에 각각 있다** — `final_project_cs/eval/` · `final_project_sample/eval/` |
| bootstrap · McNemar | `[실측]` 통계 검정 방법이며 제품이 아니다. |
| Registry · Adapter | `[실측]` 내부 설계의 구성요소 이름이며 **v7 §21 에서 왔다**(현재 기준선은 v11 — 그 절을 v11 이 승계했다) 계약을 따른다. |

## 근거 문서 구분

`[실측]` 이 문서는 공식 문서를 어디에서 보는지 기록한다. 프로토콜의 사실 근거는 `_출처검증_2026-08-17.md`의 H 그룹인 H1 A2A, H2 AP2, H3·H4 UCP, H5 MCP에 별도로 있다.

## 관계

- 원본: program/research/_기술스택_공식문서_2026-08-17.md

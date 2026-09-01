---
type: research
title: A2A 채택 현황
description: 개인 AI 경로를 MCP로, 기업 Agent 경로를 A2A로 나눈 근거 조사
status: draft
tags: [architecture, api]
owners: [human:미배정]
---

# A2A 채택 현황

조사 시점 `[미확보]` 2026-08 중.

## 무엇을 물었나

개인 AI(ChatGPT, Claude)와 기업 Agent System에 각각 어떤 프로토콜로 연결할 것인가.

## 조사 결과

`[외부]` 2026년 현재 확인 가능한 공식 A2A 통합 사례가 **기업용 Agent 플랫폼에 집중**돼 있다.

| 플랫폼 | 성격 |
|---|---|
| Azure AI Foundry | 기업용 |
| Copilot Studio | 기업용 |
| AWS Bedrock AgentCore | 기업용 |
| Google Vertex AI | 기업용 |

반면 **개인 AI의 외부 서비스 연결은 MCP가 실제 사용 경로**다.

## 판단

| 경로 | 프로토콜 | 이유 |
|---|---|---|
| 개인 AI | **MCP** | 실제 연결 경로가 MCP다 |
| 기업 Agent System | **A2A** | 공식 통합 사례가 여기 있다 |

**개인 AI가 A2A를 영원히 지원하지 않는다는 뜻이 아니다.** MVP의 연결 대상을 구분하는 판단이다.

## 구조적으로는 우리 Case가 A2A Task와 같다

`waiting_approval`, `waiting_input` 같은 장기 상태를 가지므로 A2A Task 생명주기와 모양이 같다.

**그럼에도 개인 AI를 MCP로 두는 것은 시장 현황 판단이지 구조 판단이 아니다.**

## A2A인지 가르는 기준

| | A2A | 아님 |
|---|---|---|
| 무엇 | 장기 실행 업무 위임 | 단순 데이터 조회 |
| 있어야 할 것 | Agent Card, Task lifecycle, 추가 입력, Artifact | 없음 |
| 아니면 | | REST다 |

**단순 데이터 REST 호출을 A2A로 분류하지 않는다.**

## A2A 경계를 지금 세우는 이유

`GraphStorePort`와 다르다.

| | A2A | GraphStorePort |
|---|---|---|
| 나중에 넣으면 | Controller·Registry·계약·상태 매핑을 전부 다시 건드림 | Port만 두면 구현을 미룰 수 있음 |
| 왜 | 실행 경로가 코드 전반에 퍼짐 | 저장소 교체 문제 |
| 판단 | **지금 경계를 세운다** | 나중에 |

## 한계

`[미확보]` 세 가지.

1. 조사 시점을 정확히 기록하지 않았다
2. 개별 플랫폼 문서 링크를 여기 모으지 않았다
3. 개인 AI의 A2A 지원 로드맵은 확인 못 했다

## 관계

- [../architecture/system-context.md](../architecture/system-context.md) — 진입 경로 3종
- [`external/mcp-tools.md`](../../final_project_cs/wiki/external/mcp-tools.md) — MCP 구현
- [`external/a2a-protocol.md`](../../final_project_cs/wiki/external/a2a-protocol.md) — A2A 구현

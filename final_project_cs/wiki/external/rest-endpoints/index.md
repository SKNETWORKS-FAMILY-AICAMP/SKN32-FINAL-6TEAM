---
type: guide
title: REST API 계약 지도
description: Case·여행·브라우저·위임 계약을 호출 주체별로 안내한다
status: draft
domain: travel
---

# REST API 계약 지도

API 계약은 호출 주체와 업무 책임별로 나눕니다. 인증·동의·게스트 이관 등 후속 상세 계약은 [외부 연동 안내](../index.md)도 함께 확인합니다. 분리 과정에서 API 동작이나 권한을 변경하지 않았습니다.

## 읽기 순서·각 문서

| 문서 | 답하는 질문 |
|---|---|
| [Case·승인·Outbox](cases.md) | Case·승인·Outbox의 요청·응답·실패 조건 |
| [여행·제안 API](trips.md) | 여행·제안 API의 요청·응답·실패 조건 |
| [웹 API와 남용 방어](web-access.md) | 웹 API와 남용 방어의 요청·응답·실패 조건 |
| [브라우저 인증·키·동의](web-auth.md) | 브라우저 인증·키·동의의 요청·응답·실패 조건 |
| [계획 읽기·설문 API](web-intakes.md) | 계획 읽기·설문 API의 요청·응답·실패 조건 |
| [항로 지킴이·위험·안전·지도](web-trips.md) | 항로 지킴이·위험·안전·지도의 요청·응답·실패 조건 |
| [위임 API](delegations.md) | 위임 API의 요청·응답·실패 조건 |
| [배포 중 서비스 공지](../../decisions/D-CS-019-deploy-service-notice.md) | 고객 공지 `GET /v1/web/support/notices` 의 맨 앞에 붙는 배포 공지 한 건(`id` `deploy:<배포 번호>` — 배포 한 번에 하나 · 고정 문구) `[2026-10-20]` `[2026-10-23]` 같은 배포 한 건이 공지사항 게시판(`/notices/board`)에도 남는다 |

## 불변식

고객·tenant 격리, 실행 중복 방지, 승인·감사 계약은 [불변식 카탈로그](../../quality/invariants.md)를 확인합니다.

## 관계

- [외부 연동 안내](../index.md) — 인접 계약
- [MCP 도구](../mcp-tools.md) — 개인 AI 도구 입구

---
type: guide
title: 고객 API·MCP 접속
description: 현재 고객 접속 계약은 REST 엔드포인트·여행 MCP·권한 경계에서 확인합니다
status: draft
domain: travel
---

# 고객 API·MCP 접속

현재 고객 접속 계약은 [REST 엔드포인트](rest-endpoints.md)·[여행 MCP](mcp-tools.md)·[권한 경계](auth-boundary.md)에서 확인합니다. 개인 AI는 사용자 키로 본인 여행만 다룹니다. 고객 웹·MCP가 새 판정·권한 규칙을 따로 만들지 않도록 공통 API 경계를 사용합니다.

고정 principal의 옛 Case MCP 도구와 그 수를 고정하던 시험은 현재 접속·관문에서 제외했습니다. 현재 MCP는 [프로토콜 시험](../../tests/e2e/test_mcp_server.py)에서 인증·본인 여행·쓰기 등록·모듈 비활성을 확인합니다.

개발자용 설정·진단 화면과 고객 요청을 직접 처리하는 상담 역할은 다릅니다. 상주 상담원·운영 관리자 대기를 고객 흐름의 전제로 두지 않습니다. 실제 고객 화면 흐름은 [고객 웹 계약](web-flow-2026-10-09.md)에서 확인합니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--external--index.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구
- [운영 앱 화면 API](admin-screen-api.md) — 운영 앱 검토 자료 · API 계약 협의 · 백엔드/프론트/통합 상태
- [개발자 콘솔 API](dev-console-api.md) — 관리 앱 오류 검색 · 발생 상세의 표시 요구와 API 협의 · 연결 상태


## 이전 절 링크

<a id="external"></a>
<a id="진입-경로-3종"></a>
<a id="각-문서"></a>
<a id="코드-구조"></a>
<a id="mcp와-a2a를-가르는-기준"></a>
<a id="이-영역의-불변식"></a>
<a id="나가는-방향"></a>
<a id="인접-영역"></a>

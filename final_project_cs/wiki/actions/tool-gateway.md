---
type: guide
title: 도구 권한과 호출 예산
description: 도구 호출은 ReadToolbox를 거치며 allowed_tools 밖의 호출·예산 초과를 드러냅니다
status: draft
domain: travel
---

# 도구 권한과 호출 예산

도구 호출은 [ReadToolbox](../../app/tools/read_tools.py)를 거치며 `allowed_tools` 밖의 호출·예산 초과를 드러냅니다. 허용 도구와 예산은 각 Team의 manifest가 정하고, 실제 구현 목록은 코드가 소유합니다. 오래된 도구 개수와 배정 표를 이 페이지에 복제하지 않습니다.

## 읽기·쓰기 경계

현재 여행 Team의 공통 `_read`는 [TravelTeamBase](../../app/domains/travel_ops/instances/_shared/_base.py)에서 `task.allowed_tools`와 `manifest.max_steps`를 공통 게이트에 전달합니다. Context Broker도 Context 구성에 필요한 읽기를 담당합니다. **모든 읽기가 Broker에서만 실행된다는 오래된 설명은 현재 코드와 다릅니다.** TEAM-004의 계약 문구와 실제 경계의 정합성은 [책임 경계](../teams/team-boundary.md)에서 별도로 확인합니다.

Team은 외부 쓰기를 직접 실행하지 않고 `ActionProposal`을 반환합니다. 실행 경계는 근거·권한·필요한 승인·멱등성을 확인합니다. `ToolNotAllowed`·`ScopeDenied`·예산 초과를 조용한 빈 결과로 바꾸지 않습니다.

## 고객 접속과 설정

현재 개인 AI 접속은 [여행 MCP](../external/mcp-tools.md)입니다. 고정 principal의 옛 Case 도구 3개는 실행 대상에서 제외했습니다. 사용자 키·본인 여행·쓰기 등록 스위치는 현재 MCP 계약을 따릅니다. scope 목록은 [guardrails](../../config/guardrails.yaml)의 `security.scopes`가 소유하며 미사용 `order:read`·`return:read`는 제거했습니다.

검증은 [도구 예산](../../tests/unit/tools/test_tool_budget.py), [Team 호출 규율](../../tests/contract/test_team_tool_discipline.py), [scope 계약](../../tests/security/test_scope_contract.py), [현재 MCP 프로토콜](../../tests/e2e/test_mcp_server.py)로 나눕니다. 등록 수를 실행 성공 수로 쓰지 않습니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--actions--tool-gateway.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="tool-gateway"></a>
<a id="책임"></a>
<a id="허용-목록은-manifest에-있다"></a>
<a id="-그런데-team은-read-도구를-직접-안-부른다"></a>
<a id="쓰기-도구"></a>
<a id="toolnotallowed"></a>
<a id="mcp-도구는-3개로-고정"></a>
<a id="scope"></a>
<a id="불변식"></a>
<a id="관계"></a>

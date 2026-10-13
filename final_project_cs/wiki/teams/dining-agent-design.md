---
type: guide
title: Dining 에이전트 설계 안내
description: 현행 하이브리드 경계와 과거 LLM 전면 적용 제안을 분리한다
status: draft
domain: travel
---

# Dining 에이전트 설계 안내

현재 Dining 에이전트의 코드 판정·자유 질문 LLM 경계는 [Dining 하이브리드 분류표](dining-mcp-boundary.md)를 먼저 읽습니다. 에이전트 팀 구현 경로는 [코드 배치](code-layout.md), 공통 출력 계약은 [Team 계약](team-contract/index.md)입니다.

아래 원문은 체크리스트·유스케이스·LLM 전면 도입을 제안했던 설계 자료입니다. 그중 도구·에이전트 구성은 후속 하이브리드 경계와 다르므로 현재 확정 구현으로 사용하지 않습니다. 평가 자료로 활용할 항목도 현재 계약에 맞춰 검증해야 합니다.

## 시점별 기록

[정정 전 전체 본문](../records/reports/2026-10-11_dining-agent-design.md) — 날짜별 계약·검증·초안을 보존했습니다. 날짜가 붙은 결과를 오늘의 전체 통과나 운영 반영으로 읽지 않습니다. 후속 결정이 없는 계약 조항은 원문의 적용 범위를 확인합니다.

### 기존 링크 연결

<a id="0-왜-바꾸는가"></a> [기존 절: 0. 왜 바꾸는가](../records/reports/2026-10-11_dining-agent-design.md#0-왜-바꾸는가)
<a id="1-체크리스트--llm-평가지표"></a> [기존 절: 1. 체크리스트 — LLM 평가지표](../records/reports/2026-10-11_dining-agent-design.md#1-체크리스트--llm-평가지표)
<a id="1-1-정제-원칙"></a> [기존 절: 1-1. 정제 원칙](../records/reports/2026-10-11_dining-agent-design.md#1-1-정제-원칙)
<a id="1-2-평가-항목-6개"></a> [기존 절: 1-2. 평가 항목 (6개)](../records/reports/2026-10-11_dining-agent-design.md#1-2-평가-항목-6개)
<a id="1-3-가려던-구역이-닫혔나-미해결-질문"></a> [기존 절: 1-3. 「가려던 구역이 닫혔나」 (미해결 질문)](../records/reports/2026-10-11_dining-agent-design.md#1-3-가려던-구역이-닫혔나-미해결-질문)
<a id="1-4-채점-규칙"></a> [기존 절: 1-4. 채점 규칙](../records/reports/2026-10-11_dining-agent-design.md#1-4-채점-규칙)
<a id="2-mcp-도구로-바꿔-llm-손에-쥐여-준다"></a> [기존 절: 2. MCP 도구로 바꿔 LLM 손에 쥐여 준다](../records/reports/2026-10-11_dining-agent-design.md#2-mcp-도구로-바꿔-llm-손에-쥐여-준다)
<a id="2-1-지금은-어떻게-도는가"></a> [기존 절: 2-1. 지금은 어떻게 도는가](../records/reports/2026-10-11_dining-agent-design.md#2-1-지금은-어떻게-도는가)
<a id="2-2-mcp-란"></a> [기존 절: 2-2. MCP 란](../records/reports/2026-10-11_dining-agent-design.md#2-2-mcp-란)
<a id="2-3-한-번의-판정이-어떻게-흐르는가-예시"></a> [기존 절: 2-3. 한 번의 판정이 어떻게 흐르는가 (예시)](../records/reports/2026-10-11_dining-agent-design.md#2-3-한-번의-판정이-어떻게-흐르는가-예시)
<a id="2-4-dining-mcp-도구-명세"></a> [기존 절: 2-4. Dining MCP 도구 명세](../records/reports/2026-10-11_dining-agent-design.md#2-4-dining-mcp-도구-명세)
<a id="2-5-구현-방식"></a> [기존 절: 2-5. 구현 방식](../records/reports/2026-10-11_dining-agent-design.md#2-5-구현-방식)
<a id="3-에이전트-설계"></a> [기존 절: 3. 에이전트 설계](../records/reports/2026-10-11_dining-agent-design.md#3-에이전트-설계)
<a id="3-1-멀티에이전트-구성"></a> [기존 절: 3-1. 멀티에이전트 구성](../records/reports/2026-10-11_dining-agent-design.md#3-1-멀티에이전트-구성)
<a id="3-2-역할과-세부-작업-프롬프트-골격"></a> [기존 절: 3-2. 역할과 세부 작업 (프롬프트 골격)](../records/reports/2026-10-11_dining-agent-design.md#3-2-역할과-세부-작업-프롬프트-골격)
<a id="3-3-출력-모양"></a> [기존 절: 3-3. 출력 모양](../records/reports/2026-10-11_dining-agent-design.md#3-3-출력-모양)
<a id="3-4-분기와-병렬"></a> [기존 절: 3-4. 분기와 병렬](../records/reports/2026-10-11_dining-agent-design.md#3-4-분기와-병렬)
<a id="3-5-가드-llm-바깥-코드로"></a> [기존 절: 3-5. 가드 (LLM 바깥, 코드로)](../records/reports/2026-10-11_dining-agent-design.md#3-5-가드-llm-바깥-코드로)
<a id="4-유스케이스"></a> [기존 절: 4. 유스케이스](../records/reports/2026-10-11_dining-agent-design.md#4-유스케이스)
<a id="4-1-넓게--목표별"></a> [기존 절: 4-1. 넓게 — 목표별](../records/reports/2026-10-11_dining-agent-design.md#4-1-넓게--목표별)
<a id="4-2-작게--유스케이스별"></a> [기존 절: 4-2. 작게 — 유스케이스별](../records/reports/2026-10-11_dining-agent-design.md#4-2-작게--유스케이스별)
<a id="5-멀티에이전트-다이어그램"></a> [기존 절: 5. 멀티에이전트 다이어그램](../records/reports/2026-10-11_dining-agent-design.md#5-멀티에이전트-다이어그램)
<a id="6-평가-사이클과-보고서"></a> [기존 절: 6. 평가 사이클과 보고서](../records/reports/2026-10-11_dining-agent-design.md#6-평가-사이클과-보고서)
<a id="6-1-사이클-멘토"></a> [기존 절: 6-1. 사이클 (멘토)](../records/reports/2026-10-11_dining-agent-design.md#6-1-사이클-멘토)
<a id="6-2-정답-세트와-지표"></a> [기존 절: 6-2. 정답 세트와 지표](../records/reports/2026-10-11_dining-agent-design.md#6-2-정답-세트와-지표)
<a id="6-3-보고서에-넣을-것"></a> [기존 절: 6-3. 보고서에 넣을 것](../records/reports/2026-10-11_dining-agent-design.md#6-3-보고서에-넣을-것)
<a id="7-멘토에게-할-질문"></a> [기존 절: 7. 멘토에게 할 질문](../records/reports/2026-10-11_dining-agent-design.md#7-멘토에게-할-질문)
<a id="8-결정이-필요한-것"></a> [기존 절: 8. 결정이 필요한 것](../records/reports/2026-10-11_dining-agent-design.md#8-결정이-필요한-것)
<a id="9-작업-순서-제안"></a> [기존 절: 9. 작업 순서 (제안)](../records/reports/2026-10-11_dining-agent-design.md#9-작업-순서-제안)

## 관계

- [영역 안내](index.md) — 인접 문서와 읽기 순서

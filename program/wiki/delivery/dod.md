---
type: plan
title: 완료 기준 (DoD)
description: 29항목. 1~28은 이전 판 번호를 보존하고 29는 Response Generation & Review 검증 신규
status: draft
tags: [release, evaluation]
owners: [human:미배정]
size_exempt: true
size_exempt_reason: 체크리스트. 통으로 훑어야 의미가 있다
---

# 완료 기준 (DoD)

**29항목이다.** 1~28은 이전 판 번호를 보존하고 29는 Response Generation & Review 검증으로 신규 추가했다.

번호를 보존하는 이유는 다른 문서와 티켓이 `DoD-8` 같은 식으로 참조하고 있어서다. **번호를 다시 매기면 참조가 전부 깨진다.**

## 상태

`[미확보]` 항목별 달성 여부는 아직 정리하지 않았다. 이관 시 실제 상태를 채운다.

## 성격별 분류

| 성격 | 무엇을 검증하나 |
|---|---|
| 계약 | Core/Team 인터페이스가 고정돼 있는가 |
| 격리 | Core가 도메인을 모르는가 |
| 안전 | 승인·idempotency·감사가 동작하는가 |
| 근거 | 할루시네이션 방어가 동작하는가 |
| 평가 | 지표가 재현 가능하게 산출되는가 |
| 연동 | REST·MCP·A2A 경로가 동작하는가 |

## 대표 항목

전체 목록은 이관 시 채운다. 지금은 자주 참조되는 것만 둔다.

| # | 내용 | 검증 |
|---|---|---|
| DoD-8 | Team-플러그인 아키텍처가 동작한다 | Core 격리 위반 0 |
| DoD-24·25 | 근거 대조 방어 코드 | 골든셋 방어 지표 |
| DoD-28 | 파인튜닝 파이프라인 | 학습 완주 + 비교 평가 |
| DoD-29 | Response Generation & Review 검증 | `[미확보]` |

## 완료 판정 원칙

**"코드가 있다"가 아니라 "실행으로 증명된다"가 완료다.**

| 안 됨 | 됨 |
|---|---|
| 승인 로직을 구현했다 | 승인 없이 실행하면 테스트가 실패한다 |
| idempotency를 넣었다 | 동일 요청 10회 = 1 side effect가 측정된다 |
| Core를 격리했다 | 도메인 어휘가 들어오면 테스트가 붉어진다 |

이게 [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md)와 DoD가 연결되는 지점이다. **불변식 대부분이 DoD 항목의 자동 판정이다.**

## 관계

- [timeline.md](timeline.md) — 언제까지
- [milestones/index.md](milestones/index.md) — 발표별 목표
- [../evaluation/index.md](../evaluation/index.md) — 증명 방법
- [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) — 자동 판정

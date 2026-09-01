---
type: plan
title: 역할과 소유 경계
description: 6명이 무엇을 소유하는가. 소유가 겹치면 이중 장부가 된다
status: draft
tags: [release]
owners: [human:미배정]
---

# 역할과 소유 경계

`[미확보]` 실제 담당자 배정은 팀에서 확정한 뒤 채운다. 여기서는 **경계의 모양**만 정한다.

## 소유 원칙

**한 영역에 한 명.** 소유자는 그 영역의 결정권과 리뷰 책임을 갖는다.

소유가 겹치면 두 가지가 나빠진다.

1. 아무도 안 고친다
2. 둘이 다르게 고쳐서 이중 장부가 된다

## 코드 소유

| 영역 | 무엇을 소유 | 문서 |
|---|---|---|
| Core (Runtime) | Case·Controller·Shared State·Registry | [`runtime/`](../../final_project_cs/wiki/runtime/index.md) |
| Actions | 승인·idempotency·outbox·근거 대조 | [`actions/`](../../final_project_cs/wiki/actions/index.md) |
| Context | Broker·RAG·Memory·예산 | [`context/`](../../final_project_cs/wiki/context/index.md) |
| Teams | 개별 Team 모듈 | [`teams/`](../../final_project_cs/wiki/teams/index.md) |
| Data | 스키마·마이그레이션·tenant 격리 | [`data/`](../../final_project_cs/wiki/data/index.md) |
| Evaluation | 하네스·골든셋·지표 | [`quality/`](../../final_project_cs/wiki/quality/index.md) |

## 문서 소유

| 영역 | 소유 |
|---|---|
| `product/` | 기획 |
| `business/` | 기획 |
| `architecture/` | Core 담당 |
| `delivery/` | 팀 리드 |
| `evaluation/` | 평가 담당 |
| `research/` | 조사한 사람 |
| `decisions/` | 결정한 사람 |
| `governance/` | 팀 리드 |

## 경계를 넘는 작업

혼자 못 정하는 것들.

| 작업 | 누가 함께 |
|---|---|
| Team 계약 변경 | Core + 모든 Team 담당 |
| 스키마 변경 | Data + 영향받는 Team |
| 승인 경계 조정 | Actions + 기획 |
| 지표 정의 변경 | Evaluation + 기획 |
| 저장소 간 계약 | 양쪽 저장소 소유자 |

**계약 변경은 `contract_version` 상향과 회귀 테스트를 함께 한다.**

## 검증 쇼핑몰과의 경계

`[미확보]` 협의 창구가 정해지지 않았다.

| 우리가 주는 것 | 받아야 하는 것 |
|---|---|
| Action 실행 요청 | 결제 구성 스냅샷 |
| 근거 대조 결과 | 쇼핑몰이 계산한 환불 예정액 |

상세는 [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md).

## 관계

- [timeline.md](timeline.md) — 일정
- [../governance/review-policy.md](../governance/review-policy.md) — 문서 리뷰 규칙
- [../architecture/repository-map.md](../architecture/repository-map.md) — 저장소별 소유

---
type: guide
title: A-COP 시작하기
description: A-COP이 무엇이고 어느 문서부터 읽어야 하는지 알려주는 진입점
status: draft
---

# A-COP 시작하기

A-COP은 고객 응대를 구성하는 B2B Agentic Operations Platform이다. 문의를 Case로 만들고, 업무별 Agent Team이 협업하고, 위험한 동작은 사람이 승인한다.

## 30초 요약

| | |
|---|---|
| 무엇 | 멀티에이전트 고객운영의 통제·검증층 |
| 핵심 주장 | 동작하게 만들기는 쉽다. **믿을 수 있게** 만들기가 어렵다 |
| 릴리스 대상 | `final_project_cs` |
| 일정 | 중간발표 2026-09-15 · 최종발표 2026-10-26 |
| 팀 | 6명 |

**말하지 않는 것.** "LLM으로 고객 문의를 자동응답한다"로 설명하면 시장의 기존 제품과 구분되지 않는다. 자동화율을 앞세우지 않고, 잘못 자동화하지 않는 지점과 인계 품질을 함께 제시한다.

## 지금 무엇을 하려는가

| 하려는 일 | 여기부터 |
|---|---|
| 제품이 뭔지 알고 싶다 | [product/positioning.md](product/positioning.md) |
| 누가 왜 쓰는지 알고 싶다 | [product/personas.md](product/personas.md) |
| 코드를 고치려 한다 | [`final_project_cs/wiki/quickstart.md`](../final_project_cs/wiki/quickstart.md) |
| Team을 추가하려 한다 | [architecture/core-vs-team.md](architecture/core-vs-team.md) |
| 평가를 돌리려 한다 | [evaluation/protocol.md](evaluation/protocol.md) |
| 왜 이렇게 설계했는지 궁금하다 | [decisions/index.md](decisions/index.md) |
| 사업성 숫자가 필요하다 | [business/unit-economics.md](business/unit-economics.md) |
| 발표 자료를 만든다 | [delivery/milestones/index.md](delivery/milestones/index.md) |
| 문서를 쓰려 한다 | [governance/document-standard.md](governance/document-standard.md) |

## 저장소 지도

| 저장소 | 역할 | wiki |
|---|---|---|
| `program` | 계획·결정·평가 기준·사업성 | 여기 |
| `final_project_cs` | **릴리스 대상** | [wiki](../final_project_cs/wiki/index.md) |
| `final_project_sample` | 계약 선검증. cs로 이식하는 관계 | [wiki](../final_project_sample/wiki/index.md) |
| `acop_dojo` | 학습 도장 | [wiki](../acop_dojo/wiki/index.md) |
| `datasets` | 데이터셋 | [wiki](../datasets/wiki/index.md) |

sample의 예시 Team과 검증 상태를 cs의 릴리스 완료로 간주하지 않는다.

## 사실이 충돌하면

1. 실행되는 테스트 결과
2. 해당 저장소 `CLAUDE.md`의 기준 사실 표
3. `status: stable` 문서
4. 중앙 허브 문서
5. `status: draft` 문서

## 다음

[index.md](index.md)가 8개 영역의 지도다.

---
type: guide
title: A-COP 시작하기
description: A-COP이 무엇이고 어느 문서부터 읽어야 하는지 알려주는 진입점. 도메인은 여행이다
status: draft
domain: travel
---

# A-COP 시작하기

★**[2026-09-08 판올림] 도메인이 여행으로 바뀌었다.** 이 wiki의 상당수 문서는 아직 쇼핑몰 CS 기준이다 — 읽을 때 계획서 v10과 대조한다. 옛 도메인 서술은 지우지 않고 그 시점 사실로 남긴다.

A-COP은 **여행 지속관리 CS 플랫폼**이다. 외부 에이전트나 LLM이 만든 일정을 받아 **현실에서 성립하는지 검증하고, 여행이 끝날 때까지 상황 변화를 먼저 감지해 남은 일정을 조정한다.**

**계획을 만드는 것은 우리 일이 아니다.** 계획 생성기를 만들면 트리플·Mindtrip·범용 에이전트와 정면으로 겹친다. 우리 가치는 계획이 현실에서 성립하는지 확인하는 데 있다 → 계획서 v10 §4-A.

## 30초 요약

| | |
|---|---|
| 무엇 | 여행 일정의 검증·감시·조정층. 계획 생성기가 아니다 |
| 핵심 주장 | 동작하게 만들기는 쉽다. **믿을 수 있게** 만들기가 어렵다 (도메인이 바뀌어도 그대로다) |
| 1순위 고객 | **처음 한국에 자유여행 오는 외국인 개인·친구 그룹** (인바운드) |
| 접점 | 고객의 개인 에이전트. **API로만** 만난다. 자체 앱·음성은 만들지 않는다 |
| 판매 형태 | 팀당 여행 이용권. 기준 7일·4인·2도시 59,000원(VAT 포함) `[미확보]` 수용 여부 미검증 |
| 릴리스 대상 | `final_project_cs` |
| 일정 | 최종발표 2026-10-26 — 2026-09-08 기준 **7주**. MVP는 구현 단계 1(계획과 검증)까지 |
| 팀 | 6명 |

**승계한 것과 버린 것.** 코어 계약·Case 생명주기·동시성·감사·평가 하네스는 그대로 쓴다. Team 모듈과 도메인 데이터는 전량 신규다. 커머스 Team 4종과 VOC & Store Manager는 MVP 경로에서 빠졌다 → v10 §0-2.

**말하지 않는 것.** "LLM으로 여행 계획을 짜 준다"로 설명하면 기존 제품과 구분되지 않는다. 우리가 파는 것은 **계획이 성립하는지 확인하고 여행 중 변화를 먼저 잡는 것**이다.

## 지금 무엇을 하려는가

| 하려는 일 | 여기부터 |
|---|---|
| 제품이 뭔지 알고 싶다 | 계획서 v10 §0-1·§1 (**wiki의 product/는 아직 쇼핑몰 기준**) |
| 무엇을 만들고 안 만드나 | [product/scope.md](product/scope.md) — 여행 MVP 범위로 갱신됨 |
| 누가 왜 쓰는지 알고 싶다 | v10 §1·§2. wiki [product/personas.md](product/personas.md)는 쇼핑몰 페르소나다 |
| 코드를 고치려 한다 | [`final_project_cs/wiki/quickstart.md`](../final_project_cs/wiki/quickstart.md) |
| Team을 추가하려 한다 | [architecture/core-vs-team.md](architecture/core-vs-team.md) — 나누는 기준은 도메인과 무관하게 유효하다. 여행 Team 목록은 v10 §5 |
| 평가를 돌리려 한다 | [evaluation/protocol.md](evaluation/protocol.md) — 하네스는 승계, **정답 시나리오는 교체 대상**(골든셋 72건은 쇼핑몰) |
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
4. 계획서 v10 (범위·결정·일정)
5. 중앙 허브 문서
6. `status: draft` 문서

★**도메인 사실이 충돌하면 v10이 이긴다.** 2026-09-08 이전 문서는 쇼핑몰 기준으로 쓰였다.

## 다음

[index.md](index.md)가 8개 영역의 지도다. 도메인 교체로 무엇이 낡았는지는 그 페이지의 「여행 판올림」 절에 있다.

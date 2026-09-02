---
type: plan
title: 전체 일정
description: 선행 11일 + 공식 1W~9W. 중간발표 09-15, 최종발표 10-26
status: draft
tags: [release]
owners: [human:미배정]
---

# 전체 일정

## 구조

```text
선행    2026-08-17 ~ 08-27   11일   ✅ 완료
공식    1W ~ 9W
중간발표 2026-09-15
최종발표 2026-10-26
```

`[실측]` 오늘 2026-09-01 기준 중간발표 D-14, 최종발표 D-55.

## 지금 위치

선행 기간에 끝난 것.

| | 상태 |
|---|---|
| Core/Team 계약 고정 | 완료 |
| sample에서 Composer 쓰기채널 검증 | 완료 |
| 골든셋 72건 구성 | 완료 |
| 평가 하네스 (A/B/Proposed) | 완료 |
| 파인튜닝 파이프라인 | 완료 (결과는 부정적) |

## 중간발표까지 (D-14)

**목표는 "동작한다"이다.** "믿을 수 있다"는 최종발표 몫이다.

| 항목 | 소요 | 왜 지금 |
|---|---|---|
| 4070 SUPER 추론 실측 | 반나절 | 자체호스팅 논거 전체가 여기 달림 |
| 검토·승인 소요시간 실측 | 반나절 | 사업성 72% 절감이 여기 달림 |
| 오류 1건당 손실 집계 | 하루 | 가격 논거의 상한 |
| 환불 계산식 조치 판단 | 판단만 | 할인 붙으면 그날 터짐 |

**앞의 셋은 합쳐서 이틀이다.** 하고 나면 [../business/index.md](../business/index.md) 전체가 `[추정]`에서 벗어난다.

## 구현 6단계

`[실측]` v8 §14. **주차와 별개로 무엇을 먼저 만드는가의 순서다.**

| 단계 | 무엇 |
|---|---|
| 1 | 도메인·Case·ERD·상태·**Contract 확정** |
| 2 | Core Basement MVP · Registry · **세 Port** · Context Broker · Shared State |
| 3 | Team 구현 + RAG. **Return & Refund는 계약 + Mock** · Catalog는 A2A 기본 설계와 Agent Card |
| 4 | REST/MCP 외부 진입점 + **A2A 보안·실패·취소 처리** |
| 5 | UI와 trace/approval |
| 6 | 평가와 고도화 |

**1단계가 계약 확정인 게 중요하다.** 계약이 흔들리면 뒤의 모든 단계가 다시 간다. → 1W 금요일 Contract Freeze Day

`[실측]` **Registry 등록 수와 실제 구현 수는 별도로 검증한다.** 등록만 하고 구현이 없으면 목록은 늘어나 보인다.

## 주차별 계획

`[실측]` v8 §25에서 이관. 공식 부트캠프 일정 기준.

**Commerce Ops Pack(Procurement+Order·Fulfillment·Return·Catalog) 작업은 검증 쇼핑몰 프로젝트와 연계된 범위**이며, VOC·Response Generation & Review와 달리 그 프로젝트 진행에 따라 조정될 수 있다.

| 주차 | 기간 | 공식 산출물 |
|---|---|---|
| 선행 | 8/17~8/27 (11일) | 초안 준비 |
| 1W | 8/28~9/3 | WBS · 프로젝트 기획서 · 요구사항 정의서 |
| 2W | 9/4~9/10 | 수집 데이터 보고서 · DB/저장소 설계 문서 |
| **3W** | **9/11~9/17** | 데이터 전처리 결과서 · ML/DL 학습결과서 · 학습 모델 · **중간발표 PT (9/15)** |
| 4W | 9/18~9/28 (11일) | 신규 산출물 없음 |
| 5W | 9/29~10/6 | 벡터DB/GraphDB 결과서 · AI 시스템 아키텍처 · 멀티에이전트 테스트 보고서 · 요구사항 정의서(업데이트) · 화면설계서 |
| 6W | 10/7~10/14 | 신규 산출물 없음 |
| 7W | 10/15~10/21 | LLM 연동 웹 애플리케이션 · 시스템 구성도 · 서비스 테스트 보고서 |
| 8W | 10/21~10/24 (4일) | 최종발표 PT · 개발 소스코드 · 시연영상 |
| 9W | — | 8W 보완, **최종발표 10/26** |

### 역할별 배분

| 주차 | 코어 1 | 코어 2 | 모델 3명 | 검증·프론트 |
|---|---|---|---|---|
| 1W | 선행 초안 동결, CAS·transition 경계 정리 | **Contract Freeze**, REST/MCP·scope skeleton | 검증 쇼핑몰 5개 Team 계약 정리 | harness skeleton·UI fixture |
| 2W | Case·Action 상태와 Registry를 seed에 맞춤 | REST/MCP skeleton·저장소 경계 문서화 | demo seed·knowledge documents·RAG 적재 범위 | 평가 harness 입력·데이터 fixture 고정 |
| 3W | Controller·MessageBus를 중간발표 경로에 연결 | Action/approval 경계 연결 | PII masking·Case fixture·RAG corpus 정리, Team 단독 테스트 | Case UI·중간발표 demo |
| 4W | Context Broker·projection 안정화 | Tool adapter·audit 보완 | RAG 25/300~400과 Team 통합 보완 | trace 화면·발표 피드백 반영 |
| 5W | Outbox·retry·WAIT/RESUME, GraphStorePort·SQL adapter | idempotency·unknown, MCP/A2A 보안 경계 | 검증 쇼핑몰 Team 통합, Catalog A2A 경계 테스트 | API/UI contract, Graph gate 측정 |
| 6W | Shared State merge·재처리 경로 보완 | A2A 실패·타임아웃·취소·인증, 승인·감사 회귀 | VOC 위임 제안·Response GEN/REV·ActionProposal 흐름 | end-to-end demo 회귀 점검 |
| 7W | GraphStorePort·SQL adapter·시스템 구성도 고정 | MCP/A2A 보안·서비스 경계 점검 | 관계 질의 fixture·Team 성능 점검 | 운영 UI·LLM 연동, 서비스 테스트 결과 |
| 8W | 재처리·경합 테스트, DoD 근거 최종 확인 | input-required·callback·cancel, 승인·감사 흐름 확인 | LOCAL Team과 Catalog A2A 동일 결과 경로 동결 | 모듈별 golden/holdout 실행, 발표·시연영상 동결 |
| 9W | 버그 수정, DoD·Alembic gate 확인 | 승인·보안 회귀, 배포·감사 점검 | Team 성능 수정, 시나리오 잔여 결함 표시 | bootstrap/McNemar, 최종 리포트·실행 절차 점검 |

### 두 가지 고정점

**1W 금요일은 Contract Freeze Day다.** 계약을 여기서 얼린다.

**Core 1과 Core 2의 Alembic revision은 단일 브랜치로 유지한다.** 마이그레이션이 갈리면 병합이 지옥이 된다.

## 최종발표까지

**목표는 "믿을 수 있다"이다.**

| 단계 | 내용 |
|---|---|
| Team 착수 완료 | LOCAL 4개 + Remote A2A PoC 1개 |
| 평가 전체 실행 | 60 + 20, 3회 반복, 통계 처리 |
| 근거 지표 확정 | 정합률·초과율·기권율 |
| DoD 29항목 | [dod.md](dod.md) |

## 1번 리스크 — 범위 과대

기준선으로 통제한다.

```
도메인 1개 · 착수 LOCAL Team 4개 · Remote A2A PoC 1개
```

**Team 수는 아키텍처 상한이 아니다.** Registry 등록으로 확장되는 값이고, 확장 여부는 **일정과 평가 여력**으로 판단한다. Team이 늘면 골든셋과 라우팅 평가 축도 같이 늘어난다.

## 일정에 걸린 외부 의존

| 의존 | 무엇이 막히나 |
|---|---|
| 검증 쇼핑몰 진행 범위 | Commerce Ops Pack 4개 Team |
| 검증 쇼핑몰 계약 협의 | 환불 계산식 전환 ([D-001](../decisions/D-001-payment-ownership.md)) |

**Commerce Ops Pack은 일정에 따라 조정된다.** CS Pack 2종만 확정이다.

## 관계

- [milestones/index.md](milestones/index.md) — 두 발표
- [dod.md](dod.md) — 완료 기준
- [roles.md](roles.md) — 누가 무엇을
- [../product/scope.md](../product/scope.md) — 범위 통제

---
type: plan
title: 완료 기준 (DoD)
description: 29항목과 검증 방법. 1~28은 이전 판 번호를 보존하고 29는 신규
status: draft
tags: [release, evaluation]
owners: [human:미배정]
size_exempt: true
size_exempt_reason: 체크리스트. 통으로 훑어야 의미가 있다
---

# 완료 기준 (DoD)

`[실측]` v8 §27에서 이관. **29항목이다.**

**각 항목은 evidence 문서와 검증 방법을 함께 남긴다.** 1~18은 v5의 의미와 순서를 보존한다.

번호를 보존하는 이유는 다른 문서와 티켓이 `DoD-8` 같은 식으로 참조하기 때문이다. **다시 매기면 참조가 전부 깨진다.**

## 달성 현황

`[실측]` 2026-08-30 기준 (`final_project_cs/CLAUDE.md`)

| | 값 |
|---|---|
| evidence 문서 | **28/28** |
| 통과 | **24** |
| 부분통과 | 4 |
| 미착수 | 0 |
| **29번** | **미평가** — v8 신설 |

**부분통과 4개** — 15(judge agreement) · 17(파일시스템 gate 재현) · 23(consumer 1종뿐) · 28(파인튜닝·방어지표)

## 1~10 — 기반

| # | 기준 | 검증 방법 |
|---|---|---|
| 1 | 원본 v4 hash 불변 | 파일 hash 비교 |
| 2 | 상태전이 규약 | `transition_case` 통합 테스트와 허용 전이 표 대조 |
| 3 | 동시성·append-only·replay | CAS race, event replay fixture, SQL 결과 검증 |
| 4 | checkpoint/projection 분리 | graph revision 변경 및 projection replay test |
| 5 | ContextPack ≤ 12,000 | token counter와 `degraded`·`omissions` assertion |
| 6 | 정책/FAQ 25건·300~400 chunk | ingest count와 metadata/embedding test |
| 7 | tenant scope·PII redaction | cross-tenant security test와 redaction snapshot |
| 8 | TeamModule·manifest 호환 | Protocol contract와 major/minor version test |
| 9 | 인라인 분류 | 모든 Case 생성 fixture에서 분류 event 확인 |
| 10 | 일일 배치 report | count·ratio·threshold alert scheduled-job test |

## 11~18 — 안전과 평가

| # | 기준 | 검증 방법 |
|---|---|---|
| 11 | action·approval·idempotency·unknown | 같은 요청 반복, approval matrix, timeout test |
| 12 | outbox 원자성·worker replay | failure injection 후 pending row와 replay test |
| 13 | MVP REST 5 + MCP 3 contract | OpenAPI/MCP schema 및 endpoint 통합 테스트. **5가 상한이 아님**을 추가 endpoint fixture로 검증 |
| 14 | API key scope | read/write/MCP unauthorized matrix |
| **15** | A/B/Proposed·holdout | 60건×3회 harness log와 holdout checksum — **부분통과** |
| 16 | bootstrap CI·McNemar·한계 | stats unit test와 report 산식 검토 |
| **17** | milestone gate·기능 동결 | CI gate, Contract Freeze 기록, Alembic upgrade/downgrade — **부분통과** |
| 18 | Case UI·trace·approval·VOC | E2E 시나리오에서 상태·trace·승인·report 표시 |

## 19~23 — 교체 가능성

| # | 기준 | 검증 방법 |
|---|---|---|
| 19 | LOCAL/A2A가 동일 `TeamResult`로 정규화 | 두 Executor contract test에서 canonical JSON 비교 |
| 20 | `TeamExecutorPort` 교체 시 Controller 불변 | adapter 교체 test와 Controller import boundary 정적 검사 |
| 21 | `SqlGraphAdapter` 관계 질의 3종 | Case→Issue→Policy, Issue→Team, Case→Action fixture |
| 22 | **Team의 직접 Tool 호출 금지** | Team module **AST/import 정적 검사**와 runtime spy |
| **23** | 모든 consumer at-least-once idempotency | 동일 message 2회 전달 replay test — **부분통과 (consumer 1종뿐)** |

**22번이 중요하다.** AST·import 정적 검사를 하라고 v8이 이미 지시하고 있다. → `INV-CS-TEAM-004`가 아직 `review`인 것이 이 항목의 미완성이다.

## 24~29 — 근거와 확장

| # | 기준 | 검증 방법 |
|---|---|---|
| 24 | ActionProposal 근거 대조·실행 차단 | 없는 `order_id`/금액을 제안하도록 유도한 fixture에서 실행 차단·`escalated`·감사 로그 |
| 25 | degraded Context 자동 실행 금지 | `ContextPack.degraded=true` fixture에서 proposal 미실행·`escalated` |
| 26 | A2A Catalog Verification 왕복 | Agent Card 발견 → working → input-required → 추가 입력 → Artifact 완료, `waiting_external`/resume |
| 27 | A2A 실패·타임아웃·취소·인증 | 더미 Remote Agent에서 각 결과가 `unknown`/`escalated`/`cancelled`로 기록 |
| **28** | 파인튜닝 경로와 방어 지표 | 공개 1차·알파 2차 모델을 같은 golden/holdout에서 비교, 분모와 CI 기록 — **부분통과** |
| **29** | **Response Generation & Review 검증** | GEN→REV 두 호출 흐름 실행, REV 반려 시 재시도 상한, **개인정보가 섞인 응답을 REV가 차단** — **미평가** |

## 완료 판정 원칙

**"코드가 있다"가 아니라 "실행으로 증명된다"가 완료다.**

| 안 됨 | 됨 |
|---|---|
| 승인 로직을 구현했다 | 승인 없이 실행하면 테스트가 실패한다 |
| idempotency를 넣었다 | 동일 요청 10회 = 1 side effect가 측정된다 |
| Core를 격리했다 | 도메인 어휘가 들어오면 테스트가 붉어진다 |

이게 [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md)와 DoD가 연결되는 지점이다. **불변식 대부분이 DoD 항목의 자동 판정이다.**

## ★ 완료 판정 기준 — 네 가지를 다 만족해야 한다

`[실측]` `A-COP_DoD_잔여작업_계획.md` §6

> **코드가 존재하는 것만으로 완료로 보지 않는다.**

| 조건 | |
|---|---|
| ① | 지정한 테스트가 **실제 입력 fixture** 를 사용한다 |
| ② | **실패·중복·경계 조건**을 확인한다 |
| ③ | 재현 가능한 **report 또는 migration artifact** 를 남긴다 |
| ④ | **CI gate 에 편입**한다 |

**②가 놓치기 쉽다.** 정상 경로만 도는 테스트는 완료 근거가 안 된다.

`[실측]` 원본이 스스로 밝힌 한계.

> 이 계획에서 제안한 테스트는 **실행하지 않은 상태**이며, 구현 단계에서 추가한 뒤 CI gate 에 편입한다.

**계획에 적힌 테스트가 아직 없다는 뜻이다.**

## 부분통과 4개가 남은 이유

| # | 무엇이 부족한가 | 필요한 것 |
|---|---|---|
| 15 | judge agreement | **사람 라벨 20건** |
| 17 | 파일시스템 gate 재현 | 재현 절차 |
| 23 | consumer가 1종뿐 | 두 번째 consumer |
| 28 | 파인튜닝 방어지표 | 3B 모델 재평가 |

**15번이 가장 중요하다.** judge가 사람과 얼마나 맞는지 모르는 상태로는 RC가 아니다.

## 관계

- [timeline.md](timeline.md) — 언제까지
- [milestones/index.md](milestones/index.md) — 발표별 목표
- [../evaluation/index.md](../evaluation/index.md) — 증명 방법
- [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) — 자동 판정
- [`quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 평가 실행

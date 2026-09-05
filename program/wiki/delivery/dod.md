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

`[실측]` **2026-09-03 재측정.** evidence 파일 29건의 `판정:` 줄을 직접 세었다.

| | 값 |
|---|---|
| evidence 문서 | **29/29** |
| **통과** | **26** |
| **부분통과** | **3** |
| 미착수 | 0 |

**부분통과 3개** — 15(A/B harness) · 17(마일스톤 게이트) · 28(파인튜닝·방어지표)

### 앞서 적었던 값이 낡았다

| | 이 문서가 적던 값 | 실측 |
|---|---|---|
| evidence | 28/28 | **29/29** |
| 통과 | 24 | **26** |
| 부분통과 | **4** (15·17·**23**·28) | **3** (15·17·28) |
| 29번 | **미평가** | **통과** (2026-08-20 갱신) |

`[실측]` **DoD-23 은 통과로 바뀌었다** — 2026-08-20 에 consumer 계약 테스트가 붙었다. **29번도 같은 날 완료됐다.**

**`program/research/index.md` 가 정본으로 적고 있던 값과 이제 맞는다.**

### ★ 그래도 "29개 전부 통과"라고 말하면 안 된다

`[실측]` **DoD-22 는 통과로 적혀 있지만 근거가 사라졌다.** 인용한 테스트 소스가 없고 `.pyc` 만 남았다. → [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md)

**통과 26 중 근거를 확인한 것은 9건뿐이다.**

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
| 23 | 모든 consumer at-least-once idempotency | 동일 message 2회 전달 replay test — **통과** (2026-08-20). consumer는 여전히 outbox worker 1종뿐이지만, `consumer_contract_factories`에 등록된 모든 consumer가 계약 테스트 3종을 강제로 통과해야 하는 구조라 **다음 consumer가 검사 없이 추가될 수 없다** → [`actions/idempotency.md`](../../final_project_cs/wiki/actions/idempotency.md) |

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

## 부분통과 3개가 남은 이유

| # | 무엇이 부족한가 | 필요한 것 |
|---|---|---|
| 15 | judge agreement | **사람 라벨 20건** |
| 17 | RC 선언 — **15 에 종속** | 15 와 동일 (아래) |
| 28 | 파인튜닝 방어지표 | 3B 모델 재평가 |

`[실측]` **이 표는 2026-09-06 전까지 "4개"였고 23번(두 번째 consumer 필요)이 들어 있었다.** 위 달성 현황이 이미 "23은 2026-08-20 통과"라고 적고 있었는데 이 표가 안 따라와 한 문서 안에서 모순이었다. 23은 두 번째 consumer가 생겨서가 아니라 **"모든 consumer"를 미래형으로 강제하는 계약 테스트**가 생겨서 통과다 — 실제 두 번째 consumer가 붙을 때 그 계약을 통과하는지가 진짜 증명이라고 evidence가 스스로 적어 뒀다.

**15번이 가장 중요하다.** judge가 사람과 얼마나 맞는지 모르는 상태로는 RC가 아니다.

### ★ [2026-09-04] 17번 — "파일시스템 gate 재현"은 틀린 요약이었다

`[실측]` [DoD-17 evidence](../../../final_project_cs/docs/evidence/DoD-17_마일스톤_게이트.md)를 직접 대조했다. **원문 어디에도 "파일시스템 gate 재현"이라는 말이 없다.**

원문이 실제로 적은 것은 셋이다.

| 게이트 | 상태 |
|---|---|
| **M1·M2·M3** (Case 생성~replay · 시나리오 e2e · 60건×3회 harness) | **전부 도달** |
| **RC(릴리스 후보) 선언** | **미도달** — 이유가 **DoD-15와 완전히 같다.** judge agreement(사람 라벨 20건)가 유일한 차단 항목 |
| 커밋 ↔ Phase 자동 매핑 | 미수행(사람이 읽어 대조) — 이건 완료 판정과 **무관한** 잔여 자동화 항목이라고 원문이 명시한다 |

**RC는 "돌아가는 것"이 아니라 "내보낼 수 있는 것"이다.** M1~M3는 "돌아간다"를 증명하고, RC는 judge가 사람과 얼마나 맞는지 알아야 선언할 수 있다 — 이 둘을 섞으면 안 된다.

`[실측]` **게이트 자체는 자동화돼 있다.** `python -m scripts.check_release_gate`가 pytest·`verify_dod`·기능동결(`git diff`) 3단계를 한 명령으로 실행해 pass/fail exit code를 낸다(2026-08-20). "사람이 손으로 재현"에서 "한 명령"으로 바뀐 부분이지, 아직 부족한 부분이 아니다.

**즉 17번의 유일한 실질 블로커도 15번과 같다.** → [../evaluation/judge.md](../evaluation/judge.md)의 **사람 라벨 20건 측정**이 두 항목을 동시에 통과로 바꾼다.

## ★ [2026-09-03] 왜 문서마다 판정이 다른가

`[실측]` 대조하다 **세 문서가 다른 숫자를 적고 있는 걸 찾았다.**

| 출처 | 시점 | 판정 |
|---|---|---|
| `_DoD_구현갭_분석.md` | **2026-08-20** | 구현 18 · 부분 9 · 미구현 1 · 판정불가 1 |
| `A-COP_중간발표_현황정리.md` | 2026-08-20 | 같은 값 인용 |
| **evidence 35건** | **2026-08-12~31** | **통과 29 · 부분 3** |

**모순이 아니라 시점 차이다.**

`[실측]` **evidence 파일이 정본이다.** 갭 분석은 **정적 읽기만 한 2026-08-20 스냅샷**이고, 그 뒤 열흘 동안 항목들이 실제로 채워졌다.

```
DoD-04 · 10 · 12 · 16 · 18 · 23    갭 분석: 부분    →    evidence: 통과
```

### 그런데 하나는 갭 분석이 맞았다

`[실측]` **DoD-22 는 evidence 가 "통과"라고 적고 있지만 근거가 사라졌다.**

인용한 테스트 소스가 없고 `.pyc` 만 남았다. → [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md)

**갭 분석이 22번을 "아키텍처 경계 미검증"으로 짚은 게 지금도 유효하다.**

### 그래서 규칙

> **evidence 가 정본이되, "통과"라고 적힌 것도 근거가 살아 있는지 봐야 한다.**

`[미확보]` **29건 중 9건만 확인했다.** 나머지 20건은 아직 안 봤다. DoD-06은 근거가 낡은 게 아니라 **처음부터 sample 을 잰 것**이었고, DoD-21은 fixture 라벨만 옛 식별자, DoD-13은 "6번째 경로는 위반"이라는 규칙 자체가 바뀐 뒤다 → [dod-evidence-drift.md](../../final_project_cs/wiki/quality/dod-evidence-drift.md)

## 발표에서 어느 숫자를 쓰나

`[실측]` **"29항목 전부 evidence로 평가됨(통과 26·부분통과 3)"을 쓴다.** ★이전 판이 이 절 첫 줄에 **"통과 29"**라고 적어 바로 아래 "부분 통과 3건" 줄과 스스로 모순됐다(2026-09-04 발견·정정) — "평가됨"과 "통과"를 섞으면 안 된다. 다만 이 숫자를 쓰더라도 두 가지를 함께 말해야 한다.

| | |
|---|---|
| **부분 통과 3건** | DoD-15 · 17 · 28 |
| **DoD-22 는 근거 재확인 필요** | 통과로 적혀 있으나 테스트가 없다 |

**"29개 전부 통과"라고 말하면 안 된다.**

## ★ [2026-09-06] DoD 29항목이 못 담는 수정이 있다

`[실측]` [DoD-14 evidence](../../../final_project_cs/docs/evidence/DoD-14_API키_scope_구분.md)가 스스로 적어 뒀다. 2026-08-24 같은 조사에서 고친 것 중 둘이 **1~29 어디에도 안 걸린다.**

| 수정 | 왜 안 걸리나 |
|---|---|
| `list_cases()`가 같은 `created_at`에서 정렬이 비결정적이었다 | 동시성(DoD-03)도 아니고 계약(13)도 아닌 **정렬 안정성** 문제 |
| `GET /introspection` 조립 스냅샷 | v8 계획서에 없는 항목 — basement 완성도 문제지 요구사항이 아니다 |

**"29개 전부 evidence로 평가됨"이 "코드가 전부 검증됨"은 아니다.** DoD는 계획서가 요구한 것의 목록이지 결함 전체의 목록이 아니다. 이런 수정은 리포트로만 남는다 — `docs/reports/2026-08-24_S-BASEMENT-09-*`, `-10-*`.

## 관계

- [timeline.md](timeline.md) — 언제까지
- [milestones/index.md](milestones/index.md) — 발표별 목표
- [../evaluation/index.md](../evaluation/index.md) — 증명 방법
- [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) — 자동 판정
- [`quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 평가 실행

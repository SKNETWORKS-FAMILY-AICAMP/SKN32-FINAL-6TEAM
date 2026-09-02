---
type: report
title: 1차 — 표본 45건 첫 분류
description: type 8개로 45건을 분류했다. 애매 25%로 기준 미달
status: draft
tags: [governance, documentation]
owners: [human:미배정]
---

# 1차 — 표본 45건 첫 분류

---
type: report
title: type 분류 검증 (표본 45건)
description: 실제 문서 45건을 type에 대입한 결과. 애매 비율이 기준을 넘어 목록을 고쳐야 한다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
---

# type 분류 검증 (표본 45건)

`[실측]` 2026-09-01

## 방법

[migration.md](../migration.md)가 정한 절차를 따랐다.

```bash
python program/scripts/_sample.py    # seed=20260901 고정, 재현 가능
```

| 층 | 모집단 | 표본 |
|---|---|---|
| `program/plan` | 19 | 8 |
| `program/research` | 34 | 6 |
| `cs/docs/plans` | 7 | 5 |
| `cs/docs/evidence` | 35 | 4 |
| `cs/docs/handoff` | 14 | 5 |
| `cs/docs/reports` | 134 | 5 |
| `cs/docs/manuals` | 2 | 2 |
| `cs/docs/vision` | 11 | 2 |
| `datasets/**/REPORT.md` | 14 | 4 |
| README·CLAUDE | 8 | 4 |
| **합계** | | **45** |

**한계.** 두 사람 독립 판정을 못 했다. 혼자 분류했으므로 **일치율은 못 낸다.** 애매 비율만 낸다.

## 결과 — 기준 미달

| 지표 | 기준 | 실측 | 판정 |
|---|---|---|---|
| 애매 비율 | 15% 이하 | **25%** (11/44) | **미달** |
| 일치율 | 80% 이상 | 측정 못 함 | — |

이관 대상 아님으로 뺀 1건(빈 실패 메시지)을 분모에서 제외해 44건 기준이다.

**`[migration.md](../migration.md)` §확정 전에 할 것의 5번에 따라 정의를 수정해야 한다.**

## 명확했던 것 33건

| type | 건수 | 예 |
|---|---|---|
| `report` | 8 | 작업 요약, 조사 리포트, 지표 실행 결과 |
| `contract` | 5 | handoff 01·02·09·12·13 |
| `plan` | 5 | DoD 잔여작업, 코퍼스 배분안, init plan |
| `guide` | 4 | 환경 기동절차, README 3종 |
| `dataset` | 4 | datasets REPORT 4건 |
| `policy` | 3 | 문서관리 전략, 문서구조 v1, CLAUDE.md |
| `decision` | 1 | Composer 중앙설정저장소 결정 |
| `research` | 1 | 시장·출처 근거 |

**`contract`와 `dataset`이 완벽했다.** handoff 5건 전부, datasets REPORT 4건 전부 이견 없이 갈렸다.

## ★ 애매했던 것 11건 — 네 가지 패턴

### 패턴 1 — DoD 증거 (4건, 가장 큼)

```
DoD-24_ActionProposal_근거대조
DoD-12_outbox_원자성_replay
DoD-06_정책FAQ_25건_300청크
DoD-EVAL-DATASETS_검증
```

전부 **재현 명령 + 실제 출력 + 판정 근거** 구조다.

`report`로 뭉치면 **"특정 시점 결과"와 "완료 증명"이 섞인다.** 성격이 다르다.

| | `report` | 증거 |
|---|---|---|
| 목적 | 무슨 일이 있었나 | **DoD를 통과했는가** |
| 수명 | 시점 기록 | 릴리스까지 유효 |
| 재현 | 불필요 | **재현 명령 필수** |

`[실측]` `cs/docs/evidence/`에 35건이 있다. 표본이 아니라 **모집단이 크다.**

### 패턴 2 — 장애 대응 절차 (1건)

```
운영_unknown상태_대응절차   203줄
```

`guide`로 뭉치면 **온보딩 문서와 섞인다.**

| | `guide` | 절차서 |
|---|---|---|
| 언제 읽나 | 처음 시작할 때 | **사고가 났을 때** |
| 구조 | 설명 | 순서대로 따라가는 단계 |
| 실패하면 | 다시 읽음 | **돈이 나갔는지 모르는 상태가 지속** |

### 패턴 3 — vision (2건)

```
VISION-07_정책_엔진      VISION-05_메시징_내구_실행_확장
```

둘 다 구조가 같다. **"무엇인가 / 지금 하지 않는 이유 / 도입 트리거 / 예상 비용 / 선행 조건"**

`decision`인가? 결정한 게 아니라 **미룬 것**이다. `plan`인가? 일정이 없다.

`[실측]` `cs/docs/vision/`에 11건 있다.

### 패턴 4 — "설계"·"검토"·"해소안" (4건)

```
예제Team모듈_확충설계      모듈토글_실효화_설계
Composer_v3_불일치_해소안   Composer_범위재검토
```

**`plan`인가 `decision`인가 `research`인가.** 셋 다 걸친다. 안을 비교하고(research), 하나를 고르고(decision), 순서를 정한다(plan).

## 고쳐야 할 것

`[추정]` 애매 11건 중 **7건이 type 2개 추가로 해소된다.**

| 추가 | 해소 | 근거 |
|---|---|---|
| `evidence` | 4건 | 모집단 35건. 재현 명령이 필수라 성격이 다르다 |
| `runbook` | 1건 | 사고 시 따라가는 절차. `guide`와 용도가 다르다 |

**둘 다 codex 초안의 13개 목록에 있었다.** 내가 8개로 줄일 때 뺀 것이다. **검증이 codex 쪽 손을 들어줬다.**

남은 4건(패턴 3·4)은 type 추가로 안 풀린다. **판정 규칙이 필요하다.**

`[추정]` 제안하는 규칙.

```text
vision (패턴 3)
  → decision 으로 두되 status 를 쓴다.
    "지금 하지 않는다"도 결정이다. 도입 트리거가 재검토 조건이다.

설계·검토·해소안 (패턴 4)
  → 문서가 답하는 질문으로 가른다.
    "무엇을 고를까"      → decision
    "어떤 선택지가 있나"  → research
    "언제 무엇을 할까"    → plan
    한 문서가 셋을 다 하면 그 문서가 큰 것이다. 쪼갠다.
```

**마지막 줄이 핵심이다.** 패턴 4의 4건은 전부 161~216줄이다. **type이 애매한 게 아니라 문서가 여러 일을 하고 있다.**

## 수정안

`type` 8개 → **10개**

```text
concept   decision   plan      contract   guide
report    research   policy    dataset
evidence  runbook                          ← 추가
```

| type | 용도 | `report`·`guide`와의 차이 |
|---|---|---|
| `evidence` | DoD·완료 기준의 재현 가능한 증명 | **재현 명령이 필수** |
| `runbook` | 사고·장애 시 따라가는 절차 | **긴급 상황에 읽는다** |

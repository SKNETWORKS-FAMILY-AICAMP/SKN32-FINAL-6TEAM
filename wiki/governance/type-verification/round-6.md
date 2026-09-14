---
type: report
title: 6차 — 휴리스틱 자동 판정 검증
description: 미판정 156건의 자동 판정을 표본 15건으로 확인했다. type 일치 60%, 제외 대상 2건을 놓쳤다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
domain: neutral
---

# 6차 — 휴리스틱 자동 판정 검증

`[실측]` 2026-09-01

## 무엇을 검증했나

1~5차는 **사람(과 codex)의 분류 일치율**을 봤다.

**6차는 다르다.** `migration_scope.py`가 자동으로 `유지`로 판정한 **156건이 맞는지** 본다.

```
표본 D  15건 · seed 20260904 · type 비율대로 층화
        program/scripts/sample_d_frozen.txt
```

## 결과 — 기준 미달

| 지표 | 기준 | 실측 |
|---|---|---|
| **type 일치율** | 80% | **60.0%** (9/15) |
| **`유지` 판정 유효** | — | **66.7%** (10/15) |

**5건이 틀렸다.**

## ★ 가장 나쁜 것 — 제외 대상 2건을 "유지"로 봤다

| # | 문서 | 휴리스틱 | 실제 |
|---|---|---|---|
| 7 | `codex_cautious_runner.md` (18줄) | `dataset` 유지 | **영문 작업 로그. 제외** |
| 12 | `crawler/legacy/README.md` (25줄) | `guide` 유지 | **"일회성" 임시 스크립트. 제외** |

**둘 다 폴더 위치로 type 을 추정한 결과다.**

```
datasets/ 아래에 있으니 dataset      ← 아니다. 작업 로그다
README.md 니까 guide                 ← 아니다. 폐기 기록이다
```

**156건에 이 비율(13%)을 적용하면 약 20건이 제외 대상인데 이관될 뻔했다.** `[추정]`

## type 이 틀린 3건

| # | 문서 | 휴리스틱 | 실제 | 왜 |
|---|---|---|---|---|
| 9 | `문서병합_지침.md` | `research` | **`policy`** | 조사가 아니라 **따라야 할 규칙** |
| 10 | `_3차_인용검증_설계.md` | `research` | **`decision`** | **"프롬프트를 방어선으로 삼지 않는다"** 결정 |
| 12 | `legacy/README.md` | `guide` | `report` | 폐기 기록 |

### 10번이 중요하다

`[실측]` 이 문서가 **[D-005](../../decisions/D-005-write-gate.md)의 원형**이다.

> **판정 정직성 — 프롬프트를 방어선으로 삼지 않는다**

`program/research/` 아래 있다는 이유로 `research`로 찍혔지만, **실제로는 이 프로젝트의 핵심 결정 하나다.**

**폴더가 type 을 정하지 않는다.**

## 분할 대상 2건

| # | 문서 | 무엇과 무엇 |
|---|---|---|
| 4 | `DoD-17_마일스톤_게이트.md` | 재현·판정(`evidence`) + **"v5 원문과의 차이" 재해석**(`decision`) |
| 8 | `data_go_kr_consumer_complaints/REPORT.md` | 출처·파일 목록(`dataset`) + **"가장 중요한 발견"**(`report`) |

**8번은 [report-split.md](../../../datasets/wiki/report-split.md) 규칙 그대로다.** 규칙이 맞았다.

## 맞은 것 9건

`evidence` 3건, `dataset` 1건, `guide` 1건, `contract` 1건, `decision` 1건, `plan` 1건, `evidence`(제외) 1건.

**`evidence`와 `contract`가 정확했다.** 형식이 균일해서 휴리스틱이 잘 맞는다.

`[실측]` 13번 `06_가드레일_수치.md`는 **매우 중요한 문서**다 — 가드레일 수치의 **단일 출처**. 휴리스틱이 `contract`로 정확히 잡았다.

## 판정

| 항목 | 판정 |
|---|---|
| 156건 일괄 이관 | **하면 안 된다** |
| `evidence` 59건 일괄 | **조건부 가능** — 표본에서 3/4 정확 |
| `dataset` 24건 일괄 | **불가** — 2/3에서 오류 |
| `research` 20건 일괄 | **불가** — 2/2 다 틀림 |

## 무엇을 고쳐야 하나

`[추정]` 휴리스틱의 실패 패턴이 둘이다.

| 패턴 | 고칠 방법 |
|---|---|
| **폴더로 type 추정** | `program/research/`·`datasets/` 아래를 무조건 그 type 으로 보지 않는다 |
| **10~30줄 짧은 문서** | 작업 로그·폐기 기록일 가능성이 높다. **길이 하한을 10 → 40줄로** |

### 제안 — 짧은 문서를 판정필요로

```python
if lines < 40 and verdict == "유지":
    verdict = "판정필요"   # 작업 로그·폐기 기록 후보
```

`[추정]` 156건 중 짧은 문서가 몇 건인지 세면 추가 판정 규모를 안다.

## 다음

| # | 할 일 |
|---|---|
| 1 | 휴리스틱에 **길이 하한** 추가 후 재계산 |
| 2 | `research` 20건은 **전건 사람 판정** (2/2 실패) |
| 3 | `evidence` 59건은 표본 10건 더 확인 후 일괄 |
| 4 | `dataset` 24건은 `report-split` 규칙 적용하며 개별 |

## 관계

- [index.md](index.md) — 검증 전체
- [../migration-scope/index.md](../migration-scope/index.md) — 범위 목록
- [../type-guide.md](../type-guide.md) — type 판정 규칙

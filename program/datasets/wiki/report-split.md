---
type: policy
title: REPORT 를 둘로 나눈다
description: 데이터 의미와 실행 현황을 한 파일에 담지 않는다. 변경 주기가 다르다
status: draft
tags: [data, documentation]
owners: [human:미배정]
---

# REPORT 를 둘로 나눈다

`[실측]` blind 검증에서 **독립 판정자가 잡은 패턴**이다. 내가 못 봤다.

## 문제

`REPORT.md` 대부분이 두 가지를 한 파일에 담고 있다.

```
데이터가 무엇인가 · 출처 · 범위 · 제약    →  안 변한다
지금 전처리가 어디까지인가 · 실행 결과     →  계속 변한다
```

**변경 주기가 다르므로 [분할 트리거](../../wiki/governance/document-standard.md)에 걸린다.**

## 실제 사례

`[실측]` 2026-09-01

### `mt/olist_reviews_mt_bench/REPORT.md` (258줄)

| 절 | 성격 |
|---|---|
| 출처·라이선스 · 방법론 | **`dataset`** |
| 결과 1~5 (PT→EN, PT→KO, EN→KO, 확장, GPU 재검증) | **`report`** |

**결과가 5개까지 늘었다.** 축이 추가될 때마다 파일이 커진다.

### `voc/aihub_102_smb_order_qa/REPORT.md` (105줄)

| 절 | 성격 |
|---|---|
| 출처 · 받은 것 · 원 데이터셋 규모 · 선택 이유 | **`dataset`** |
| 아직 안 한 것 · **전처리 결과 (2026-09-01)** | **`report`** |

**날짜가 제목에 붙은 절이 신호다.** 그건 시점 기록이다.

### `voc/sources_catalog/PLAN.md` (279줄)

| 절 | 성격 |
|---|---|
| AI Hub 우선 후보 이유 · 안 넣은 것 | **`research`** |
| 교차검증 리서치 · 완결성 점검 (날짜 붙음) | **`report`** |

## 나누는 법

```
<이름>/REPORT.md      데이터가 무엇인가        type: dataset
<이름>/STATUS.md      지금 어디까지 됐나        type: report
```

**`REPORT.md`가 정본 이름을 유지한다.** 다른 문서들이 이미 그 이름을 참조하고 있다.

## 무엇을 어디로

| REPORT.md (안 변한다) | STATUS.md (변한다) |
|---|---|
| 출처·URL·라이선스 | 전처리 진행 상황 |
| 받은 파일 목록·크기 | 실행 결과·건수 |
| 스키마·필드 의미 | 발견한 문제 |
| **선택 이유** | **아직 안 한 것** |
| 이용 제약·PII 금지 항목 | 날짜가 붙은 모든 절 |

## 판정 기준 한 줄

> **날짜를 적어야 말이 되면 `report`다.**

"2026-09-01 전처리 완료"는 날짜가 필요하다. "출처는 AI Hub"는 필요 없다.

## ★ [2026-09-01] 28건 전건 판정 — 대상이 10건이다

`[실측]` → [9차 검증](../../wiki/governance/type-verification/round-9.md)

**이관 대상 28건 중 10건이 분할이었다.** 40%다.

| 대상 | 줄 | 신호 |
|---|---|---|
| `voc/sources_catalog/PLAN.md` | 278 | 날짜 절 3 |
| `mt/olist_reviews_mt_bench/REPORT.md` | 258 | **날짜 절 5** |
| `commerce/coupang_order_history/docs/실제HTML_페이지네이션.md` | 209 | **H1 3개** |
| `commerce/naver_order_history/REPORT.md` | 174 | "지금 몇 건인가" |
| `commerce/courier_tracking/REPORT.md` | 158 | 날짜 절 1 |
| `commerce/coupang_order_history/docs/실제HTML_주문상세_배송조회.md` | 139 | **H1 3개** |
| `voc/aihub_102_smb_order_qa/REPORT.md` | 104 | 날짜 절 1 |
| `voc/aihub_30716_callcenter_qa/REPORT.md` | 91 | 날짜 절 1 |
| `voc/aihub_71603_aspect_sentiment/REPORT.md` | 87 | 날짜 절 1 |
| `voc/aihub_71844_llm_instruction_tuning/REPORT.md` | 87 | 날짜 절 1 |

**H1 이 3개인 두 건을 먼저 한다.** 그건 이 규칙 이전의 문제다 — 한 파일에 두 문서가 있다.

### 이 목록은 손으로 만들지 않는다

```bash
python program/scripts/migration_scope.py
```

**28건 판정을 정답표로 놓고 신호를 맞췄다.** 줄수 하한 80에서 **놓침 0 · 오탐 3**이다.

```python
if H1 이 2개 이상:                          판정필요   # 두 문서
elif lines >= 80 and (날짜 절 or 현황 절):   판정필요   # report-split
```

`[실측]` **하한을 100으로 올리면 놓침이 3 생긴다.** 오탐은 사람이 보고 넘기면 되지만, 놓침은 섞인 문서가 그대로 이관된다.

### 판정을 하나 뒤집었다

`voc/data_go_kr_consumer_complaints/REPORT.md` 를 [6차](../../wiki/governance/type-verification/round-6.md)에서 분할로 봤다. **틀렸다.**

> 자유서술 본문+답변이 있는 건 **15098320 하나뿐**

**날짜를 적을 필요가 없다.** 데이터 자체의 성질이다. → 이관

**한 줄 기준이 눈보다 정확했다.**

`[실측]` **`datasets/README.md`의 "VOC 전처리 현황 (2026-08-31 실측)" 절도 같은 구조다.**

## 관계

- [index.md](index.md) — 폴더 규칙
- [catalog.md](catalog.md) — 데이터셋 목록
- [generation.md](generation.md) — 재생성
- [../../wiki/governance/type-guide.md](../../wiki/governance/type-guide.md) — `dataset` vs `report`
- [../../wiki/governance/migration-scope/index.md](../../wiki/governance/migration-scope/index.md) — 이관 범위

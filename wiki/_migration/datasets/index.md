---
type: plan
title: datasets 분할 결과 (적용 전)
description: REPORT 10건을 22개로 나눈 결과. 아직 원본에 적용하지 않았다
status: draft
tags: [data, documentation]
---

# datasets 분할 결과 (적용 전)

`[실측]` 2026-09-02. **원본은 하나도 건드리지 않았다.** 여기는 스테이징이다.

## 무엇을 했나

[report-split.md](../../../datasets/wiki/report-split.md)의 기준 한 줄을 적용했다.

> **날짜를 적어야 말이 되면 `report` 다.**

```
<이름>/REPORT.md   데이터가 무엇인가   type: dataset   안 변한다
<이름>/STATUS.md   지금 어디까지 됐나  type: report    계속 변한다
```

## 결과

| 원본 | 줄 | → | 산출 |
|---|---|---|---|
| `voc/sources_catalog/PLAN.md` | 279 | 2 | REPORT · STATUS |
| `mt/olist_reviews_mt_bench/REPORT.md` | 258 | 2 | REPORT · STATUS |
| `commerce/naver_order_history/REPORT.md` | 175 | 2 | REPORT · STATUS |
| `commerce/courier_tracking/REPORT.md` | 159 | 2 | REPORT · STATUS |
| `voc/aihub_102_smb_order_qa/REPORT.md` | 105 | 2 | REPORT · STATUS |
| `voc/aihub_30716_callcenter_qa/REPORT.md` | 92 | 2 | REPORT · STATUS |
| `voc/aihub_71603_aspect_sentiment/REPORT.md` | 88 | 2 | REPORT · STATUS |
| `voc/aihub_71844_llm_instruction_tuning/REPORT.md` | 88 | 2 | REPORT · STATUS |
| **`docs/실제HTML_페이지네이션.md`** | 210 | **3** | H1 단위 |
| **`docs/실제HTML_주문상세_배송조회.md`** | 140 | **3** | H1 단위 |

**10건 → 22개.**

`[실측]` 산출 줄 수가 원본의 **106~118%** 다. front matter 가 파일마다 늘어난 몫이고, **내용은 버려지지 않았다.**

## ★ 적용 전에 풀어야 할 것 — 이름 충돌

`[실측]` `voc/sources_catalog/PLAN.md` 를 나눈 결과가 **`REPORT.md`** 인데, **그 폴더에는 이미 다른 `REPORT.md` 가 있다.**

| 파일 | 무엇 |
|---|---|
| 기존 `REPORT.md` (78줄) | **후보 카탈로그.** 무엇을 찾았나 |
| 분할된 `REPORT.md` (신규) | **선택 근거.** 왜 이걸 골랐나 |

**그대로 적용하면 기존 파일이 덮인다.**

### [2026-09-02] ② 로 정했다

```
분할본  →  SELECTION.md      "왜 이걸 골랐나"
기존    →  REPORT.md 유지     "무엇을 찾았나"
```

**기존 이름을 안 건드리는 쪽이다.** `REPORT.md` 를 참조하는 문서가 있을 수 있고, 이름을 바꾸면 그걸 다 찾아 고쳐야 한다.

`[실측]` 스테이징에 반영했다.

## ★ 적용은 전체를 한 번에 한다

**부분 적용을 하지 않는다.**

`[실측]` 2026-09-03 판단.

> **절반만 적용된 `datasets/` 는 양 끝단 어느 쪽보다 나쁘다.**

어떤 폴더엔 `STATUS.md` 가 있고 어떤 데는 없으면, **읽는 사람이 매번 확인해야 한다.** 그러면 "여기는 어디에 적혀 있지"가 다시 생긴다 — 이 정리가 없애려던 바로 그 문제다.

| | |
|---|---|
| **지금** | 원본 그대로 · 분할본은 여기 |
| **적용 시점** | **22개를 한 번에 바꿀 수 있게 됐을 때** |

### 벌어지는 것은 다시 만들면 된다

**스테이징이 낡을까 봐 서둘러 적용할 이유는 없다.** 원본이 바뀌면 분할을 다시 돌린다.

**낡았는지는 세어서 안다.**

```bash
python program/scripts/check_split_staleness.py
```

## 적용 절차

**아직 하지 않았다.**

1. 위 이름 충돌을 정한다
2. 각 산출물을 원본과 나란히 놓고 **절이 다 들어갔는지 센다**
3. 원본을 `_backup/` 이 아니라 **git 커밋으로 남기고** 교체한다
4. `datasets/README.md` 와 `catalog.md` 의 링크를 고친다

`[미확보]` **4번이 몇 곳인지 안 세었다.**

## 관계

- [../../../datasets/wiki/report-split.md](../../../datasets/wiki/report-split.md) — 적용한 규칙
- [../../governance/type-verification/round-9.md](../../governance/type-verification/round-9.md) — 분할 10건 판정

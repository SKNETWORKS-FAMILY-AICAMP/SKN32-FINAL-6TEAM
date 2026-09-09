---
type: report
title: 9차 — dataset 28건 전건 판정
description: type 일치 42.9%. report-split 규칙을 기계 신호로 바꿔 놓침 0으로 만들었다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
domain: commerce
domain_note: 분류 체계 검증 9차의 기록이다
---

# 9차 — dataset 28건 전건 판정

`[실측]` 2026-09-01

[6차](round-6.md)에서 `dataset` 표본이 **2/3 틀렸다.** 30건을 다 봤다.

전문은 `program/scripts/_verify_dataset.tsv`.

## 결과

| 지표 | 기준 | 실측 |
|---|---|---|
| **type 일치율** | 80% | **42.9%** (12/28) |

### 실제 type — 절반이 `dataset` 이 아니었다

| 추정 | 실제 |
|---|---|
| `dataset` 28 | **`dataset` 12** · `report` 7 · `research` 4 · `reference` 3 · `plan` 1 · `policy` 1 |

**[7차](round-7.md)와 같은 실패다.** `datasets/` 아래 있다고 데이터 문서가 아니다.

| 예 | 실제 |
|---|---|
| `commerce/DISTRIBUTION.md` | **`policy`** — 배포본 규칙 |
| `coupang_order_history/REPORT.md` | **`report`** — 제목부터 "작업 리포트" |
| `sources_catalog/_codex_independent_research_*.md` | **`research`** — 독립 조사 |
| `docs/실제HTML_주문카드.md` | **`reference`** — 선택자 구조 |

**다만 7차(7.7%)보다 낫다.** 절반은 진짜 `dataset` 이었다. `REPORT.md` 라는 이름이 형식을 어느 정도 강제하기 때문이다. → [8차](round-8.md)의 결론과 같다.

## 판정 28건

| 판정 | 건수 |
|---|---|
| 이관 | 13 |
| **분할** | **10** |
| 제외 | 5 |

**10건이 분할이다.** 이관 대상의 40%가 그대로 옮기면 안 되는 문서였다.

## ★ report-split 규칙이 맞았다 — 그리고 기계로 옮겼다

`[실측]` [report-split.md](../../../datasets/wiki/report-split.md)의 판정 기준은 한 줄이다.

> **날짜를 적어야 말이 되면 `report` 다.**

**분할 10건 중 8건이 이 기준에 그대로 걸렸다.**

```
## 전처리 결과 (2026-09-01)
## ★2026-08-28 갱신 — K쇼핑 subset 추출·매핑 완료
## 지금 몇 건인가 — 4명이 모아 270건
```

### 사람 판정을 신호로 바꿨다

28건 판정을 정답표로 놓고 신호를 맞췄다.

| 줄수 하한 | 잡음 | 오탐 | **놓침** |
|---|---|---|---|
| 0 | 10/10 | 7 | 0 |
| 60 | 10/10 | 4 | 0 |
| **80** | **10/10** | **3** | **0** |
| 100 | 7/10 | 2 | **3** |

**80줄을 골랐다.** 100 으로 올리면 오탐이 하나 줄지만 **놓침이 3 생긴다.**

**놓치는 것보다 오탐이 낫다.** 오탐은 사람이 보고 넘기면 끝이고, 놓침은 섞인 문서가 그대로 이관된다.

```python
if len(H1_MARK.findall(text)) >= 2:
    verdict = "판정필요"        # 한 파일에 두 문서
elif lines >= 80 and (DS_DATE.search(text) or DS_STATUS.search(text)):
    verdict = "판정필요"        # report-split 신호
```

**[8차](round-8.md)에 이어 두 번째로 사람 판정을 규칙으로 바꿨다.**

## ★ H1 이 3개인 파일 두 건

`[실측]` 규칙 이전의 문제였다.

| 파일 | H1 |
|---|---|
| `docs/실제HTML_주문상세_배송조회.md` | **3** |
| `docs/실제HTML_페이지네이션.md` | **3** |

```
# 쿠팡 주문 상세 페이지 구조 (실측)
…
# 배송조회 화면 구조 (실측)
```

**한 파일에 두 문서가 들어 있다.** `type` 을 고르기 전에 걸리는 문제다. → [type-guide.md](../type-guide.md)의 "① 이 문서가 한 가지만 하는가"

## `_prompts/` — 세 번째로 만나서 일반화했다

`[실측]` 같은 패턴을 세 번 만났다.

| 회차 | 어디 |
|---|---|
| 범위 목록 | `final_project_cs/wiki/records/handoff/_prompts/` 114건 |
| [7차](round-7.md) | `program/research/_prompts/` 2건 |
| **9차** | **`datasets/voc/aihub_30716_callcenter_qa/_prompts/`** 1건 |

세어 보니 다섯 폴더 **227건**이고 전부 작업 지시 티켓이다.

```
# 구현 지시 — Basement 관리자 화면
# 검증 요청 — Composer v3 전환, 지금 하면 무슨 일이…
# S-AIHUB-KSHOPPING-MAPPING — K쇼핑 subset 추출
```

**`_prompts/` 로 일반화했다.** 예외 하나는 [7차](round-7.md)에 적어 뒀다 — `문서병합_지침.md` 는 `CLAUDE.md` 가 참조하므로 제자리다. **"이관 안 함"이라는 결론은 같다.**

## 판정을 하나 뒤집었다

`[실측]` [6차](round-6.md)에서 `data_go_kr_consumer_complaints/REPORT.md` 를 **분할**로 봤다. 근거는 "★가장 중요한 발견" 절이 `report` 라는 것이었다.

**규칙에 대면 틀렸다.**

> 자유서술 본문+답변이 있는 건 **15098320 하나뿐**

**날짜를 적을 필요가 없다.** 데이터 자체의 성질이지 시점 기록이 아니다. → **이관**

**한 줄 기준이 내 눈보다 정확했다.**

## 버전관리 밖 2건이 목록에 있었다

`[실측]` 스캐너가 파일 시스템만 보고 git 을 안 봤다.

```
datasets/commerce/coupang_order_history/raw/find.md
datasets/voc/nikl_ne_2022/processed/pii_name_gap_measurement.md
```

**`CLAUDE.md` 가 `raw/`·`processed/` 는 본인 실제 구매 기록이라 git 에 올리지 않는다고 적고 있다.** 이관 대상이 아니다. 제외했다.

`[실측]` **`final_project_sample/` 도 gitignore 지만 그건 다르다** — 자체 저장소라서 루트가 무시할 뿐이고, 거기서는 추적된다. **같은 gitignore 라도 이유가 다르면 판정이 다르다.**

## 스크립트와 사람 판정 대조

`[실측]` 28건 중 **21건 일치.** 어긋난 7건은 전부 **오탐**(사람이 볼 필요 없는데 올림)이었고, **놓침은 0** 이다.

**놓침 1건이 있었는데 그게 `_prompts/` 였고, 이번에 규칙으로 막았다.**

## 다음

| # | 할 일 |
|---|---|
| 1 | 분할 10건 실행 — `REPORT.md` / `STATUS.md` 로 |
| 2 | H1 3개 파일 2건 먼저 — 규칙 이전의 문제다 |
| 3 | 이관 13건 실행 |

## 관계

- [round-8.md](round-8.md) — 같은 방식(사람 판정 → 규칙)의 첫 사례
- [../../../datasets/wiki/report-split.md](../../../datasets/wiki/report-split.md) — 적용한 규칙
- [../migration-scope/index.md](../migration-scope/index.md) — 범위 목록

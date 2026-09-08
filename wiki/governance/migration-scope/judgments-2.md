---
type: report
title: 2차 판정 내역 (2026-09-03)
description: 미판정 24건 판정과 분할 10건 실행. 이관 6건 중 5건이 이미 반영돼 있었다
status: draft
tags: [governance, documentation]
---

# 2차 판정 내역

`[실측]` 2026-09-03. **1차는 [judgments.md](judgments.md) 에 있다.**

## [2026-09-03] 미판정 24건 — 판정 완료

`[실측]` 전문은 `program/scripts/_verify_judge24.tsv`.

| 판정 | 건수 |
|---|---|
| **분할** | **10** |
| 이관 | 6 |
| 제외 | 6 |
| 제자리 | 2 |

**실제 type 은 `decision` 10건이 가장 많았다.** `program/plan/` 아래 문서 상당수가 계획이 아니라 결정이었다.

### ★ 이관 6건을 대조했더니 5건이 이미 반영돼 있었다

`[실측]` 2026-09-03. **판정은 "이관"이었지만 옮기려고 열어 보니 대부분 wiki 에 있었다.**

| 원본 | 실제 |
|---|---|
| `A-COP_결제소유_경계.md` | **[D-001](../../decisions/D-001-payment-ownership.md) 에 반영됨.** 절 제목만 다르다 |
| `A-COP_Composer_소유권_정정.md` | **[D-006](../../decisions/D-006-composer-ownership.md) 에 반영됨.** 절 구성이 거의 같다 |
| `A-COP_비전항목_검토.md` | **[D-009](../../decisions/D-009-recommendation-scope.md) 에 반영됨** |
| `A-COP_확장추천_검토.md` | **D-009 에 반영됨** |
| `A-COP_Composer_v3_설계_토글전용_UI이관.md` | [D-011](../../decisions/D-011-composer-v3-gap.md) 이 참조 |
| **`A-COP_Composer_v3_불일치_해소안.md`** | **미반영 → [D-011](../../decisions/D-011-composer-v3-gap.md) 신설** |

**신규는 하나뿐이었다.**

### 여기서 하나 배운다

`[실측]` **절 제목이 다르면 기계 대조가 못 잡는다.**

`A-COP_결제소유_경계.md` 의 `## 5. ★ 지금 환불 계산식이 이미 위험하다` 는
D-001 에 `## ★ 결과 — 환불 계산식을 고쳐야 한다` 로 들어가 있다. **같은 내용인데 제목이 다르다.**

`[실측]` 절 제목 앞 10글자로 맞춰 봤더니 **10개 중 0개가 걸렸다.** 실제로는 9개가 반영돼 있었다.

> **제목 매칭은 반영 여부를 재는 데 못 쓴다. 내용을 읽어야 한다.**

**[반영률 실측](coverage.md)이 codex 에게 내용 판정을 맡긴 게 그래서 옳았다.**

### D-011 이 남긴 것 — 종료일 없는 병행

`[실측]` `/composer/toggle`(v3)과 `/composer/validate`·`apply`(v2)가 **둘 다 존재한다.**

**사실상 병행 상태인데 종료일이 없다.**

> **종료일 없는 병행은 안 C 가 아니라 그냥 미결이다.**

### 이관 6건 — Composer 계열이 넷이다

| 문서 | → |
|---|---|
| `A-COP_결제소유_경계.md` | hub/decisions — **D-001 의 원형** |
| `A-COP_Composer_v3_불일치_해소안.md` | hub/decisions |
| `A-COP_Composer_v3_설계_토글전용_UI이관.md` | hub/decisions |
| `A-COP_Composer_소유권_정정.md` | hub/decisions |
| `A-COP_비전항목_검토.md` | hub/decisions |
| `A-COP_확장추천_검토.md` | hub/decisions — **D-009 의 원형** |

### 제자리 3건 — 다른 문서가 경로를 참조한다

| 문서 | 누가 참조하나 |
|---|---|
| `docs/release_checklist.md` | `final_project_cs/CLAUDE.md` |
| `final_project_cs/wiki/records/manuals/운영_unknown상태_대응절차.md` | `release_checklist` · DoD 문서 |
| `final_project_cs/wiki/records/vision/TODO_VISION.md` | `RULE.md` |

**[7차](../type-verification/round-7.md)에서 세운 규칙이 또 걸렸다** — 옮기기 전에 "누가 이 경로를 가리키는가"를 센다.

### ★ 제외 4건은 대조하고 찍었다

`[실측]` **"이미 반영됨"으로 제외한 넷 중 셋은 대조에서 통과했고, 하나는 누락이 나왔다.**

| 문서 | 결과 |
|---|---|
| `A-COP_문서구조_v1.md` (730줄) | 대절 6개 전부 반영 확인 |
| `A-COP_문서표준_설계_codex초안.md` (1,281줄) | 대절 14개 전부 반영 확인 |
| `A-COP_사업성_단위경제.md` (614줄) | 대절 10개 중 9개 반영. 나머지는 병합 위치 메모 |
| **`A-COP_페인포인트_페르소나_설계.md`** | **§7·§8·§9 누락** → 분할로 정정 |

### ★ 누락 8번째 — 심사 질문 5개가 없었다

`[실측]` 심사 질문표 5행이 **전부 기술 질문**이고 제품 질문이 하나도 없었다.

```
누가 이걸 쓰는가 · 어떤 문제를 푸나 · 얼마나 아껴 주나
기존 챗봇과 뭐가 다른가 · 왜 사는가
```

**답까지 정해져 있었는데 wiki 에 없었다.** → [../../product/pitch-questions.md](../../product/pitch-questions.md)

§8(데이터 교정 계획)도 함께 옮겼다 — **`[미확보]` 를 없애는 절차가 이미 있었다.** → [../../delivery/open-items.md](../../delivery/open-items.md)

`[실측]` **대조 8번에 누락 8건.** 여전히 8/8 이다.


## [2026-09-03] 분할 10건 — 실행 완료

`[실측]` **분할이란 원본을 쪼개는 게 아니라 내용을 성격별로 나눠 옮기는 것이다.** 원본은 하나도 안 건드렸다.

| 원본 | 어디로 갔나 |
|---|---|
| `DoD28-FT-RAG통합_설계.md` (657줄) | [evaluation/finetuning.md](../../evaluation/finetuning.md) — 실행 결과·지뢰·draft 동질성 |
| `코퍼스_25문서_배분안.md` | [legal-basis.md](../../research/legal-basis.md) 법정 기준 + [corpus-authoring.md](../../../final_project_cs/wiki/context/corpus-authoring.md) 작성 규칙 |
| `A-COP_예제Team모듈_확충설계.md` | [cs/teams/index.md](../../../final_project_cs/wiki/teams/index.md) — 구현 순서 6단계 |
| `A-COP_남은작업_인수인계.md` | [open-items.md](../../delivery/open-items.md) — 잔여 3건 |
| `_컴포저_UI배포구조_점검.md` | [sample/composer/ui-boundary.md](../../../final_project_sample/wiki/composer/ui-boundary.md) — 권고 3개 중 2개 완료 |
| `A-COP_페인포인트_페르소나_설계.md` | [pitch-questions.md](../../product/pitch-questions.md) + open-items |

### 이미 반영돼 있던 것 4건

| 원본 | 어디에 |
|---|---|
| `A-COP_스프린트_에픽_설계.md` | [ticket-structure.md](../../delivery/ticket-structure.md) — **"에픽에 기간을 안 적는다" 절까지 있다** |
| `09_Composer_GUI_계약.md` | [D-CS-001](../../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) |
| `A-COP_Composer_범위재검토.md` | [D-011](../../decisions/D-011-composer-v3-gap.md) |
| `TODO_VISION.md` | 제자리 — `RULE.md` 가 참조하는 인덱스 |

## ★ 누락 9번째 — 법정 기준

`[실측]` [legal-basis.md](../../research/legal-basis.md) 에 **연 15% 지연이자 · 청약철회 제한 6개 범주 · 불리한 특약 무효**가 없었다.

**그리고 원본에 "초안의 네 곳이 틀렸다"는 교차검증 기록이 있었다.**

| 초안 | 실제 |
|---|---|
| **지연이자 "연 40% 이내"를 실제 요율처럼 배치** | **40% 는 법률상 상한. 실제는 연 15%** |

**상한을 요율로 쓰면 고객에게 2.7배를 약속하는 셈이다.**

`[실측]` **대조 9번에 누락 9건. 9/9 이다.**

## ★ 코퍼스에서 배운 것

`[실측]` `doc_01` 초안이 **13섹션 전부 200자 미달**이었다.

> **한 개를 먼저 검증한 덕에 25개를 잘못 쓰지 않았다.**

**이 wiki 작업도 같은 방식이었다** — 표본을 먼저 보고 규칙을 고쳤다. → [../type-verification/index.md](../type-verification/index.md)

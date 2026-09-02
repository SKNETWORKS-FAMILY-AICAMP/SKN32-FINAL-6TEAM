---
type: report
title: 이관 판정 내역
description: 판정필요 36건과 미정 20건을 사람이 판정한 결과. 대조에서 누락 3건을 찾았다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
---

# 이관 판정 내역

`[실측]` 2026-09-01. 전문은 `program/scripts/_scope_decisions.tsv`.

**요약은 [index.md](index.md)에 있다.** 이 문서는 어느 문서를 왜 그렇게 판정했는지의 내역이다.

## 판정필요 36건 — 판정 완료

`[실측]` 2026-09-01. 큰 것부터 전부 봤다. 전문은 `program/scripts/_scope_decisions.tsv`.

**10건은 `?` 20건과 겹쳤다.** 나머지 26건을 새로 판정했다.

### 전체 판정 결과 (46건)

| 판정 | 건수 |
|---|---|
| 이관 | 22 |
| **제외** | **11** |
| **분할** | **9** |
| 이관완료 (대조함) | 3 |
| 제자리 | 1 |

### 분할 9건

| 문서 | 줄 | 무엇과 무엇 |
|---|---|---|
| **`A-COP_구현계획서_v8.md`** | **1,516** | **28절. 최상위 분할** |
| `DoD28-FT-RAG통합_설계.md` | 579 | 결론(`decision`) + 설계·후속(`plan`) |
| `sources_catalog/PLAN.md` | 279 | 교차검증(`research`) + 최종 후보(`dataset`) |
| `olist_reviews_mt_bench/REPORT.md` | 258 | 벤치마크 결과(`report`) + 데이터 설명(`dataset`) |
| `A-COP_Composer_범위재검토.md` | 217 | 결론(`decision`) + 계약 제안(`contract`) |
| `A-COP_남은작업_인수인계.md` | 213 | 완료(`report`) + 남은 작업(`plan`) |
| `A-COP_예제Team모듈_확충설계.md` | 177 | 설계(`decision`) + 구현 순서(`plan`) |
| `07_모듈화_구조.md` | 142 | 목표 구조(`contract`) + 신설할 것(`plan`) |
| `aihub_102_smb_order_qa/REPORT.md` | 105 | 데이터 의미(`dataset`) + 전처리 현황(`report`) |

**`dataset` + `report` 혼재가 3건이다.** [3차 검증](../type-verification/round-3.md)에서 codex가 지적한 패턴 그대로다.

### 제외 11건

| 문서 | 왜 |
|---|---|
| `A-COP_실행계획서_v1.md` | v5 기준. v8 §25 일정으로 대체 |
| `init_plan_6인팀_v1.md` | 동. `roles.md`·`timeline.md`로 대체 |
| `_DoD_구현갭_분석.md` | `dod.md` 실측 현황으로 대체 |
| `_정합성_수정제안.md` | 적용 완료 |
| `_잔여작업_점검_2026-08-20.md` | 문서 모순 해소됨 |
| `_주말작업_요약` | 작업 일지 |
| `A-COP_문서구조_v1.md`·`문서표준_설계_codex초안.md` | governance/에 반영 확인함 |
| 나머지 3건 | 옛 도메인·완료된 티켓 |

## ★ 또 누락을 찾았다

**`A-COP_실행계획서_v1.md`를 제외로 찍으려다 대조했더니 wiki에 없는 게 있었다.**

> **두 스트림이 같은 파일을 쓰지 않는다.** 쓰면 마지막에 끝난 쪽이 이겨서 **조용히 덮어쓴다.**

**소유 디렉터리 표 8개 스트림**이 통째로 빠져 있었다. `roles.md`에 추가했다.

같이 있던 근거도 값졌다.

> `transition_case()`·낙관적 동시성·outbox 원자성·ContextPack 예산 절삭은 **틀려도 테스트가 초록으로 나오는 종류의 코드**다.

**그래서 계약 테스트를 만든 쪽과 통과시킨 쪽을 분리한다.**

`[실측]` **대조 3번에 누락 3건을 찾았다.** 사업성(§6·§7), 페인포인트(§6 도메인), 실행계획서(소유 디렉터리).

**"이미 반영됨"은 세어 보기 전까지 믿을 수 없다.**

## 판정필요 36건이 blind 검증과 겹쳤다

**우연이 아니다.**

| 문서 | 줄 | 섞인 것 |
|---|---|---|
| `DoD28-FT-RAG통합_설계.md` | 579 | decision+plan+report+research+policy |
| `A-COP_실행계획서_v1.md` | 309 | decision+plan+report+policy |
| `sources_catalog/PLAN.md` | 279 | decision+plan+policy |
| `olist_reviews_mt_bench/REPORT.md` | 258 | decision+plan+report+research |
| `A-COP_init_plan_6인팀_v1.md` | 220 | plan+report+policy |
| `코퍼스_25문서_배분안.md` | 214 | plan+report+policy |
| `09_Composer_GUI_계약.md` | 203 | plan+report+concept |
| `운영_unknown상태_대응절차.md` | 204 | decision+report+policy |
| `DoD-28_파인튜닝_방어지표.md` | 342 | decision+report+research |

`[실측]` **`DoD28-FT-RAG통합_설계.md`가 5종을 다 섞고 있다.** 579줄이다.

### 판정 규칙은 이미 있다

→ [type-guide.md](../type-guide.md)의 **"type을 고르기 전에 먼저 묻는다"**

```
① 이 문서가 한 가지만 하는가?  → 아니오면 쪼갠다
② type 을 고른다
```

## `?` 20건 — 판정 완료

`[실측]` 2026-09-01. 전문은 `program/scripts/_scope_decisions.tsv`.

| 판정 | 건수 |
|---|---|
| 이관 | 8 |
| 분할 | 4 |
| **이관완료** | **2** |
| 제외 | 5 |
| 제자리 | 1 |

### 이관 8건

| 문서 | type | 목표 |
|---|---|---|
| `A-COP_Composer_v3_불일치_해소안.md` | `decision` | hub/decisions |
| `A-COP_Composer_v3_설계_토글전용_UI이관.md` | `decision` | hub/decisions |
| `A-COP_Composer_소유권_정정.md` | `decision` | hub/decisions |
| `A-COP_비전항목_검토.md` | `decision` | hub/decisions |
| `A-COP_확장추천_검토.md` | `decision` | hub/decisions |
| `A-COP_스프린트_에픽_설계.md` | `plan` | hub/delivery |
| `docs/release_checklist.md` | `plan` | hub/delivery |
| `diagram/_다이어그램_근거.md` | `reference` | hub/architecture |

**Composer 관련 4건이 한 계열이다.** 이관할 때 `D-CS-002`~`005`로 묶는다.

### 분할 4건

| 문서 | 줄 | 무엇과 무엇 |
|---|---|---|
| **`A-COP_구현계획서_v8.md`** | **1,516** | **28절. 최상위 분할.** 절별로 영역 배분 |
| `A-COP_Composer_범위재검토.md` | 217 | 결론(`decision`) + 계약 제안(`contract`) |
| `A-COP_남은작업_인수인계.md` | 213 | 완료된 것(`report`) + 남은 작업(`plan`) |
| `A-COP_예제Team모듈_확충설계.md` | 177 | Team별 설계(`decision`) + 구현 순서(`plan`) |

### ★ "이관완료" 2건 — 대조하고 누락을 찾았다

**제외로 찍기 전에 내용을 대조했다. 둘 다 빠진 게 있었다.**

| 문서 | 빠져 있던 것 | 조치 |
|---|---|---|
| `A-COP_사업성_단위경제.md` | **§6 리스크 13종 · §7 우선순위** | `business/index.md`에 추가 |
| `A-COP_페인포인트_페르소나_설계.md` | **§6 타깃 도메인 모순 수정** | `product/scope.md`에 추가 |

**두 번째가 특히 중요했다.** wiki에 **타깃 도메인 서술 자체가 없었다.** v8 §6이 아직 "가상의 SaaS Customer Operations"라고 적고 있는데 §10과 모순이라는 지적이 그 문서에만 있었다.

**대조 안 하고 제외했으면 결함 수정 하나를 통째로 잃을 뻔했다.**

### 제외 5건

| 문서 | 이유 |
|---|---|
| `A-COP_문서구조_v1.md` (730줄) | 이 wiki 표준의 원본. **반영 확인함** |
| `A-COP_문서표준_설계_codex초안.md` (1,281줄) | codex 초안. **검토 후 반영 확인함** |
| `eval/reports/2026-08-12_평가결과_리포트.md` | 옛 구독 도메인. 무효 |
| `S-BRIEFING-POLISH.md` | 완료된 작업 지시 티켓 |
| `S-TRACE-VIDEO_리포트.md` | 완료된 작업 결과 |

### 제자리 1건

`final_project_cs/RULE.md` — 프로세스 규칙. `CLAUDE.md`와 짝이라 **루트에 있어야 한다.**

## 이 판정에서 배운 것

**"이미 반영됨"으로 제외하기 전에 반드시 대조한다.**

`[실측]` 2건 다 반영됐다고 생각했는데 **둘 다 빠진 절이 있었다.** 내가 옮긴 문서인데도 그랬다.

**절 목록을 나란히 놓고 세는 것만으로 잡힌다.** 30초면 된다.

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
| `docs/manuals/운영_unknown상태_대응절차.md` | `release_checklist` · DoD 문서 |
| `docs/vision/TODO_VISION.md` | `RULE.md` |

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


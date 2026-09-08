---
type: policy
title: 작업 루프와 기록 의무
description: 세션마다 무엇을 읽고 무엇을 남기는가. 파일명 체계가 wiki와 충돌한다
status: draft
tags: [governance, documentation]
---

# 작업 루프와 기록 의무

`[실측]` 원본은 `RULE.md`. **프로세스 규칙이고, 도메인 규칙은 `CLAUDE.md` 에 있다.**

## ★ 두 저장소의 `RULE.md` 가 완전히 같다

`[실측]` 2026-09-02 확인.

```bash
diff final_project_cs/RULE.md final_project_sample/RULE.md
# 차이 0줄
```

**같은 프로세스 규칙을 두 벌 들고 있다.** 한쪽만 고치면 조용히 갈라진다.

`[미확보]` **어느 쪽이 정본인지 정해져 있지 않다.** 셋 중 하나여야 한다.

```
① 루트로 올린다 (프로세스는 저장소 무관이다)
② 한쪽을 정본으로 하고 다른 쪽은 링크
③ 지금처럼 두 벌 두고 동기화 검사를 건다
```

**③이면 검사가 있어야 한다.** 지금은 없다.

## 충돌하면 무엇이 이기나

> **`CLAUDE.md` §0(근거 없이 확정하지 않는다)이 `RULE.md` 의 어떤 조항보다 앞선다.**
>
> 그 밖의 충돌은 **`RULE.md` 가 우선**한다.

**고객이 잘못된 확답이나 승인 없는 결제 변경으로 손해를 보는 것이 절차 위반보다 무겁다.**

그리고 하나 더.

> **중복 조항을 새로 만들지 않는다.** 도메인 규칙은 `CLAUDE.md` 에만 두고 여기서는 링크한다.

## 작업 루프 9단계

```text
[시작]
 0. RULE.md · CLAUDE.md · 이 저장소 wiki/index.md 를 먼저 읽는다. 대상 wiki 페이지를 읽고, wiki/records/ 는 근거 확인할 때만
    ★읽지 못했거나 어떤 문서가 적용되는지 모르면 파일 변경을 시작하지 않는다
 1. 할 일·현재 상태 — 허브 wiki/delivery/open-items.md · wiki/decisions/
 2. (삭제, 2026-09-08) records/history · records/plans 는 동결

[수행]
 3. 계획서(v9)·wiki 결정의 해당 단계만 한다. 범위 밖이면 open-items 에 올리고 결정 먼저
 4. 코드를 대체·삭제하면 legacy/ 에 보존한다
 5. 실행·테스트로 검증하고 재현 명령과 출력을 wiki/records/evidence/ 에 남긴다

[종료]
 6. wiki/records/reports/ 에 작업 리포트 (필수, 생략 불가). 파일명은 날짜 접두 그대로
 7. wiki 에 결론 한 줄 + 리포트 링크. 주장이 바뀌면 그 페이지를 고친다. 같은 내용을 두 곳에 쓰지 않는다
 8. (삭제, 2026-09-08) history·plans 갱신 없음 — 7 에서 open-items 를 고친다
```

**0번이 강제다.** 무엇이 적용되는지 모르면 손대지 않는다.

| 규칙 | |
|---|---|
| 범위 초과 금지 | 범위 변경이 필요하면 **계획서를 먼저 고치고 사유를 남긴다** |
| 작업 단위 | **"검증 가능한 최소 단위"**. 한 번에 여러 기능을 섞지 않는다 |

## 버그를 찾으면 리포트부터 쓴다

`[실측]` **고치는지와 무관하게 즉시 기록한다.** 다섯 항목.

```
위치 · 재현 · 실측 · 위험도 · 잘못 보고한 수치 정정
```

**마지막이 중요하다.** 전에 낸 숫자가 틀렸으면 그것도 같이 적는다.

## "지금은 안 한다"로 끝내지 않는다

`[실측]` 미루는 결정은 `docs/vision/` 에 등록한다.

| 적을 것 | |
|---|---|
| **관측 가능한 도입 트리거** | "나중에"가 아니라 **무엇이 몇 건 쌓이면** |
| 실소요 일수 | |
| **폐기 조건** | 언제 이 항목을 버리나 |

**트리거가 관측 가능해야 한다.** → [D-009](../decisions/D-009-recommendation-scope.md) 의 `30일에 50건 또는 동일 유형 10건`

## ★ 파일명 체계가 이 wiki 와 다르다

`[실측]` `RULE.md` 4.2 의 규칙.

```
YYYY-MM-DD_HHmm_<제목>.md      기본
NN_<제목>.md                   docs/handoff/  — 시점이 아니라 순서로 읽는다
DoD-NN_<항목>.md               docs/evidence/
VISION-NN_<제목>.md            docs/vision/   — 시점이 아니라 주제로 읽는다
```

**이 wiki 는 kebab-case 다.** `core-design.md`·`team-contract.md`.

| | 이유 |
|---|---|
| `docs/` | **작업 기록.** 언제 썼는지가 정보다 |
| `wiki/` | **현재 지식.** 언제 썼는지는 front matter 에 있다 |

**둘은 다른 것을 담으므로 체계가 달라도 된다.** 다만 **한 트리 안에서 섞이면 안 된다.**

`[미확보]` **wiki 가 `program/` 을 떠나 실제 저장소로 들어갈 때 어디에 놓을지 안 정했다.** `docs/wiki/` 로 들어가면 4.2 와 부딪힌다.

### 갱신 규칙은 같다

`handoff` 와 `vision` 은 **갱신할 때 파일을 새로 만들지 않고 같은 번호를 고치고 안에 개정 이력을 남긴다.**

**이 wiki 도 같다.** → [review-policy.md](review-policy.md)

## 기준선 참조가 낡았다

`[실측]` `RULE.md` 가 `A-COP_구현계획서_v6.md` 를 **"구현·평가 기준선"**이라 부른다.

**지금 기준선은 v9 다**(2026-09-06 판올림. v8 은 `program/plan/archive/`). → 루트 `CLAUDE.md`

`[미확보]` **v6 참조 13곳을 고쳐야 하는지, 아니면 RULE.md 자체를 갱신할지 안 정했다.**

**[drift-case-voc.md](drift-case-voc.md) 와 같은 종류의 위험이다** — 낡은 참조가 규칙 문서에 남아 있고, 규칙 문서는 자주 읽힌다.

## ★ [2026-09-03] 구조를 옮길 때 — 되돌릴 여지를 남긴다

`[실측]` `final_project_cs/wiki/records/handoff/07_모듈화_구조.md` §5 에서 이관. **코드 이동 규칙인데 문서 이관에도 그대로 맞는다.**

| # | 규칙 |
|---|---|
| 1 | **테스트가 계속 통과해야 한다.** 당시 `113 passed` 가 기준선이었다 |
| 2 | **기존 경로에 re-export 를 남긴다** — 한 번에 모든 호출부를 고치면 되돌리기 어렵다 |
| 3 | **한 계층씩** 옮기고 매번 `pytest tests -q` 를 돌린다 |
| 4 | `transition_case()` 단일 진입점·append-only·Core 격리는 **구조가 바뀌어도 유지된다** |

### 2번이 핵심이다

```python
# app/core/contracts.py
from app.core.case_runtime.contracts import *
```

**옮기되 옛 문을 열어 둔다.** 그러면 호출부를 천천히 고칠 수 있고, 잘못되면 되돌릴 수 있다.

### 이 wiki 전환에도 그대로 맞는다

`[실측]` [cutover.md](cutover.md) 가 **305곳 링크를 한 번에 고쳐야 한다**고 적고 있다.

**2번을 적용하면 다르게 할 수 있다** — 옛 경로에 **"여기로 옮겼다"는 한 줄짜리 문서**를 남기면 링크가 안 깨진다.

`[미확보]` **그 방식을 쓸지 안 정했다.** 파일이 두 배로 늘어나는 대가가 있다.

**다만 4번은 이미 지키고 있다** — [check_wiki.py](review-policy.md) 의 불변식 검사가 구조와 무관하게 돈다.

## ★ [2026-09-08] `docs/` 를 `wiki/records/` 로 합쳤다

`[실측]` 사용자 결정. 진입점 하나·검사기 하나로 가고, 기록은 압축·삭제할 수 있게 한다. 도구는 `program/scripts/merge_docs_apply.py`(zip 백업 → 링크 재계산 → `git mv`). 백업은 `program/research/_backup/2026-09-08_docs_통합전.zip` 과 태그 `docs-pre-merge-2026-09-08`.

| 기록 구역 `wiki/records/` | 무엇 | 지위 |
|---|---|---|
| `evidence/` · `reports/` | 재현 출력 · 작업 리포트(디버그 리포트 포함) | **계속 쓴다.** 날짜 파일명 그대로, 고치지 않는다 |
| `handoff/` | 계약·지시서 129건 | **동결.** 계약의 현재 정본은 wiki 본문(contracts·teams·external). 인용 63곳이 있어 2단계에서 정리 |
| `history/` · `plans/` · `vision/` · `manuals/` · `submission/` · `TODO/` · `labeling/` · `screenshots/` | 옛 작업 기록 | **동결.** 읽기 전용. wiki 가 필요한 것만 인용 |

**검사기 규칙.** `records/` 는 front matter·크기·index 규칙을 적용하지 않고, 깨진 링크는 위반이 아니라 집계로만 낸다 — 옛 기록의 링크가 낡는 건 정상이고, 그걸 고치면 기록이 아니게 된다. 파일명도 kebab-case 규칙의 예외다(§4.2 날짜 접두 유지).

**이중 작업이 어디서 없어졌나.** 전에는 세션마다 evidence·reports·history·plans 넷을 쓰고 wiki 도 따로 갱신했다. 지금은 evidence(있을 때)·리포트·wiki 한 줄이고, 같은 문장을 두 곳에 쓰지 않는다. history 44건 중 wiki 가 인용한 건 1건, reports 173건 중 6건이었다 — 아무도 안 읽던 기록을 계속 쓰고 있었다.

## 관계

- [review-policy.md](review-policy.md) — 정합성 점검 주기
- [drift-case-voc.md](drift-case-voc.md) — 낡은 문장이 규칙이 된 사고
- [structure-guide.md](structure-guide.md) — wiki 배치 규칙
- 원본: `final_project_cs/RULE.md` · `final_project_sample/RULE.md` (**내용 동일**)

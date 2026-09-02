---
type: plan
title: 릴리스 게이트
description: 기능 게이트 통과와 RC 선언은 다르다. 지금 RC 를 막고 있는 것은 judge agreement 미측정이다
status: draft
tags: [release, evaluation]
owners: [human:미배정]
---

# 릴리스 게이트

`[실측]` `docs/release_checklist.md`에서 이관.

**각 항목은 재현 명령과 합격선을 함께 적는다.**

## ★ 기능 게이트와 RC 를 분리한다

| | 뜻 | 지금 |
|---|---|---|
| **기능 게이트** | DoD 항목이 통과하는가 | 통과 24 · 부분통과 4 |
| **RC 선언** | 내보내도 되는가 | **아니다** |

**둘을 섞으면 안 된다.** 기능이 다 돌아도 내보낼 수 없는 상태가 있다.

## 지금 RC 를 막는 것 — judge agreement

`[실측]` **사람 라벨 20건과 대조하지 않았다.**

기계 검사는 했다.

```bash
python -m eval.check_judge
```

540행 전량에서 **근거 없이 grounding 점수를 받은 행 0건.** 0이 아니면 exit 1.

**그런데 이게 잡는 것은 judge 가 대놓고 틀리는 경우뿐이다.**

**그럴듯하게 틀리는 경우** — 답변이 실제로 옳은지, `correctness`·`safety` 점수가 사람 판단과 맞는지 — 는 **여전히 모른다.**

> **judge 가 사람과 얼마나 맞는지 모르는 상태에서 평가 수치를 근거로 내보낼 수 없다.**

### 필요한 것

```
golden 20건을 사람이 rubric 대로 채점
→ judge 점수와 일치율·Cohen's κ 산출
```

`[미확보]` **1인 환경이라 2인 독립 라벨링 + adjudication 이 불가하다.** 그 한계를 함께 적어야 한다.

**이 프로젝트가 [type 분류 검증](../governance/type-verification/index.md)에서 codex 를 독립 판정자로 쓴 것과 같은 문제다.** 혼자 하면 확증 편향이 들어간다.

## 일반화 한계

**golden 60건 × 3회는 방향성과 불확실성을 말한다.** 다음을 증명하지 **않는다.**

```
모집단 일반화 · 장기 drift · 실제 손실률 · SLA
```

### ablation 도 마찬가지다

`[실측]` `no_approval`·`no_feedback_inline`·`no_team_split` 이 차이를 안 보였다.

> **효과가 없다는 뜻이 아니라 이 지표가 재지 않는다는 뜻이다.**

**이 구분이 중요하다.** 차이 없음을 "필요 없다"로 읽으면 안전장치를 걷어내게 된다.

## 검사 항목

| 층 | 무엇 | 합격선 |
|---|---|---|
| **빌드·테스트** | `pytest` · `python -m scripts.verify_dod` | **실패·skip·flaky 0** |
| **안전** | 되돌릴 수 없는 것 — 승인·idempotency·감사 | 불변식 통과 |
| **데이터·격리** | tenant·PII | `INV-CS-SEC-*` |
| **배포 산출물** | `publish_public` 검증 | **내부 문서·작업 흔적·AI 커밋 identity 제외 확인** |

**배포 산출물 행이 놓치기 쉽다.** 공개 대상 파일 수를 세고, **내부 흔적이 안 섞였는지** 확인한다.

## 미해결 — 차단은 아님

`[실측]` RC 를 막지는 않지만 남아 있는 것.

| 항목 | 상태 |
|---|---|
| 마우스 오버 하이라이트 튐 | **원인 미특정.** 브라우저 제어가 없어 재현 자체를 못 함 |
| 커밋 ↔ Phase 수동 매핑 | 자동화 안 됨 |
| 화면 캡처 | 없음 |
| mock 결제 timeout E2E | `[미확보]` |

**첫 줄이 정직하다.** 재현을 못 했으면 추측으로 고치지 않는다.

## 관계

- [dod.md](dod.md) — 완료 기준 29항목
- [open-items.md](open-items.md) — 열린 항목
- [../evaluation/judge.md](../evaluation/judge.md) — judge 루브릭
- [../evaluation/protocol.md](../evaluation/protocol.md) — 평가 한계
- [`quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 실행

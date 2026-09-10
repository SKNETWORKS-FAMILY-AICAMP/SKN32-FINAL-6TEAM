---
type: report
title: 분류 정확도와 confusion matrix
description: intent·issue_code 100% 는 모델 입력에 정답이 들어간 결과였다. next_action 52.8% 는 모델이 아니라 Team 로직을 쟀다
status: draft
impl_scope: cs — golden.jsonl 과 Proposed 실행 기록은 cs 도메인 평가다. sample 은 계약 테스트로 검증한다
tags: [evaluation]
domain: neutral
---

# 분류 정확도와 confusion matrix

`[실측]` 2026-09-04. `eval/reports/2026-08-28_reeval_Proposed_v3.jsonl` (72건 golden, 216행 = 72×3) 을 직접 세었다.

## 왜 쟀나

`[실측]` 중간발표 현황정리 §1.1 이 이렇게 적었다.

> **계획서의 60건 분류 정확도·confusion matrix 는 아직 발표 근거가 아니다.**

**이미 있는 실행 기록으로 계산할 수 있었다.**

## 결과 — 셋이 완전히 다르다

| 항목 | 정확도 |
|---|---:|
| **intent** | **100%** (72/72) |
| **issue_code** | **100%** (72/72) |
| **next_action** | **52.8%** (38/72) |

**분류(intent·issue_code)는 완벽하다. 행동 선택(next_action)만 틀린다.**

## ★ confusion matrix — 두 값을 아예 안 낸다

`[실측]` 216행(72건 × 3회) 전체에서 셌다.

```
next_action 분포:  respond 114 · wait_for_approval 60 · escalate 42
                   wait_for_input   0
                   handoff          0
```

**`wait_for_input`과 `handoff`가 216번 중 단 한 번도 안 나왔다.**

### 골든셋 기대값 대비

| 기대 | 건수 | 실제로 나온 것 |
|---|---:|---|
| respond | 40 | respond 28 · wait_for_approval 8 · **escalate 4** |
| wait_for_approval | 15 | wait_for_approval 9 · respond 2 · **escalate 4** |
| **wait_for_input** | **13** | **respond 6 · wait_for_approval 3 · escalate 4** — **정답 0건** |
| escalate | 3 | respond 2 · escalate 1 |
| **handoff** | **1** | **escalate 1** — **정답 0건** |

**`wait_for_input`이 필요한 13건이 전부 다른 셋 중 하나로 잘못 갑니다.**

## ★ [2026-09-10] 이 문서의 수치가 재는 것이 달랐다

`[실측 2026-09-10]` **평가받는 모델의 입력에 정답이 들어가 있었다** — 골든 행 전체가 `json.dumps(record)` 로 프롬프트에 들어간다(`eval/runners/common.py:524`). 상세와 코드 위치는 [protocol.md](protocol.md) 「정답이 모델 입력에 들어간다」.

| 이 문서의 수치 | 실제로 잰 것 |
|---|---|
| intent · issue_code **100%** | **분류 능력이 아니다** — 입력에 `expected_intent`·`expected_issue_code` 가 있었다 |
| next_action **52.8%** | **모델이 아니라 Team 로직**이다 — Proposed 군은 `next_action` 을 Team 결과로 덮어쓴다(`common.py:531`). 그 Team 도 정답 intent 로 골라졌다 |

★**그래서 아래 「프롬프트가 몰라서」「모델 행동 문제」라는 원인 설명은 틀렸다.** 모델이 고른 값이 아니라 Team 이 돌려준 값이다. 아래는 그 전 서술이다.

## 이건 프롬프트가 몰라서다 — `[정정]` Team 로직이다

`[실측]` 계약(`app/core/contracts.py:68-76`)에는 **`NextAction` 이 7개**다.

```python
CONTINUE · WAIT_FOR_INPUT · WAIT_FOR_APPROVAL
CALL_TOOL · HANDOFF · RESPOND · ESCALATE
```

**값은 정의돼 있다.** `[정정 2026-09-10]` 「모델이 그 값을 고르지 않을 뿐」이라 적었는데 **고르는 것은 모델이 아니라 Team 이다**(Proposed 군 `next_action` 은 Team 결과로 덮어쓴다).

> **추가 정보가 필요하면 물어봐야 하는데, 대신 승인 대기로 보내거나(과잉 안전) 그냥 답하거나(과잉 확신) 에스컬레이트한다(과잉 회피).**

**셋 다 안전 쪽으로 치우친 오류다.** 틀린 답을 내지는 않지만, **꼭 필요한 되물음을 안 한다.**

`[미확보]` **왜 그런지는 안 팠다.** 프롬프트에 `wait_for_input`·`handoff` 예시가 없거나, 판단 기준이 명시 안 됐을 수 있다.

## 이게 D-010·평가 결함과 어떻게 다른가

| | 무엇을 잰다 |
|---|---|
| [metrics.md](metrics.md) 결함 1~4 | **judge 채점식**이 옳게 재는지 |
| **이 문서** | **모델이 옳은 값을 고르는지** |

**채점이 맞아도 모델이 틀리면 소용없다.** `[정정 2026-09-10]` 이건 채점 문제도 모델 행동 문제도 아니라 **Team 로직과 평가 러너의 문제**다 — next_action 은 Team 이 정하고, 그 Team 은 정답으로 골라졌다.

## 발표에서 쓸 수 있는 문장

★★`[2026-09-10]` **아래 문장을 쓰면 안 된다.** 「의도 분류는 100%」는 **모델 입력에 정답이 들어간 결과**다. 발표에서 이렇게 말하면 틀린 주장이 된다. **정답을 뺀 상태로 다시 잴 때까지 분류 정확도는 「모른다」가 맞는 답이다.** 아래는 거둔 문장이다.

> **의도 분류(intent·issue_code)는 100%. 다음 행동 선택(next_action)이 약점이고, 특히 "추가 정보를 물어야 할 때" 를 놓친다.**

**숨기지 않고 적는다.** → [../delivery/milestones/midterm-2026-09-15.md](../delivery/milestones/midterm-2026-09-15.md)

## 관계

- [metrics.md](metrics.md) — 평가 지표 결함 4종
- [dod28-rerun.md](dod28-rerun.md) — 재측정 순서
- [../../final_project_cs/wiki/external/rest-api.md](../../final_project_cs/wiki/external/rest-api.md) — `classification_failed` 계약

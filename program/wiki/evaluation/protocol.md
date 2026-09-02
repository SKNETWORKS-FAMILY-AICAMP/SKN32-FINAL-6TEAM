---
type: concept
title: 평가 프로토콜
description: A/B/Proposed 비교군, 60+20 분리, 3회 반복, 통계 처리
status: draft
tags: [evaluation]
owners: [human:미배정]
---

# 평가 프로토콜

## 비교군

| 군 | 구현 | 건당 비용 | p50 | 새 도메인 측정 |
|---|---|---|---|---|
| **A** | 단일 LLM + 원문 prompt + **최소 DB 조회** | `[미확보]` | `[미확보]` | **없음** |
| **B** | 고정 workflow/rule + policy retrieval. **Team 없음** | `[미확보]` | `[미확보]` | **없음** |
| **Proposed** | Case lifecycle + Context Broker + Team + approval + REST/MCP/A2A 경계 | 3.03원 `[실측]` | 20.0초 | golden 216건 |

**B가 "RAG 추가"가 아니라 "고정 workflow + Team 없음"이다.** 이게 정확한 정의다. A→B는 검색의 기여가 아니라 **구조화된 흐름의 기여**를 본다.

## 통제 변수

`[실측]` v8 §15. **이걸 고정하지 않으면 비교가 무의미하다.**

```
model / provider · temperature · seed · dataset
timeout · tool fixture · prompt registry snapshot
```

**`prompt registry snapshot`이 특히 중요하다.** 프롬프트가 바뀌면 같은 모델도 다른 답을 낸다. `prompts` 테이블의 `(prompt_key, version)`과 sha256이 이걸 고정한다.

**세 군을 두는 이유**는 "A-COP이 좋다"가 아니라 **"무엇이 개선을 만들었나"**를 보기 위해서다.

- A → B: RAG의 기여
- B → Proposed: Team 분리·근거 대조·승인 경계의 기여

### ★ Baseline 재측정이 밀려 있다

2026-08-17에 코퍼스와 golden/holdout이 쇼핑몰 도메인으로 교체되면서 **이전 측정이 전부 무효**가 됐다. Proposed만 재측정했다.

`[실측]` 무효가 된 파일들. `case_id`가 `g-billing-*`이다.

```
raw_baseline_a.jsonl   2026-08-13
raw_baseline_b.jsonl   2026-08-13
raw_proposed.jsonl     2026-08-13
abl_no_*.jsonl         2026-08-14   ← ablation 5종도 전부 무효
```

**ablation 5종도 같이 무효다.** "RAG를 빼면 grounding이 3.98→0.00"이라는 방향성은 메커니즘이 안 바뀌었으니 참고할 수 있지만, **수치를 근거로 쓰면 안 된다.**

재측정 명령은 `final_project_cs/docs/reports/2026-08-17_1540_RAG적재_평가데이터셋_재작성_리포트.md` §5에 있다.

## 표본

```
golden   60건   개발 중 반복 측정
holdout  20건   최종 1회만
```

**holdout을 개발 중에 보면 안 된다.** 보는 순간 golden과 같아진다.

`[실측]` 현재 골든셋 총 72건이다. 60+20 분리는 이 중에서 한다.

## 반복

**3회.** LLM 출력이 비결정적이라 1회 측정은 의미가 없다.

같은 입력·같은 설정으로 3회 돌리고 분산을 함께 본다. 분산이 크면 그 자체가 결과다.

## 통계 처리

`[실측]` v8 §15

| 항목 | 방법 |
|---|---|
| 신뢰구간 | **10,000회 paired bootstrap**으로 Proposed−A/B 차이의 95% percentile CI |
| 유의성 | McNemar. **discordant cell이 25 미만이면 exact McNemar** |
| 다중 지표 p-value | **보조 결과로만 표시.** 효과크기와 CI를 우선한다 |
| 한계 | **함께 보고** |

**마지막 두 줄이 이 프로젝트의 태도다.** p-value를 앞세우지 않는다. 표본 60건에서 p<0.05를 여러 지표에 걸쳐 찾으면 우연히 나온다.

**한계를 같이 적는다.** 60건에서 나온 3%p 차이를 유의하다고 주장하지 않는다.

### 밝혀야 할 한계 5가지

`[실측]` v8 §15가 명시한 것.

```
표본 60건 · 고정 도메인 · LLM judge 편향
mock provider 의존성 · 운영 규모 미검증
```

**일반화 주장을 하지 않는다.**

## Ablation

무엇이 기여했는지 보려고 하나씩 뺀다.

`[실측]` 현재 실행된 것들.

| 실험 | 무엇을 뺐나 |
|---|---|
| `abl_no_rag` | RAG |
| `abl_no_approval` | 승인 경계 |
| `abl_no_context_broker` | Context Broker |
| `abl_no_team_split` | Team 분리 |
| `abl_no_feedback_inline` | 인라인 분류 |

## 실행

```bash
python -m eval.run --arm Proposed
```

결과는 `eval/reports/`에 JSONL로 쌓인다. 각 행에 `cost_usd`, `input_tokens`, `output_tokens`, `latency_ms`가 있다.

## 재현 가능성

**같은 명령으로 같은 결과가 나와야 한다.**

| 고정하는 것 | 방법 |
|---|---|
| 프롬프트 | `prompts` 테이블에 버전·sha256 저장 |
| 모델 | 설정에 명시 |
| 골든셋 | 파일 고정 |
| Judge 루브릭 | 버전 저장 |

## 한계

`[미확보]` 세 가지를 인정한다.

1. **골든셋 72건은 적다**
2. **실제 알파 로그가 아니다.** 운영 전환 전이라 실 고객 데이터가 없다
3. **사람 라벨 20건이 아직 없다.** Judge 신뢰도를 확인 못 했다

## 관계

- [metrics.md](metrics.md) — 무엇을 재는가
- [golden-set.md](golden-set.md) — 무엇으로 재는가
- [judge.md](judge.md) — 사람 없이 판정하는 방법
- [`cs/quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 구현
- [`sample/wiki/quality/`](../../final_project_sample/wiki/quality/index.md) — 같은 프로토콜을 계약 테스트로 건다

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

| 군 | 무엇 | 건당 비용 | p50 지연 | 새 도메인 측정 |
|---|---|---|---|---|
| Baseline A | 단순 LLM 호출 | `[미확보]` | `[미확보]` | **없음** |
| Baseline B | RAG 추가 | `[미확보]` | `[미확보]` | **없음** |
| **Proposed** | A-COP 전체 | 3.03원 `[실측]` | 20.0초 | golden 216건 |

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

| 항목 | 방법 | 왜 |
|---|---|---|
| 신뢰구간 | paired bootstrap CI | 표본이 작아 정규성 가정이 위험 |
| 유의성 | McNemar | 같은 케이스를 두 군으로 본 쌍 데이터 |
| 한계 | **함께 보고** | 72건은 적다 |

**한계를 같이 적는다.** 60건에서 나온 3%p 차이를 유의하다고 주장하지 않는다.

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
- [`quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 구현

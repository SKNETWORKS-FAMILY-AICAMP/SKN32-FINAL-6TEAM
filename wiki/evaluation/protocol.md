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

재측정 명령은 `final_project_cs/wiki/records/reports/2026-08-17_1540_RAG적재_평가데이터셋_재작성_리포트.md` §5에 있다.

## ★ [2026-09-05] 이 숫자에 이르기까지 측정 결함 5건을 고쳤다

`[실측]` [DoD-15](../../final_project_cs/wiki/records/evidence/DoD-15_AB_Proposed_60x3_holdout.md)에서. **위 무효가 된 옛 도메인 수치조차, 처음 나온 값이 아니었다.** 순서대로 잡아야 했던 것들이다.

| # | 증상 | 실제 원인 |
|---|---|---|
| 1 | 540행 생성, 전부 성공 | **provider=mock**(fixture)으로 돌렸다 — 진짜 LLM을 안 부른 것 |
| 2 | provider=openai, 540행인데 전부 실패 | 구현 담당 샌드박스가 외부망을 막고 있었다 |
| 3 | A 35/180 · B 0/180 | **judge가 환각 인용에 점수를 줬다** — A가 `doc_06 §1`을 지어냈는데 실재 확인이 없었다 |
| 4 | Proposed 0/180 | 실제 시스템이 안 돌아서 LLM 어댑터가 안 움직였고, `json_object` 400 에러가 나자 **Team이 LLM 결과를 버리고 하드코딩 문구로 대체**하고 있었다 |
| 5 | B 115/180 · Proposed 0/180 | **`next_action` 채점이 어휘 일치를 쟀다** — golden은 자유형 라벨인데 Proposed는 계약 Enum이라 **계약을 지킨 쪽이 벌점**을 받았다 |

**3번과 5번이 가장 위험했다.** 그대로 실었다면 "RAG가 오히려 해롭다"(3번), "Context Broker+Team이 baseline보다 나쁘다"(5번)는 **정반대 결론**이 나왔을 것이다. 이미 잘 동작하는 시스템이 채점 결함 때문에 나쁘게 보이는 쪽이, 안 되는 시스템이 좋게 보이는 쪽보다 알아채기 어렵다 — 결과가 "그럴듯하게" 나쁘기 때문이다.

`[실측]` 1번의 산출물이 **`final_project_cs/eval/reports/2026-08-12_평가결과_리포트.md`로 아직 남아 있다.** 세 군 전부 task success·intent·groundedness 1.00, p95 지연 0.004ms, bootstrap CI `[0, 0]`, McNemar discordant 0 — mock fixture가 낸 값이라 **어디에도 인용하지 않는다.** 리포트 본문은 "실제 과금 $0.000, 로컬 mock fixture 결과"라 스스로 밝히고 있지만 제목만 보면 실측처럼 읽힌다.

### ablation flag 4종이 실행 전엔 아무것도 안 끄고 있었다

`abl_no_approval`·`abl_no_context_broker`·`abl_no_team_split`·`abl_no_feedback_inline` 네 flag가 결과의 `config.ablations`에는 기록되면서 **실제 실행 경로에는 반영되지 않고 있었다** — `no_rag`만 실제로 껐다. 그 상태로 돌렸다면 다섯 구성이 전부 같은 결과를 내 **"각 기능이 기여하지 않는다"는 정반대 결론**이 나왔을 것이다. 실행 전에 발견해 고쳤다.

### `policy_evidence` 필드와 본문 인용은 다른 것을 잰다

baseline_b 20행이 `policy_evidence`에 유효 인용 8건을 담고도 `policy_grounding` 0점을 받은 게 한동안 judge 결함으로 의심됐다. 실제로는 **답변 본문에 인용이 0개**였다 — 필드에는 doc id를 채워 뒀지만 주장에 근거를 붙이지 않은 것이다. `CLAUDE.md §0.1`("모든 핵심 주장에는 Evidence가 붙어야 한다")에 비춰 **judge 쪽이 계약에 더 가까웠다** — 이건 오류가 아니라 `field_only_evidence` 경고로만 남겼다.

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

### ★ 통계 모듈이 카이제곱 통계량을 p값이라고 찍고 있었다

`[실측]` [DoD-16](../../final_project_cs/wiki/records/evidence/DoD-16_bootstrap_McNemar_한계.md). 수정 전 McNemar 출력이 `p_value=38.025000`이었다 — p는 0~1인데 38이다. `(|0−40|−1)²/40 = 38.025`, **통계량이다.** 실제 p는 `6.98e-10`. bootstrap은 `KeyError: 'score'`로 아예 죽어 있었다.

**심사 리포트에 실렸다면 즉시 걸렸을 값이다.** 지금은 알려진 값 검증(b=0·c=40 → p<1e-8 / 합 8 → exact 분기 / 차이 0 → CI가 0 포함)이 `eval/tests/`에 있고 **p가 1을 넘지 않는지 단언**한다. 위 "측정 결함 5건"이 runner·judge 쪽이었다면 이건 **통계 계산 쪽**의 여섯 번째다.

`[실측]` **셀 수 < 25면 exact 분기**는 실제로 탔다 — B vs A는 discordant 6건이라 `exact binomial`로 갔다(옛 도메인 수치라 값 자체는 무효, 분기 동작만 참고).

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

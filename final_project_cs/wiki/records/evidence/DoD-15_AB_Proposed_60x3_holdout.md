# DoD-15 — A/B/Proposed 를 60건×3회 실행하고 holdout 20건을 보존한다

- v5 §20 항목 15 / 검증 방법: harness log
- 실행: 2026-08-13
- 판정: 부분 통과

## 재현 명령

```powershell
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --concurrency 8 --output eval/reports/raw_baseline_a.jsonl
python -m eval.runners.baseline_b ... --output eval/reports/raw_baseline_b.jsonl
python -m eval.runners.proposed   ... --concurrency 2 --output eval/reports/raw_proposed.jsonl
python -m eval.rescore --input eval/reports/raw_<arm>.jsonl --output eval/reports/rescored_<arm>.jsonl
```

## 실제 결과 (재채점본)

| 군 | 행수 | 성공 | policy_grounding | 총점 중앙 | 비용 |
|---|---:|---:|---:|---:|---:|
| A (단일 LLM, RAG 없음) | 180 | **0/180** | 0.00 | 9 | $0.046 |
| B (rule + 정책 retrieval) | 180 | **6/180** | 2.22 | 12 | $0.118 |
| **Proposed** (Case lifecycle + Context Broker + 2 Teams) | 180 | **40/180** | **3.98** | 13 | $0.522 |

**60건 × 3회 × 3군 = 540 관측.** 오류 0건, degraded 1/180(Proposed).
provider `openai`, model `gpt-4o-mini`, temperature 0.0, seed 7.
dataset sha256 `4792f860f6ff...`.

## 통과한 것

- 세 군 **각 180행**(60건×3회) 실행 완료
- 통제 변수 고정: 동일 model·temperature·seed·dataset·prompt snapshot
- ★**holdout 20건은 실행하지 않았다** — 보존됨. 프롬프트 수정에 쓰지 않았다
- 실패를 재시도로 덮지 않았다 (429 발생 시 동시성을 낮춰 **전량 재실행**)
- 각 행에 실행 조건·비용·토큰·latency 가 실측으로 기록됨

## ★부분 통과인 이유

| 항목 | 상태 |
|---|---|
| 60×3 × 3군 실행 | **통과** |
| holdout 20건 보존 | **통과** |
| 통제 변수 고정 | **통과** |
| ★**ablation 5종 실행** | **통과** (2026-08-14, 아래 참조) |
| ★**judge agreement 20건** | ★**여전히 미측정** — 사람 라벨이 없다. 대신 기계 검사를 했다(아래) |
| ★**2인 독립 라벨링 + adjudication** | **미수행** — 1인 환경이라 불가. 대신 라벨 근거를 각 항목에 기록 |

## ★judge 기계 검사 (2026-08-14) — agreement 를 대신하지 못한다

```powershell
python -m eval.check_judge
```

v5 §15-4 는 judge agreement 를 **사람 라벨 20건과의 일치율**로 정의한다.
1인 환경이라 사람 라벨을 만들 수 없다. **없는 것을 있다고 하지 않는다.**
대신 **사람 없이 확인할 수 있는 것**을 쟀다 — 이 프로젝트를 이미 한 번 태운 실패다:

> judge 가 환각 인용에 점수 — A 군이 `doc_06 §1` 을 지어냈고 실재 확인이 없었다
> (`wiki/records/reports/debugs/2026-08-13_1200_평가가_환각인용에_점수를_준다.md`)

| 군 | 행 | 무효 인용 행 | ★**근거 없이 grounding 점수** | 필드에만 근거 |
|---|---:|---:|---:|---:|
| baseline_a | 180 | 0 | **0** | 0 |
| baseline_b | 180 | 0 | **0** | 20 |
| proposed | 180 | 0 | **0** | 0 |

★**540행 전체에서 "실재하지 않는 근거에 점수를 준 행" 이 0건이다.**
defect #3 의 수정이 유지되고 있다. 이 검사는 `check_judge.py` 가 0 이 아니면 **exit 1** 로 실패한다
(★검사하지 않는 규칙은 지켜지지 않는다).

### ★그 과정에서 지표 정의가 어긋나 있다는 걸 찾았다

baseline_b 20행이 **유효 인용 8건을 갖고도 grounding 0** 을 받았다.
judge 의 사유는 이랬다:

```
"Policy grounding is 0 due to the absence of valid citations."
```

**8건이 있는데 없다고 한다.** 처음엔 judge 결함으로 봤으나, 원인은 다른 것이었다:

| 지표 | 무엇을 보는가 |
|---|---|
| `rescore.citations.valid` | prediction 의 **`policy_evidence` 필드**를 코퍼스와 대조 |
| `judge.policy_grounding` | ★**답변 본문**이 근거를 대고 있는지 |

문제의 답변은 이랬다 — 필드에는 doc id 8개, **본문에는 인용 0개**:

```json
{"answer": "I will resend the invoice to your email. Please confirm that your email address is correct.",
 "policy_evidence": ["doc_05#c7", "doc_02#c10", "doc_05#c2", ...8개]}
```

★**judge 쪽이 계약에 더 가깝다.** `CLAUDE.md` §0.1 —
> 모든 핵심 주장에는 `Evidence`(`source_type`·`source_id`·`observed_at`)가 붙어야 한다.

검색 결과를 필드에 담아 둔 것은 **주장에 근거를 붙인 것이 아니다.**
그래서 이 값을 "judge 오류" 로 세지 않고 `field_only_evidence` **경고**로만 낸다.

### ★이 검사가 judge agreement 를 대신하지 못하는 이유

- 잡는 것은 **judge 가 대놓고 틀리는 경우**(없는 근거에 점수)뿐이다
- **judge 가 그럴듯하게 틀리는 경우**는 못 잡는다 — 답변이 실제로 옳은지,
  `correctness`·`safety`·`personalization` 점수가 사람 판단과 맞는지는 여전히 모른다
- 사람 라벨 20건이 있어야 v5 §15-4 를 충족한다. **이 항목은 미측정으로 남는다**

## ★Ablation 5종 (v5 §15-6) — 2026-08-14

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 \
  --provider openai --concurrency 2 --ablation <flag> --output eval/reports/abl_<flag>.jsonl
```

| 구성 | 행 | 성공 | grounding | 총점 평균 | degraded |
|---|---:|---:|---:|---:|---:|
| **Proposed 전체** (180행 기준) | 180 | 40 (22%) | **3.98** | 13.00 | 1 |
| **`no_context_broker`** | 60 | **0** | **0.00** | **4.98** | **60** |
| **`no_rag`** | 60 | **0** | **0.00** | **5.10** | **60** |
| `no_approval` | 60 | 13 (22%) | 3.98 | 13.25 | 0 |
| `no_feedback_inline` | 60 | 13 (22%) | 4.00 | 13.03 | 0 |
| `no_team_split` | 60 | 13 (22%) | 3.93 | 13.00 | 1 |

### 읽는 법

★**Context Broker 와 RAG 를 빼면 성능이 붕괴한다.**
grounding 3.98 → 0.00, 총점 13 → 5, degraded 60/60. 근거를 못 찾으니 확정 답변을 못 만든다.
**이 시스템의 성능은 근거 조합에서 나온다**는 것이 ablation 으로 확인됐다.

★**나머지 세 기능(`no_approval`·`no_feedback_inline`·`no_team_split`)은
이 지표로 차이가 관측되지 않았다.** 성공률·grounding·총점이 전체 구성과 거의 같다.

**★이것을 "세 기능이 기여하지 않는다" 로 읽으면 안 된다.**
- `no_approval` — 승인은 **안전** 장치다. golden 60건 중 승인이 필요한 케이스가 소수이고,
  rubric 의 `safety` 항목이 승인 여부를 직접 채점하지 않는다
- `no_feedback_inline` — VOC 분류는 **일일 집계와 급증 탐지**를 위한 것이고,
  단건 답변 품질을 재는 이 지표와 목적이 다르다
- `no_team_split` — golden 60건이 billing/technical 로 나뉘어 있어도
  단일 Team 이 처리 못 할 만큼 복잡한 케이스가 적을 수 있다

**지표가 재지 않는 것을 "효과 없음" 으로 결론내지 않는다.**
세 기능의 가치를 재려면 다른 측정이 필요하다 —
승인은 **잘못된 side effect 발생률**, VOC 는 **급증 탐지 정확도**,
Team 분리는 **도메인이 늘었을 때의 확장성**.

### ★ablation flag 4종이 실제로는 아무것도 끄지 않고 있었다

이 실행 전에 발견했다:
> 기존 구현에서 실제 실행 경로에 반영되던 것은 `no_rag` 뿐이었다.
> 나머지 네 flag 는 결과 `config.ablations` 에 **기록되지만 기능을 끄지 않았다.**

그 상태로 돌렸다면 다섯 구성이 모두 같은 결과를 내고
**"각 기능이 기여하지 않는다" 는 정반대 결론**이 나왔을 것이다.
→ `wiki/records/reports/2026-08-14_S-TRACE-ABL_리포트.md`

## ★이 결과에 이르기까지 측정 결함 5건을 고쳤다

이 수치는 **처음 나온 값이 아니다.** 다음을 차례로 잡아 고친 뒤의 값이다:

| # | 증상 | 실제 원인 |
|---|---|---|
| 1 | 540행 생성, 전부 성공 | **provider=mock** (fixture) |
| 2 | provider=openai, 540행 | **전 건 `APIConnectionError`** (구현 담당 샌드박스는 외부망 차단) |
| 3 | A 35/180 · B 0/180 | ★**judge 가 환각 인용에 점수** — A 가 `doc_06 §1` 을 지어냈고 실재 확인이 없었다 |
| 4 | Proposed 0/180 | **실제 시스템 미실행** → LLM 어댑터 미동작 → `json_object` 400 → **Team 이 LLM 결과를 버리고 하드코딩 문구 사용** |
| 5 | B 115/180 · Proposed 0/180 | ★**`next_action` 이 어휘 일치를 쟀다** — golden 이 자유형 라벨, Proposed 는 계약 Enum. **계약을 지킨 쪽이 벌점** |

★특히 **3번과 5번은 그럴듯한 숫자를 냈다.** 그대로 실었다면
"RAG 가 오히려 해롭다"(3번), "Context Broker + Team 이 baseline 보다 나쁘다"(5번)는
**정반대 결론**을 냈을 것이다.

관련 결함 리포트:
- `wiki/records/reports/debugs/2026-08-13_1200_평가가_환각인용에_점수를_준다.md`
- `wiki/records/reports/debugs/2026-08-13_1500_Proposed군이_실제시스템을_돌리지_않는다.md`
- `wiki/records/reports/debugs/2026-08-13_1600_Team의_LLM_실호출_경로가_동작한적이_없다.md`
- `wiki/records/reports/debugs/2026-08-13_1800_next_action_지표가_어휘일치를_잰다.md`

## 재측정 조건 (통과로 바꾸려면)

1. ~~ablation 5종 실행~~ → **2026-08-14 완료**
2. ★**judge agreement — 사람 라벨 20건과 judge 판정의 일치율.** 여전히 남아 있다.
   `eval/check_judge.py` 는 이것을 대신하지 못한다 (위 참조)

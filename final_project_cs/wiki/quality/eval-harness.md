---
type: guide
title: 평가 하네스
description: A/B/Proposed 세 군을 돌리고 통계까지 내는 실행 도구
status: draft
tags: [evaluation, testing]
owners: [human:미배정]
domain: neutral
domain_note: 하네스 구조는 도메인 무관이다. 「여행 시나리오 측정」 절만 지금 도메인의 데이터셋·러너를 가리킨다(쇼핑몰 골든셋과 분모가 다르다)
---

# 평가 하네스

`eval/`

## 구조

```text
eval/
├─ runners/        baseline_a.py · baseline_b.py · proposed.py · common.py
│                  travel_scenarios.py      ← [2026-09-22] 여행 시나리오 측정(DoD-22)
├─ stats/          bootstrap · mcnemar · agreement
├─ datasets/       golden.jsonl (72) · holdout (24)   ← [정정 2026-09-10] 60·20 으로 적혀 있었다
│                  travel_scenarios.jsonl (10)        ← [2026-09-22] 여행용. 위 둘은 쇼핑몰 시절 것이다
├─ reports/        실행 결과 JSONL · travel_scenarios_<run>.json
└─ finetune/       자체호스팅 실험
```

## 여행 시나리오 측정 `[2026-09-22]`

```bash
python -m eval.runners.travel_scenarios              # 전체 10건, 보고서는 eval/reports/
python -m eval.runners.travel_scenarios --case t-cash-only --keep
```

확정 시나리오 하루를 변형해 흘리고(감시 사건 넣기·빼기 · 고객 신고 · 재요청 · 여행 제약 교체), **적용된 모든 일정 버전**을 등록 때와 **같은 판정기**(`app/modules/travel_ops/itinerary_checks.py`)로 다시 본다 — 겹침 · 이동 소요 · 영업시간 · 브레이크 · 결제 수단 · 예산. v11 DoD-22 「필수 조건 위반 0건」이 이것이다.

| | |
|---|---|
| 실측(2026-09-22) | 10/10 통과 · **필수 조건 위반 0건** |
| 일부러 깨뜨림 | 대안 고르기의 결제 조건 필터를 끄니 `t-cash-only` 에서 위반 3건을 잡았다 — 이 측정이 실제로 본다는 뜻이다 |
| LLM | **안 부른다.** 분류·신고 추출은 흉내이고 감시 소스는 재생이다 — 이 측정이 보는 것은 판단과 적용이다. 실제 모델까지 넣은 하루 측정은 [이식 검증 §7](../records/evidence/CASE-VERSION-ITINERARY_이식검증.md) |
| ★표본 | 시나리오 10건 · 하루 1종 · 서울 1도시. **다른 일정을 대표하지 않는다** |

★사건을 「없던 일」로 만들 때는 **평상 수치로 바꾼다.** 타임라인에서 통째로 빼면 그 시간대에 값이 없어져 「소스가 답하지 않음」(결정 15 의 치명)이 되고, 그건 「사건 없는 하루」가 아니다 — 첫 두 실행에서 실제로 그렇게 났다.

회귀 고정은 `tests/scenario/test_travel_eval_scenarios.py` 가 성격이 다른 네 건만 돌린다(전부 돌리면 시험 한 판이 길어진다).

## 실행

```bash
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
```

```bash
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
```

```bash
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

## 결과 형식

각 행에 이것들이 있다.

```json
{"case_id": "...", "arm": "Proposed", "repeat": 1, "run_id": "...",
 "success": true, "score": 18, "input_tokens": 8968, "output_tokens": 1366,
 "latency_ms": 19980, "cost_usd": 0.002165, "retries": 0, "degraded": false,
 "prediction": {...}, "team_result": {...}, "citations": [...], "judge": {...}}
```

**비용·토큰·지연이 행마다 들어 있다.** 그래서 [사업성 원가](../../../wiki/business/infrastructure-cost.md)를 여기서 바로 뽑는다.

## ★ 어느 파일이 유효한가

`[실측]` **2026-08-17에 도메인이 쇼핑몰로 교체되면서 이전 측정이 전부 무효가 됐다.**

판별법은 `case_id`다.

| `case_id` 패턴 | 도메인 | 유효 |
|---|---|---|
| `g-billing-*` · `g-technical-*` | 옛 구독 | **무효** |
| `g-exchange-*` · `g-order-*` · `h-*` · `synth-*` | 쇼핑몰 | 유효 |

```bash
python -c "import json; print(json.loads(open('eval/reports/raw_proposed.jsonl',encoding='utf-8').readline())['case_id'])"
```

**무효 파일 목록** `[실측]`

```
raw.jsonl · raw_proposed.jsonl · raw_baseline_a.jsonl · raw_baseline_b.jsonl
pairs*.jsonl · rescored_*.jsonl · live_smoke.jsonl
abl_no_*.jsonl   ← ablation 5종 전부
```

**유효한 기준값** `[실측]`

```
2026-08-28_reeval_Proposed_v3.jsonl   golden 216건   3.03원 · p50 20.0초
2026-08-30_holdout_proposed.jsonl     holdout 72건   3.20원
```

## 지금 비어 있는 것

`[미확보]` **Baseline A·B의 새 도메인 재측정본이 없다.**

그래서 "A-COP이 단순 LLM보다 낫다"를 수치로 말할 수 없다. **ablation 5종도 같이 무효다.**

재측정 명령은 `wiki/records/reports/2026-08-17_1540_RAG적재_평가데이터셋_재작성_리포트.md` §5.

## 재현성

같은 명령이 같은 결과를 내야 한다.

| 고정하는 것 | 방법 |
|---|---|
| 프롬프트 | `prompts` 테이블에 `(prompt_key, version)` UNIQUE + sha256 immutable |
| 어떤 프롬프트가 만든 답인지 | `llm_calls.prompt_id` FK |
| 실행 조건 | `run_id` + `seed` + `model` + prompt snapshot을 파일명·메타에 박음 |
| Context 예산 | 12,000 고정. 바꾸면 이전과 비교 불가 |

**덮어쓰지 않고 공존시킨다.** 프롬프트·모델이 바뀌면 결과가 달라지기 때문이다.

## Judge

`eval/check_judge.py`가 **근거 없이 grounding 점수를 받은 행**을 센다. 0이 아니면 exit 1.

`[미확보]` **사람 라벨 20건 대조는 아직 안 했다.** 기계 검사는 agreement를 대신하지 못한다.

→ [../../../wiki/evaluation/judge.md](../../../wiki/evaluation/judge.md)

## 자주 걸리는 함정

`[실측]` 실제로 겪은 것들.

**하나 — runner가 삭제된 모듈을 import.** `eval/runners/common.py`가 없어진 옛 Team 모듈을 import해 라이브 경로가 깨져 있었다. **pytest가 이 모듈을 안 돌려서 안 잡혔다.**

**둘 — holdout을 건드리는 것.** 만지는 순간 holdout이 아니다.

**셋 — 평균만 보고하는 것.** paired bootstrap 95% CI와 McNemar를 함께 낸다.

## 관계

- [invariants.md](invariants.md) — 불변식은 pytest가, 품질은 하네스가 본다
- [test-map.md](test-map.md) — 테스트 위치
- [../../../wiki/evaluation/protocol.md](../../../wiki/evaluation/protocol.md) — 평가 설계
- [../../../wiki/evaluation/metrics.md](../../../wiki/evaluation/metrics.md) — 지표 정의
- [../../../wiki/business/infrastructure-cost.md](../../../wiki/business/infrastructure-cost.md) — 원가를 여기서 뽑는다

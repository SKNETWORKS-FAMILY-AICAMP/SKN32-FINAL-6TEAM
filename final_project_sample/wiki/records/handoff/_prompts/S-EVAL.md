# Codex — 스트림 S-EVAL (골든 데이터셋 · A/B/Proposed 하네스 · 통계)

## 0. 먼저 읽을 것
1. `RULE.md` ★§1.4(평가 수치는 분모를 함께 적는다) §3.4
2. `CLAUDE.md` ★§4 — 평균만 보고하지 않는다 / holdout 으로 프롬프트 고치지 않는다 / 표본이 작으면 작다고 말한다
3. `wiki/records/handoff/06_가드레일_수치.md` **§8 평가 수치**
4. `../A-COP_구현계획서_v5.md` **§15 전체** ← 이번 작업의 기준. 읽기 전용, **수정 금지**
5. 구현돼 있는 것: `app/core/contracts.py`, `app/core/context.py`,
   `app/infrastructure/rag/retriever.py`, `app/presentation/api/**`, `app/core/settings.py`

## 1. 소유 범위
```
eval/**            (datasets, runners, judge, stats, reports)
prompts/judge/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**. `app/**`, `knowledge/**`, `scripts/**`, `tests/**` 를 건드리지 마라.
지금 `app/modules/`, `app/application/` 은 **다른 세션이 작업 중**이다.

## 2. 만들 것 (v5 §15-7 구조 그대로)
```
eval/
  datasets/{golden.jsonl, holdout.jsonl}
  runners/{baseline_a.py, baseline_b.py, proposed.py}
  judge/rubric.json
  stats/{bootstrap.py, mcnemar.py}
  reports/
```

### 2-1. 데이터셋 (v5 §15-2)
- `golden.jsonl` **60건** — billing 20 / technical 20 / feedback·other 20
- `holdout.jsonl` **20건** — ★평가 기간 중 프롬프트 수정에 쓰지 않는다
- 각 유형에 **정상·모호·PII·승인 필요·RAG degraded** 사례를 섞는다
- 필드: `case_id`, `message`, `channel`, `expected_intent`, `expected_issue_code`,
  `expected_sentiment`, `expected_next_action`, `notes`
- ★도메인은 **Nimbus**(Free/Pro/Business). `knowledge/documents/` 의 정책과 **모순되면 안 된다** —
  코퍼스를 읽고 맞춰라 (코퍼스는 인수 완료, **수정 금지**)
- ★2인 독립 라벨링은 이 환경에서 불가하다. **그 사실을 리포트에 명시**하고,
  라벨 근거(어느 정책 섹션에 따른 것인지)를 각 항목에 남겨 대체하라

### 2-2. 러너 (v5 §15-1)
| 군 | 구현 |
|---|---|
| A | 단일 LLM + 원문 prompt + 최소 DB 조회 |
| B | 고정 workflow/rule + 정책 retrieval, Team 없음 |
| Proposed | Case lifecycle + Context Broker + 2 Teams + approval + REST |

- 통제 변수 고정: 동일 model/provider·temperature·seed·dataset·timeout·prompt snapshot
- ★`--repeats 3 --seed 7` (`06` §8). 실행 조건을 결과 파일에 **박아 넣어라**
- ★**Proposed 러너는 Team 구현에 의존한다.** 아직 없으면 `--arm proposed` 가
  **명확한 오류로 실패**하게 하라. 가짜 결과를 만들지 마라
- 결과: `eval/reports/raw.jsonl` (Case별 성공/실패·점수·latency·cost·degraded 여부)

### 2-3. Judge (v5 §15-4)
`judge/rubric.json` — 기준 5종(correctness/policy_grounding/next_action/safety/personalization)
각 0~4, `pass_rule: "safety>=3 and correctness>=3 and total>=16"`.
judge prompt 는 `prompts/judge/` 에 두고 버전을 박는다.

### 2-4. 통계 (v5 §15-5) ★핵심
```powershell
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```
- **paired bootstrap 10,000회**, 95% percentile CI. `seed` 고정
- **McNemar** — discordant pair. 셀 수 **< 25 면 exact**(`scipy.stats.binomtest`)
- ★출력에 **평균만 쓰지 마라.** `mean diff [CI_low, CI_high]` 형식
- ★**CI 가 0 을 걸치면 "유의하지 않다"고 쓰라.** "우수하다"로 쓰면 결함이다

### 2-5. Ablation (v5 §15-6)
`no_context_broker`, `no_team_split`, `no_approval`, `no_rag`, `no_feedback_inline` 플래그.

## 3. ★한계 서술 (v5 §15-8) — 빠지면 미완료
리포트 템플릿에 **반드시** 넣는다: 60건×3회는 통제 조건에서의 **방향성과 불확실성**만 말한다.
모집단 일반화·장기 drift·실제 손실률·모든 도메인 우월성·운영 SLA 를 **증명하지 않는다**.
holdout 20건은 과적합 감시용이며 대표성을 보장하지 않는다.

## 4. 테스트
`eval/` 안에 자체 테스트를 둔다 (`tests/` 는 당신 소유가 아니다):
1. `bootstrap` 이 **알려진 입력에 대해 알려진 CI** 를 낸다 (고정 seed)
2. `mcnemar` 가 셀 수 < 25 일 때 **exact 로 분기**한다
3. golden 60건 / holdout 20건 **건수와 유형 배분**을 세는 검사
4. golden 과 holdout 에 **중복 항목이 없다**

## 5. 완료 조건 (실제로 돌리고 출력을 붙인다)
```powershell
python -m eval.stats.bootstrap --input eval/reports/sample_raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/sample_pairs.jsonl
python -c "import json;print(sum(1 for _ in open('eval/datasets/golden.jsonl',encoding='utf-8')))"
python -c "import json;print(sum(1 for _ in open('eval/datasets/holdout.jsonl',encoding='utf-8')))"
```
기대: `60`, `20`. 통계 모듈은 **샘플 입력으로 실제 실행**해 출력을 보여라.

★러너 실행(A/B)은 LLM 비용이 든다. **먼저 `--dry-run` 으로 호출 수와 예상 비용을 출력**하고,
실제 실행은 **소규모(예: 5건)로만** 해서 파이프라인이 도는 것을 증명하라.
60건×3회 전량 실행은 **하지 마라** — Claude 가 판단해서 따로 지시한다.

## 6. 리포트
`wiki/records/reports/2026-08-12_S-EVAL_리포트.md` — §5 **실제 출력 원문**, 데이터셋 배분표,
통계 모듈 검증 결과, **2인 라벨링 불가에 대한 대체 방법**, 한계 서술 포함 여부.
`wiki/records/history/2026-08-12_S-EVAL.md` 이력 추가.

## 7. 하지 말 것
- ❌ 소유 범위 밖 수정 (`app/**`, `tests/**`, `knowledge/**`)
- ❌ Team 없이 Proposed 결과를 **지어내기**
- ❌ 평균만 보고 / CI 가 0 을 걸치는데 "우수" 라고 쓰기
- ❌ holdout 을 튜닝에 쓰기
- ❌ 60건×3회 전량 실행 (비용)
- ❌ 한계 서술 생략
- ❌ 명령을 돌리지 않고 "동작함"

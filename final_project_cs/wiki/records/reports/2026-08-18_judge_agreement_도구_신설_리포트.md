# 작업 리포트 — judge-사람 라벨 agreement 도구 신설 (DoD-15/17 차단 항목의 절반)

- 담당: Claude (전 과정 직접 수행)
- 계획: 없음. `wiki/records/evidence/DoD-15_AB_Proposed_60x3_holdout.md`/`DoD-17_마일스톤_게이트.md`
  가 "judge agreement 사람 라벨 20건만 있으면 통과로 바뀐다"고 적어 뒀길래
  라벨을 소비할 도구(`eval/label_holdout_template.py`, `eval/stats/agreement.py`)
  가 실제로 있는지 확인하다가, **둘 다 저장소에 존재하지 않는다**는 것을 발견했다.

## 1. 무엇을 발견했나

과거 세션 기록(메모리)에 "도구는 준비됨"이라고 적혀 있었지만 실측 결과
`eval/label_holdout_template.py`, `eval/stats/agreement.py`,
`eval/reports/holdout_human_labels_template.jsonl` 셋 다 **존재하지
않았다.** 사람이 지금 당장 라벨 20건을 채워도 그걸 읽어서 judge 점수와
비교할 도구가 없었다는 뜻이다. **"없는 것을 있다고 적어 둔 기록"** 자체가
`CLAUDE.md` §1 "지어내지 않는다"에 걸리는 결함이라 여기서 바로잡는다.

## 2. 무엇을 만들었나

- `eval/label_holdout_template.py` — holdout 20건에 대해 사람이 채울
  빈 라벨 템플릿(judge 와 같은 rubric: correctness/policy_grounding/
  next_action/safety/personalization 0~4 + total + pass)을 만든다.
  `--predictions` 로 rescore 산출물을 주면 candidate 답변을 함께 보여준다
  (judge 점수는 일부러 안 보여준다 — 앵커링 방지). holdout 이 아직
  실행되지 않았으면 `candidate_answer` 를 `null` 로 남기고 몇 건이 비어
  있는지 경고한다 — 조용히 채우지 않는다.
- `eval/stats/agreement.py` — judge 채점 파일과 사람 라벨 파일을
  `case_id` 로 짝지어, rubric 5축 각각의 정확 일치율과 Cohen's kappa
  (`scikit-learn`, 이미 의존성에 있음)를 낸다. 라벨 안 채워진 행·짝
  안 맞는 행을 조용히 넘기지 않고 결과에 명시한다. 표본이 작으면
  경고를 남긴다(`CLAUDE.md` §4).
- 신규 테스트 7건(`eval/tests/test_holdout_labeling.py`) — 합성 데이터로
  완전 일치/불일치/라벨 누락/전체 누락/라벨 0건 상태를 검증한다.
  ★**사람 라벨 값 자체는 지어내지 않았다** — 도구가 올바르게 동작하는지만
  합성 데이터로 검증했다.

## 3. 검증

```powershell
python -m eval.label_holdout_template
# {"output": "...holdout_human_labels_template.jsonl", "rows": 20, "missing_candidate_answer": 20}
```

첫 실행에서 Windows 콘솔(cp949)이 em dash(—)를 못 그려 `UnicodeEncodeError`
로 죽는 실제 버그를 발견해 그 자리에서 고쳤다(일반 마침표로 교체) —
JSON 결과 자체는 문제없이 파일로 저장됐지만, 경고 문구 출력이 죽는 건
운영 스크립트로는 실패다.

```powershell
python -m pytest eval/tests/test_holdout_labeling.py -v
# 7 passed

python -m pytest -q
# 295 passed, 2 deselected (기존 288 + 신규 7)
```

## 4. 아직 안 한 것 (사람 또는 실비용 승인 필요)

1. **holdout 20건을 실제로 실행**해 `rescored_holdout_proposed.jsonl` 을
   만드는 것 — 실 OpenAI 호출 비용이 든다. 이전에도 "실비용, 사용자 승인
   필요"로 미룬 항목이라 여기서도 임의로 돌리지 않았다.
2. **사람이 실제로 20건을 라벨링**하는 것 — 이건 애초에 내가 할 수 없는
   부분이다(judge 와 독립적인 사람 판단이 목적이라 AI 가 대신 채우면
   측정 자체가 무의미해진다).

이 두 가지가 채워지면 `eval.stats.agreement` 로 DoD-15/17 을 실제로
통과 판정할 수 있다 — 지금까지는 "도구가 없어서 못 했다"였다면, 이제는
"도구는 있고 사람 라벨만 있으면 된다"로 바뀌었다.

## 5. 함께 진행한 감사(S-AUDIT-SWEEP-2)

같은 시간에 Codex 에게 `app/domain`·`app/application`·`eval` 을 "발견만"
계약으로 감사시켰다(`wiki/records/reports/2026-08-18_S-AUDIT-SWEEP-2_리포트.md`).
결과 — 패턴 A(status 기본값 누수) 0건, 패턴 C(옛 도메인 잔재) 실행
코드에서 0건(과거 평가 산출물 JSONL 에만 역사적 문자열 존재, 문제 아님).
패턴 B(죽은 코드) 후보 4건은 Codex 가 자기 감사 범위(`app/presentation`·
`scripts` 제외) 때문에 "보류"로 정직하게 남겼는데, Claude 가 전체
저장소로 직접 재확인해 4건 전부 해소했다:

- `fold_events`, `run_daily_feedback`, `recheck_before_execution` — 전부
  감사 범위 밖 파일(`app/core/transition.py`, `scripts/run_daily_feedback.py`,
  `app/presentation/api/cases.py`)에 실제 호출부가 있었다 — 오탐.
- `allowed_next_statuses` — 자기 docstring 이 "v5 §5-1 대조용 조회"라고
  명시한 계약 테스트 전용 헬퍼다. 테스트에서만 불리는 게 설계 의도이므로
  결함 아님.

새 결함은 없었다 — 두 번의 audit sweep(app/tools·infrastructure·scripts,
그리고 app/domain·application·eval) 전부 이 세션에서 이미 고친 것 외의
새 항목을 못 찾았다는 뜻이고, 이는 이번 세션의 이전 수정들이 완전했다는
독립적 확인이다.

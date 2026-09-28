# S-JUDGE-AGREEMENT-HARNESS — DoD-15/17 사람 라벨 대조 도구 (라벨링 자체는 범위 밖)

## 배경 (읽지 않아도 되는 맥락)

`wiki/records/evidence/DoD-15_AB_Proposed_60x3_holdout.md`, `DoD-17_마일스톤_게이트.md`
둘 다 같은 항목이 남아 있다고 적는다: **judge 가 사람 라벨 20건과 얼마나
일치하는지(agreement)를 아직 측정 못 했다.** `eval/check_judge.py` 의 docstring
이 이유를 이미 밝혀 놨다 — **"1인 환경이라 사람 라벨을 만들 수 없다."**
그래서 지금까지는 사람 없이 확인 가능한 대체 지표(인용 근거 대조)만 잰다.

이번 작업의 목표는 **라벨을 만드는 게 아니다.** 라벨은 이 저장소의 유일한
사람(사용자)이 직접 20건을 채워야 하고, 그건 이 작업 밖이다. 이번엔 그 사람이
**채우기만 하면 바로 agreement 를 계산할 수 있는 도구**를 만든다.

## 반드시 읽을 파일 (이 목록 밖은 읽지 않아도 된다)

1. `eval/check_judge.py` — 지금 있는 대체 지표. docstring 을 특히 잘 읽는다
2. `eval/stats/mcnemar.py`, `eval/stats/bootstrap.py` — 이 저장소의 통계 스크립트
   스타일(`argparse`, `config/guardrails.yaml` 에서 수치 읽기, 순수 함수 분리) 참고용
3. `eval/datasets/holdout.jsonl` — 20건. `case_id`, `message`, `expected_intent`,
   `expected_issue_code`, `expected_sentiment`, `expected_next_action` 필드
4. `config/guardrails.yaml` 의 `evaluation:` 섹션(약 30줄) — `holdout_size: 20`,
   `judge_pass_rule` 확인용

## 만들 것

### 1. `eval/label_holdout_template.py`
`eval/datasets/holdout.jsonl` 20건을 읽어 **사람이 채울 라벨링 워크시트**를
`eval/reports/holdout_human_labels_template.jsonl` 로 만든다. 각 행에는:
- `case_id`, `message` (원본에서 그대로)
- `human_intent`, `human_issue_code`, `human_sentiment`, `human_pass`(bool),
  `human_notes` — **전부 빈 값**(`null` 또는 `""`)으로 둔다. ★값을 지어내지
  않는다 — 채우는 건 사람의 일이다
- 각 필드 옆에 무엇을 적어야 하는지 짧은 안내 주석을 문서(README 형태로 별도)로 남긴다

### 2. `eval/stats/agreement.py`
`mcnemar.py`/`bootstrap.py` 와 같은 스타일로 만든다. 입력 2개를 받는다:
- 사람이 채운 라벨 파일(1번의 결과물과 같은 스키마)
- judge/시스템 예측 파일(기존 `eval/reports/raw_proposed.jsonl` 류와 같은 스키마 —
  `case_id`, `intent`, `issue_code`, `sentiment` 등)

계산할 것:
- **필드별 exact-match agreement 율** (intent/issue_code/sentiment/pass 각각)
- **Cohen's kappa** — 우연 일치를 보정한 지표. 우연 일치만으로도 점수가 높게
  나올 수 있다는 걸 이 저장소는 이미 한 번 겪었다(judge 가 환각 인용에 점수
  준 사건, `wiki/records/reports/debugs/2026-08-13_1200_평가가_환각인용에_점수를_준다.md`)
  — **exact-match 비율만 보고하지 않는다.**
- `case_id` 가 두 파일에서 안 맞으면(누락/추가) 조용히 넘기지 않고 **명시적으로
  보고한다** (RULE.md §3.2 폴백 금지 — 조용한 스킵 금지)

### 3. 단위 테스트 `tests/unit/eval/test_agreement.py`
**합성 더미 데이터로만** 테스트한다 — 실제 golden/holdout 값이나 실제 judge
점수를 쓰지 않는다(그건 아직 없다). 최소 케이스:
- 완전 일치(kappa=1.0에 가까움)
- 완전 불일치
- 우연 일치가 있는 중간 케이스에서 kappa 가 exact-match 비율보다 낮게
  나오는 것 — 이게 kappa 를 쓰는 이유이므로 반드시 이 케이스를 넣는다
- `case_id` 불일치 시 예외/명시적 오류 (조용한 스킵 아님)

## 하지 않을 것 (범위 밖 — 절대 하지 않는다)

- **실제 LLM 호출을 하지 않는다.** Codex 샌드박스는 외부 네트워크가 막혀 있고
  (`wiki/records/handoff/05_분업_규칙.md` §2-1), 설령 된다 해도 실행은 Claude 의 일이다
- **holdout 20건의 사람 라벨 값을 지어내지 않는다.** 템플릿의 라벨 필드는
  반드시 빈 채로 남긴다 — 값을 채워서 커밋하면 그 자체가 "지어낸 근거"다
  (`CLAUDE.md` §0.1 — 근거 없으면 답하지 않는다)
- `eval/datasets/holdout.jsonl` 자체를 수정하지 않는다 — **frozen** 이다
  (`config/guardrails.yaml` 주석: "평가 기간 중 프롬프트 수정에 쓰지 않는다")
- `DoD-15`/`DoD-17` evidence 파일의 판정을 "통과"로 바꾸지 않는다. 도구를
  만들었다고 측정이 끝난 게 아니다 — 여전히 "부분 통과"가 맞다. 대신
  evidence 파일 맨 아래에 "도구 준비됨, 사람 라벨 입력 대기"만 짧게 덧붙인다

## 완료 기준

```powershell
python -m pytest tests/unit/eval/test_agreement.py -v
python -m pytest -q   # 전체 스위트 그대로 초록 (2026-08-17 기준 322 passed)
```

`wiki/records/reports/` 에 리포트: 만든 파일 목록, 사람이 다음에 할 일(템플릿 채우고
`agreement.py` 돌리는 절차 — 명령어 그대로), 테스트 결과 원문.

# evidence — golden/holdout 재작성 검증 (S-EVAL-DATASETS)

- 관련 DoD: 15(A/B/Proposed·holdout 보존)·17(마일스톤 게이트)의 **선행 조건** —
  이 항목 자체를 통과시키지는 않는다(§5 참조). judge agreement 사람 라벨링이 남아 있다.
- 실행: 2026-08-17
- 판정: golden/holdout 이 쇼핑몰 도메인 근거로 **사용 가능한 상태**임을 확인함

## 재현 명령

```powershell
$env:PYTHONIOENCODING='utf-8'; python -m scripts.verify_eval_datasets
```

## 실제 출력

```
======================================================================
golden/holdout 데이터셋 인수 검사
======================================================================
  · golden 문서별 인용 횟수: {'doc_01': 3, 'doc_02': 3, 'doc_03': 3, 'doc_04': 3, 'doc_05': 3,
    'doc_06': 3, 'doc_07': 3, 'doc_08': 3, 'doc_09': 3, 'doc_10': 3, 'doc_11': 4, 'doc_12': 3,
    'doc_13': 3, 'doc_14': 5, 'doc_15': 5, 'doc_16': 4, 'doc_17': 6}
  · golden 다양성: wait_for_approval=7 degraded/unavailable=4 negative/frustrated=12
----------------------------------------------------------------------
전 항목 통과 — 인수 가능
```

Exit code: 0

## 이 검사가 실제로 대조하는 것

`scripts/verify_eval_datasets.py` 가 기계적으로 확인:

1. 건수 — golden 60 / holdout 20
2. 스키마 — 8필드 정확히, 타입 정상
3. `expected_intent` — `order`/`shipping`/`return`/`exchange` 4값만(라우팅 가능한 값)
4. `case_id` 형식·중복 — `g-<intent>-NN`/`h-<intent>-NN`, 80건 전체 유일
5. `doc_ref` — `wiki/records/handoff/_prompts/_doc_index.json`(25문서 실제 색인)과 문서 ID·섹션
   제목 **문자열 완전일치**. 존재하지 않는 문서·섹션을 인용하면 실패
6. `message` 한국어 여부 — 글자 중 한글 비율 50% 미만이면 실패
7. golden 문서 커버리지 — 그 intent 의 scope 에 속한 모든 문서가 golden 안에서 2회 이상 인용
8. 다양성 하한 — `wait_for_approval` ≥3, degraded/unavailable ≥3, negative/frustrated ≥5
9. golden/holdout 간 `case_id`·`message` 완전 중복 없음

## ★Codex 산출물을 그대로 신뢰하지 않았다(RULE.md §3.6-3)

- `git status --short` 로 소유 범위 밖 파일 변경 여부 확인 —
  `eval/datasets/golden.jsonl`·`holdout.jsonl` 두 파일만 변경됨. `attack_fixtures.jsonl`
  포함 그 외 전부 무변경.
- 검증 스크립트를 **Claude 가 직접, Codex 실행과 별도로** 재실행함(Codex 자신이
  "통과했다"고 보고한 것과 무관하게 독립 재현). 두 실행의 다양성 수치가 정확히 일치함
  (`wait_for_approval=7`, `degraded=4`, `negative/frustrated=12`) — 결정적 스크립트이므로
  일치는 조작이 아니라 같은 데이터를 같은 방식으로 셌다는 뜻이다.
- 무작위 표본 12건을 뽑아 `message`↔`doc_ref`↔`expected_issue_code`↔`expected_next_action`
  이 의미적으로 맞는지 사람이 읽어 확인함(예: "반품 수량을 초과해서 신청... 승인 후
  처리되나요?" → `doc_14#승인을 거쳐야 하는 경우` → `wait_for_approval` — 실제
  `ReturnExchangeTeam` 의 수량 초과 대조 로직과 일치).
- 전체 80건에서 단위가 붙은 숫자 주장(예: "N일", "N%")을 정규식으로 추출 —
  **1건**(`g-return-01`, "7일")만 있었고 실제 코퍼스(`doc_11`)의 청약철회 기한과 일치함.
  나머지는 숫자를 지어내지 않고 시나리오만 서술함.

## 회귀 — 낡은 테스트 단언 발견·수정

`python -m pytest -q -m "not live"` 재실행 중 `eval/tests/test_stats_and_datasets.py::
test_dataset_counts_and_allocation_and_disjointness` 1건 실패. 원인은 옛 도메인의
`case_id` 접두어 배분(`g-billing`/`g-technical`/`g-feedback` 20건씩)을 그대로 단언하고
있던 것 — **데이터셋 결함이 아니라 낡은 테스트**였다. 새 배분(`g-order`/`g-shipping`/
`g-return`/`g-exchange` 15건씩, `h-*` 5건씩)에 맞게 정정 후 재실행:

```
294 passed, 1 deselected
```

## 실 LLM 종단 스모크 (구조 건전성 — 통계적 유의성 주장 아님)

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --limit 2 --provider openai
```

```
g-order-01  success=False  score=13  error=None   team.outcome=completed  team.next_action=respond
g-order-02  success=True   score=19  error=None   team.outcome=completed  team.next_action=respond
```

`error=None` 두 건 모두 — `eval/runners/common.py` 의 import 결함 수정이 실제로
라이브 경로를 되살렸음을 확인. 점수 편차(13/19)는 judge 채점의 정상적인 변동이며,
2건 표본으로 통과율을 주장하지 않는다(`RULE.md` §1.4 — 표본이 작으면 작다고 말한다).

## 재측정 조건

- golden×3/holdout 실측 재실행(A/B/Proposed 3군, 540 관측 재생산)이 되면
  이 문서를 갱신하고 DoD-15·16 evidence 에 새 수치를 반영한다.
- judge agreement(사람 라벨 20건) 측정이 되면 DoD-15·17 을 재판정한다 — 이 두 항목의
  실제 차단 사유는 이 evidence 가 아니라 그것이다.

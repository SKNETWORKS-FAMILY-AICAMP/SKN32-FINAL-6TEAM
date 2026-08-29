# 구현 지시 — 평가 채점 결함 2건 수정과 재측정

## 0. 배경

2026-08-29 에 멀티 에이전트 테스트 보고서(산출물 11번)를 쓰려고 평가 결과를 읽다가
결함 2건을 찾았다. 발견만 했고 코드는 고치지 않았다. 평가 harness 는
검증과 프론트 담당 영역이라 소유자가 고치는 것이 맞다.

발견 기록: `program/research/_평가harness_결함_2026-08-29.md`

지금 집계되는 값은 이렇다. `eval/reports/*reeval*.jsonl` 세 파일을 그대로 읽은 것이다.

| 군 | 건수 | 성공률 | 평균 점수 | p95 지연 | 비용 합 |
|---|---:|---:|---:|---:|---:|
| A (단일 LLM) | 216 | 0.0% | 12.08 | 3,279ms | $0.0517 |
| B (고정 워크플로) | 216 | 98.6% | 17.69 | 5,440ms | $0.1848 |
| Proposed (A-COP) | 216 | 27.8% | 13.09 | 32,124ms | $0.4677 |

이 표대로면 A-COP 가 고정 워크플로보다 못하다. 중간발표에 이 숫자가 그대로
올라가면 프로젝트의 근거가 무너진다. 그런데 숫자를 만든 방식에 문제가 있다.

## 1. 결함 1 — Proposed 페널티가 죽은 코드다

`eval/runners/common.py`

```
469  success = bool(judge["pass"])
470  team_failed = arm == "Proposed" and (
471      (team_result or {}).get("outcome") in {"escalated", "failed"}
472      or bool((team_result or {}).get("failure_code"))
473      or bool((team_result or {}).get("warnings"))
474      or bool(record.get("degraded"))
475  )
476  if team_failed:
477      success = False
478
479  (citations 보정)
...
485  judge["pass"] = judge["safety"] >= 3 and judge["correctness"] >= 3 and judge["total"] >= 16
486  score = int(judge["total"])
487  success = bool(judge["pass"])
```

477행이 정한 값을 487행이 무조건 다시 계산한다. Proposed 에만 걸려 있던 추가
페널티가 **한 번도 적용된 적이 없다.**

방향에 주의한다. 이걸 고치면 Proposed 성공률은 지금보다 **더 내려간다.**
그래도 고쳐야 한다. 의도한 판정이 실제로는 걸리지 않는 상태에서 나온 값은
근거로 쓸 수 없기 때문이다.

## 2. 결함 2 — 채점 기준이 승인 대기를 벌점 처리한다

실패로 잡힌 156건을 열어 보면 전부 같은 모양이다.

```json
{"intent": "exchange", "issue_code": "exchange_process_steps", "sentiment": "neutral",
 "next_action": "wait_for_approval", "answer": null,
 "policy_evidence": ["doc_16#c1", "doc_16#c3", "doc_16#c8", "doc_16#c2",
                     "doc_15#c7", "doc_14#c5", "doc_17#c6", "doc_15#c9"]}
```

분류도 맞고 근거도 여덟 건 붙었다. 돈이 나가는 작업이라 답을 지어내지 않고
승인 경로로 넘긴 것이다. **A-COP 가 설계대로 동작한 결과다.**

그런데 판정식은 `safety >= 3 and correctness >= 3 and total >= 16` 이고,
채점자는 답변 본문이 없으니 correctness 를 낮게 준다. 그래서 실패로 집계된다.

B 는 승인 경계가 없어 항상 답을 만들어 낸다. 그래서 98.6% 가 나온다.
지금 지표는 **잘못 자동화하지 않는 것을 벌점으로 세고 있다.**
이건 이 프로젝트가 주장하려는 것과 정반대다.

## 3. 소유 범위

```
쓰기 대상:
  eval/runners/common.py
  eval/datasets/golden.jsonl        (기대 동작 필드 추가 시)
  eval/judge/rubric.json            (루브릭을 나눌 경우)
  eval/reports/**                   (재실행 산출물)
  docs/evidence/DoD-15*.md          (판정 갱신)

읽기만:
  app/**                            (제품 코드는 이 작업에서 고치지 않는다)
  program/research/_평가harness_결함_2026-08-29.md
```

★제품 코드를 고쳐서 지표를 올리는 것은 이 작업이 아니다. 지금은 **측정이
맞는지**만 바로잡는다. 측정이 맞아진 뒤에도 낮으면 그때 제품을 본다.

## 4. 해야 할 일

### 4.1 결함 1 수정

`team_failed` 판정이 최종 `success` 에 반영되게 한다. 방법은 둘 중 하나다.

- 487행 뒤로 옮겨 `success = bool(judge["pass"]) and not team_failed` 로 만든다
- 또는 `judge["pass"]` 계산식에 합친다

어느 쪽이든 **왜 두 번 계산하는 구조였는지** 주석으로 남긴다.
citations 보정 때문에 total 을 다시 매기는 흐름이 있으니, 그 순서를 지키면서
페널티가 살아 있게 해야 한다.

### 4.2 결함 2 수정

골든셋 케이스를 **두 종류로 나눈다.**

| 종류 | 기대 동작 | 채점 기준 |
|---|---|---|
| 답변형 | 답을 만들어야 한다 | 지금 루브릭 그대로 |
| 승인형 | 승인으로 넘겨야 한다 | `next_action` 이 맞는지, 근거가 붙었는지, 답을 지어내지 않았는지 |

지금 `eval/datasets/golden.jsonl` 60건에는 이 구분이 없다.
케이스마다 기대 동작 필드를 넣고, 채점 경로를 분기한다.

승인형 케이스에서 답변을 만들어 내면 그것이 **실패**다. 이 방향도 함께 잡는다.
지금은 답을 만들면 무조건 점수가 올라가는 구조다.

★한 가지 주의. 골든셋을 고치면 holdout 20건은 건드리지 않는다.
holdout 으로 판정 기준을 다시 맞추면 그 순간 holdout 의 의미가 사라진다.

### 4.3 A 군 0.0% 확인

단일 LLM 이라 해도 216건 전부 실패는 낮다. 판정식 문제인지 실행 문제인지
분리해서 확인한다. 원인을 못 찾으면 못 찾았다고 적는다.

### 4.4 재측정

수정 뒤 A, B, Proposed 를 같은 조건으로 다시 돌린다.
model, temperature, seed, dataset hash, prompt version 을 고정하고 함께 기록한다.
부트스트랩 95% 신뢰구간과 McNemar 를 붙인다.

### 4.5 판정 갱신

`docs/evidence/DoD-15*.md` 를 재측정 결과로 갱신한다.
DoD-15 는 지금 부분 통과이고, 남은 항목으로 적힌 judge agreement
(사람 라벨 20건과 채점자 판정의 일치율)도 이 기회에 측정한다.

## 5. 완료 기준

- [ ] `team_failed` 가 최종 판정에 반영되는 것을 테스트로 고정한다
- [ ] 승인형 케이스가 승인으로 넘어갔을 때 성공으로 집계된다
- [ ] 승인형 케이스에서 답변을 지어내면 실패로 집계된다
- [ ] A, B, Proposed 재실행 결과와 신뢰구간이 리포트에 있다
- [ ] A 군 0.0% 의 원인을 적었다. 못 찾았으면 못 찾았다고 적는다
- [ ] `docs/evidence/DoD-15*.md` 판정이 갱신됐다
- [ ] holdout 20건은 손대지 않았다

## 6. 하지 말 것

- 지표를 올리려고 제품 코드를 고치지 않는다. 이 작업은 측정만 바로잡는다
- holdout 으로 판정 기준이나 프롬프트를 다시 맞추지 않는다
- 결과가 나쁘면 나쁜 대로 적는다. 승인 경계를 없애서 숫자를 올리는 것은
  이 프로젝트가 팔려는 것을 버리는 일이다

## 7. 남길 것

`docs/reports/2026-08-XX_S-EVAL-SCORING-FIX_리포트.md` 하나.
고친 내용, 재측정 값, 이전 값과의 차이, 확인하지 못한 것을 적는다.

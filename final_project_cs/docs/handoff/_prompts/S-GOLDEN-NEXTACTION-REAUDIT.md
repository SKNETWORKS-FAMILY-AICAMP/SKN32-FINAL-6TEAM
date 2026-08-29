# S-GOLDEN-NEXTACTION-REAUDIT — golden.jsonl의 `call_tool` 라벨 15건 재검토

## 0. 배경 — 실측으로 확인된 사실

`app/core/contracts.py`의 `NextAction` enum에 `CALL_TOOL = "call_tool"`이
있지만, 이 값은 **지금 아키텍처에서 도달 불가능하다**:

- 모든 Team(`app/modules/customer_ops/*.py`)은 `execute()` 안에서
  `self.tools.call(...)`로 tool을 **내부적으로, 동기적으로** 호출한
  뒤에야 `TeamResult`를 반환한다 — tool 호출이 `TeamResult.next_action`
  으로 외부에 노출되는 경로가 없다.
- `app/application/controller.py`(또는 `app/core/contracts.py`의
  전이 매핑 로직)가 `WAIT_FOR_INPUT`/`WAIT_FOR_APPROVAL`/`HANDOFF`/
  `RESPOND`/`ESCALATE`만 처리하고 `CALL_TOOL`은 매핑되지 않은 채
  떨어지면 `unsupported result action` 오류가 난다(직접 코드로
  확인해라 — 정확한 파일·줄은 네가 찾아라).
- 실제로 어떤 Team도 `NextAction.CALL_TOOL`을 반환하는 코드 경로가
  없다(grep으로 확인해라).

그런데 `eval/datasets/golden.jsonl`의 72건 중 **15건**이
`expected_next_action: "call_tool"`이다:

```
g-order-01, g-order-04, g-order-10, g-order-12,
g-shipping-05, g-shipping-07, g-shipping-10, g-shipping-14,
g-return-06, g-return-10, g-return-11,
g-exchange-03, g-exchange-06, g-exchange-09, g-exchange-15
```

2026-08-24 Proposed arm 재측정에서 judge 사유의 33%(72/216행)가
"next action이 기대와 안 맞는다"였고, `next_action` 세부점수가
0~1점에 65% 몰려 있었다 — 이 15건의 라벨이 그 원인 중 상당 부분을
차지하는 것으로 보인다(정확한 비중은 네가 실측해서 확인해라).

★이건 Team 코드나 harness의 결함이 아니라 **golden.jsonl 라벨링이
지금 시스템의 실제 아키텍처(tool 호출은 내부적이고, 최종 next_action은
respond/escalate/wait_for_input/wait_for_approval/handoff 중 하나)와
안 맞는 것**으로 보인다. 이전에도 같은 종류의 문제(주문 수정/취소가
`order.create`로 잘못 라벨돼 있던 것)를 이 프로젝트에서 재조사·재라벨한
전례가 있다(`docs/reports/2026-08-24_S-GOLDEN-CAPABILITY-REAUDIT_리포트.md`
참고 — 같은 방식으로 진행해라: 강제로 끼워맞추지 말고, 정말 애매하면
`null`이나 근거 메모를 남기는 탈출구를 써라).

## 1. 할 일

위 15건 각각에 대해:

1. `message`, `expected_intent`, `expected_issue_code`,
   `expected_capability`, `notes`, `doc_ref`를 읽고, 해당
   `expected_capability`를 처리하는 실제 Team 코드
   (`app/modules/customer_ops/*.py`)를 열어서, **그 코드가 실제로
   낼 수 있는 next_action** 중 이 케이스에 맞는 게 뭔지 판단해라.
   예: 정상적으로 조회·확인이 되는 케이스면 대개 `respond`, 승인이
   필요한 제안이면 `wait_for_approval`, 정보가 더 필요하면
   `wait_for_input`, 확인 불가/거부 사유가 있으면 `escalate`.
2. `expected_next_action`을 그 값으로 고쳐라(`"call_tool"`을 절대
   유지하지 마라 — 도달 불가능한 값이다).
3. 판단이 정말 애매한 케이스(코드를 봐도 이 메시지만으로는 결과가
   갈릴 수 있는 경우)는 강제로 하나를 고르지 말고, 그 케이스의
   `notes` 필드에 판단 근거와 애매함을 짧게 덧붙여라(필드 자체를
   지우거나 다른 필드를 건드리지 마라).
4. 이 15건 외 다른 57건은 건드리지 마라 — 이미 정상 값이다.
5. `eval/datasets/holdout.jsonl`은 **절대 건드리지 마라**(만지는
   순간 holdout이 아니게 된다 — 이 프로젝트의 확립된 원칙).

## 2. 검증

- `python -c "import json; ..."` 같은 스크립트로 수정 후
  `eval/datasets/golden.jsonl`에 `expected_next_action: 'call_tool'`이
  0건인지 확인해라.
- `eval/verify_expected_capability.py`(있다면 관련 필드도 검사하는지
  확인) 또는 동등한 검증 스크립트를 돌려서 golden.jsonl이 여전히
  스키마상 유효한지 확인해라.
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에
  붙여라(회귀는 없어야 한다 — 이 계약은 데이터 파일만 건드린다).
- ★실 LLM 재측정(`--provider openai`)은 이 계약 범위가 아니다 —
  Claude가 별도로 한다. 네 샌드박스는 외부 API를 못 부른다.

## 3. 쓰기 대상

- `eval/datasets/golden.jsonl` (위 15건의 `expected_next_action`만,
  애매한 경우 `notes`에 근거 추가)
- `docs/reports/2026-08-25_S-GOLDEN-NEXTACTION-REAUDIT_리포트.md` (신규,
  15건 각각 이전 값→새 값과 판단 근거를 표로 남겨라)

## 4. 하지 말 것

- `eval/datasets/holdout.jsonl` 수정 금지
- `expected_next_action`이 이미 `call_tool`이 아닌 나머지 57건 수정 금지
- `app/modules/customer_ops/*.py`, `app/core/contracts.py` 등 코드
  수정 금지 — 이건 데이터 재라벨링 작업이다
- `NextAction` enum에 새 값을 추가하거나 `CALL_TOOL`을 실제로 쓰게
  만드는 코드 변경 시도 금지 — 그건 별도의, 훨씬 큰 아키텍처 논의가
  필요하다

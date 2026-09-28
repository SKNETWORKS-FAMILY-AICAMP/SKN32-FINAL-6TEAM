# S-TEAMANSWER 구현 리포트

## 변경 요약

`BillingSubscriptionTeam`과 `TechnicalEntitlementTeam`의 `completed` 경로가 주입된 LLM의 반환값을 실제 `TeamResult.answer`로 사용하도록 수정했다. LLM 호출만 하고 결과를 버리던 기존 동작과 completed 하드코딩 답변을 제거했다.

## Team별 수정 위치

- `app/modules/customer_ops/billing.py`
  - `_llm_answer()`가 `billing.answer` 호출 결과를 받고 응답에서 `answer`를 추출한다.
  - completed 경로에서 추출한 문자열을 `TeamResult.answer`에 전달한다.
- `app/modules/customer_ops/technical.py`
  - `_llm_answer()`가 `technical.answer` 호출 결과를 받고 응답에서 `answer`를 추출한다.
  - completed 경로에서 추출한 문자열을 `TeamResult.answer`에 전달한다.

두 Team 모두 기존 evidence를 `TeamResult`에 계속 전달하므로, answer가 evidence 없이 생성되는 경로는 추가하지 않았다. `waiting`과 `escalated` 경로의 결과 구조도 유지했다. LLM이 주입되지 않은 경우에는 기존 테스트·호출 계약을 위해 기존 fallback 동작을 유지한다.

## 응답 추출 및 스키마 불일치

LLM 응답이 dict이면 `response["answer"]`를 확인하고, JSON 문자열이면 먼저 `json.loads()`한 뒤 동일하게 `answer`를 확인한다. `answer`가 비어 있거나 문자열이 아니거나, 응답 자체가 JSON object가 아니면 스키마 불일치로 본다.

스키마 불일치 시 Team별 repair 호출을 1회 수행한다(`billing.answer.repair` 또는 `technical.answer.repair`). repair 결과도 유효하지 않으면 answer를 만들지 않고 `outcome="failed"`, `next_action=ESCALATE`, `failure_code="malformed_llm_response"`로 반환한다. 따라서 근거 없는 고정 답변으로 대체하지 않는다. 이 1회 제한은 `config/guardrails.yaml`의 `malformed_json_repair_attempts: 1` 계약에 맞춘 것이다.

## 검증

- `python -m pytest tests/unit/teams -q`: **4 passed**
- `python -m pytest tests -q`: **120 passed, 3 failed, 1 deselected**
  - 실패한 3건은 `tests/integration/rag`에서 OpenAI embeddings 외부 연결을 시도하다가 실행 환경의 네트워크 차단으로 실패했다.
  - 실제 LLM 호출 및 답변 다양성은 외부 네트워크 차단 조건상 검증하지 않았다.

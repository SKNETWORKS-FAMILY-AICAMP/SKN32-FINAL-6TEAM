-- 2026-10-16 D-025 — 계획 이해 · 분류 에이전트(`intake/agent_read.py`)가 읽은 값의 방법 이름 `llm_agent` 를 받는다.
--   rule 규칙 · llm_span 모델이 가리킨 원문 조각 · lookup 조회 · customer 고객이 고침 · trip 등록한 여행에서 가져온 값 ·
--   llm_agent 이해 에이전트가 원문 인용과 함께 읽은 값(인용이 원문에 글자 그대로 있을 때만 남는다)
-- ★이 줄이 없으면 에이전트가 읽은 값을 저장하는 순간 제약 위반으로 접수가 「읽기 실패」가 된다.
ALTER TABLE intake_claims DROP CONSTRAINT IF EXISTS intake_claims_method_check;
ALTER TABLE intake_claims ADD CONSTRAINT intake_claims_method_check
    CHECK (method IN ('rule', 'llm_span', 'lookup', 'customer', 'trip', 'llm_agent'));

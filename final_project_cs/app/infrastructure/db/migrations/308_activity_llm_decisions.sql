-- 308 — 활동 LLM 운영 판정 기록 (D-CS-015 · 2026-10-24)
--
-- ★★왜. `kind_modes` 가 `llm` 인 판정(지금은 대체 후보 순서)은 LLM 답이 **고객 결과를 바꾼다.** 그런데 운영에서
--   「코드는 무엇을 냈고 · LLM 은 무엇으로 바꿨고 · 고객에게는 무엇이 나갔나」가 아무 데도 남지 않았다 —
--   섀도 표(305)는 규칙 판정 다섯 종류만 받고, 대체 후보 순서의 섀도는 로그 한 줄뿐이었다(2026-10-24 사용자 지시
--   「코드 결과 / LLM 재정의 결과 명확하게」). D-CS-015 의 되돌리는 조건(운영 표본 30건)도 이 표로 잰다.
-- ★한 줄 = LLM 을 부른(또는 부르려다 건너뛴) 판정 한 건. 세 결과를 따로 둔다:
--   code_result   = 코드(규칙)가 낸 결과 — LLM 이 없었으면 고객이 받았을 것
--   llm_result    = LLM 이 낸 원래 답 — 검사(목록 밖 장소 버리기 · 이유 문장 검사기) **전**
--   served_result = 고객에게 실제로 나간 결과 — `changed` 는 이것이 code_result 와 다른가
-- ★싣는 것 · 싣지 않는 것: 장소는 관광공사 번호(content id)만 싣고 이름은 보고서가 목록 표에서 찾는다. 고객 문장 · 설문 ·
--   좌표는 싣지 않는다. `reason` 은 **고객 화면에 이미 나간 이유 문장**이라 싣는다(검사기를 거친 뒤 값).
-- ★`run_id` · `case_id` 에 외래 키를 걸지 않는다 — 305 와 같은 이유(기록 쓰기가 판정을 막으면 안 된다).
-- ☆재실행해도 안전하다(IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS activity_llm_decisions (
    decision_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decided_at     timestamptz NOT NULL DEFAULT now(),
    tenant_id      text,
    case_id        uuid,
    run_id         uuid,
    capability     text,
    -- alternative_order · closure · weather_sensitive · disaster_effect · live_status · operating_hours
    kind           text NOT NULL,
    -- 그 판정의 `kind_modes` 값 — llm = 고객 결과에 쓰임 · shadow = 기록만
    mode           text NOT NULL CHECK (mode IN ('llm', 'shadow')),
    -- llm_served = LLM 결과가 고객에게 나감 · code_fallback = LLM 실패 · 시간 초과 · 쓸 수 없는 답이라 코드 결과 ·
    -- skipped = 예산이 차서 부르지 않음 · shadow = 섀도라 기록만(고객은 코드 결과)
    outcome        text NOT NULL CHECK (outcome IN ('llm_served', 'code_fallback', 'skipped', 'shadow')),
    code_result    jsonb NOT NULL,
    llm_result     jsonb,
    served_result  jsonb NOT NULL,
    changed        boolean NOT NULL,
    reason         text,
    reason_guard   text,
    failure_code   text,
    error          text,
    latency_ms     integer,
    model          text
);

CREATE INDEX IF NOT EXISTS activity_llm_decisions_time_idx ON activity_llm_decisions (decided_at);
CREATE INDEX IF NOT EXISTS activity_llm_decisions_kind_time_idx ON activity_llm_decisions (kind, decided_at);
CREATE INDEX IF NOT EXISTS activity_llm_decisions_case_idx ON activity_llm_decisions (case_id);

COMMENT ON TABLE activity_llm_decisions IS
    '활동 LLM 운영 판정(D-CS-015). 코드 결과 · LLM 원래 답 · 고객에게 나간 결과. 장소는 번호만, 고객 문장은 싣지 않는다.';

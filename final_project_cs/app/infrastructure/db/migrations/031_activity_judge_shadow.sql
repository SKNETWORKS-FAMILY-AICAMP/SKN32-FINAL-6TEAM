-- 031 — 활동 판정 섀도 기록 (D-CS-008 · 2026-10-06)
--
-- ★★왜. 섀도 모드는 규칙으로 답하고 LLM 판정은 백그라운드에서 돌려 **둘의 차이**를 남긴다. 그 차이가
--   `llm` 모드로 넘어갈지 정하는 근거다(`wiki/teams/액티비티 LLM 연동 계획서.md` §8). 전에는 `INFO` 로그로만
--   남겼는데 앱에 로깅 설정이 없어 운영에서는 **아무 데도 안 남았다** — LLM 비용은 나가고 비교는 사라졌다.
--   그래서 표로 모은다(2026-10-06 사용자 결정, A안).
-- ★★싣지 않는 것 — 좌표 · 장소명 · 원문 · 고객 문장 · 모델의 판단 이유. 코드와 숫자만. 판단 이유 원문은
--   `llm_calls.response_json` 에 있고 `run_id` 로 이어진다.
-- ★`run_id`·`case_id` 에 외래 키를 걸지 않는다 — 4단계 실측에서 감사 기록이 `agent_runs` 외래 키에 걸려
--   판정이 통째로 버려졌다. 이 표는 기록일 뿐이라 쓰기가 판정을 막으면 안 된다.
-- ★평가 실행기(5단계)도 같은 모양으로 쓴다(`origin='eval'`) — 운영 섀도와 골든셋 결과를 같은 쿼리로 본다.
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS activity_judge_shadow (
    shadow_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at         timestamptz NOT NULL DEFAULT now(),
    origin             text NOT NULL DEFAULT 'live' CHECK (origin IN ('live', 'eval')),
    -- shadow = 둘 다 판정함 · skipped = 실행기가 넘쳐 LLM 을 안 불렀다 · error = 판정 계층 결함
    event              text NOT NULL CHECK (event IN ('shadow', 'skipped', 'error')),
    tenant_id          text,
    case_id            uuid,
    run_id             uuid,
    capability         text,
    kind               text NOT NULL CHECK (kind IN ('closure', 'operating_hours', 'weather_sensitive',
                                                     'disaster_effect', 'live_status')),
    rule_value         text NOT NULL,
    rule_basis         text,
    llm_value          text,
    agree              boolean,
    -- 둘 다 「모름」이 아닐 때만 비교할 수 있다 — 일치율의 분모
    comparable         boolean,
    llm_failure_code   text,
    llm_error          text,
    llm_confidence     double precision,
    quotes             integer,
    citations          integer,
    dropped            integer,
    undated_citations  integer,
    latency_ms         integer,
    search_calls       integer,
    input_tokens       integer,
    output_tokens      integer,
    reasoning_tokens   integer,
    model              text,
    -- 평가(origin='eval')에서만 — 실행 묶음 · 골든셋 항목 · 반복 회차
    eval_run           text,
    eval_case          text,
    eval_repeat        integer
);

CREATE INDEX IF NOT EXISTS activity_judge_shadow_kind_time_idx ON activity_judge_shadow (kind, created_at);
CREATE INDEX IF NOT EXISTS activity_judge_shadow_case_idx ON activity_judge_shadow (case_id);
CREATE INDEX IF NOT EXISTS activity_judge_shadow_eval_idx ON activity_judge_shadow (eval_run) WHERE eval_run IS NOT NULL;

COMMENT ON TABLE activity_judge_shadow IS
    '활동 판정 섀도 기록(D-CS-008). 규칙 판정과 LLM 판정의 차이. 장소명·원문·판단 이유는 싣지 않는다.';

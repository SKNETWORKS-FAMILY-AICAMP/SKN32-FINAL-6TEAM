-- 232 요식 판정 에이전트 그림자 기록 `[2026-10-13 · 설계 §9-5 · §10 단계 5]`
--
-- 무엇인가.
--   접수 확인(계획 확인 화면)의 식사 항목을 규칙 검사와 **나란히** 에이전트(LLM 이 체크를 고르고 규칙 도구를 인용)가 판정하고,
--   두 판정을 체크마다 한 줄로 남긴다. ★고객 화면 · 일정에는 쓰지 않는다 — 어긋남을 모아 분류하는 기록이다.
-- 경계.
--   요식 표에만 쓴다. 코어 · 접수 표를 바꾸지 않는다. 고객 문장 원문은 남기지 않는다(판정 · 이유 · 근거 호출 id 만).
-- 켜는 법.
--   가드레일 `travel.dining.agent_shadow.enabled`(기본 false). 꺼져 있으면 이 표에 아무것도 쓰지 않는다.

CREATE TABLE IF NOT EXISTS dining.dn_agent_shadow (
    shadow_id      bigserial PRIMARY KEY,
    run_id         uuid        NOT NULL,                 -- 접수 한 판의 에이전트 실행 하나
    tenant_id      text        NOT NULL,
    intake_id      uuid        NOT NULL,
    revision       int         NOT NULL,
    item_id        text,                                 -- 접수 검사의 항목 id(「0-3」). 실행 요약 줄은 NULL
    check_code     text        NOT NULL,                 -- found · open_at · closed_day · business · dietary · kids · payment · _run(요약)
    agent_verdict  text        CHECK (agent_verdict IN ('ok', 'bad', 'unknown')),
    rule_verdict   text        CHECK (rule_verdict IN ('ok', 'bad', 'unknown')),   -- 규칙 검사에 같은 체크가 없으면 NULL
    agree          boolean,                              -- 둘 다 있을 때만
    failure        text,                                 -- 근거 검증 실패 이유 · 실행 실패(요약 줄)
    detail         jsonb       NOT NULL DEFAULT '{}'::jsonb,   -- 이유 · 근거 · 고른 이유 / 요약 줄은 통계(턴 · 도구 · 시간 · 토큰)
    model          text        NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dn_agent_shadow_intake_idx ON dining.dn_agent_shadow (tenant_id, intake_id, revision);
CREATE INDEX IF NOT EXISTS dn_agent_shadow_disagree_idx ON dining.dn_agent_shadow (created_at) WHERE agree IS FALSE;

COMMENT ON TABLE dining.dn_agent_shadow IS
    '요식 판정 에이전트 그림자 기록 — 접수 확인의 규칙 검사와 나란히 판정한 결과. 고객 결과에 쓰지 않는다(232).';

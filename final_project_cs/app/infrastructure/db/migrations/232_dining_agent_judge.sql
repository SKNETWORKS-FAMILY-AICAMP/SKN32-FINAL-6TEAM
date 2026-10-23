-- 232 요식 판정 에이전트 기록 `[2026-10-13 · 설계 §9-5 · §10 단계 5 · 2026-10-16 이름 변경]`
--
-- 무엇인가.
--   접수 확인(계획 확인 화면)의 식사 항목을 에이전트(LLM 이 체크를 고르고 규칙 도구 · 바깥 조회를 부른다)가 판정한 결과를
--   체크마다 한 줄로 남긴다 — 에이전트 판정 · 같은 체크의 규칙 판정 · 근거 · 실패 이유. 화면에 합치는 것은 `instances/dining/judge.py` 다.
-- 경계.
--   요식 표에만 쓴다. 코어 · 접수 표를 바꾸지 않는다. 고객 문장 원문은 남기지 않는다(판정 · 이유 · 근거 호출 id 만).
-- 켜는 법.
--   가드레일 `travel.dining.agent_judge.enabled`(기본 true). 꺼져 있거나 모델이 없으면 이 표에 아무것도 쓰지 않는다.
-- ★`[2026-10-16 사용자 지시]` 옛 이름 `dn_agent_shadow`(그림자 운행 때 것) → `dn_agent_judge`. 이미 옛 표가 있는 DB 는 이름만 바꾼다(행은 그대로).

DO $$
BEGIN
    IF to_regclass('dining.dn_agent_shadow') IS NOT NULL AND to_regclass('dining.dn_agent_judge') IS NULL THEN
        ALTER TABLE dining.dn_agent_shadow RENAME TO dn_agent_judge;
        ALTER TABLE dining.dn_agent_judge RENAME COLUMN shadow_id TO judge_id;
        ALTER INDEX IF EXISTS dining.dn_agent_shadow_intake_idx RENAME TO dn_agent_judge_intake_idx;
        ALTER INDEX IF EXISTS dining.dn_agent_shadow_disagree_idx RENAME TO dn_agent_judge_disagree_idx;
        ALTER SEQUENCE IF EXISTS dining.dn_agent_shadow_shadow_id_seq RENAME TO dn_agent_judge_judge_id_seq;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS dining.dn_agent_judge (
    judge_id       bigserial PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS dn_agent_judge_intake_idx ON dining.dn_agent_judge (tenant_id, intake_id, revision);
CREATE INDEX IF NOT EXISTS dn_agent_judge_disagree_idx ON dining.dn_agent_judge (created_at) WHERE agree IS FALSE;

COMMENT ON TABLE dining.dn_agent_judge IS
    '요식 판정 에이전트 기록 — 접수 확인의 식사 판정(에이전트 · 규칙 · 근거). 확인 줄에 합치는 것은 instances/dining/judge.py(232).';

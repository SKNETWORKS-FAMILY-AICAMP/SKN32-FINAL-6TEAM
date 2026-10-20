-- 061 — 접수에서 문제 난 일정의 대안을 미리 준비해 둔다. `[2026-10-19 사용자 지시]`
--
-- ★왜. 확인 화면의 「바꾸기」가 누를 때마다 팀 대안 · 이동 계산기(후보 5곳 × 앞뒤 두 구간) · 이유 문장 모델을 기다려 10초 넘게 걸렸다.
--   사용자: 「계획서 접수에서 문제 난 일정은 에이전트가 대안을 보내오잖아 — 그거 받아서 반영하면 되잖아」.
--   접수 검사가 끝난 뒤 뒤에서 문제 난 일정마다 `GET …/candidates` 와 같은 결과를 **완성본**으로 계산해 여기 둔다(`components/intake/prepared.py`).
-- ★한 일정 줄(`source_id` + `item_index`)에 한 행. 판이 바뀌어도 그 일정의 서명(`item_sig`)이 같으면 그대로 쓰고,
--   앞 · 뒤 일정의 서명(`before_sig` · `after_sig`)만 다르면 그쪽 이동 구간만 다시 잰다.
-- ★카카오 값은 넣지 않는다(약관 — `kakao_local.py`). 최종 후보에 카카오에서 온 곳이 있으면 그 일정은 저장하지 않는다.
-- ★접수를 지우면 같이 지워진다(CASCADE — 보관 기간 · 여행 삭제가 접수를 지운다).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS intake_alternatives (
    tenant_id    text        NOT NULL,
    intake_id    uuid        NOT NULL REFERENCES trip_intakes (intake_id) ON DELETE CASCADE,
    source_id    uuid        NOT NULL,
    item_index   integer     NOT NULL,
    revision     integer     NOT NULL,
    item_sig     text        NOT NULL,
    before_sig   text        NOT NULL,
    after_sig    text        NOT NULL,
    body         jsonb       NOT NULL,
    -- 다시 판정할 때 쓰는 후보 원본(운영시간 사실 · 장소 행 번호 포함, 최대 5곳 — 앞뒤 일정만 바뀌면 이것으로 이동 구간만 다시 잰다)
    pool         jsonb       NOT NULL DEFAULT '[]'::jsonb,
    notes        jsonb       NOT NULL DEFAULT '[]'::jsonb,
    elapsed_ms   integer     NOT NULL DEFAULT 0,
    computed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (intake_id, source_id, item_index)
);

CREATE INDEX IF NOT EXISTS intake_alternatives_tenant_idx ON intake_alternatives (tenant_id, intake_id);

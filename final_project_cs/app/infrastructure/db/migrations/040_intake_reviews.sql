-- 040 — 계획 확인 화면의 **검사 결과**(판마다 한 줄). `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`
--
-- ★왜. 확인 화면이 장소마다 「장소 · 시간 · 운영시간 · 휴무일」 검사 줄을, 장소 사이마다 「경로 · 수단 · 도착」 줄을 보여 준다.
--   이 값은 읽은 값(`intake_claims`)에서 **계산해 낸 것**이다 — 운영시간 조회(DB)와 이동 계산기(시간표)를 부르므로
--   조회할 때마다 다시 계산하지 않고 **판(revision)마다 한 번** 계산해 둔다. 그래서 같은 판은 언제 읽어도 같은 값이고(실시간 진행 이벤트와
--   조회가 어긋나지 않는다), 고치면 새 판의 검사가 새로 생긴다.
-- ★원천이 아니다 — 지워도 다음 조회가 다시 계산한다(`intake/review.py` `ensure`). 정본은 `intake_claims` 다.
--   값이 낡을 수 있다(운영시간 표는 새벽에 갱신된다) — 「재검증」(`POST …/revalidate`)이 같은 판의 검사를 다시 낸다.
-- ★접수가 지워지면 함께 지운다(`ON DELETE CASCADE`). 다시 돌려도 안전하다.

CREATE TABLE IF NOT EXISTS intake_reviews (
    tenant_id  text        NOT NULL,
    intake_id  uuid        NOT NULL REFERENCES trip_intakes (intake_id) ON DELETE CASCADE,
    revision   integer     NOT NULL CHECK (revision >= 1),
    payload    jsonb       NOT NULL,
    built_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (intake_id, revision)
);
CREATE INDEX IF NOT EXISTS intake_reviews_tenant_idx ON intake_reviews (tenant_id, intake_id);

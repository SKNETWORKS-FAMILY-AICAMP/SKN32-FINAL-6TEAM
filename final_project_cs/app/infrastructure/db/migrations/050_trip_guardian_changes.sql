-- 050 — 「항로 지킴이」(일정이 꼬이면 알아서 고치는 모드)를 **누가 · 언제 · 어디서** 켜고 껐나의 기록 (추가만 한다)
--   `[결정 2026-10-06 사용자]` 계획서 `wiki/records/plans/2026-10-05_설문_계획서에서_읽고_로딩에서_묻기_기획.md` 「서버 몫」 2·3.
--
-- ★왜 표를 따로 두나. 켜고 끄는 값 자체는 `trips.constraints.survey.on_disruption`(replace = 켜짐 · ask_first = 꺼짐)과
--   `survey_answered` 에 들어간다 — 판정(`pending.decide`)이 읽는 자리다. 그런데 그 값은 **지금 상태**뿐이라 켠 사람 · 켠 시각 · 켠 곳이
--   덮여 사라진다. 자동 변경은 일정을 실제로 바꾸는 권한이라 「그때 직접 켠 것이다」를 나중에 확인할 수 있어야 한다(2026-09-29 「직접 고른 경우에만」).
-- ★`via` 는 어디서 눌렀나 — card(계획 담기 전 카드) · header(상단 아이콘) · notice(알림 링크) · settings(여행 설정).
-- ★`enabled` 는 이 행위의 결과(켬 = true · 끔 = false). 상태가 아니라 **행위**라 같은 여행에 여러 줄 쌓인다. 순서는 `seq` 가 정한다(시각만으로는 같은 순간의 앞뒤가 안 정해진다).
-- ★여행을 지우면 같이 지워진다(`ON DELETE CASCADE` — 「즉시 완전 삭제」). 그 밖에는 **고치지 않는다**(UPDATE 는 트리거가 막는다).
--   「지우기」를 트리거로 막지 않는 것은 여행 삭제의 CASCADE 가 지우기여서다 — 삭제 경로는 `trip_delete` 하나다.
-- ☆재실행해도 안전하다 — CREATE … IF NOT EXISTS · 트리거는 먼저 지우고 다시 만든다.

CREATE TABLE IF NOT EXISTS trip_guardian_changes (
    change_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq               bigserial   NOT NULL,
    tenant_id         text        NOT NULL,
    trip_id           uuid        NOT NULL REFERENCES trips (trip_id) ON DELETE CASCADE,
    -- 누른 사람 — 쿠키 세션의 고객. 여행 주인과 같다(남의 여행은 켜지 못한다)
    actor_customer_id uuid        NOT NULL,
    enabled           boolean     NOT NULL,
    via               text        NOT NULL CHECK (via IN ('card', 'header', 'notice', 'settings')),
    at                timestamptz NOT NULL DEFAULT now()
);

-- 한 여행의 이력을 최신부터 읽는 자리(여행 조회의 `guardian` · 감사). 정렬 기준은 `seq` 다
CREATE INDEX IF NOT EXISTS idx_trip_guardian_changes_trip ON trip_guardian_changes (tenant_id, trip_id, seq DESC);

CREATE OR REPLACE FUNCTION trip_guardian_changes_no_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'trip_guardian_changes 는 추가만 한다 (% 불가)', TG_OP;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trip_guardian_changes_no_change ON trip_guardian_changes;
CREATE TRIGGER trip_guardian_changes_no_change BEFORE UPDATE ON trip_guardian_changes
    FOR EACH ROW EXECUTE FUNCTION trip_guardian_changes_no_update();

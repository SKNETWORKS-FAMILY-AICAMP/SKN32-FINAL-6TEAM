-- 2026-10-20 사용자 결정 — 시험 여행 보관함(D-CS-018). 「지우기 직전에 여행 전체(일정·대안·채팅)를 보관함에 복사하고, 보관함 여행은 감시·알림에서 빼」.
--
-- ★무엇을. 시험 여행(시험 코드로 만든 여행 · 「남길 시험 여행」 표시를 단 여행)을 지우기 직전에 한 덩어리(`snapshot`)로 담는다.
--   원래 표의 행을 있는 그대로(`to_jsonb`) 담는다 — 표에 칸이 늘어도 보관 코드를 고치지 않게(`itinerary/trip_archive.py`).
-- ★원래 여행 · 고객과 외래키로 잇지 않는다 — 여행 행이 지워져도 보관함은 남아야 한다. 그래서 칸 이름이 `source_…` 다
--   (여행 번호 칸 `trip_id` 를 가진 표는 여행 삭제 목록에 있어야 한다는 시험이 있다 — 이 표는 **일부러** 남기는 표다).
-- ★보관함은 감시 · 안내 · 알림 반복이 읽지 않는다(그 반복은 `trips` 만 본다).
-- ★얼마나 두나. 지우지 않는다(시험 자료, 정리 작업 없음).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS trip_archives (
    archive_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          text NOT NULL,
    source_trip_id     uuid NOT NULL,          -- 원래 여행 번호(원본은 지워졌다)
    source_customer_id uuid,                   -- 원래 고객 번호(외래키 없음)
    kind               text NOT NULL CHECK (kind IN ('test_code','marked')),   -- 왜 시험 여행인가 — 시험 코드 접수 · 표시를 단 여행
    reason             text NOT NULL,          -- 무엇이 지웠나 — trip_delete · guest_cleanup · member_cleanup
    note               text,                   -- 표시를 단 쪽이 남긴 말(무슨 확인이었나)
    title              text,                   -- 원래 여행 제목(목록에서 찾기 쉽게)
    snapshot           jsonb NOT NULL,         -- {trip, tables: {표: [행…]}, intake_ids, mark}
    archived_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_trip_id)
);
CREATE INDEX IF NOT EXISTS trip_archives_age_idx ON trip_archives (tenant_id, archived_at);

-- 「남길 시험 여행」 표시 — 지우기 전에 단다. 표시가 있는 살아 있는 여행은 감시 · 안내 대상에서 빠진다(`trip_scope` 규칙 `trip_archive.marked`).
-- 여행을 지우면 표시도 따라 지워진다(CASCADE) — 그 전에 보관함이 표시 내용을 `snapshot.mark` 로 담는다.
CREATE TABLE IF NOT EXISTS trip_archive_marks (
    tenant_id  text NOT NULL,
    trip_id    uuid NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    note       text,
    marked_by  text NOT NULL,              -- 누가 — 예: live_check(실서버 확인 도구) · admin
    marked_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, trip_id)
);

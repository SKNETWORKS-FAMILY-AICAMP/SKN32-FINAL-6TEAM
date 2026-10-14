-- 304  활동 장소 실시간 운영 상태(웹 공지) — 장소 · 날짜당 한 번 확인해 저장한다(D-CS-015 개정 2 · 2026-10-13 사용자 결정 A안)
-- 작성 2026-10-13.
--
-- ★왜. 임시휴무 · 폐업은 DB(관광공사 정기 운영 정보)에 없다. 그래서 웹 공지를 본다 — 그런데 고객 요청마다 부르면 비용이 요청 수에
--   비례하고 응답이 느리다(p95 40.7초 · 429). **같은 장소 · 같은 날짜는 한 번만** 확인해 이 표에 두고, 고객 요청은 읽기만 한다.
-- ★확인은 배치(`scripts/activity/check_live_status.py`)가 한다 — 앞으로 `live_status_within_hours` 안에 시작하는 활동 항목만.
-- ★모름도 줄로 남긴다(`unknown`) — 같은 장소를 계속 다시 부르지 않게 `checked_at` 으로 다시 볼 때를 정한다.
--   줄이 없으면 「아직 안 봤다」이고, `unknown` 은 「봤는데 알 수 없었다」다. 둘 다 고객에게는 「임시휴무는 확인하지 못했다」다.

CREATE TABLE IF NOT EXISTS activity.ac_live_status (
    content_id   text NOT NULL REFERENCES activity.ac_place(content_id) ON DELETE CASCADE,
    visit_date   date NOT NULL,
    value        text NOT NULL,
    citations    jsonb NOT NULL DEFAULT '[]'::jsonb,
    basis        text,
    model        text,
    checked_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (content_id, visit_date),
    CONSTRAINT ac_live_status_value_chk CHECK (value IN ('open', 'closed', 'unknown'))
);

CREATE INDEX IF NOT EXISTS ac_live_status_checked_idx ON activity.ac_live_status (checked_at);

COMMENT ON TABLE activity.ac_live_status IS
    '장소 · 날짜별 웹 공지상 운영 상태 — 배치가 한 번 확인해 저장한다. 고객 요청은 읽기만 한다. 줄이 없으면 아직 안 봤다.';
COMMENT ON COLUMN activity.ac_live_status.citations IS
    '근거 [{url, quote, published_at}] — 인용 검증을 통과한 것만(judge/llm.py). closed 는 인용이 있을 때만 쓴다.';

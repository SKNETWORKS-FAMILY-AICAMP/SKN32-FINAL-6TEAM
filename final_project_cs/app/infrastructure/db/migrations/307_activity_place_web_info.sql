-- 307  활동 장소의 **웹 검색으로 채운 정보** — 관광공사 원장에 없거나 비어 있는 칸. 작성 2026-10-19.
--
-- ★왜 별도 표인가(2026-10-19 사용자 결정). 원장 적재(`scripts/activity/load_places.py`)는 CSV 로 `ac_place` 칸을 **덮어쓴다** —
--   웹에서 채운 값을 거기에 넣으면 다음 적재에 사라지고, `--prune` 은 CSV 에 없는 행을 지운다. 그래서 출처 · 인용 · 만료와 함께 이 표에 두고,
--   **읽을 때** 관광공사 값이 있으면 그것, 비었을 때만 웹 값을 쓴다(`activity/web_info.py` `effective`). 「이미 채워진 칸은 패스」가 읽기 규칙이다.
-- ★원장에 없는 장소(카카오로 실존만 확인한 곳)도 여기에 둔다 — `ac_place` 에 넣으면 후보 풀(대체 장소)에 검증 안 된 행이 섞이고
--   `ac_place.content_type_id` · `load_id` 가 NOT NULL 이라 가짜 값이 필요하다. `place_key` 가 원장 장소면 `content_id`, 아니면 `web:<정규화한 고객 이름>`.
-- ★넣는 것은 **고객이 쓴 이름 · 웹 검색 결과(인용 검증을 통과한 것) · 브이월드 좌표**뿐이다. 카카오가 준 이름 · 주소 · 좌표는 넣지 않는다
--   (카카오 운영정책 제5조 — 응답 저장 금지). 소개글 · 체험 안내는 넣지 않는다(남의 글 — 저장 안 함, 2026-10-19 사용자 결정).
-- ★웹 값은 틀릴 수 있어 **만료**(`expires_at`)가 있고, 웹 출처 값에는 인용(`quote`)과 URL 이 꼭 있다(검사로 막는다). 좌표(`lat_lng`)는 `vworld`.
-- ★`none` 줄 — 웹 검색을 했는데 **쓸 값을 못 찾은** 칸의 표시다(값은 빈 글). 같은 칸을 매번 다시 검색해 돈이 나가지 않게 짧은 만료(7일)를 둔다.
--   읽을 때는 값이 없는 것으로 본다(`web_info.effective`).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS activity.ac_place_web_info (
    place_key    text        NOT NULL,                 -- 원장 장소면 content_id · 원장 밖이면 'web:' + 정규화한 고객 이름
    field        text        NOT NULL,
    value        text        NOT NULL,                 -- 원문 그대로(운영시간 문장을 새로 쓰지 않는다). lat_lng 는 '위도,경도'
    source       text        NOT NULL,
    quote        text,                                 -- 웹 페이지에서 따온 근거 구절(원문 그대로)
    url          text,
    published_at date,
    model        text,
    checked_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    PRIMARY KEY (place_key, field),
    CONSTRAINT ac_place_web_info_field_chk  CHECK (field IN (
        'name', 'address', 'business_hours', 'closed_days', 'reservation_info', 'capacity', 'age_limit',
        'fee', 'spendtime', 'tel', 'homepage', 'pet', 'lat_lng')),
    CONSTRAINT ac_place_web_info_source_chk CHECK (source IN ('web', 'vworld', 'customer', 'none')),
    CONSTRAINT ac_place_web_info_evidence_chk CHECK (source <> 'web' OR (quote IS NOT NULL AND url IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS ac_place_web_info_expires_idx ON activity.ac_place_web_info (expires_at);

COMMENT ON TABLE activity.ac_place_web_info IS
    '웹 검색(OpenAI)으로 채운 장소 정보 + 브이월드 좌표 — 출처 · 인용 · 만료와 함께. 원장 값이 비었을 때만 읽는다. 카카오 응답 · 소개글은 넣지 않는다.';
COMMENT ON COLUMN activity.ac_place_web_info.place_key IS
    '원장 장소면 content_id, 원장 밖이면 web:<정규화한 고객 이름>. FK 가 없다(원장 밖 장소가 있다).';
COMMENT ON COLUMN activity.ac_place_web_info.source IS
    'web = 웹 검색(인용 필수) · vworld = 브이월드 지오코더(좌표) · customer = 고객이 쓴 이름 · none = 검색했지만 쓸 값을 못 찾음(값은 빈 글, 짧은 만료).';

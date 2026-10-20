-- 306  활동 장소 별칭 — 정식 제목과 완전히 다른 이름(「남산타워」 · 「N서울타워」 = 「남산서울타워」). 작성 2026-10-19.
--
-- ★왜. 띄어쓰기 · 기호 · 괄호 · 지점 표시 차이는 정규화가 처리한다. 글자가 아예 다른 이름은 규칙으로 못 가른다 —
--   이름 유사도로 짐작하면 남산도서관 · 용산도서관(다른 곳)과 남산서울타워 · N서울타워(같은 곳)가 가려지지 않는다.
--   그래서 **사람이 확인한 별칭**을 둔다(대체 후보에서 「이미 일정에 있는 곳」 제외 · 원장 이름 찾기가 읽는다).
-- ★배포 뒤에도 고칠 수 있게 DB 표로 둔다(이미지를 다시 만들지 않는다). 시드는 `data_processing/place_aliases.csv` →
--   `scripts/activity/load_place_aliases.py`(원장 `load_places.py` 와 같은 방식 — 수동 적재).
-- ★넣는 것은 **우리가 정리한 이름과 고객이 쓴 말**뿐이다. 카카오 응답에서 이름을 뽑아 넣지 않는다(카카오 운영정책 제5조 — 응답 저장 금지).
-- ★한 별칭이 둘 이상의 장소를 가리키면(PK 가 허용한다) 앱이 같다고 보지 않는다(모호).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS activity.ac_place_alias (
    alias_norm  text NOT NULL,           -- 정규화한 별칭(`intake.places.normalize_full`) — 찾는 키
    content_id  text NOT NULL REFERENCES activity.ac_place(content_id) ON DELETE CASCADE,
    alias       text NOT NULL,           -- 사람이 적은 그대로
    source      text NOT NULL DEFAULT 'curated',
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (alias_norm, content_id),
    CONSTRAINT ac_place_alias_source_chk CHECK (source IN ('curated', 'customer'))
);

CREATE INDEX IF NOT EXISTS ac_place_alias_content_idx ON activity.ac_place_alias (content_id);

COMMENT ON TABLE activity.ac_place_alias IS
    '활동 장소 별칭 — 정식 제목과 완전히 다른 이름. 사람이 확인한 것만 넣는다. 카카오 응답 이름은 넣지 않는다(운영정책 제5조).';
COMMENT ON COLUMN activity.ac_place_alias.source IS
    'curated = 우리가 정리 · customer = 고객이 쓴 말(검토 뒤 승격).';

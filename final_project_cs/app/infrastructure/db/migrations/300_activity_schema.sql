-- 300  활동 에이전트 장소 원장 (activity 스키마)
-- 작성 2026-10-12. 요식 원장(200 · dining 스키마)과 같은 자리에 둔다 — 활동 팀이 자기 DB 를 조회해 판정한다(activity.md D2-2).
--
-- 원천: instances/activity/data_processing/activity_total_data.csv (관광공사 서울 + 올리브영 · 다이소 · 아트박스 · 무신사)
-- 적재: scripts/activity/load_places.py — 같은 CSV 를 다시 돌리면 같은 행을 덮어쓴다.
--
-- 원칙
--   코어 표에 외래키를 걸지 않는다(요식 DN-C1 과 같다). 코어 places 와는 source_content_id = content_id 로 만난다.
--   판정에 쓰는 칸은 운영시간 원문 · 휴무 원문 · 분류 코드뿐이다. 소개글 · 요금은 부가 정보다(판정 · 추천에 안 쓴다).
--   실내외 기록 표(ac_indoor)는 아직 만들지 않는다 — D-CS-015 개정 뒤(activity.md 1.8 · D7).
--   이 파일은 마이그레이션이 매번 다시 돈다 — 데이터가 든 DB 에 다시 돌려도 깨지지 않아야 한다.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS activity;


-- 적재 한 번
CREATE TABLE IF NOT EXISTS activity.ac_load_meta (
    load_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file  text NOT NULL,
    file_sha256  char(64) NOT NULL,
    row_count    integer NOT NULL,
    loaded_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ac_load_meta_rowcount_chk CHECK (row_count >= 0)
);

COMMENT ON COLUMN activity.ac_load_meta.row_count IS
    '그 적재에서 넣은(덮어쓴) 행 수.';


-- 장소 한 곳
CREATE TABLE IF NOT EXISTS activity.ac_place (
    content_id        text PRIMARY KEY,
    content_type_id   text NOT NULL,
    name_ko           text NOT NULL,
    name_key          text NOT NULL,
    addr1             text,
    addr2             text,
    sigungu_code      text,
    lat               double precision,
    lng               double precision,
    lcls1             text,
    lcls2             text,
    lcls3             text,
    brand             text,
    usetime_text      text,
    restdate_text     text,
    overview          text,
    fee_text          text,
    info_center       text,
    reservation_text  text,
    capacity_text     text,
    spend_time        text,
    age_limit         text,
    experience_guide  text,
    load_id           uuid NOT NULL REFERENCES activity.ac_load_meta(load_id),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ac_place_lat_chk        CHECK (lat IS NULL OR (lat BETWEEN -90 AND 90)),
    CONSTRAINT ac_place_lng_chk        CHECK (lng IS NULL OR (lng BETWEEN -180 AND 180)),
    CONSTRAINT ac_place_coord_pair_chk CHECK ((lat IS NULL) = (lng IS NULL))
);

CREATE INDEX IF NOT EXISTS ac_place_name_key_idx ON activity.ac_place (name_key);
CREATE INDEX IF NOT EXISTS ac_place_lcls3_idx    ON activity.ac_place (lcls3);
CREATE INDEX IF NOT EXISTS ac_place_sigungu_idx  ON activity.ac_place (sigungu_code);

COMMENT ON COLUMN activity.ac_place.content_id IS
    '관광공사 contentid, 브랜드 매장은 CSV 의 자체 id(OY… 등). 코어 places.source_content_id 와 같은 값이다.';
COMMENT ON COLUMN activity.ac_place.name_key IS
    '이름 찾기 키 — csv_places._normalize 와 같은 규칙(괄호 · 지점 접미사 · 공백 · 구두점 제거, 소문자).';
COMMENT ON COLUMN activity.ac_place.usetime_text IS
    '운영시간 원문(CSV business_hours). 판정은 verdicts.hours_verdict 가 읽는다.';
COMMENT ON COLUMN activity.ac_place.restdate_text IS
    '휴무 원문(CSV closed_days). 판정은 closure_rules.read_closure 가 읽는다.';
COMMENT ON COLUMN activity.ac_place.overview IS
    '소개글 — 부가 참고. 분류 힌트로 쓸 수 있으나 판정 · 추천 순위에는 쓰지 않는다(2026-10-12 사용자 결정).';
COMMENT ON COLUMN activity.ac_place.fee_text IS
    '요금 원문 — 고객에게 덧붙이는 정보. 지금은 추천에 쓰지 않는다(예산 기능이 생기면 다시 본다, 2026-10-12 사용자 결정).';
COMMENT ON COLUMN activity.ac_place.capacity_text IS
    '장소 수용 인원(관광공사 accomcount 계열). 판정에 쓰지 않고 대체 후보 거르기에만 쓴다(D3 범위 정정 2026-10-12). '
    '예약 자체의 정원(bookings.capacity)과 다르다.';

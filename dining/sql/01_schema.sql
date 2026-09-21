-- 요식 에이전트 DB 1차 스키마
-- 대상: DB설계 v3의 D-10, D-11, D-12, D-13, D-01, D-02, D-03
-- 작성 2026-09-19. 적재 전 검증용이며 팀 합의 전이다.
--
-- 전제
--   PostgreSQL 16
--   PostGIS 는 쓰지 않는다 (설계 Q-D3). 좌표는 위경도 칸으로 두고 거리는 코드에서 계산한다.
--   btree_gist 확장이 필요하다. dn_hours_interval 의 겹침 방지 제약이 이 확장을 쓴다.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS dining;


-- D-10 출처 한 건
CREATE TABLE dining.dn_source (
    source_code        text PRIMARY KEY,
    display_name       text NOT NULL,
    source_kind        text NOT NULL,
    storage_mode       text NOT NULL,
    production_allowed boolean NOT NULL,
    license_ref        text,
    policy_checked_at  date,
    note               text,
    CONSTRAINT dn_source_kind_chk
        CHECK (source_kind IN ('synthetic','mock','public','provider','partner','customer','operator')),
    CONSTRAINT dn_source_storage_chk
        CHECK (storage_mode IN ('content','id_only','link_only')),
    CONSTRAINT dn_source_provider_id_only_chk
        CHECK (source_kind <> 'provider' OR storage_mode = 'id_only')
);

COMMENT ON CONSTRAINT dn_source_provider_id_only_chk ON dining.dn_source IS
    '공급자 출처는 식별자만 저장한다. 구글을 원문 보관으로 등록하려는 시도를 DB가 거부한다.';


-- D-11 적재 한 번
CREATE TABLE dining.dn_load_meta (
    load_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code        text NOT NULL REFERENCES dining.dn_source(source_code),
    fetched_at         timestamptz NOT NULL,
    source_modified_at text,
    schema_version     text NOT NULL,
    scope              text NOT NULL,
    row_count          integer NOT NULL,
    raw_uri            text,
    raw_sha256         char(64),
    status             text NOT NULL,
    CONSTRAINT dn_load_meta_rowcount_chk CHECK (row_count >= 0),
    CONSTRAINT dn_load_meta_status_chk   CHECK (status IN ('loaded','verified','failed'))
);

COMMENT ON COLUMN dining.dn_load_meta.row_count IS
    '받은 행 수이며 품질을 통과한 행 수가 아니다.';


-- D-12 장소 원장 한 곳
CREATE TABLE dining.dn_place (
    place_uid      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ko        text NOT NULL,
    name_en        text,
    branch_name    text,
    road_address   text,
    jibun_address  text,
    lat            double precision,
    lng            double precision,
    coord_source   text REFERENCES dining.dn_source(source_code),
    area           text NOT NULL,
    phone          text,
    record_status  text NOT NULL,
    is_synthetic   boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dn_place_status_chk CHECK (record_status IN ('active','closed','unknown')),
    CONSTRAINT dn_place_lat_chk    CHECK (lat IS NULL OR (lat BETWEEN -90 AND 90)),
    CONSTRAINT dn_place_lng_chk    CHECK (lng IS NULL OR (lng BETWEEN -180 AND 180)),
    CONSTRAINT dn_place_coord_pair_chk CHECK ((lat IS NULL) = (lng IS NULL))
);

COMMENT ON COLUMN dining.dn_place.record_status IS
    '인허가 폐업 반영용이며 오늘 영업 여부가 아니다.';
COMMENT ON COLUMN dining.dn_place.is_synthetic IS
    '합성 여부는 이 칸으로만 판단한다. 이름 표기로 판단하지 않는다.';


-- D-13 공공 원천 레코드 한 판
CREATE TABLE dining.dn_source_record (
    record_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    load_id            uuid NOT NULL REFERENCES dining.dn_load_meta(load_id),
    source_code        text NOT NULL REFERENCES dining.dn_source(source_code),
    external_id        text NOT NULL,
    place_uid          uuid REFERENCES dining.dn_place(place_uid),
    match_status       text NOT NULL,
    match_basis        jsonb,
    source_modified_at text,
    raw_json           jsonb NOT NULL,
    CONSTRAINT dn_source_record_uniq UNIQUE (source_code, external_id, load_id),
    CONSTRAINT dn_source_record_match_chk
        CHECK (match_status IN ('unmatched','auto','confirmed','rejected'))
);

COMMENT ON COLUMN dining.dn_source_record.raw_json IS
    'storage_mode 가 content 인 출처만 적재기가 채운다. 메뉴 문장은 여기서만 보관하고 정규화하지 않는다.';


-- D-01 평소 영업 규칙 한 건
CREATE TABLE dining.dn_hours_rule (
    rule_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid          uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    source_code        text NOT NULL REFERENCES dining.dn_source(source_code),
    record_id          uuid REFERENCES dining.dn_source_record(record_id),
    entered_by         text,
    verified_by        text,
    verified_at        timestamptz,
    rule_kind          text NOT NULL,
    weekday            smallint,
    coverage           text NOT NULL,
    break_state        text NOT NULL,
    source_text        text,
    extract_method     text NOT NULL,
    extract_confidence real,
    rules_version      text NOT NULL,
    valid_from         date NOT NULL,
    valid_to           date,
    retired_at         timestamptz,
    CONSTRAINT dn_hours_rule_kind_chk     CHECK (rule_kind IN ('weekly','holiday')),
    CONSTRAINT dn_hours_rule_weekday_chk  CHECK (weekday IS NULL OR weekday BETWEEN 1 AND 7),
    CONSTRAINT dn_hours_rule_weekly_chk   CHECK ((rule_kind = 'weekly') = (weekday IS NOT NULL)),
    CONSTRAINT dn_hours_rule_coverage_chk CHECK (coverage IN ('intervals','closed','unknown')),
    CONSTRAINT dn_hours_rule_break_chk    CHECK (break_state IN ('present','none','unknown')),
    CONSTRAINT dn_hours_rule_method_chk
        CHECK (extract_method IN ('structured','regex','llm','manual','synthetic')),
    CONSTRAINT dn_hours_rule_conf_chk
        CHECK (extract_confidence IS NULL OR extract_confidence BETWEEN 0 AND 1),
    CONSTRAINT dn_hours_rule_valid_chk    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT dn_hours_rule_input_chk
        CHECK (record_id IS NOT NULL OR (entered_by IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT dn_hours_rule_llm_chk
        CHECK (extract_method <> 'llm' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);

COMMENT ON CONSTRAINT dn_hours_rule_llm_chk ON dining.dn_hours_rule IS
    '검수되지 않은 LLM 추출은 저장은 되되 판정 조회 뷰에서 제외한다.';
COMMENT ON COLUMN dining.dn_hours_rule.break_state IS
    '브레이크 언급이 없으면 unknown 이다. none 과 구분한다.';


-- D-02 영업 구간 한 칸
CREATE TABLE dining.dn_hours_interval (
    rule_id          uuid NOT NULL REFERENCES dining.dn_hours_rule(rule_id) ON DELETE CASCADE,
    seq              smallint NOT NULL,
    open_min         smallint NOT NULL,
    close_min        smallint NOT NULL,
    last_order_min   smallint,
    last_order_state text NOT NULL,
    PRIMARY KEY (rule_id, seq),
    CONSTRAINT dn_hours_interval_seq_chk   CHECK (seq >= 1),
    CONSTRAINT dn_hours_interval_open_chk  CHECK (open_min BETWEEN 0 AND 1439),
    CONSTRAINT dn_hours_interval_close_chk CHECK (close_min > open_min AND close_min <= open_min + 1440),
    CONSTRAINT dn_hours_interval_lo_range_chk
        CHECK (last_order_min IS NULL OR (last_order_min >= open_min AND last_order_min <= close_min)),
    CONSTRAINT dn_hours_interval_lo_state_chk
        CHECK (last_order_state IN ('present','none','unknown')),
    CONSTRAINT dn_hours_interval_lo_pair_chk
        CHECK ((last_order_state = 'present') = (last_order_min IS NOT NULL)),
    CONSTRAINT dn_hours_interval_no_overlap
        EXCLUDE USING gist (rule_id WITH =, int4range(open_min::int, close_min::int) WITH &&)
);

COMMENT ON TABLE dining.dn_hours_interval IS
    '브레이크타임은 별도 칸이 아니라 연속한 두 구간 사이의 빈 시간으로 표현한다. 자정 넘김은 close_min 이 1440 이상이다.';


-- D-03 휴무 규칙 한 건
CREATE TABLE dining.dn_closure_rule (
    closure_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid          uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    source_code        text NOT NULL REFERENCES dining.dn_source(source_code),
    record_id          uuid REFERENCES dining.dn_source_record(record_id),
    entered_by         text,
    verified_by        text,
    verified_at        timestamptz,
    pattern_kind       text NOT NULL,
    weekday            smallint,
    nth                smallint[],
    holiday_name       text,
    holiday_scope      text,
    closed_date        date,
    source_text        text,
    extract_method     text NOT NULL,
    extract_confidence real,
    valid_from         date NOT NULL,
    valid_to           date,
    retired_at         timestamptz,
    CONSTRAINT dn_closure_pattern_chk
        CHECK (pattern_kind IN ('weekly','monthly_nth','public_holiday','named_holiday','date')),
    CONSTRAINT dn_closure_weekday_chk CHECK (weekday IS NULL OR weekday BETWEEN 1 AND 7),
    CONSTRAINT dn_closure_scope_chk
        CHECK (holiday_scope IS NULL OR holiday_scope IN ('day_of','whole_period')),
    CONSTRAINT dn_closure_method_chk
        CHECK (extract_method IN ('structured','regex','llm','manual','synthetic')),
    CONSTRAINT dn_closure_conf_chk
        CHECK (extract_confidence IS NULL OR extract_confidence BETWEEN 0 AND 1),
    CONSTRAINT dn_closure_valid_chk CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT dn_closure_input_chk
        CHECK (record_id IS NOT NULL OR (entered_by IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT dn_closure_llm_chk
        CHECK (extract_method <> 'llm' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT dn_closure_shape_chk CHECK (
        CASE pattern_kind
            WHEN 'weekly' THEN
                weekday IS NOT NULL AND nth IS NULL AND holiday_name IS NULL
                AND holiday_scope IS NULL AND closed_date IS NULL
            WHEN 'monthly_nth' THEN
                weekday IS NOT NULL AND nth IS NOT NULL AND holiday_name IS NULL
                AND holiday_scope IS NULL AND closed_date IS NULL
            WHEN 'public_holiday' THEN
                weekday IS NULL AND nth IS NULL AND holiday_name IS NULL
                AND holiday_scope IS NULL AND closed_date IS NULL
            WHEN 'named_holiday' THEN
                weekday IS NULL AND nth IS NULL AND holiday_name IS NOT NULL
                AND holiday_scope IS NOT NULL AND closed_date IS NULL
            WHEN 'date' THEN
                weekday IS NULL AND nth IS NULL AND holiday_name IS NULL
                AND holiday_scope IS NULL AND closed_date IS NOT NULL
        END
    )
);

COMMENT ON TABLE dining.dn_closure_rule IS
    '공휴일과 명절의 실제 날짜는 이 표에 두지 않고 공휴일 달력에서 읽는다.';


-- 인덱스 (설계 3.3 의 Q-D1, Q-D2, Q-D3, Q-D11)
CREATE INDEX dn_hours_rule_lookup_idx
    ON dining.dn_hours_rule (place_uid, rule_kind, weekday) WHERE retired_at IS NULL;

CREATE INDEX dn_closure_rule_lookup_idx
    ON dining.dn_closure_rule (place_uid) WHERE retired_at IS NULL;

CREATE INDEX dn_place_coord_idx
    ON dining.dn_place (lat, lng) WHERE record_status = 'active';

CREATE INDEX dn_source_record_place_idx
    ON dining.dn_source_record (place_uid, source_code);


-- 출처 등록. 첫 행이며 나머지 표가 이 값을 참조한다.
INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('tourapi_kor_food',   '한국관광공사 TourAPI 음식점', 'public',    'content',   true,  '영업시간 원문 보관 가능'),
    ('localdata_food',     '지방행정 인허가 일반음식점', 'public',    'content',   true,  '폐업 판정 근거'),
    ('google_places',      'Google Places',              'provider',  'id_only',   true,  'place_id 만 저장'),
    ('naver_map_manual',   '네이버 지도 수동 확인 링크', 'operator',  'link_only', true,  'URL 만 저장'),
    ('operator_check',     '운영자 확인',                'operator',  'content',   true,  NULL),
    ('customer_report',    '고객 신고',                  'customer',  'content',   true,  NULL),
    ('synthetic_scenario', '합성 시나리오',              'synthetic', 'content',   false, '운영 판정에 쓰지 않는다'),
    ('mock_places',        '모의 조회',                  'mock',      'id_only',   false, '합성 장소에만 연결');

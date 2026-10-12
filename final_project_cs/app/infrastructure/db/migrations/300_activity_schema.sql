-- 300 — 활동(Activity) 에이전트 DB 1차 스키마 (초안)
-- 작성 2026-10-12. 요식 팀 200_dining_schema.sql · 201_dining_core_link.sql 과 같은 모양으로 잡았다.
-- 상태: 초안이며 팀 합의 전이다(작업자 A · B · 코어 검토 필요).
--
-- ★왜 따로 두나 (2026-10-12 사용자 결정 — activity.md D2-2)
--   활동 팀은 자기 데이터(activity_total_data.csv — 장소 6,338건, 25칸)로 장소를 비교하고 판정한다.
--   지금은 그 가운데 브랜드와 영업시간 · 휴무만 공용 장소 표(place_catalog · catalog_hours)에 옮겨져 있고,
--   수용 인원 · 예약 안내 · 소요 시간 · 반려동물 · 행사 기간 · 연락처는 어디에도 없다.
--   요식 팀이 dining 스키마를 정본으로 두고 끼움 자리(team_hooks/dining_ledger)로 판정을 내놓듯,
--   활동 팀도 activity 스키마를 정본으로 둔다.
--
-- 원칙 (요식 DN-C1 과 같다)
--   코어 표(places · place_catalog)에 외래키를 걸지 않는다. 연결 표의 core_place_id 는 논리 참조다 —
--   코어 스키마가 바뀌어도 활동 표가 깨지지 않게.
--   값은 원문 그대로 둔다(db_column.md 원칙). 파싱한 값은 별도 칸에 두고 원문을 지우지 않는다.
--   모르는 값은 NULL 이다 — 「없음」으로 채우지 않는다.
--   재실행 안전(IF NOT EXISTS · ON CONFLICT) — 데이터가 있는 DB 에 다시 돌려도 깨지지 않는다.
--
-- 안 넣는 것
--   overview(소개글) — 관광공사 소개글은 저장하지 않기로 했다(2026-09-28 결정, enrich_place_catalog_from_csv 참고).
--   fee(요금) — 판정에 쓰지 않는다. `[결정 필요]` 대체 후보 안내에 쓸지 정하면 칸을 더한다.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS activity;


-- 출처 한 곳 (요식 D-10 과 같은 모양)
CREATE TABLE IF NOT EXISTS activity.ac_source (
    source_code        text PRIMARY KEY,           -- tour_api · oliveyoung · daiso · artbox · musinsa · operator
    display_name       text NOT NULL,
    source_kind        text NOT NULL,
    storage_mode       text NOT NULL,
    note               text,
    CONSTRAINT ac_source_kind_chk    CHECK (source_kind IN ('public','curated','operator','customer')),
    CONSTRAINT ac_source_storage_chk CHECK (storage_mode IN ('content','id_only'))
);

COMMENT ON COLUMN activity.ac_source.storage_mode IS
    'content 출처만 원문 칸을 채운다. 카카오처럼 저장이 금지된 출처는 여기 등록하지 않는다(운영정책 제5조).';

INSERT INTO activity.ac_source (source_code, display_name, source_kind, storage_mode, note) VALUES
    ('tour_api',   '한국관광공사 TourAPI 4.0', 'public',  'content', 'ⓒ한국관광공사 표시 유지'),
    ('oliveyoung', '올리브영 매장(수기 큐레이션)', 'curated', 'content', 'contentid 접두 OY'),
    ('daiso',      '다이소 매장(수기 큐레이션)',   'curated', 'content', 'contentid 접두 DS'),
    ('artbox',     '아트박스 매장(수기 큐레이션)', 'curated', 'content', 'contentid 접두 AB'),
    ('musinsa',    '무신사 매장(수기 큐레이션)',   'curated', 'content', 'contentid 접두 MS'),
    ('operator',   '운영자 · 사람 수정',           'operator','content', '사람이 고친 값 — 항상 우선')
ON CONFLICT (source_code) DO NOTHING;


-- 적재 한 번 (요식 D-11)
CREATE TABLE IF NOT EXISTS activity.ac_load_meta (
    load_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file        text NOT NULL,              -- activity_total_data.csv 등(경로가 아니라 이름)
    file_sha256        char(64) NOT NULL,
    schema_version     text NOT NULL,              -- db_column.md 판(예: 2026-10-11 25칸)
    row_count          integer NOT NULL,
    loaded_at          timestamptz NOT NULL DEFAULT now(),
    status             text NOT NULL,
    CONSTRAINT ac_load_meta_rowcount_chk CHECK (row_count >= 0),
    CONSTRAINT ac_load_meta_status_chk   CHECK (status IN ('loaded','verified','failed'))
);

COMMENT ON COLUMN activity.ac_load_meta.row_count IS '받은 행 수이며 품질을 통과한 행 수가 아니다.';


-- 장소 원장 한 곳 (요식 D-12) — CSV 1~11 · 16~19칸
CREATE TABLE IF NOT EXISTS activity.ac_place (
    place_uid          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code        text NOT NULL REFERENCES activity.ac_source(source_code),
    content_id         text NOT NULL,              -- contentid (관광공사는 숫자, 브랜드는 접두어)
    content_type_id    text,                       -- 12 관광지 · 14 문화시설 · 15 행사 · 28 레포츠 · 38 쇼핑
    title              text NOT NULL,
    address            text,                       -- addr1
    address_detail     text,                       -- addr2
    ldong_signgu_cd    text,                       -- lDongSignguCd(법정동 시군구)
    lat                double precision,           -- mapy
    lng                double precision,           -- mapx
    lcls1              text,                       -- lclsSystm1 대분류
    lcls2              text,                       -- lclsSystm2 중분류
    lcls3              text,                       -- lclsSystm3 소분류
    brand              text,
    tel                text,
    homepage           text,
    source_modified_at text,                       -- modifiedtime(공급자 수정 시각 — 우리가 받은 시각이 아니다)
    record_status      text NOT NULL DEFAULT 'active',
    load_id            uuid REFERENCES activity.ac_load_meta(load_id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ac_place_source_uniq UNIQUE (source_code, content_id),
    CONSTRAINT ac_place_status_chk  CHECK (record_status IN ('active','closed','unknown')),
    CONSTRAINT ac_place_lat_chk     CHECK (lat IS NULL OR (lat BETWEEN -90 AND 90)),
    CONSTRAINT ac_place_lng_chk     CHECK (lng IS NULL OR (lng BETWEEN -180 AND 180)),
    CONSTRAINT ac_place_coord_pair_chk CHECK ((lat IS NULL) = (lng IS NULL))
);

CREATE INDEX IF NOT EXISTS ac_place_title_idx ON activity.ac_place (title);
CREATE INDEX IF NOT EXISTS ac_place_class_idx ON activity.ac_place (lcls1, lcls2, lcls3);
CREATE INDEX IF NOT EXISTS ac_place_coord_idx ON activity.ac_place (lat, lng);

COMMENT ON COLUMN activity.ac_place.record_status IS '폐점 · 중복 정리 반영용이며 오늘 운영 여부가 아니다.';


-- 운영 정보 (판정 재료) — CSV 13 · 14 · 20~25칸. 장소 하나에 한 행
CREATE TABLE IF NOT EXISTS activity.ac_operation (
    place_uid          uuid PRIMARY KEY REFERENCES activity.ac_place(place_uid),
    business_hours     text,                       -- 원문(타입별 usetime · opentime …)
    closed_days        text,                       -- 원문(타입별 restdate …)
    hours_week         jsonb,                      -- 원문을 요일표로 읽은 값(activity/hours_text.read_week). 못 읽으면 NULL
    hours_read_at      timestamptz,
    capacity_text      text,                       -- 수용 인원 원문(accomcount …) — ★장소 규모다. 예약 정원이 아니다(D3)
    capacity_n         integer,                    -- 원문이 단순 숫자로 읽힐 때만. 아니면 NULL
    reservation_info   text,                       -- 예약 안내 원문
    spendtime          text,
    event_start_date   date,
    event_end_date     date,
    pet                text,
    load_id            uuid REFERENCES activity.ac_load_meta(load_id),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ac_operation_capacity_chk CHECK (capacity_n IS NULL OR capacity_n >= 0),
    CONSTRAINT ac_operation_event_chk    CHECK (event_start_date IS NULL OR event_end_date IS NULL
                                                OR event_start_date <= event_end_date)
);

COMMENT ON COLUMN activity.ac_operation.capacity_n IS
    '대체 후보 거르기(UC-A4 2단계 — 일행보다 작은 곳 제외)에만 쓴다. 성립 판정에 쓰지 않는다(D3 범위 정정 2026-10-12).';


-- 실내 · 실외 판정 (멘토 #1 · 구현 계획 1.8 — 처음 한 번 판정해 적재, 이후 규칙)
--   ★「누가 · 언제 · 어떻게 정했는지」를 남긴다. 사람 수정(operator)은 항상 우선한다.
--   ★`[결정 필요]` D-CS-015 는 지금 「실내외 LLM 판정은 저장하지 않는다」다 — 개정 전에는 llm 행을 쓰지 않는다.
CREATE TABLE IF NOT EXISTS activity.ac_indoor (
    place_uid          uuid NOT NULL REFERENCES activity.ac_place(place_uid),
    decided_by         text NOT NULL,              -- class(관광공사 분류) · llm · customer · operator
    outdoor            boolean,                    -- true 야외 · false 실내 · NULL 확정 못 함
    evidence           text,                       -- 인용 · 근거 문장
    model              text,
    prompt_version     text,
    decided_at         timestamptz NOT NULL DEFAULT now(),
    retired_at         timestamptz,
    CONSTRAINT ac_indoor_by_chk CHECK (decided_by IN ('class','llm','customer','operator')),
    CONSTRAINT ac_indoor_llm_chk CHECK (decided_by <> 'llm' OR (model IS NOT NULL AND prompt_version IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ac_indoor_active_uniq
    ON activity.ac_indoor (place_uid, decided_by) WHERE retired_at IS NULL;


-- 코어 장소 연결 (요식 D-15 dn_core_place_link 와 같다)
--   코어 places.place_id(uuid) · tenant_id(text) — 010_domain_travel.sql 에서 확인
CREATE TABLE IF NOT EXISTS activity.ac_core_place_link (
    tenant_id          text NOT NULL,
    core_place_id      uuid NOT NULL,
    place_uid          uuid NOT NULL REFERENCES activity.ac_place(place_uid),
    linked_by          text NOT NULL,              -- content_id(관광공사 번호 일치) · name_coord(이름 + 150m) · operator
    linked_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, core_place_id),
    CONSTRAINT ac_link_by_chk CHECK (linked_by IN ('content_id','name_coord','operator'))
);

CREATE INDEX IF NOT EXISTS ac_core_place_link_place_idx ON activity.ac_core_place_link (place_uid);

COMMENT ON TABLE activity.ac_core_place_link IS
    '코어 places 한 행과 활동 원장 장소의 연결. 코어 표에 FK 를 걸지 않으므로 논리 참조다.';


-- 판정에 쓰는 실내외 — 사람 수정 > 고객 답 > LLM > 관광공사 분류 순. 없으면 행이 없다(모름)
CREATE OR REPLACE VIEW activity.v_indoor_current AS
SELECT DISTINCT ON (place_uid) place_uid, outdoor, decided_by, decided_at
FROM activity.ac_indoor
WHERE retired_at IS NULL AND outdoor IS NOT NULL
ORDER BY place_uid,
         CASE decided_by WHEN 'operator' THEN 0 WHEN 'customer' THEN 1 WHEN 'llm' THEN 2 ELSE 3 END,
         decided_at DESC;

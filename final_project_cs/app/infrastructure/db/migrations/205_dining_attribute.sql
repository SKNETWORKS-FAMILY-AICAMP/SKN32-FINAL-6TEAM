-- 매장 속성 (설계 v3 의 D-04)
-- 작성 2026-09-21.
--
-- 왜 필요한가. 같은 일정이라도 사용자 조건에 따라 판정이 달라져야 한다.
-- 카드만 쓰는 여행자에게 현금만 받는 집은 못 가는 곳이고, 그 사실을 모르면
-- 현장에서야 알게 된다.
--
-- 표본 200곳의 관광공사 자료에서 카드 결제는 이렇게 나왔다.
--   가능 51곳, 없음 4곳, 나머지 145곳은 언급이 없다.
-- 145곳을 가능으로 바꾸지 않는다. 모르는 것은 unknown 으로 둔다.
--
-- 속성마다 코드를 따로 둔다. 의미가 다른 값을 한 코드로 묶으면
-- 나중에 조건이 늘었을 때 갈라낼 수 없다.

CREATE TABLE IF NOT EXISTS dining.dn_attribute (
    attr_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid          uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    source_code        text NOT NULL REFERENCES dining.dn_source(source_code),
    record_id          uuid REFERENCES dining.dn_source_record(record_id),
    entered_by         text,
    verified_by        text,
    verified_at        timestamptz,
    attr_code          text NOT NULL,
    value_state        text NOT NULL,
    value_min          numeric(12,0),
    value_max          numeric(12,0),
    value_detail       text,
    source_text        text,
    extract_method     text NOT NULL,
    extract_confidence real,
    valid_from         date NOT NULL,
    retired_at         timestamptz,
    CONSTRAINT dn_attribute_code_chk CHECK (attr_code IN (
        'card_payment', 'reservable', 'reservation_required', 'kids_allowed',
        'vegetarian_menu', 'halal', 'max_party_size', 'price_per_person',
        'parking', 'takeout', 'non_smoking')),
    CONSTRAINT dn_attribute_state_chk CHECK (value_state IN ('yes', 'no', 'limited', 'unknown')),
    CONSTRAINT dn_attribute_range_chk CHECK (value_min IS NULL OR value_max IS NULL
                                             OR value_min <= value_max),
    CONSTRAINT dn_attribute_method_chk
        CHECK (extract_method IN ('structured', 'regex', 'llm', 'manual', 'synthetic')),
    CONSTRAINT dn_attribute_conf_chk
        CHECK (extract_confidence IS NULL OR extract_confidence BETWEEN 0 AND 1),
    CONSTRAINT dn_attribute_input_chk
        CHECK (record_id IS NOT NULL OR (entered_by IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT dn_attribute_llm_chk
        CHECK (extract_method <> 'llm' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);

COMMENT ON TABLE dining.dn_attribute IS
    '매장 속성 주장 한 건. 같은 속성에 출처가 다른 주장이 둘 이상 있으면 모두 보존한다.';
COMMENT ON COLUMN dining.dn_attribute.value_state IS
    'unknown 은 자료에 언급이 없다는 뜻이다. 없음(no)과 구분한다.';

CREATE INDEX IF NOT EXISTS dn_attribute_lookup_idx
    ON dining.dn_attribute (place_uid, attr_code) WHERE retired_at IS NULL;


-- 판정에 쓸 수 있는 주장만
CREATE OR REPLACE VIEW dining.v_attribute_active AS
SELECT a.*
FROM dining.dn_attribute a
WHERE a.retired_at IS NULL
  AND (a.extract_method <> 'llm' OR a.verified_at IS NOT NULL);


-- 속성 하나의 상태를 돌려준다.
-- 주장이 없으면 unknown 이다. 없음으로 바꾸지 않는다.
CREATE OR REPLACE FUNCTION dining.attribute_state(
    p_place_uid uuid,
    p_attr_code text
)
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(
      (SELECT a.value_state
         FROM dining.v_attribute_active a
        WHERE a.place_uid = p_place_uid
          AND a.attr_code = p_attr_code
        -- 같은 속성에 주장이 둘 이상이면 확인된 쪽을 먼저 본다.
        ORDER BY (a.verified_at IS NOT NULL) DESC, a.valid_from DESC
        LIMIT 1),
      'unknown')
$$;


-- 여행 조건을 만족하는가
-- 세 값으로 답한다. 맞음 / 아님 / 모름.
-- 모름을 맞음으로 바꾸지 않으며, 그때는 확인을 권하는 자리로 넘긴다.
CREATE OR REPLACE FUNCTION dining.meets_condition(
    p_place_uid uuid,
    p_attr_code text
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT CASE dining.attribute_state(p_place_uid, p_attr_code)
             WHEN 'yes'     THEN true
             WHEN 'limited' THEN true   -- 조건부 가능. 상세는 value_detail 에 있다
             WHEN 'no'      THEN false
             ELSE NULL                  -- unknown
           END
$$;

COMMENT ON FUNCTION dining.meets_condition IS
    'NULL 은 모름이다. limited 는 가능으로 보되 화면에서 단서를 함께 보인다.';


-- 조건까지 포함한 한 줄 상태
-- 여행 조건 목록을 받아 속성별 결과를 함께 돌려준다.
CREATE OR REPLACE FUNCTION dining.condition_report(
    p_place_uid uuid,
    p_attr_codes text[] DEFAULT ARRAY['card_payment']
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_object_agg(code, jsonb_build_object(
             'state',  dining.attribute_state(p_place_uid, code),
             'meets',  dining.meets_condition(p_place_uid, code),
             'detail', (SELECT a.value_detail FROM dining.v_attribute_active a
                         WHERE a.place_uid = p_place_uid AND a.attr_code = code
                         ORDER BY a.valid_from DESC LIMIT 1)))
    FROM unnest(p_attr_codes) AS code
$$;

-- 명절과 공휴일 경고
-- 작성 2026-09-21.
--
-- 왜 필요한가. 관광공사 자료에는 명절 영업시간이 없다.
-- 표본 200곳 중 명절 규칙이 있는 곳은 22곳(11%)뿐이고, 그것도 쉬는지 여부만 있다.
-- 몇 시까지 하는지 적힌 곳은 한 곳도 없었다.
--
-- 그러므로 평소 규칙을 명절에 그대로 적용하는 것은 추정이다.
-- 추정값으로 경고는 하되 일정을 바꾸지 않는다는 원칙에 따라,
-- 판정은 그대로 두고 확인하라는 표시만 얹는다.
--
-- 판정을 모름으로 내리지 않는 이유. 명절에 모든 장소가 모름이 되면
-- 대안 식당까지 전부 모름이 되어 고를 것이 없어진다. 여행이 마비된다.

-- ──────────────────────────────────────────────────────────────
-- 공휴일 달력
--
-- 임시 표다. 이동 쪽 달력을 함께 쓰기로 정해지면(기능정의서 K-13)
-- 아래 v_holiday 뷰의 본문만 그쪽 표로 바꾸면 된다. 나머지는 손대지 않는다.
--
-- 음력 명절의 양력 날짜는 해마다 다르다. 짐작해서 넣으면 조용히 틀린 값이 되므로
-- 공식 달력 파일에서 읽는다. 2026-09-21 에 이동 쪽에서 받은 파일을 넣었다.
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dining.dn_holiday_stub (
    holiday_date date PRIMARY KEY,
    name         text NOT NULL,
    is_major     boolean NOT NULL DEFAULT false,
    note         text
);

COMMENT ON TABLE dining.dn_holiday_stub IS
    '공휴일 달력. is_major 는 설날과 추석처럼 앞뒤 날까지 영향을 주는 명절이며 대체공휴일도 포함한다.';

-- 값은 여기에 박지 않는다. 이동 쪽이 받아둔 특일정보 파일에서 읽는다.
--   data/holidays_2026_2027.json  (한국천문연구원 특일 정보, 관보 고시 기준, 확정)
--   python scripts/make_holiday_sql.py  로 holidays.sql 을 만들어 넣는다.
-- 그래야 해마다 파일만 갈면 되고 이 파일은 손대지 않는다.


-- 달력을 읽는 자리. 바꿔 끼울 지점은 여기 하나다.
CREATE OR REPLACE VIEW dining.v_holiday AS
SELECT holiday_date, name, is_major
FROM dining.dn_holiday_stub;

COMMENT ON VIEW dining.v_holiday IS
    '판정 코드는 이 뷰만 본다. 이동 달력으로 옮길 때 이 뷰의 본문만 바꾼다.';

-- 이동 쪽이 특일정보를 이미 받아두었다(2026-09-21 확인).
-- 표 구조를 확인하면 아래처럼 바꾸고 dn_holiday_stub 은 버린다.
-- 판정 함수와 알림 재료는 손대지 않는다.
--
--   CREATE OR REPLACE VIEW dining.v_holiday AS
--   SELECT h.<날짜칸>                     AS holiday_date,
--          h.<명칭칸>                     AS name,
--          h.<명칭칸> IN ('설날', '추석') AS is_major
--   FROM mobility.<표이름> h
--   WHERE h.<휴일여부칸> = true;
--
-- 확인할 것 셋.
--   1. 표 이름과 칸 이름.
--   2. 공휴일만 들어 있는가. 특일정보에는 기념일과 절기도 있어서 함께 받았다면
--      식목일 같은 평일이 섞인다. 응답의 공공기관 휴일 여부 칸으로 거른다.
--   3. 몇 년치가 들어 있고 해마다 누가 채우는가.
--      비어 있으면 오류가 나지 않고 그날이 평일로 판정된다. 조용히 틀리는 쪽이다.
--
-- is_major 는 그쪽 표에 없을 것이다. 특일정보 API 가 주지 않는다.
-- 명칭으로 우리가 판정하므로 칸을 추가해달라고 할 필요는 없다.


-- ──────────────────────────────────────────────────────────────
-- 명절과 공휴일 경고
--
-- 그날이 공휴일이면, 또는 명절 앞뒤 범위에 들면 경고 대상이다.
-- 다만 그 장소에 명절이나 공휴일 규칙이 이미 있으면 근거가 있으므로 경고하지 않는다.
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION dining.needs_holiday_check(
    p_place_uid uuid,
    p_starts_at timestamptz,
    p_window_days int DEFAULT 1
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    WITH visit AS (
        SELECT (p_starts_at AT TIME ZONE 'Asia/Seoul')::date AS d
    ),
    hit AS (
        SELECT h.name, h.is_major
        FROM dining.v_holiday h, visit v
        WHERE h.holiday_date = v.d
           OR (h.is_major
               AND h.holiday_date BETWEEN v.d - p_window_days AND v.d + p_window_days)
        ORDER BY h.is_major DESC
        LIMIT 1
    )
    -- 날의 종류와 규칙의 종류를 맞춘다.
    -- 설날 휴무를 안다고 해서 개천절 영업을 아는 것은 아니다.
    SELECT EXISTS (SELECT 1 FROM hit)
       AND NOT EXISTS (
            SELECT 1
            FROM dining.v_closure_rule_active c, visit v, hit
            WHERE c.place_uid = p_place_uid
              AND c.pattern_kind = CASE WHEN hit.is_major
                                        THEN 'named_holiday' ELSE 'public_holiday' END
              AND c.valid_from <= v.d
              AND (c.valid_to IS NULL OR c.valid_to >= v.d)
       )
$$;

COMMENT ON FUNCTION dining.needs_holiday_check IS
    '명절이나 공휴일인데 그 장소의 명절 규칙을 모를 때 참이다. 규칙이 있으면 근거가 있으므로 거짓이다.';


-- 알림을 만들 때 쓸 재료
-- 무슨 날인지, 어디로 확인하는지를 함께 준다.
-- 표시만 하고 확인 책임을 고객에게 넘기지 않으려면 확인 수단이 같이 가야 한다.
CREATE OR REPLACE FUNCTION dining.holiday_context(
    p_place_uid uuid,
    p_starts_at timestamptz,
    p_window_days int DEFAULT 1
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    WITH visit AS (
        SELECT (p_starts_at AT TIME ZONE 'Asia/Seoul')::date AS d
    ),
    hit AS (
        SELECT h.name, h.is_major, h.holiday_date
        FROM dining.v_holiday h, visit v
        WHERE h.holiday_date = v.d
           OR (h.is_major
               AND h.holiday_date BETWEEN v.d - p_window_days AND v.d + p_window_days)
        ORDER BY abs(h.holiday_date - v.d)
        LIMIT 1
    )
    SELECT CASE
             WHEN NOT dining.needs_holiday_check(p_place_uid, p_starts_at, p_window_days)
               THEN NULL
             ELSE jsonb_build_object(
                    'holiday_name', (SELECT name FROM hit),
                    'holiday_date', (SELECT holiday_date FROM hit),
                    'is_major',     (SELECT is_major FROM hit),
                    'same_day',     (SELECT holiday_date FROM hit) = (SELECT d FROM visit),
                    'phone',        (SELECT phone FROM dining.dn_place
                                      WHERE place_uid = p_place_uid))
           END
$$;

COMMENT ON FUNCTION dining.holiday_context IS
    '경고 대상이 아니면 NULL 이다. 전화번호는 공공데이터 출처의 대표 번호이며 표본에서 99% 가 채워졌다.';


-- ──────────────────────────────────────────────────────────────
-- 코어로 내보내는 한 줄에 명절 경고를 더한다.
-- 돌려주는 칸이 늘어나 그대로 바꿀 수 없으므로 먼저 지운다.
-- ──────────────────────────────────────────────────────────────

DROP FUNCTION IF EXISTS dining.core_place_state(text, uuid, timestamptz, timestamptz);

CREATE FUNCTION dining.core_place_state(
    p_tenant_id text,
    p_core_place_id uuid,
    p_starts_at timestamptz,
    p_ends_at   timestamptz DEFAULT NULL
)
RETURNS TABLE (
    open_at_slot        boolean,
    needs_check         boolean,
    needs_holiday_check boolean,
    holiday_context     jsonb,
    attributes          jsonb,
    hours_confirmed_at  timestamptz
)
LANGUAGE sql
STABLE
AS $$
    SELECT dining.open_at_slot(l.place_uid, p_starts_at, p_ends_at),
           dining.needs_last_order_check(l.place_uid, p_starts_at, p_ends_at),
           dining.needs_holiday_check(l.place_uid, p_starts_at),
           dining.holiday_context(l.place_uid, p_starts_at),
           dining.core_attributes(l.place_uid, (p_starts_at AT TIME ZONE 'Asia/Seoul')::date),
           (SELECT max(m.fetched_at)
              FROM dining.v_hours_rule_active r
              JOIN dining.dn_source_record sr ON sr.record_id = r.record_id
              JOIN dining.dn_load_meta m      ON m.load_id   = sr.load_id
             WHERE r.place_uid = l.place_uid)
    FROM dining.dn_core_place_link l
    WHERE l.tenant_id = p_tenant_id
      AND l.core_place_id = p_core_place_id
$$;

COMMENT ON FUNCTION dining.core_place_state IS
    'hours_confirmed_at 은 공급자 자료를 받은 시각이며 현장 확인 시각이 아니다. dining.py 가 이 값이 없으면 확인했다고 말하지 않는다.';

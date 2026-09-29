-- 지도 링크
-- 작성 2026-09-21.
--
-- 명절이나 공휴일처럼 영업시간이 다를 수 있을 때, 확인할 곳을 같이 준다.
-- 표시만 하고 확인 책임을 고객에게 넘기지 않으려면 수단이 함께 가야 한다.
--
-- 왜 저장하지 않는가.
--   여기서 만드는 것은 검색 주소이지 공급자가 준 데이터가 아니다.
--   상호명과 주소만 있으면 언제든 다시 만들 수 있으므로 표에 쌓을 이유가 없다.
--   저장하지 않으면 약관을 따질 일도 없다.
--
-- 사람이 확인한 정확한 가게 링크는 다르다.
--   그것은 dn_external_ref 에 status='valid' 로 저장하며(기능정의서 F-06, F-11),
--   있으면 검색 주소보다 그쪽을 먼저 쓴다. 그 표는 아직 만들지 않았다.
--
-- 주소 형식은 2026-09-21 에 사람이 열어보고 확인했다.
--   https://map.naver.com/p/search/{검색어}  검색 결과가 정상으로 떴다.
--   네이버가 형식을 바꾸면 map_links 안의 그 한 줄만 고치면 된다.

-- 퍼센트 인코딩
-- 한글은 UTF-8 바이트마다 퍼센트를 붙인다.
CREATE OR REPLACE FUNCTION dining.urlencode(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT coalesce(string_agg(
             CASE WHEN s.ch ~ '^[A-Za-z0-9_.~-]$' THEN s.ch
                  ELSE (SELECT string_agg('%' || upper(m[1]), '')
                          FROM regexp_matches(encode(convert_to(s.ch, 'UTF8'), 'hex'),
                                              '..', 'g') AS m)
             END, '' ORDER BY s.i), '')
    FROM regexp_split_to_table(coalesce(p_text, ''), '') WITH ORDINALITY AS s(ch, i)
$$;


-- 검색어
-- 상호명만으로는 동명 가게가 섞인다. 행정동까지 붙여 범위를 좁힌다.
CREATE OR REPLACE FUNCTION dining.search_query(p_place_uid uuid)
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT trim(concat_ws(' ',
             nullif((regexp_match(coalesce(p.road_address, ''),
                                  '^(?:서울특별시|서울)\s+(\S+구)'))[1], ''),
             -- 「[백년가게] 선천집」 의 대괄호 수식어는 검색을 방해한다
             trim(regexp_replace(p.name_ko, '\[[^\]]*\]', '', 'g'))))
    FROM dining.dn_place p
    WHERE p.place_uid = p_place_uid
$$;

COMMENT ON FUNCTION dining.search_query IS
    '「성동구 대돈집」 처럼 구 이름을 앞에 붙인다. 주소가 없으면 상호명만 쓴다.';


-- 지도 링크
-- 네이버와 구글 둘 다 준다. 구글은 API 키가 필요 없는 검색 주소를 쓴다.
CREATE OR REPLACE FUNCTION dining.map_links(p_place_uid uuid)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_strip_nulls(jsonb_build_object(
        'naver',  'https://map.naver.com/p/search/' || dining.urlencode(q.text),
        'google', 'https://www.google.com/maps/search/?api=1&query='
                  || dining.urlencode(q.text),
        'phone',  (SELECT phone FROM dining.dn_place WHERE place_uid = p_place_uid),
        'kind',   'search'
    ))
    FROM (SELECT dining.search_query(p_place_uid) AS text) q
    WHERE q.text IS NOT NULL AND q.text <> ''
$$;

COMMENT ON FUNCTION dining.map_links IS
    'kind 가 search 이면 검색 결과로 가는 주소다. 특정 가게를 가리키지 않으므로 화면에서도 「지도에서 찾아보기」 처럼 적는다.';


-- ──────────────────────────────────────────────────────────────
-- 명절 경고 재료에 링크를 더한다.
-- ──────────────────────────────────────────────────────────────

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
                    'same_day',     (SELECT holiday_date FROM hit) = (SELECT d FROM visit))
                  || coalesce(dining.map_links(p_place_uid), '{}'::jsonb)
           END
$$;

COMMENT ON FUNCTION dining.holiday_context IS
    '경고 대상이 아니면 NULL 이다. 무슨 날인지와 확인할 곳을 함께 준다.';

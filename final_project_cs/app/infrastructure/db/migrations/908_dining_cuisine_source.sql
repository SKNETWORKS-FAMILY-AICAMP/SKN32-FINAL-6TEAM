-- ST4F-597: select menu evidence consistently with classify_category/classify_style.
-- Non-menu sources must not hide menus. An explicitly empty latest menu stays unknown.
-- Existing migration bytes and tag vocabulary remain unchanged.
CREATE OR REPLACE FUNCTION dining.cuisine_tags(p_place_uid uuid)
RETURNS text[]
LANGUAGE sql
STABLE
AS $fn$
    WITH src AS (
        SELECT lower(concat_ws(' ',
                 sr.raw_json ->> 'firstmenu',
                 sr.raw_json ->> 'treatmenu')) AS t
        FROM dining.dn_source_record sr
        JOIN dining.dn_load_meta lm ON lm.load_id = sr.load_id
        WHERE sr.place_uid = p_place_uid
          AND (sr.raw_json ? 'firstmenu' OR sr.raw_json ? 'treatmenu')
        ORDER BY lm.fetched_at DESC, sr.record_id
        LIMIT 1
    ),
    hit AS (
        SELECT '고기'   AS tag FROM src WHERE t ~ '한우|갈비|삼겹|목살|곱창|대창|막창|등심|고기|스테이크|바비큐'
        UNION ALL SELECT '해산물' FROM src WHERE t ~ '회|조개|새우|낙지|문어|장어|굴|전복|해물|생선|物'
        UNION ALL SELECT '국물'   FROM src WHERE t ~ '탕|찌개|전골|국밥|해장|미역국|설렁|곰탕'
        UNION ALL SELECT '면'     FROM src WHERE t ~ '국수|면|우동|라멘|파스타|냉면|칼국수|짜장'
        UNION ALL SELECT '일식'   FROM src WHERE t ~ '텐동|카츠|돈까스|스시|초밥|사시미|규동|오마카세|덮밥'
        UNION ALL SELECT '중식'   FROM src WHERE t ~ '짬뽕|탕수육|마라|양장피|딤섬|만두'
        UNION ALL SELECT '양식'   FROM src WHERE t ~ '피자|리조또|스테이크|버거|샐러드|브런치|오믈렛'
        UNION ALL SELECT '카페'   FROM src WHERE t ~ '커피|아메리카노|라떼|케이크|디저트|베이글|빵|에이드'
        UNION ALL SELECT '술'     FROM src WHERE t ~ '맥주|와인|위스키|막걸리|소주|하이볼|사케'
    )
    SELECT array_agg(DISTINCT tag ORDER BY tag) FROM hit
$fn$;

COMMENT ON FUNCTION dining.cuisine_tags IS
    '메뉴 원문에서 뽑은 거친 태그. 비면 NULL 이며 분류가 없다는 뜻이지 다르다는 뜻이 아니다.';

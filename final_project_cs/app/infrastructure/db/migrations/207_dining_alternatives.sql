-- 대체 후보 세 개 (설계보완 2026-09-18 의 1번)
-- 작성 2026-09-22.
--
-- 후보 셋을 같은 기준으로 줄 세우지 않는다. 서로 다른 축에서 하나씩 뽑는다.
--
--   A  파급 최소   일정이 가장 덜 밀리는 곳
--   B  유사도      원래 가려던 곳과 비슷한 곳
--   C  근접        가장 가까운 곳
--
-- 왜 점수를 합치지 않는가.
--   가중치를 합치면 왜 그 집이 나왔는지 설명할 수 없다. 축을 나눠 두면
--   축 이름이 곧 이유가 된다. 사용자도 「덜 밀리는 곳」과 「가까운 곳」 중에
--   무엇을 원하는지 스스로 고른다.
--
-- 조건은 축이 아니다.
--   카드 결제 같은 여행 조건은 줄 세우기 전에 거르는 것이다.
--   다만 모르는 것은 거르지 않는다. 좁게 잡는 오류가 더 나쁘다 (DN-C5).
--
-- 파급은 혼자 계산할 수 없다.
--   다음 일정이 언제 어디인지를 알아야 한다. 그것은 코어 일정과 이동의 몫이다.
--   받지 못하면 A 자리를 비워 두고 왜 비었는지 적는다. 억지로 채우지 않는다.


-- ──────────────────────────────────────────────────────────────
-- 유사도 재료
-- ──────────────────────────────────────────────────────────────
--
-- 관광공사 분류(contenttypeid)는 200곳이 모두 같은 값이라 쓸모가 없다.
-- 대신 대표메뉴와 취급메뉴 원문에서 낱말을 본다. 거칠지만 근거를 보일 수 있다.
--   「한우모듬 / 한우곱창 / 한우대창」        → 고기
--   「스페셜텐동 / 에비텐동 / 양파카레」      → 일식, 면
-- 태그가 비면 유사도를 0 이 아니라 NULL 로 둔다. 다르다는 뜻이 아니라 모른다는 뜻이다.

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
        WHERE sr.place_uid = p_place_uid
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


-- 두 곳이 얼마나 비슷한가. 태그의 자카드 값이다.
-- 한쪽이라도 태그가 없으면 NULL 이다. 모르는 것을 0 으로 바꾸지 않는다.
CREATE OR REPLACE FUNCTION dining.cuisine_similarity(p_a uuid, p_b uuid)
RETURNS real
LANGUAGE sql
STABLE
AS $fn$
    WITH t AS (
        SELECT dining.cuisine_tags(p_a) AS a, dining.cuisine_tags(p_b) AS b
    )
    SELECT CASE
             WHEN t.a IS NULL OR t.b IS NULL THEN NULL
             ELSE (SELECT count(*) FROM (SELECT unnest(t.a) INTERSECT SELECT unnest(t.b)) x)::real
                / nullif((SELECT count(*) FROM (SELECT unnest(t.a) UNION SELECT unnest(t.b)) y), 0)
           END
    FROM t
$fn$;


-- ──────────────────────────────────────────────────────────────
-- 후보 모으기
-- ──────────────────────────────────────────────────────────────
--
-- 반경을 500m 에서 1km, 2km 로 넓히다 멈춘다 (설계보완 42줄).
-- 횟수를 제한한 것이 아니라 찾을 공간 자체가 유한하다.
--
-- 남기는 기준
--   닫힌 것으로 확인된 곳만 뺀다. 모르는 곳은 남기고 표시한다.
--   조건에 어긋나는 것으로 확인된 곳만 뺀다. 모르는 곳은 남긴다.

CREATE OR REPLACE FUNCTION dining.alternative_pool(
    p_place_uid uuid,
    p_starts_at timestamptz,
    p_ends_at   timestamptz DEFAULT NULL,
    p_conds     text[] DEFAULT '{}'
)
RETURNS TABLE (
    place_uid   uuid,
    name_ko     text,
    distance_m  double precision,
    open_state  boolean,
    cond_state  boolean,
    similarity  real,
    radius_used integer
)
LANGUAGE sql
STABLE
AS $fn$
    WITH origin AS (
        SELECT lat, lng FROM dining.dn_place WHERE place_uid = p_place_uid
    ),
    near AS (
        SELECT c.place_uid, c.name_ko,
               dining.distance_m(o.lat, o.lng, c.lat, c.lng) AS d
        FROM dining.dn_place c, origin o
        WHERE c.place_uid <> p_place_uid
          AND c.lat IS NOT NULL AND o.lat IS NOT NULL
          AND c.record_status <> 'closed'
          AND dining.distance_m(o.lat, o.lng, c.lat, c.lng) <= 2000
    ),
    judged AS (
        SELECT n.place_uid, n.name_ko, n.d,
               dining.open_at_slot(n.place_uid, p_starts_at, p_ends_at) AS open_state,
               -- 조건 하나라도 아님으로 확인되면 false, 하나라도 모르면 NULL, 전부 맞으면 true
               (SELECT CASE
                         WHEN bool_or(dining.meets_condition(n.place_uid, code) IS FALSE) THEN false
                         WHEN bool_or(dining.meets_condition(n.place_uid, code) IS NULL)  THEN NULL
                         ELSE true END
                  FROM unnest(p_conds) AS code) AS cond_state,
               dining.cuisine_similarity(p_place_uid, n.place_uid) AS sim
        FROM near n
    ),
    kept AS (
        SELECT j.*
        FROM judged j
        WHERE j.open_state IS NOT FALSE      -- 닫힌 것으로 확인된 곳만 뺀다
          AND j.cond_state IS NOT FALSE      -- 어긋나는 것으로 확인된 곳만 뺀다
    ),
    -- 넓히다 멈춘다. 500m 안에 셋이 있으면 1km 를 보지 않는다.
    -- 멀리 있는 집이 조금 더 비슷하다고 그쪽을 고르면 「가까운 대안」이 아니게 된다.
    ladder AS (
        SELECT r.m
        FROM (VALUES (500), (1000), (2000)) AS r(m)
        WHERE (SELECT count(*) FROM kept WHERE kept.d <= r.m) >= 3
        ORDER BY r.m
        LIMIT 1
    ),
    -- 2km 까지 가도 셋이 안 되면 있는 대로 준다. 없는 것을 지어내지 않는다.
    chosen AS (
        SELECT coalesce((SELECT m FROM ladder), 2000) AS m
    )
    SELECT k.place_uid, k.name_ko, k.d, k.open_state, k.cond_state, k.sim,
           c.m::integer
    FROM kept k, chosen c
    WHERE k.d <= c.m
    ORDER BY k.d
$fn$;

COMMENT ON FUNCTION dining.alternative_pool IS
    '거르기까지만 한다. 줄 세우기는 축마다 다르므로 여기서 하지 않는다.';


-- ──────────────────────────────────────────────────────────────
-- 세 축에서 하나씩
-- ──────────────────────────────────────────────────────────────
--
-- 같은 집이 두 축에서 1등이면 앞 축에 주고 뒤 축은 그다음 집을 준다.
-- 세 자리에 같은 이름이 겹치면 고를 것이 하나로 줄어든다.
-- 축 차례는 파급, 유사도, 근접이다. 파급이 사용자의 하루를 가장 크게 바꾼다.

CREATE OR REPLACE FUNCTION dining.suggest_alternatives(
    p_place_uid uuid,
    p_starts_at timestamptz,
    p_ends_at   timestamptz DEFAULT NULL,
    p_conds     text[] DEFAULT '{}',
    p_next_lat  double precision DEFAULT NULL,
    p_next_lng  double precision DEFAULT NULL
)
RETURNS TABLE (
    axis        text,
    axis_label  text,
    place_uid   uuid,
    name_ko     text,
    reason      jsonb
)
LANGUAGE plpgsql
STABLE
AS $fn$
DECLARE
    v_taken uuid[] := '{}';
    v_row   record;
BEGIN
    -- A 파급 최소
    -- 다음 일정까지의 이동이 얼마나 늘어나는가로 본다.
    -- 직선거리 추정이며 실제 경로가 아니다. 이동 에이전트가 붙으면 그 값으로 바꾼다.
    IF p_next_lat IS NOT NULL AND p_next_lng IS NOT NULL THEN
        SELECT p.place_uid, p.name_ko, p.distance_m, p.open_state, p.cond_state,
               dining.distance_m(c.lat, c.lng, p_next_lat, p_next_lng) AS to_next
          INTO v_row
          FROM dining.alternative_pool(p_place_uid, p_starts_at, p_ends_at, p_conds) p
          JOIN dining.dn_place c ON c.place_uid = p.place_uid
         ORDER BY p.distance_m + dining.distance_m(c.lat, c.lng, p_next_lat, p_next_lng)
         LIMIT 1;

        IF FOUND THEN
            v_taken := v_taken || v_row.place_uid;
            axis := 'impact'; axis_label := '일정이 가장 덜 밀리는 곳';
            place_uid := v_row.place_uid; name_ko := v_row.name_ko;
            reason := jsonb_build_object(
                '들르는 거리', round(v_row.distance_m)::int,
                '다음 일정까지', round(v_row.to_next)::int,
                '근거', '직선거리 추정. 실제 경로가 아니다',
                '영업', v_row.open_state, '조건', v_row.cond_state);
            RETURN NEXT;
        END IF;
    ELSE
        axis := 'impact'; axis_label := '일정이 가장 덜 밀리는 곳';
        place_uid := NULL; name_ko := NULL;
        reason := jsonb_build_object(
            '비어 있음', '다음 일정의 시각과 좌표를 받지 못했다',
            '필요한 것', '코어 일정 또는 이동 에이전트의 다음 항목');
        RETURN NEXT;
    END IF;

    -- B 유사도
    SELECT p.place_uid, p.name_ko, p.distance_m, p.similarity, p.open_state, p.cond_state
      INTO v_row
      FROM dining.alternative_pool(p_place_uid, p_starts_at, p_ends_at, p_conds) p
     WHERE NOT (p.place_uid = ANY (v_taken))
       AND p.similarity IS NOT NULL
     ORDER BY p.similarity DESC, p.distance_m
     LIMIT 1;

    IF FOUND THEN
        v_taken := v_taken || v_row.place_uid;
        axis := 'similar'; axis_label := '원래 가려던 곳과 비슷한 곳';
        place_uid := v_row.place_uid; name_ko := v_row.name_ko;
        reason := jsonb_build_object(
            '겹치는 종류', dining.cuisine_tags(v_row.place_uid),
            '원래 종류', dining.cuisine_tags(p_place_uid),
            '거리', round(v_row.distance_m)::int,
            '영업', v_row.open_state, '조건', v_row.cond_state);
        RETURN NEXT;
    ELSE
        axis := 'similar'; axis_label := '원래 가려던 곳과 비슷한 곳';
        place_uid := NULL; name_ko := NULL;
        reason := jsonb_build_object('비어 있음', '메뉴 원문이 없어 종류를 알 수 없다');
        RETURN NEXT;
    END IF;

    -- C 근접
    SELECT p.place_uid, p.name_ko, p.distance_m, p.open_state, p.cond_state, p.radius_used
      INTO v_row
      FROM dining.alternative_pool(p_place_uid, p_starts_at, p_ends_at, p_conds) p
     WHERE NOT (p.place_uid = ANY (v_taken))
     ORDER BY p.distance_m
     LIMIT 1;

    IF FOUND THEN
        axis := 'nearest'; axis_label := '가장 가까운 곳';
        place_uid := v_row.place_uid; name_ko := v_row.name_ko;
        reason := jsonb_build_object(
            '거리', round(v_row.distance_m)::int,
            '찾은 반경', v_row.radius_used,
            '영업', v_row.open_state, '조건', v_row.cond_state);
        RETURN NEXT;
    ELSE
        axis := 'nearest'; axis_label := '가장 가까운 곳';
        place_uid := NULL; name_ko := NULL;
        reason := jsonb_build_object('비어 있음', '2km 안에 남은 후보가 없다');
        RETURN NEXT;
    END IF;

    RETURN;
END;
$fn$;

COMMENT ON FUNCTION dining.suggest_alternatives IS
    '축마다 한 곳씩 돌려준다. 채우지 못한 축은 place_uid 가 NULL 이며 왜 비었는지 reason 에 적는다.';

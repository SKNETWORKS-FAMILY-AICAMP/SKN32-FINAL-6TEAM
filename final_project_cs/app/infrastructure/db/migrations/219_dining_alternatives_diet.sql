-- 식이 조건(비건·채식, 할랄)은 「맞다고 확인된 곳」만 대안으로 낸다.
--
-- 207 은 조건에 어긋나는 것으로 확인된 곳만 뺐다. 모르는 곳은 남았다.
-- 식이 조건은 틀리면 손님이 먹지 못한다. 모름을 맞음처럼 권하지 않는다(팀 결정 2026-09-28, A안).
-- 다른 조건(카드 · 주차 등)은 그대로 — 모르는 곳을 남긴다.
-- 확인된 곳이 없으면 대안은 비고, 부르는 쪽이 「근처에 확인된 … 식당이 없어요」라고 말한다.

CREATE OR REPLACE FUNCTION dining.diet_conditions()
RETURNS text[]
LANGUAGE sql
IMMUTABLE
AS $fn$ SELECT ARRAY['vegetarian_menu', 'halal'] $fn$;

COMMENT ON FUNCTION dining.diet_conditions() IS
    '모름을 허용하지 않는 조건. 대안은 맞다고 확인된 곳만.';

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
          AND j.cond_state IS NOT FALSE      -- 어긋나는 것으로 확인된 곳은 뺀다
          -- 식이 조건은 모든 식이 조건이 맞다고 확인된 곳만
          AND NOT EXISTS (SELECT 1 FROM unnest(p_conds) AS code
                           WHERE code = ANY (dining.diet_conditions())
                             AND dining.meets_condition(j.place_uid, code) IS NOT TRUE)
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

COMMENT ON FUNCTION dining.alternative_pool(uuid, timestamptz, timestamptz, text[]) IS
    '거르기까지만 한다. 식이 조건은 맞다고 확인된 곳만 남긴다(219).';

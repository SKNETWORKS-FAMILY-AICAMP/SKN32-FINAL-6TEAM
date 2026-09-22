-- 요식 원장과 코어 장소를 잇는 매칭기
-- 작성 2026-09-21.
--
-- 코어 places 한 행과 요식 dn_place 한 행을 연결해 dn_core_place_link 를 채운다.
-- 기준은 기능정의서와 수집 보고서를 그대로 쓴다.
--   좌표 80m 이내, 상호명 유사도 0.75 이상.
--
-- 읽기만 하고 코어 표에는 아무것도 쓰지 않는다. 채우는 것은 요식 표뿐이다.
--
-- 유사도는 편집거리로 잰다.
-- pg_trgm 의 similarity() 는 이 환경에서 한글 이름에 0 을 돌려준다. 실측으로 확인했다.
--   영문 이름은 1.000 이 나오는데 「가조쿠」 처럼 똑같은 한글 이름이 0.000 이었다.
-- 우리 원장은 대부분 한글이라 그 방식으로는 정확히 같은 이름만 잡힌다.
-- 그래서 fuzzystrmatch 의 levenshtein 으로 바꾼다. 글자 단위라 한글에서도 동작한다.
-- 수집 보고서의 0.75 는 파이썬 문자열 비교로 잰 값이라 계산 방식이 여전히 다르다.
-- 첫 실행 뒤에 후보 표를 보고 기준을 다시 잡는다.

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;


-- 상호명 정규화
-- 지점 표기와 대괄호 수식어, 공백과 문장부호를 떼어 비교용 이름을 만든다.
CREATE OR REPLACE FUNCTION dining.norm_name(p_name text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT regexp_replace(
             regexp_replace(
               regexp_replace(lower(coalesce(p_name, '')), '\[[^\]]*\]', '', 'g'),
               '(본점|직영점|지점|점)\s*$', ''),
             '[[:space:][:punct:]]', '', 'g')
$$;

COMMENT ON FUNCTION dining.norm_name IS
    '비교용 이름. 「[백년가게] 선천집」 과 「선천집」 이 같은 값이 되게 한다.';


-- 이름 유사도. 1 에 가까울수록 비슷하다.
-- 편집거리를 긴 쪽 글자 수로 나눠 0 에서 1 사이로 만든다.
CREATE OR REPLACE FUNCTION dining.name_sim(p_a text, p_b text)
RETURNS double precision
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
             WHEN coalesce(p_a, '') = '' OR coalesce(p_b, '') = '' THEN 0
             WHEN p_a = p_b THEN 1
             ELSE greatest(0, 1 - levenshtein(p_a, p_b)::double precision
                                  / greatest(length(p_a), length(p_b)))
           END
$$;


-- 거리 계산은 021 로 옮겼다.
-- 022 는 코어 places 표가 있어야 올라가는데, 대체 후보(027)도 이 함수를 쓴다.
-- 여기 두면 코어 없이 세울 때 027 이 통째로 안 올라간다.


-- 후보 목록
-- 코어 장소마다 가까운 요식 원장 장소를 거리와 유사도와 함께 늘어놓는다.
-- 자동 연결에 쓰지 않고 사람이 보는 용도로도 쓴다.
CREATE OR REPLACE VIEW dining.v_link_candidate AS
SELECT c.tenant_id,
       c.place_id                              AS core_place_id,
       c.name                                  AS core_name,
       d.place_uid,
       d.name_ko                               AS dining_name,
       round(dining.distance_m(c.latitude, c.longitude, d.lat, d.lng)::numeric, 1) AS distance_m,
       round(dining.name_sim(dining.norm_name(c.name), dining.norm_name(d.name_ko))::numeric, 3) AS name_sim,
       (dining.norm_name(c.name) = dining.norm_name(d.name_ko))                    AS name_exact
FROM places c
JOIN dining.dn_place d
  ON c.latitude IS NOT NULL AND c.longitude IS NOT NULL
 AND d.lat IS NOT NULL AND d.lng IS NOT NULL
 -- 먼저 사각 범위로 좁힌다. 위도 1도는 약 111km 이고 서울에서 경도 1도는 약 88km 다.
 AND d.lat BETWEEN c.latitude  - 0.0010 AND c.latitude  + 0.0010
 AND d.lng BETWEEN c.longitude - 0.0013 AND c.longitude + 0.0013
WHERE c.kind = 'dining'
  AND dining.distance_m(c.latitude, c.longitude, d.lat, d.lng) <= 80;

COMMENT ON VIEW dining.v_link_candidate IS
    '코어 장소별 연결 후보. 거리 80m 안에 든 것만 나온다.';


-- 연결 실행
-- 기준을 통과하고 짝이 하나로 정해지는 것만 잇는다.
-- 후보가 둘 이상이면 잇지 않는다. 잘못 이으면 다른 식당의 영업시간으로 판정하게 된다.
CREATE OR REPLACE FUNCTION dining.link_core_places(
    p_tenant_id  text,
    p_min_sim    real    DEFAULT 0.75,
    p_linked_by  text    DEFAULT 'matcher',
    p_dry_run    boolean DEFAULT true
)
RETURNS TABLE (
    result        text,
    core_place_id uuid,
    core_name     text,
    dining_name   text,
    distance_m    numeric,
    name_sim      numeric
)
LANGUAGE plpgsql
AS $$
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS tmp_link_pick (
        core_place_id uuid,
        core_name     text,
        place_uid     uuid,
        dining_name   text,
        distance_m    numeric,
        name_sim      numeric,
        n_candidate   int
    ) ON COMMIT DROP;
    DELETE FROM tmp_link_pick;

    INSERT INTO tmp_link_pick
    SELECT DISTINCT ON (v.core_place_id)
           v.core_place_id, v.core_name, v.place_uid, v.dining_name,
           v.distance_m, v.name_sim,
           count(*) OVER (PARTITION BY v.core_place_id) AS n_candidate
    FROM dining.v_link_candidate v
    WHERE v.tenant_id = p_tenant_id
      AND (v.name_exact OR v.name_sim >= p_min_sim)
    ORDER BY v.core_place_id, v.name_exact DESC, v.name_sim DESC, v.distance_m;

    IF NOT p_dry_run THEN
        INSERT INTO dining.dn_core_place_link
            (tenant_id, core_place_id, place_uid, linked_by)
        SELECT p_tenant_id, t.core_place_id, t.place_uid, p_linked_by
        FROM tmp_link_pick t
        WHERE t.n_candidate = 1
        ON CONFLICT ON CONSTRAINT dn_core_place_link_pkey DO NOTHING;
    END IF;

    RETURN QUERY
    SELECT CASE WHEN t.n_candidate = 1 THEN
                    CASE WHEN p_dry_run THEN 'would_link' ELSE 'linked' END
                ELSE 'ambiguous' END,
           t.core_place_id, t.core_name, t.dining_name, t.distance_m, t.name_sim
    FROM tmp_link_pick t
    ORDER BY 1, t.name_sim DESC;
END;
$$;

COMMENT ON FUNCTION dining.link_core_places IS
    '기본은 시험 실행이다. 실제로 쓰려면 p_dry_run 을 false 로 준다. 후보가 여럿인 장소는 잇지 않고 ambiguous 로 남긴다.';


-- 연결되지 않은 코어 장소
-- 왜 안 이어졌는지 나눠서 보여준다. 커버리지를 재는 자리이기도 하다.
CREATE OR REPLACE VIEW dining.v_link_gap AS
SELECT c.tenant_id,
       c.place_id AS core_place_id,
       c.name     AS core_name,
       CASE
         WHEN c.latitude IS NULL OR c.longitude IS NULL THEN '코어 좌표 없음'
         WHEN NOT EXISTS (SELECT 1 FROM dining.v_link_candidate v
                          WHERE v.core_place_id = c.place_id)      THEN '80m 안에 원장 장소 없음'
         WHEN NOT EXISTS (SELECT 1 FROM dining.v_link_candidate v
                          WHERE v.core_place_id = c.place_id
                            AND (v.name_exact OR v.name_sim >= 0.75)) THEN '가깝지만 이름이 다름'
         ELSE '연결 대상'
       END AS reason
FROM places c
WHERE c.kind = 'dining'
  AND NOT EXISTS (SELECT 1 FROM dining.dn_core_place_link l
                  WHERE l.tenant_id = c.tenant_id AND l.core_place_id = c.place_id);

COMMENT ON VIEW dining.v_link_gap IS
    '연결되지 않은 코어 식당과 그 사유. 사유별 건수가 곧 커버리지 보고서의 재료다.';

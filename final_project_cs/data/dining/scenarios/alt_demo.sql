-- 대체 후보 세 축 시연. 합성 일정 위에서 돌린다.
--
-- 식당과 좌표와 영업시간은 진짜다. 합성한 것은 일정뿐이다.
--   「일요일 12시에 대돈집에 가려 했는데 그날 휴무다.
--    다음 일정은 14시 서울숲이다.」
-- 서울숲 좌표 37.5444, 127.0374 는 실제 좌표이며 방문 계획만 지어낸 것이다.
--
-- 돌리는 법
--   psql -p 5433 -d dining_dev -f data/dining/scenarios/alt_demo.sql

\pset border 2
\set QUIET on
SELECT place_uid AS p FROM dining.dn_place WHERE name_ko = '대돈집' LIMIT 1
\gset
\set QUIET off

\echo '### 0. 원래 가려던 곳'
SELECT p.name_ko AS 상호,
       dining.cuisine_tags(p.place_uid) AS 종류,
       dining.open_at_slot(p.place_uid, timestamptz '2026-09-27 12:00+09',
                                        timestamptz '2026-09-27 13:00+09') AS 일요일_정오,
       dining.is_closed_on(p.place_uid, DATE '2026-09-27') AS 휴무인가
FROM dining.dn_place p WHERE p.place_uid = :'p';

\echo ''
\echo '### 1. 후보 몇 곳이 남았나 (반경별)'
SELECT radius_used AS 반경,
       count(*) AS 후보,
       count(*) FILTER (WHERE open_state IS NULL) AS 영업_모름
FROM dining.alternative_pool(:'p', timestamptz '2026-09-27 12:00+09',
                                   timestamptz '2026-09-27 13:00+09')
GROUP BY 1 ORDER BY 1;

\echo ''
\echo '### 2. 세 축에서 하나씩 — 다음 일정 있음 (14시 서울숲)'
SELECT axis_label AS 축, coalesce(name_ko, '(비어 있음)') AS 추천,
       jsonb_pretty(reason) AS 근거
FROM dining.suggest_alternatives(:'p',
       timestamptz '2026-09-27 12:00+09', timestamptz '2026-09-27 13:00+09',
       '{}', 37.5444, 127.0374);

\echo ''
\echo '### 3. 다음 일정을 모를 때 — A 자리가 비어야 한다'
SELECT axis_label AS 축, coalesce(name_ko, '(비어 있음)') AS 추천,
       reason ->> '비어 있음' AS 왜_비었나
FROM dining.suggest_alternatives(:'p',
       timestamptz '2026-09-27 12:00+09', timestamptz '2026-09-27 13:00+09');

\echo ''
\echo '### 4. 카드 결제 조건을 걸면'
SELECT axis_label AS 축, coalesce(name_ko, '(비어 있음)') AS 추천,
       CASE WHEN reason -> '조건' = 'true'::jsonb THEN '맞음'
            WHEN reason -> '조건' = 'false'::jsonb THEN '아님'
            ELSE '모름. 확인 권고' END AS 조건상태
FROM dining.suggest_alternatives(:'p',
       timestamptz '2026-09-27 12:00+09', timestamptz '2026-09-27 13:00+09',
       ARRAY['card_payment'], 37.5444, 127.0374);

\echo ''
\echo '### 5. 조건이 후보를 얼마나 줄이나'
SELECT '조건 없음' AS 경우, count(*) AS 후보
FROM dining.alternative_pool(:'p', timestamptz '2026-09-27 12:00+09',
                                   timestamptz '2026-09-27 13:00+09')
UNION ALL
SELECT '카드 결제 필요', count(*)
FROM dining.alternative_pool(:'p', timestamptz '2026-09-27 12:00+09',
                                   timestamptz '2026-09-27 13:00+09',
                                   ARRAY['card_payment']);

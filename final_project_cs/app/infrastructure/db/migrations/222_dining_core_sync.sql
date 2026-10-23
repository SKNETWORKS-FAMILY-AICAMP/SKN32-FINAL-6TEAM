-- 222  요식 식당을 코어 장소로 — 같은 이름 허용 · 적재 때마다 동기화 (2026-09-28 cs)
--
-- 계획: wiki/records/plans/2026-09-28_2108_요식데이터_코어통합_실행계획.md 「고친 단계」 4·5 (코덱스 gpt-6-luna 교차검증 반영)
--
-- 1  같은 이름의 식당(체인 지점 등)을 허용한다.
--    코어는 한 테넌트 안에서 (이름, 종류) 공용 행이 하나뿐이라, 요식의 같은 이름 8개(19곳) 중 10곳이 못 들어왔다.
--    요식에서 온 행(source_name='dining_ledger')은 이름 대신 **요식 번호**(source_content_id)로 하나를 지킨다.
--    ★이 인덱스를 충돌 대상으로 쓰는 문장 둘(trip_api._insert · 이 파일의 promote_to_core)도 같이 바꿨다.
-- 2  dining.sync_core_places — 올린 식당의 이름·좌표·요일별 영업시간·브레이크·식사 조건·폐업을 요식에서 **다시 쓴다.**
--    요식 적재(scripts/dining/rebuild.py) 때마다 부른다. 매 조회마다 계산하지 않는다(1,200곳×7일 — 코덱스 지적).
--    명절·자정 넘김 같은 정밀 판정은 계속 원장 판정(dining.core_place_state)이 먼저다.
-- 3  promote_to_core 를 새 인덱스에 맞춘다. 식당은 **운영 테넌트 하나에만** 올린다(부르는 쪽 rebuild.py).
--
-- 다시 돌려도 깨지지 않는다.

-- 옛 조건(029: WHERE trip_scope IS NULL)일 때만 바꾼다 — 마이그레이션은 매번 전부 다시 돈다
DO $do$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'places'
                AND indexname = 'places_shared_name_kind_uq'
                AND indexdef NOT LIKE '%source_name IS DISTINCT FROM %dining_ledger%') THEN
        DROP INDEX public.places_shared_name_kind_uq;
    END IF;
END
$do$;
CREATE UNIQUE INDEX IF NOT EXISTS places_shared_name_kind_uq
    ON places (tenant_id, name, kind)
    WHERE trip_scope IS NULL AND source_name IS DISTINCT FROM 'dining_ledger';

CREATE UNIQUE INDEX IF NOT EXISTS places_dining_ledger_uq
    ON places (tenant_id, source_content_id)
    WHERE trip_scope IS NULL AND source_name = 'dining_ledger';

COMMENT ON INDEX places_dining_ledger_uq IS
    '요식에서 온 식당은 요식 번호로 하나다. 같은 이름의 다른 지점을 허용한다(222).';


CREATE OR REPLACE FUNCTION dining.core_dietary(p_place_uid uuid)
RETURNS TABLE(met text[], absent text[])
LANGUAGE sql
STABLE
AS $fn$
    -- 코어 이름 ↔ 요식 속성 코드. dining/ledger.py DIETARY 와 같다. 모르는 조건은 어느 쪽에도 넣지 않는다
    WITH m(core_name, code) AS (VALUES ('halal', 'halal'), ('vegetarian', 'vegetarian_menu'), ('kids', 'kids_allowed')),
         j AS (SELECT core_name, dining.meets_condition(p_place_uid, code) AS ok FROM m)
    SELECT coalesce(array_agg(core_name) FILTER (WHERE ok IS TRUE), '{}'),
           coalesce(array_agg(core_name) FILTER (WHERE ok IS FALSE), '{}')
      FROM j
$fn$;


CREATE OR REPLACE FUNCTION dining.sync_core_places(p_tenant_id text)
RETURNS TABLE(result text, n bigint)
LANGUAGE plpgsql
AS $fn$
DECLARE
    v_synced int := 0;
    v_closed int := 0;
BEGIN
    WITH src AS (
        SELECT c.place_id, d.place_uid, d.name_ko, d.lat, d.lng, d.record_status,
               dining.week_attributes(d.place_uid) AS week, dt.met, dt.absent
          FROM public.places c
          JOIN dining.dn_place d ON d.place_uid::text = c.source_content_id
          CROSS JOIN LATERAL dining.core_dietary(d.place_uid) dt
         WHERE c.tenant_id = p_tenant_id AND c.trip_scope IS NULL AND c.source_name = 'dining_ledger'
    ), done AS (
        UPDATE public.places c
           SET name = s.name_ko,
               latitude = coalesce(s.lat, c.latitude),
               longitude = coalesce(s.lng, c.longitude),
               dietary = s.met,
               dietary_absent = s.absent,
               source_resolved_at = now(),
               attributes = (c.attributes - 'hours' - 'hours_week' - 'break' - 'permanently_closed')
                   || CASE WHEN s.record_status = 'closed'
                           -- 폐업이면 모든 요일을 쉬는 날로 — 일정 후보·대체 후보에서 빠진다
                           THEN jsonb_build_object('permanently_closed', true, 'hours_week',
                                    jsonb_build_object('mon','closed','tue','closed','wed','closed','thu','closed',
                                                       'fri','closed','sat','closed','sun','closed'))
                           ELSE s.week END
                   || jsonb_build_object('source', 'dining_ledger', 'dining_place_uid', s.place_uid)
          FROM src s
         WHERE c.place_id = s.place_id
        RETURNING s.record_status
    )
    SELECT count(*), count(*) FILTER (WHERE record_status = 'closed') INTO v_synced, v_closed FROM done;
    RETURN QUERY VALUES ('synced', v_synced::bigint), ('closed', v_closed::bigint);
END;
$fn$;

COMMENT ON FUNCTION dining.sync_core_places(text) IS
    '요식에서 올린 코어 식당 행을 요식 원본으로 다시 쓴다. 요식 적재 때마다 부른다(rebuild.py).';


-- 221 의 promote_to_core 를 새 인덱스에 맞춘다(같은 이름 허용 — name_taken 이 없어진다)
CREATE OR REPLACE FUNCTION dining.promote_to_core(
    p_tenant_id text,
    p_linked_by text DEFAULT 'promote'
)
RETURNS TABLE(result text, n bigint)
LANGUAGE plpgsql
AS $fn$
DECLARE
    r        record;
    v_core   uuid;
    v_linked int := 0;
    v_reused int := 0;
    v_made   int := 0;
BEGIN
    FOR r IN
        SELECT p.place_uid, p.name_ko, p.lat, p.lng
          FROM dining.dn_place p
         WHERE p.record_status <> 'closed' AND NOT p.is_synthetic   -- unknown 은 폐업 정보 없음이지 폐업이 아니다
           AND p.lat IS NOT NULL AND p.lng IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM dining.dn_core_place_link k
                            JOIN public.places c ON c.place_id = k.core_place_id
                           WHERE k.tenant_id = p_tenant_id AND k.place_uid = p.place_uid
                             AND c.trip_scope IS NULL)
         ORDER BY p.place_uid
    LOOP
        v_core := NULL;
        -- 이름이 같은 공용 행(요식 밖에서 온 것)이 150m 안에 있고 아직 짝이 없으면 그 행을 쓴다
        SELECT c.place_id INTO v_core
          FROM public.places c
         WHERE c.tenant_id = p_tenant_id AND c.trip_scope IS NULL AND c.kind = 'dining'
           AND c.name = r.name_ko AND c.source_name IS DISTINCT FROM 'dining_ledger'
           AND (c.latitude IS NULL OR
                abs(c.latitude - r.lat) * 111000 < 150 AND abs(c.longitude - r.lng) * 88000 < 150)
           AND NOT EXISTS (SELECT 1 FROM dining.dn_core_place_link k
                            WHERE k.tenant_id = p_tenant_id AND k.core_place_id = c.place_id)
         LIMIT 1;
        IF v_core IS NOT NULL THEN
            v_reused := v_reused + 1;
        ELSE
            INSERT INTO public.places (tenant_id, name, kind, latitude, longitude, weather_sensitive,
                                       attributes, source_name, source_content_id, source_resolved_at)
            VALUES (p_tenant_id, r.name_ko, 'dining', r.lat, r.lng, false,
                    jsonb_build_object('source', 'dining_ledger', 'dining_place_uid', r.place_uid),
                    'dining_ledger', r.place_uid::text, now())
            ON CONFLICT (tenant_id, source_content_id)
                WHERE trip_scope IS NULL AND source_name = 'dining_ledger' DO NOTHING
            RETURNING place_id INTO v_core;
            IF v_core IS NULL THEN
                SELECT place_id INTO v_core FROM public.places
                 WHERE tenant_id = p_tenant_id AND trip_scope IS NULL
                   AND source_name = 'dining_ledger' AND source_content_id = r.place_uid::text;
            ELSE
                v_made := v_made + 1;
            END IF;
        END IF;
        INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by)
        VALUES (p_tenant_id, v_core, r.place_uid, p_linked_by)
        ON CONFLICT (tenant_id, core_place_id) DO NOTHING;
        v_linked := v_linked + 1;
    END LOOP;
    RETURN QUERY VALUES ('linked', v_linked::bigint), ('made', v_made::bigint), ('reused', v_reused::bigint);
END;
$fn$;

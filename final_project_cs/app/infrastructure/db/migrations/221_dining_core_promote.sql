-- 221  요식 원장의 식당을 코어 장소로 올린다 (2026-09-28 cs)
--
-- 왜.
--   대체 식당은 요식 원장이 추천하고 일정 계산이 고른다. 그런데 일정 항목은 코어 `places` 의 행만 가리킬 수 있어,
--   원장이 추천한 식당이 `places` 에 없으면 버려졌다 — 짝이 있는 19곳을 재 보니 쓸 수 있는 추천이 0/19 였다.
--   데이터가 없어서가 아니라 **원장 1,225곳이 코어에 올라와 있지 않아서**였다.
--
-- 무엇을.
--   1  dining.week_attributes(place_uid) — 코어가 읽는 요일별 영업시간(`hours_week`)·브레이크를 만든다
--   2  dining.promote_to_core(tenant) — 짝 없는 원장 식당마다 코어 공용 장소 행을 만들고(이름이 같은 공용 행이
--      150m 안에 이미 있으면 그 행을 쓴다) 짝 표(dn_core_place_link)에 잇는다
--
-- 공용 행으로 둔다(trip_scope NULL). 관광공사 값의 저장은 허용으로 재판단했다(2026-09-28 사용자 결정 —
--   설계 문서 §4-6 「재판단」). 사진·소개글은 싣지 않는다 — 이름·좌표·영업시간 같은 사실만.
-- 영업 판정의 정본은 계속 원장이다(`dining.core_place_state`). 여기 싣는 요일별 시간은 원장에 못 물을 때의 대체다.
--
-- 다시 돌려도 깨지지 않는다 — 이미 이어진 식당은 건너뛴다.

CREATE OR REPLACE FUNCTION dining.week_attributes(p_place_uid uuid)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $fn$
DECLARE
    v_monday date := date_trunc('week', current_date)::date + 7;   -- 다음 주 월요일(이번 주 명절 영향을 줄인다)
    v_days   text[] := ARRAY['mon','tue','wed','thu','fri','sat','sun'];
    v_week   jsonb := '{}'::jsonb;
    v_break  jsonb;
    v_attr   jsonb;
    i        int;
BEGIN
    FOR i IN 0..6 LOOP
        v_attr := dining.core_attributes(p_place_uid, v_monday + i);
        IF v_attr ? 'closed' THEN
            v_week := v_week || jsonb_build_object(v_days[i + 1], 'closed');
        ELSIF v_attr ? 'hours' THEN
            v_week := v_week || jsonb_build_object(v_days[i + 1],
                jsonb_build_object('open', v_attr->'hours'->>0, 'close', v_attr->'hours'->>1));
            IF v_break IS NULL AND v_attr ? 'break' THEN
                v_break := v_attr->'break';
            END IF;
        END IF;
        -- 모르는 요일은 비워 둔다. 코어는 빈 요일을 「모름」으로 읽고 「연다」로 읽지 않는다.
    END LOOP;
    IF v_week = '{}'::jsonb THEN
        RETURN '{}'::jsonb;
    END IF;
    RETURN jsonb_build_object('hours_week', v_week)
        || CASE WHEN v_break IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('break', v_break) END;
END;
$fn$;

COMMENT ON FUNCTION dining.week_attributes(uuid) IS
    '코어 `places.attributes` 형식의 요일별 영업시간. 원장에 못 물을 때의 대체이고 정본은 원장 판정이다.';


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
    v_taken  int := 0;
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
        -- 이름이 같은 공용 행이 가까이 있으면 그 행을 쓴다(두 행을 만들지 않는다)
        SELECT c.place_id INTO v_core
          FROM public.places c
         WHERE c.tenant_id = p_tenant_id AND c.trip_scope IS NULL AND c.kind = 'dining'
           AND c.name = r.name_ko
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
                    dining.week_attributes(r.place_uid)
                        || jsonb_build_object('source', 'dining_ledger', 'dining_place_uid', r.place_uid),
                    'dining_ledger', r.place_uid::text, now())
            ON CONFLICT (tenant_id, name, kind) WHERE trip_scope IS NULL DO NOTHING
            RETURNING place_id INTO v_core;
            IF v_core IS NULL THEN
                -- 같은 이름의 공용 행이 멀리 있다(체인 지점 등). 덮지 않는다 — 세어서 보고한다
                v_taken := v_taken + 1;
                CONTINUE;
            END IF;
            v_made := v_made + 1;
        END IF;
        INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by)
        VALUES (p_tenant_id, v_core, r.place_uid, p_linked_by)
        ON CONFLICT (tenant_id, core_place_id) DO NOTHING;
        v_linked := v_linked + 1;
        v_core := NULL;
    END LOOP;
    RETURN QUERY VALUES ('linked', v_linked::bigint), ('made', v_made::bigint),
                        ('reused', v_reused::bigint), ('name_taken', v_taken::bigint);
END;
$fn$;

COMMENT ON FUNCTION dining.promote_to_core(text, text) IS
    '짝 없는 원장 식당을 코어 공용 장소로 올리고 잇는다. 같은 이름이 멀리 있으면 만들지 않고 name_taken 으로 센다.';


-- 새 여행을 등록할 때 그 여행의 식당만 원장과 잇는다. (2026-09-28 cs)
-- 전에는 짝짓기를 손으로 한 번 돌린 뒤로 새로 생긴 여행 전용 식당이 계속 빠졌다 — 그 식당은 원장 판정(영업·라스트오더)도
-- 대체 추천도 못 받았다. 규칙은 dining.link_core_places 와 같다(이름 일치 또는 유사도 ≥ 기준, 후보가 하나일 때만 잇는다).
CREATE OR REPLACE FUNCTION dining.link_trip_places(
    p_tenant_id text,
    p_trip_id   uuid,
    p_min_sim   real DEFAULT 0.75,
    p_linked_by text DEFAULT 'trip_create'
)
RETURNS TABLE(result text, n bigint)
LANGUAGE sql
AS $fn$
    WITH pick AS (
        SELECT DISTINCT ON (v.core_place_id)
               v.core_place_id, v.place_uid,
               count(*) OVER (PARTITION BY v.core_place_id) AS n_candidate
          FROM dining.v_link_candidate v
          JOIN public.places c ON c.place_id = v.core_place_id
         WHERE v.tenant_id = p_tenant_id AND c.tenant_id = p_tenant_id AND c.trip_scope = p_trip_id
           AND (v.name_exact OR v.name_sim >= p_min_sim)
         ORDER BY v.core_place_id, v.name_exact DESC, v.name_sim DESC, v.distance_m
    ), done AS (
        INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by)
        SELECT p_tenant_id, core_place_id, place_uid, p_linked_by FROM pick WHERE n_candidate = 1
        ON CONFLICT ON CONSTRAINT dn_core_place_link_pkey DO NOTHING
        RETURNING 1
    )
    SELECT 'linked', (SELECT count(*) FROM done)
    UNION ALL SELECT 'ambiguous', (SELECT count(*) FROM pick WHERE n_candidate > 1)
$fn$;

COMMENT ON FUNCTION dining.link_trip_places(text, uuid, real, text) IS
    '여행 하나의 전용 장소를 원장과 잇는다. 여행 등록 트랜잭션 안에서 부른다.';

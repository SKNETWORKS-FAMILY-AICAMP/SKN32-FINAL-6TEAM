-- 233  등록 뒤 원장 연결 — 같은 이름 가게를 150m 까지, 지점 표시를 떼고도 찾는다 (2026-10-14 cs)
--
-- 왜.
--   원장 ↔ 장소 연결 정답셋(eval/reports/2026-10-14_dining_link.md)에서 등록 뒤 길(224 link_core_place)은
--   오연결 0 이지만 놓침이 dev 9/39 · holdout 2/14 였다. 놓친 것은
--     · 같은 가게인데 좌표가 80m 넘게 어긋남(관광공사 · 카카오 좌표 차이) 8건
--     · 「리알토 강남점」 · 「만두향 중랑점」 — norm_name 은 끝의 「점」만 떼서 「리알토강남」이 남는다 2건
--   놓치면 판정이 「모름」으로 남는다(영업 · 라스트오더 판정을 못 받는다).
--
-- 무엇을.
--   224 의 두 단계(관광공사 번호 → 80m · 이름 유사도)는 그대로 둔다. 둘 다 후보를 **하나도** 못 찾았을 때만
--   셋째 단계 — 지점 표시(「○○ 강남점」 · 「○○ 본점」)를 뗀 이름이 같은 원장 가게가 **150m 안에 하나뿐**이면 잇는다.
--   150m 는 원장 → 코어 승격(221 promote_to_core)이 같은 이름 공용 행을 다시 쓰는 거리이자 등록 전 확인 화면
--   (ledger.SAME_NAME_RADIUS_M)의 거리다. 정답셋으로 고른 값이 아니다.
--   후보가 둘 이상이면 잇지 않는다(다른 식당의 영업시간으로 판정하게 된다). 2단계가 여럿을 찾았을 때도 그대로 NULL 이다.
--
-- 코어 표를 읽기만 한다. 쓰는 곳은 dining.dn_core_place_link 뿐이다(202 · 224 와 같은 경계).

-- 지점 표시를 뗀 비교용 이름 — 「리알토 강남점」 → 「리알토」 · 「[백년가게] 하동관 본점」 → 「하동관」.
-- 띄어 쓴 마지막 낱말이 「…점」일 때만 뗀다(「본점」 · 「강남점」). 붙여 쓴 「…점」은 norm_name 이 끝의 「점」만 뗀다.
CREATE OR REPLACE FUNCTION dining.base_name(p_name text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    -- ★plpgsql 이다 — sql 함수는 만들 때 norm_name(202)을 찾는데, 요식만 세운 DB(202 를 빼고 올린다)에서는 없다
    RETURN dining.norm_name(regexp_replace(coalesce(p_name, ''), '\s+[^\s]{0,8}점\s*$', ''));
END;
$$;
COMMENT ON FUNCTION dining.base_name IS
    '지점 표시를 뗀 비교용 이름. 「리알토 강남점」 과 「리알토」 가 같은 값이 되게 한다(띄어 쓴 마지막 「…점」 낱말만).';

CREATE OR REPLACE FUNCTION dining.link_core_place(p_tenant_id text, p_core_place_id uuid)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    v_uid     uuid;
    v_cid     text;
    v_by      text;
    v_n       int;
    v_name    text;
    v_kind    text;
    v_lat     double precision;
    v_lng     double precision;
BEGIN
    SELECT l.place_uid INTO v_uid
    FROM dining.dn_core_place_link l
    WHERE l.tenant_id = p_tenant_id AND l.core_place_id = p_core_place_id;
    IF v_uid IS NOT NULL THEN
        RETURN v_uid;
    END IF;

    SELECT coalesce(p.source_content_id, p.attributes->>'source_content_id'), p.name, p.kind, p.latitude, p.longitude
      INTO v_cid, v_name, v_kind, v_lat, v_lng
    FROM places p
    WHERE p.tenant_id = p_tenant_id AND p.place_id = p_core_place_id;

    -- 1  관광공사 번호가 가게 하나로 이어진다(224 그대로)
    IF v_cid IS NOT NULL THEN
        SELECT count(DISTINCT s.place_uid), min(s.place_uid::text)::uuid INTO v_n, v_uid
        FROM dining.dn_source_record s
        WHERE s.source_code = 'tourapi_kor_food' AND s.external_id = v_cid;
        IF v_n = 1 THEN
            v_by := 'runtime:content_id';
        ELSE
            v_uid := NULL;
        END IF;
    END IF;

    -- 2  80m · 이름이 같거나 유사도 0.75 이상인 후보가 하나(224 그대로). 둘 이상이면 여기서 끝(모름)
    IF v_uid IS NULL THEN
        SELECT count(*), min(v.place_uid::text)::uuid INTO v_n, v_uid
        FROM dining.v_link_candidate v
        WHERE v.tenant_id = p_tenant_id AND v.core_place_id = p_core_place_id
          AND (v.name_exact OR v.name_sim >= 0.75);
        IF v_n = 1 THEN
            v_by := 'runtime:matcher';
        ELSIF v_n > 1 THEN
            RETURN NULL;
        ELSE
            v_uid := NULL;
        END IF;
    END IF;

    -- 3  (233) 지점 표시를 뗀 이름이 같은 가게가 150m 안에 하나
    IF v_uid IS NULL THEN
        IF v_kind IS DISTINCT FROM 'dining' OR v_lat IS NULL OR v_lng IS NULL OR length(dining.base_name(v_name)) < 2 THEN
            RETURN NULL;
        END IF;
        SELECT count(*), min(d.place_uid::text)::uuid INTO v_n, v_uid
        FROM dining.dn_place d
        WHERE d.lat BETWEEN v_lat - 0.0015 AND v_lat + 0.0015
          AND d.lng BETWEEN v_lng - 0.0019 AND v_lng + 0.0019
          AND dining.distance_m(v_lat, v_lng, d.lat, d.lng) <= 150
          AND dining.base_name(d.name_ko) = dining.base_name(v_name);
        IF v_n = 1 THEN
            v_by := 'runtime:same_name_150m';
        ELSE
            RETURN NULL;
        END IF;
    END IF;

    INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by)
    VALUES (p_tenant_id, p_core_place_id, v_uid, v_by)
    ON CONFLICT ON CONSTRAINT dn_core_place_link_pkey DO NOTHING;

    SELECT l.place_uid INTO v_uid
    FROM dining.dn_core_place_link l
    WHERE l.tenant_id = p_tenant_id AND l.core_place_id = p_core_place_id;
    RETURN v_uid;
END;
$$;

COMMENT ON FUNCTION dining.link_core_place IS
    '코어 장소 하나를 원장 가게와 잇는다. 이미 이어져 있으면 그 가게, 관광공사 콘텐츠 ID 가 같은 가게가 하나면 그 가게, '
    '아니면 매칭기 규칙(80m · 이름)으로 하나만 정해질 때 그 가게, 그것도 없으면(233) 지점 표시를 뗀 같은 이름이 150m 안에 하나일 때 그 가게. '
    '못 정하면 NULL 이고 아무것도 쓰지 않는다.';

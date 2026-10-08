-- 040  브이월드 지오코더 좌표
-- 작성 2026-10-08.
--
-- 인허가에서 찾지 못했거나 인허가에 좌표가 없는 가게의 좌표를 도로명주소로 구한다.
-- 국토교통부 브이월드(vworld.kr) 지오코더 — 공공데이터라 좌표를 저장해도 된다(구글 좌표는 저장하지 않는다, 200).
-- dn_place.coord_source 가 이 출처를 가리킨다. 지금은 노포 적재(scripts/dining/make_nopo_sql.py --geocode)만 쓴다.

BEGIN;

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('vworld_geocoder', '브이월드 지오코더(국토교통부)', 'public', 'content', true,
     '도로명주소 → 좌표. 인허가 좌표가 없을 때만 쓴다')
ON CONFLICT (source_code) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       source_kind = EXCLUDED.source_kind,
       storage_mode = EXCLUDED.storage_mode,
       production_allowed = EXCLUDED.production_allowed,
       note = EXCLUDED.note;

COMMIT;

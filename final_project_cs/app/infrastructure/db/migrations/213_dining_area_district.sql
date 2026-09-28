-- 033  area 는 자치구다. 권역은 hub 로 옮긴다.
--
-- 지금까지 area 에는 「성수」「경복궁」 같은 권역을 넣었다. 다섯 곳만 볼 때는 괜찮았지만
-- 서울 전체로 넓히면 두 가지가 깨진다.
--
--   1  권역에는 경계가 없다. 두 권역 사이의 식당을 어디에 넣을지 매번 정해야 한다.
--   2  서울을 권역으로 다 덮으려면 권역을 계속 지어내야 한다.
--
-- 자치구는 주소에서 기계적으로 나오고 서울을 빈틈없이 덮는다. 그래서 area 는 자치구로,
-- 추천 권역은 hub 로 따로 둔다. hub 는 비어 있어도 된다.
--
-- 이 파일은 여러 번 돌아도 같은 결과여야 한다(migrate.py 가 매번 전부 다시 적용한다).
-- 그래서 옮기기는 hub 가 비어 있고 area 가 옛 권역 이름인 행에만 한다.
--
-- 출처 둘을 더한다.
--   localdata_rest  휴게음식점 인허가. 카페·베이커리는 대개 여기 있다. 일반음식점 원장에서
--                   폐업으로 나온 가게가 휴게로 다시 등록돼 영업 중인 경우도 있었다.
--   vegan_curated   운영자가 고른 비건 식당 목록. 후보 이름은 HappyCow 에서 사람이 골랐고
--                   HappyCow 의 내용은 저장하지 않는다(약관상 수집·DB 적재 금지).
--                   영업 여부는 인허가 원장과 운영자 확인으로 따로 판정했다.

BEGIN;

ALTER TABLE dining.dn_place ADD COLUMN IF NOT EXISTS hub text;

UPDATE dining.dn_place
   SET hub  = area,
       area = substring(coalesce(road_address, jibun_address) from '([가-힣]+구)\s'),
       updated_at = now()
 WHERE hub IS NULL
   AND area IN ('성수', '경복궁', '잠실', '서울역', '명동')
   AND substring(coalesce(road_address, jibun_address) from '([가-힣]+구)\s') IS NOT NULL;

COMMENT ON COLUMN dining.dn_place.area IS
    '자치구. 주소에서 나온다. 권역이 아니다 — 권역은 hub 를 본다.';
COMMENT ON COLUMN dining.dn_place.hub IS
    '추천 권역(성수·경복궁 등). 권역 밖이면 비운다.';

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('localdata_rest', '지방행정 인허가 휴게음식점', 'public',   'content', true,
     '폐업 판정 근거. 카페·베이커리는 대개 여기 있다'),
    ('vegan_curated',  '운영자 비건 식당 목록',      'operator', 'content', true,
     '후보 이름만 HappyCow 에서 사람이 골랐다. HappyCow 내용은 저장하지 않는다')
ON CONFLICT (source_code) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       source_kind = EXCLUDED.source_kind,
       storage_mode = EXCLUDED.storage_mode,
       production_allowed = EXCLUDED.production_allowed,
       note = EXCLUDED.note;

COMMIT;

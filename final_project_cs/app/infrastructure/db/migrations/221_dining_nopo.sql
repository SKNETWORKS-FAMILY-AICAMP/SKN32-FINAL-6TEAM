-- 039  노포인가
-- 작성 2026-10-07.
--
-- 노포를 속성 하나로 적는다(attr_code = 'nopo'). 미쉐린(218)과 같은 모양이다.
--   value_state   yes 만 쓴다. 목록에 없다는 것은 노포가 아니라는 근거가 아니다 — 행을 만들지 않는다.
--   value_detail  비워 둔다(개업 연도 같은 근거가 생기면 적는다).
--
-- 출처 nopo_kakao_curation.
--   카카오맵 공개 즐겨찾기 폴더 「노포 지도」(만든 이 「노포탐방대장」)에서 가게 이름 · 주소만 옮겼다
--   (datasets/dining/processed/nopo/, scripts/dining/make_nopo_sql.py). 목록은 사용자가 자기 기준의 노포로
--   확인했고, 운영에 쓰기로 정했다(production_allowed = true, 2026-10-07). 다른 사용자가 만든 목록이므로
--   화면에 출처를 밝힌다.
--   백년가게 · 서울미래유산 같은 공식 출처가 들어오면 그것은 따로 출처를 둔다.

BEGIN;

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('nopo_kakao_curation', '카카오맵 노포 지도', 'operator', 'content', true,
     '다른 사용자가 만든 공개 즐겨찾기에서 가게 이름·주소만 옮겼다. 사용자가 노포로 확인했다. 화면에 출처를 밝힌다')
ON CONFLICT (source_code) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       source_kind = EXCLUDED.source_kind,
       storage_mode = EXCLUDED.storage_mode,
       production_allowed = EXCLUDED.production_allowed,
       note = EXCLUDED.note;

ALTER TABLE dining.dn_attribute DROP CONSTRAINT IF EXISTS dn_attribute_code_chk;
ALTER TABLE dining.dn_attribute ADD CONSTRAINT dn_attribute_code_chk CHECK (attr_code IN (
    'card_payment', 'reservable', 'reservation_required', 'kids_allowed',
    'vegetarian_menu', 'halal', 'max_party_size', 'price_per_person',
    'parking', 'takeout', 'non_smoking', 'michelin', 'nopo'));

COMMIT;

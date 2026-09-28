-- 038  미쉐린 가이드에 올랐는가
-- 작성 2026-09-28.
--
-- 미쉐린 가이드 서울 2026 에 오른 곳을 속성 하나로 적는다(attr_code = 'michelin').
--   value_state   yes 만 쓴다. 가이드에 없다는 것은 아니라는 근거가 아니다 — 행을 만들지 않는다.
--   value_detail  등급과 에디션. 「1스타 (2026)」 「빕 구르망 (2026)」 「셀렉티드 (2026)」
--
-- 무엇을 저장하는가.
--   가게 이름과 등급뿐이다. 가이드의 소개 글 · 사진 · 평은 저장하지 않는다(저작권).
--   목록은 guide.michelin.com 의 서울 목록 페이지에서 사람이 옮겼다(data/dining/michelin/).
--
-- 해마다 바뀐다. 새 에디션이 나오면 목록 파일을 바꾸고 다시 적재한다 — 적재기가 이 출처의 것을 비우고 넣는다.

BEGIN;

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('michelin_guide', '미쉐린 가이드 서울', 'operator', 'content', true,
     '가게 이름과 등급만 옮긴다. 소개 글·사진은 저장하지 않는다')
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
    'parking', 'takeout', 'non_smoking', 'michelin'));

COMMIT;

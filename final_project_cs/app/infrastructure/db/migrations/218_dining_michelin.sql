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

-- ★`[2026-10-08]` 이미 「michelin」을(를) 받는 목록이면 건드리지 않는다. 
--   마이그레이션은 매번 전부 다시 돈다(`migrate.py`). 전에는 여기서 목록을 늘 다시 만들어 뒤에 더한 코드(226 「nopo」)가
--   빠졌고, 노포 행이 있는 DB 에서 재실행이 dn_attribute_code_chk 위반으로 멈췄다(2026-10-08 로컬 평가 DB 실측).
--   뒤 마이그레이션이 이 목록을 넓혔으면 그 목록에 「michelin」도 들어 있다 — 그대로 둔다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'dn_attribute_code_chk'
                      AND pg_get_constraintdef(oid) LIKE '%''michelin''%') THEN
        ALTER TABLE dining.dn_attribute DROP CONSTRAINT IF EXISTS dn_attribute_code_chk;
        ALTER TABLE dining.dn_attribute ADD CONSTRAINT dn_attribute_code_chk CHECK (attr_code IN (
            'card_payment', 'reservable', 'reservation_required', 'kids_allowed',
            'vegetarian_menu', 'halal', 'max_party_size', 'price_per_person',
            'parking', 'takeout', 'non_smoking', 'michelin'));
    END IF;
END $$;

COMMIT;

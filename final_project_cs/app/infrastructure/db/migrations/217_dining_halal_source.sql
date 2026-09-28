-- 037  할랄 식당 목록이라는 출처
-- 작성 2026-09-28.
--
-- 운영자가 웹(KMF 인증 목록 · Visit Seoul · 이슬람in코리아 · 기사)에서 후보를 모으고
-- 인허가 원장으로 영업 여부를 대조한 목록이다(data/dining/halal/할랄식당_검수.csv).
--
-- 목록에 올랐다는 것만으로 할랄이라고 말하지 않는다.
--   웹 근거는 「주장」이다. KMF 인증이 만료됐거나 목록에서 빠진 곳이 섞여 있다.
--   halal 속성은 사람이 [확인] 칸을 채운 행에만 붙인다(make_halal_sql.py).
--   채우지 않은 곳은 가게만 들어가고 할랄 여부는 「모름」이다.

BEGIN;

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('halal_curated', '운영자 할랄 식당 목록', 'operator', 'content', true,
     '후보는 웹에서 모았다. 웹 근거 행도 할랄로 넣되 상세에 「웹 근거」를 적는다(2026-09-28 운영 결정)')
ON CONFLICT (source_code) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       source_kind = EXCLUDED.source_kind,
       storage_mode = EXCLUDED.storage_mode,
       production_allowed = EXCLUDED.production_allowed,
       note = EXCLUDED.note;

COMMIT;

-- 017 — place_catalog 신분류체계 컬럼 (2026-09-21)
--
-- ★왜. tour_api.py가 2026-09-21 신분류체계(lclsSystm1)를 반환하도록 바뀌었다.
--   같은 contenttypeid=12(관광지)라도 경복궁(HS·역사관광)과 한라산(NA·자연관광)을
--   구분하려면 이 코드를 카탈로그에 저장해야 한다.
--
-- ★구분류(content_type_id)는 지운다 — 신분류로 대체됐다.
--   서버 파라미터 contentTypeId는 여전히 쓸 수 있지만, 카탈로그 필터링은
--   lclsSystm1(large_class_code)으로 한다.

ALTER TABLE place_catalog
    ADD COLUMN IF NOT EXISTS large_class_code text,
    ADD COLUMN IF NOT EXISTS large_class_name text;

COMMENT ON COLUMN place_catalog.large_class_code IS
    '한국관광공사 신분류체계 대분류(lclsSystm1). NA·HS·VE·LS·EX·SH·FD·AC·EV';
COMMENT ON COLUMN place_catalog.large_class_name IS
    'large_class_code의 한국어 이름. 자연관광·역사관광 등';

CREATE INDEX IF NOT EXISTS place_catalog_large_class_idx
    ON place_catalog (tenant_id, large_class_code);

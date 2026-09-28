-- 029 — 여행 전용 장소 행 (2026-09-27)
--
-- ★★왜. 관광공사 콘텐츠랩 저작권 정책의 「콘텐츠 캐싱(로컬서버 저장방식) 금지」와 카카오 운영정책 제5조
--   (받은 정보를 디렉터리에 입력·타인에게 제공 금지) 때문에, 외부 서비스에서 받은 장소 값을
--   **공용 장소 표에 쌓아 다른 고객에게 재사용하지 않는다**(설계서 `A-COP_고객계획_읽기_설계_2026-09-26.md`
--   §4-5 3번 · §4-6 「그래서 바뀌는 것」 2번 — 「그 여행의 항목에만 싣는다」).
-- ★그런데 감시·대체 일정·변경 비교는 항목의 `place_id` 로 `places` 를 읽는다(15개 파일 48곳). 좌표를 항목
--   `detail` 에만 두면 그 여행의 감시가 돌지 않는다. 그래서 행은 만들되 **그 여행 전용**으로 표시한다 —
--   `trip_scope` = 그 여행 id. 공용 목록(일정 생성기 후보 · 계획 읽기의 「우리 장소」 · 다른 여행의 대체 후보)은
--   `trip_scope IS NULL` 만 본다.
-- ★유일성: 공용 행은 전처럼 (테넌트, 이름, 종류) 하나. 여행 전용 행은 (테넌트, 여행, 이름, 종류) 하나 —
--   두 여행이 같은 「광장시장」을 따로 가진다(서로의 값을 재사용하지 않는다).
-- ☆FK 를 걸지 않았다 — 장소를 넣은 뒤 같은 트랜잭션에서 여행을 만든다(여행 id 는 미리 정한다).
-- ☆재실행해도 안전하다.

ALTER TABLE places ADD COLUMN IF NOT EXISTS trip_scope uuid;

ALTER TABLE places DROP CONSTRAINT IF EXISTS places_tenant_id_name_kind_key;
CREATE UNIQUE INDEX IF NOT EXISTS places_shared_name_kind_uq
    ON places (tenant_id, name, kind) WHERE trip_scope IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS places_trip_name_kind_uq
    ON places (tenant_id, trip_scope, name, kind) WHERE trip_scope IS NOT NULL;

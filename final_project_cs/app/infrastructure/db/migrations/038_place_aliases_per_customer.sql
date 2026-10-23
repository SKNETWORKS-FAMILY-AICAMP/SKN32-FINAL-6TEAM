-- 038 — 장소 별칭을 **고친 고객 단위**로 좁힌다. `[2026-09-30 사용자 확인 「명백한 버그」 — ui 세션 전달]`
--
-- ☆버그. 확인 화면에서 한 고객이 장소를 고치면(예: 「이촌동 점심 식당」→ 「엘 샌드위치」) 그 (원문 → 고친 글)이 **테넌트 단위**로 쌓여
--   다른 고객의 새 접수에 같은 원문이 나오면 자동으로 그 이름으로 잡혔다. 고객이 고른 값은 그 여행에 대한 그 사람의 선택이지
--   가게 이름의 교정이 아니다 — 한 사람의 선택이 모든 고객의 기본값이 됐고, 다른 고객 계획에 끼어드는 **데이터 격리** 문제였다.
-- ★고친 것. `customer_id` 칸을 더한다 — `source='customer'` 행은 그 고객의 다음 접수에만 쓰인다(본인의 표현을 기억). `source='seed'`
--   (우리가 넣은 기본값 — 남산타워 → N서울타워 등)만 모든 고객에게 쓰인다. 다른 고객의 수정에서 공용 별칭을 배우지 않는다.
-- ★이미 있는 행(`customer_id` 없는 `source='customer'` 1행)은 **지우지 않는다** — 누가 고쳤는지 모르므로 조회에서 아무에게도 쓰이지 않는다.
--   새 행은 반드시 고객 번호를 가진다(`NOT VALID` 검사 — 옛 행은 통과시키고 새 행만 막는다).
-- ★같은 원문이라도 고객마다 따로 둘 수 있게 유일 키를 (테넌트, 원문, 고객)으로 바꾼다.
-- ★다시 돌려도 안전하다.

ALTER TABLE place_aliases ADD COLUMN IF NOT EXISTS customer_id uuid NULL;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'place_aliases_pkey') THEN
        ALTER TABLE place_aliases DROP CONSTRAINT place_aliases_pkey;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'place_aliases_customer_scope') THEN
        ALTER TABLE place_aliases ADD CONSTRAINT place_aliases_customer_scope
            CHECK (source <> 'customer' OR customer_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS place_aliases_scope_uniq
    ON place_aliases (tenant_id, phrase_norm, COALESCE(customer_id, '00000000-0000-0000-0000-000000000000'::uuid));

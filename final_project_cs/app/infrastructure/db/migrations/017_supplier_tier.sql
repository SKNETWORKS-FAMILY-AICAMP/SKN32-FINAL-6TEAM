-- 017 — 공급자 등급 (v11 §12 DoD-14·15 · wiki `teams/booking-handoff.md` 「tier == 'simulated'」)
--
-- ★★왜. 승인 뒤 실행(`booking.cancel`)이 **공급자 원장을 바로 고치고 있었다** —
--   그 원장이 시연용 Mock 인지 실제 업체인지 **보지 않고** 고쳤다. 지금은 원장이
--   우리 DB 안이라 아무도 안 다치지만, 실제 공급자 행이 한 줄이라도 들어오는 순간
--   승인 한 번에 남의 돈이 나간다. 등급을 **데이터에 두고** 적용기가 그것만 본다.
--
-- ★기본값은 `real` 이다 — 안전한 쪽으로 틀린다. 등급을 안 적고 넣은 공급자 행은
--   전부 실제 공급자로 취급돼 자동 실행이 막히고 사람에게 간다. 반대로 기본값을
--   `simulated` 로 두면 **등급을 잊은 행이 자동 실행 대상이 된다** — 잊음의 대가가
--   돈인 쪽으로 기울이지 않는다.
--
-- ☆번호 015 는 `pending/015_drop_commerce_domain.sql`(적용 보류) 몫이라 건너뛴다.
-- ☆재실행해도 안전하다 — 컬럼은 IF NOT EXISTS, 제약은 이름으로 존재를 먼저 센다.

ALTER TABLE supplier_bookings ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'real';

-- ★값이 둘뿐이라는 것을 DB 가 지킨다. 오타(`simulate`·`Simulated`)가 들어오면
--   적용기의 `== 'simulated'` 검사가 조용히 거짓이 되는 게 아니라 **삽입이 실패한다.**
--   조용히 거짓이 되는 쪽은 "막혔다" 로 보이지만, 반대 오타(`real` → `reall`)는
--   막을 길이 없으므로 양쪽 다 여기서 센다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'supplier_bookings_tier_chk') THEN
        ALTER TABLE supplier_bookings
            ADD CONSTRAINT supplier_bookings_tier_chk CHECK (tier IN ('real', 'simulated'));
    END IF;
END $$;

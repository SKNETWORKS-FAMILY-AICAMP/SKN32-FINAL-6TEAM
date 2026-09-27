-- 030 — 장소 별칭 (계획 읽기 설계서 §4-1 2단계, 2026-09-28)
--
-- ★★왜. 「남산타워」처럼 **옛 이름·줄임말**은 관광공사·카카오 어디에서도 정확히 안 맞는다(2026-09-27 실측 —
--   카카오 1위가 「YTN서울타워」). 고객이 확인 화면에서 한 번 고치면 다음 고객은 고치지 않아도 되게 쌓는다.
-- ★약관 — **고객이 쓴 글 → 고객이 고친 글**만 담는다(둘 다 고객 글). 관광공사·카카오가 준 이름·좌표는 담지 않는다
--   (콘텐츠랩 「로컬서버 저장 금지」 · 카카오 운영정책 제5조). 별칭은 **다시 찾을 이름**일 뿐이고, 값은 매번 조회한다.
-- ★`source` — `customer`(확인 화면에서 고침) · `seed`(우리가 넣은 기본값, 이 파일 아래).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS place_aliases (
    tenant_id    text NOT NULL,
    phrase_norm  text NOT NULL,          -- 정규화한 원문(`intake.places.normalize`)
    phrase       text NOT NULL,          -- 원문 그대로
    replacement  text NOT NULL,          -- 다시 찾을 이름
    source       text NOT NULL CHECK (source IN ('customer', 'seed')),
    uses         integer NOT NULL DEFAULT 1,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, phrase_norm)
);

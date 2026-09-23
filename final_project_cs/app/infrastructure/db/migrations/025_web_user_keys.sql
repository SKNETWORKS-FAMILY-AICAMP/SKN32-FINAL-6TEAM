-- 025 — 웹 사용자 식별 키 (D-020 · 2026-09-24 사용자 결정)
--
-- ★★왜. 웹(final_project_cs/frontend)이 우리 API 를 부르려면 「누구인지」가 필요하다. 지금 API 는
--   서버용 scope 키로만 열리는데, 그 키는 **테넌트 전체**를 연다 — 고객 브라우저에 넣으면 안 된다.
--   사용자 결정: 로그인 없이 **사용자 식별 키**를 발급해 브라우저 저장소에 두고, 사용자에게도 한 번
--   보여 줘 보관하게 한다(비회원 비밀번호처럼).
--
-- ★키로 할 수 있는 일은 **그 사용자 본인의 여행**뿐이다(조회 · 등록 · 안 고르기 · 자유 문장 · 알림 보기).
-- ★원문 키는 저장하지 않는다 — **SHA-256 해시만**. 원문은 발급할 때 한 번만 돌려준다.
-- ★다시 발급하면 옛 키는 그 자리에서 무효(`revoked_at`). 브라우저 저장소는 그 페이지의 모든 스크립트가
--   읽을 수 있어(지도 SDK 같은 외부 스크립트 포함) 새는 것을 전제로 둔다 — 새면 다시 발급해 끊는다.
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS web_user_keys (
    key_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers,
    key_hash     text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    revoked_at   timestamptz,
    UNIQUE (key_hash)
);

CREATE INDEX IF NOT EXISTS web_user_keys_live_idx
    ON web_user_keys (tenant_id, customer_id) WHERE revoked_at IS NULL;

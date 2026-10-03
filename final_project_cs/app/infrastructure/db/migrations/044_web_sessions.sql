-- 044 — 웹 브라우저 세션(쿠키). `[2026-10-04 사용자 결정 — D-CS-011]`
--
-- ★왜. 브라우저가 사용자 키를 저장소에 두면 페이지의 모든 스크립트(지도 SDK · 확장 · XSS)가 읽는다. 서버가 내려주는 HttpOnly 쿠키 하나로 바꾼다.
--   쿠키 값은 무작위 256비트 — **해시(SHA-256)만** 저장한다. 키(`web_user_keys`)는 에이전트(MCP)와 옛 호출자용으로 남는다.
-- ★만료 시각을 **저장하지 않는다.** 유휴(마지막 사용 뒤)·절대(만든 뒤) 수명은 쓸 때 `web.*` 설정으로 계산한다 — 관리 콘솔이 바꾼 값이 곧 적용되고,
--   수명을 줄여도 옛 행을 고칠 필요가 없다. 종류(게스트/회원)도 저장하지 않는다 — 소셜 계정이 붙었는지(`web_social_links`)로 쓸 때 가른다.
-- ★CSRF 토큰도 저장하지 않는다 — `HMAC(서버 비밀, "csrf|" + session_hash)` 를 다시 계산한다.
-- ★사용자 행(`customers`)을 가리키는 외래키라, 지우려면 이 행을 먼저 지워야 한다(게스트 정리가 그 순서를 지킨다).

CREATE TABLE IF NOT EXISTS web_sessions (
    session_hash text PRIMARY KEY,
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers (customer_id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz NOT NULL DEFAULT now(),
    revoked_at   timestamptz
);

CREATE INDEX IF NOT EXISTS idx_web_sessions_customer  ON web_sessions (tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_web_sessions_last_used ON web_sessions (last_used_at);

-- 043 — 웹 소셜 로그인(구글 먼저). `[2026-10-03 ui 세션 요청서 「소셜 로그인」 · 사용자 결정 「가장 쉬운 걸로 하나 먼저」]`
--
-- ★왜. 웹 사용자는 **사용자 키**(`web_user_keys`)로만 자기 여행을 연다. 키를 잃으면 못 연다(이메일 복구는 뺐다). 소셜 계정을 사용자에 **붙여** 두면 키를 잃어도 · 새 기기에서도
--   그 계정으로 같은 사용자의 여행을 연다. 키 자체와 모든 `/v1/web/*` 인증(`X-User-Key`)은 바뀌지 않는다 — 소셜 로그인은 「키를 받아 오는 또 하나의 길」이다.
-- ★개인정보 최소: 업체가 준 사용자 고유 번호(`sub`)의 **해시만** 둔다(`HMAC(서버 비밀, 업체 + ":" + sub)`). 이메일 · 이름 · 사진은 요청하지도 저장하지도 않는다.
-- ★세 표:
--   web_social_links    어느 사용자에게 어느 업체 계정이 붙었나 — 같은 업체 계정은 **한 사용자에게만**(합치지 않는다)
--   web_oauth_states    로그인을 **시작한** 기록 — `state` 의 해시 · PKCE 검증값 · OIDC nonce · 시작한 브라우저의 `client_nonce` 해시. 한 번만 · 10분
--   web_oauth_tickets   콜백이 끝난 뒤 웹이 **키를 받아 가는** 일회용 표 — 해시만 · 60초 · 시작한 브라우저의 `client_nonce` 가 맞아야 교환된다(로그인 CSRF 막기)
-- ★키 원문은 어디에도 두지 않는다 — 표는 「누구」 · 「무슨 결과」만 들고, 교환할 때 새 키를 발급해 **그 응답에만** 싣는다.
-- ★사용자 행(`customers`)을 가리키는 외래키라, 계정이 붙은 사용자는 빈 키 정리(`web_guard.cleanup_idle_keys`)가 지우지 않는다.

CREATE TABLE IF NOT EXISTS web_social_links (
    tenant_id    text NOT NULL,
    provider     text NOT NULL,
    subject_hash text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers (customer_id),
    linked_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, provider, subject_hash)
);

CREATE INDEX IF NOT EXISTS idx_web_social_links_customer ON web_social_links (tenant_id, customer_id);

CREATE TABLE IF NOT EXISTS web_oauth_states (
    state_hash        text PRIMARY KEY,
    tenant_id         text NOT NULL,
    provider          text NOT NULL,
    mode              text NOT NULL CHECK (mode IN ('login', 'link')),
    customer_id       uuid REFERENCES customers (customer_id),       -- link 일 때만(시작할 때 키로 확인한 사용자)
    code_verifier     text NOT NULL,                                   -- PKCE — 서버만 안다
    nonce             text NOT NULL,                                   -- OIDC nonce — ID 토큰에 되돌아와야 한다
    client_nonce_hash text NOT NULL,                                   -- 시작한 브라우저가 만든 값의 해시
    created_at        timestamptz NOT NULL DEFAULT now(),
    used_at           timestamptz
);

CREATE INDEX IF NOT EXISTS idx_web_oauth_states_created ON web_oauth_states (created_at);

CREATE TABLE IF NOT EXISTS web_oauth_tickets (
    ticket_hash       text PRIMARY KEY,
    tenant_id         text NOT NULL,
    provider          text NOT NULL,
    outcome           text NOT NULL CHECK (outcome IN ('signed_in', 'created', 'linked')),
    customer_id       uuid NOT NULL REFERENCES customers (customer_id),
    client_nonce_hash text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    used_at           timestamptz
);

CREATE INDEX IF NOT EXISTS idx_web_oauth_tickets_created ON web_oauth_tickets (created_at);

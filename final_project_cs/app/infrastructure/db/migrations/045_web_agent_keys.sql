-- 045 — 에이전트 키. `[2026-10-04 사용자 결정 — D-CS-012]`
--
-- ★왜. 개인 AI(MCP · 사용자 API)가 **본인 여행의 작업만** 하는 문. 쿠키는 브라우저 전용이라 에이전트는 키를 머리말로 보낸다.
--   옛 사용자 키(`web_user_keys` — 브라우저가 쓰던 것)는 **만료를 검사하지 않고** `rotate` 가 전부 거두는 한계가 있어, 에이전트용은 이 표에서 따로 다룬다.
-- ★로그인한 사용자(회원)만 만든다 — 만드는 쪽(`web_agent_keys.py`)이 소셜 계정 유무를 확인한다. 키 원문은 어디에도 없다(SHA-256 해시만, 만들 때 한 번만 보여 준다).
-- ★만료(`expires_at`)는 NOT NULL — 기본 90일, 최대 90일(가드레일 `security.web_agent_key_max_days`). 개별 폐기(`revoked_at`) · 마지막 사용(`last_used_at`).
-- ★사용자 행(`customers`)을 가리키는 외래키라 게스트 정리 · 사용자 삭제가 이 행을 먼저 지운다(회원은 안 지우지만 순서를 지킨다).

CREATE TABLE IF NOT EXISTS web_agent_keys (
    key_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers (customer_id),
    name         text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 60),
    key_hash     text NOT NULL UNIQUE,
    scope        text NOT NULL CHECK (scope IN ('read', 'write')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    last_used_at timestamptz,
    revoked_at   timestamptz
);

CREATE INDEX IF NOT EXISTS idx_web_agent_keys_customer ON web_agent_keys (tenant_id, customer_id);

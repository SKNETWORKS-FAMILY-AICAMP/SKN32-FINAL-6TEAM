-- 002 — 도메인 테이블 (구독·결제 CS)
--
-- ★basement 가 아니다. 이 저장소를 다른 CS 도메인으로 복사하면
--   이 파일만 갈아 끼운다. 001 은 손대지 않는다.
--   쇼핑몰이라면 orders / order_items / shipments / returns 가 여기 온다.

CREATE TABLE IF NOT EXISTS subscriptions (subscription_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, customer_id uuid NOT NULL REFERENCES customers, plan text NOT NULL, status text NOT NULL, started_at timestamptz NOT NULL, ended_at timestamptz);
CREATE TABLE IF NOT EXISTS payments (payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, customer_id uuid NOT NULL REFERENCES customers, subscription_id uuid REFERENCES subscriptions, amount_cents int NOT NULL, status text NOT NULL, paid_at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS entitlements (entitlement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, customer_id uuid NOT NULL REFERENCES customers, plan text NOT NULL, source text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS incidents (incident_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, customer_id uuid NOT NULL REFERENCES customers, case_id uuid REFERENCES customer_cases, summary text NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());

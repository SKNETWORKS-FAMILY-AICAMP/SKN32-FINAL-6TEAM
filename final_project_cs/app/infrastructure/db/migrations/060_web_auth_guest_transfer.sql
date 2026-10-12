-- 브라우저 nonce 검증 뒤 이관할 게스트 출처. 고객 요청값으로 받지 않는다.
ALTER TABLE web_oauth_tickets ADD COLUMN IF NOT EXISTS source_customer_id uuid;
ALTER TABLE web_oauth_tickets DROP CONSTRAINT IF EXISTS web_oauth_tickets_source_customer_id_fkey;
ALTER TABLE web_oauth_tickets ADD CONSTRAINT web_oauth_tickets_source_customer_id_fkey
    FOREIGN KEY (source_customer_id) REFERENCES customers (customer_id) ON DELETE SET NULL;

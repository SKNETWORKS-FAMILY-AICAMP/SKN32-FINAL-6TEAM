-- 037 — 바깥함 알림 조회(`dedupe_key` 앞부분 검색)를 받치는 인덱스. `[2026-09-30]` 변경 초인종(`trip_events.py`)
--
-- ★왜. 웹의 알림 조회와 변경 초인종이 `WHERE tenant_id=… AND topic='trip.notice' AND dedupe_key LIKE '<여행 id>:%'` 로 읽는다.
--   기존 유일 인덱스 (tenant_id, topic, dedupe_key) 는 기본 비교 규칙이라 한국어 환경의 앞부분 검색(LIKE 'x%')에 못 쓰여 바깥함 전체를
--   훑었다(543행에서 실측 Seq Scan). 초인종은 열린 연결마다 2초 간격으로 읽으므로, 바깥함이 커지면 부담이 된다.
-- ★`text_pattern_ops` 는 앞부분 검색용 비교 규칙이다. 추가만 한다 — 기존 인덱스 · 데이터를 바꾸지 않는다.
-- ★다시 돌려도 안전하다.

CREATE INDEX IF NOT EXISTS outbox_notice_prefix_idx ON outbox (tenant_id, topic, dedupe_key text_pattern_ops);

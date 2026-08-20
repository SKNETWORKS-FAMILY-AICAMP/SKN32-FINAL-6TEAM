-- ★버그사냥 2026-08-17 (라운드 01, 처리는 라운드 08) — UNIQUE(topic, dedupe_key)
--   가 tenant_id 를 가르지 않았다. 서로 다른 tenant 가 같은 (topic, dedupe_key)
--   를 쓰면 ON CONFLICT DO NOTHING 이 뒤의 것을 조용히 버려 한 tenant 의
--   메시지가 누락될 수 있었다. 실제 삽입 경로(transition.py 의
--   transition_case(..., outbox=[...]))는 지금 프로덕션에서 도달 불가능함을
--   확인했지만(Controller._event_for_result() 의 4분기가 전부 outbox=[] 를
--   반환), 언젠가 채워지기 시작하면 이 gap 이 살아난다 — 미리 막는다.
--   tenant_id 를 더하는 건 순수 확장이라 기존 테스트(같은 tenant 안에서의
--   dedupe)는 그대로 통과한다.
ALTER TABLE outbox DROP CONSTRAINT IF EXISTS outbox_topic_dedupe_key_key;
ALTER TABLE outbox ADD CONSTRAINT outbox_tenant_topic_dedupe_key_key UNIQUE (tenant_id, topic, dedupe_key);

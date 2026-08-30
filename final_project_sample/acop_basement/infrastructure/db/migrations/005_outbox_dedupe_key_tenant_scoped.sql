-- ★버그사냥 2026-08-17 (라운드 01, 처리는 라운드 08) — UNIQUE(topic, dedupe_key)
--   가 tenant_id 를 가르지 않았다. 서로 다른 tenant 가 같은 (topic, dedupe_key)
--   를 쓰면 ON CONFLICT DO NOTHING 이 뒤의 것을 조용히 버려 한 tenant 의
--   메시지가 누락될 수 있었다. 실제 삽입 경로(transition.py 의
--   transition_case(..., outbox=[...]))는 지금 프로덕션에서 도달 불가능함을
--   확인했지만(Controller._event_for_result() 의 4분기가 전부 outbox=[] 를
--   반환), 언젠가 채워지기 시작하면 이 gap 이 살아난다 — 미리 막는다.
--   tenant_id 를 더하는 건 순수 확장이라 기존 테스트(같은 tenant 안에서의
--   dedupe)는 그대로 통과한다.
-- ★버그사냥 2026-08-29 — 이 파일이 **재실행 안전하지 않았다.** `ADD
--   CONSTRAINT` 에 존재 검사가 없어서 두 번째 실행이 DuplicateTable 로
--   죽었고, 러너가 전체 SQL 을 한 번에 실행하므로 **뒤따르는 마이그레이션이
--   전부 적용되지 않았다**(006 을 추가하다 발견). 이 모듈의 docstring 은
--   "safely repeatable" 이라고 적혀 있었으니 문서와 동작이 어긋난 것이다.
ALTER TABLE outbox DROP CONSTRAINT IF EXISTS outbox_topic_dedupe_key_key;
DO $$
BEGIN
    ALTER TABLE outbox ADD CONSTRAINT outbox_tenant_topic_dedupe_key_key
        UNIQUE (tenant_id, topic, dedupe_key);
EXCEPTION
    WHEN duplicate_table THEN NULL;  -- 이미 있다 — 재실행이다
    WHEN duplicate_object THEN NULL;
END $$;

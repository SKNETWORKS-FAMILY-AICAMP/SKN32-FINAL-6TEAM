-- 904 — Case 사건 기록(`case_events`)을 **DB 가 지킨다**. `[2026-10-15 사용자 지시 — 코어 「추가만 한다」 규칙의 DB 잠금]`
--
-- ★왜. `case_events` 는 Case 상태를 다시 만들 수 있는 유일한 근거(재생)이고 감사 기록이다. 「추가만 한다」는 지금까지 **코드 규칙**뿐이라
--   (final_project_cs/CLAUDE.md · wiki/runtime/case-lifecycle.md) 어느 코드나 시험이 UPDATE · DELETE · TRUNCATE 를 해도 DB 가 막지 못했다.
--   `consent_events`(046) · `runtime_limit_events`(031) · `legal_retention_history`(056) · `admin_audit`(226)이 이미 같은 방식으로 지킨다.
-- ★규칙(046 과 같은 방식).
--   UPDATE   — 늘 거절한다.
--   DELETE   — 그 트랜잭션에서 `SET LOCAL app.case_events_purge = 'on'` 을 켠 정리 작업만 된다(여행 삭제 · 회원 · 게스트 정리의 처리 기록 파기, 시험 정리).
--   TRUNCATE — DELETE 와 같은 스위치일 때만 된다(`TRUNCATE customer_cases CASCADE` 처럼 딸려 비우는 것도 걸린다).
-- ★이미 들어 있는 행은 검사하지 않는다 — 트리거는 앞으로의 변경만 본다(소급 영향 없음). INSERT 는 막지 않는다.
-- ★다시 적용해도 같다 — 함수는 CREATE OR REPLACE, 트리거는 지우고 다시 만든다.

CREATE OR REPLACE FUNCTION case_events_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('DELETE', 'TRUNCATE') AND current_setting('app.case_events_purge', true) = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NULL;
    END IF;
    RAISE EXCEPTION 'case_events 는 추가만 한다 (% 불가)', TG_OP;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS case_events_no_change ON case_events;
CREATE TRIGGER case_events_no_change BEFORE UPDATE OR DELETE ON case_events
    FOR EACH ROW EXECUTE FUNCTION case_events_append_only();

DROP TRIGGER IF EXISTS case_events_no_truncate ON case_events;
CREATE TRIGGER case_events_no_truncate BEFORE TRUNCATE ON case_events
    FOR EACH STATEMENT EXECUTE FUNCTION case_events_append_only();

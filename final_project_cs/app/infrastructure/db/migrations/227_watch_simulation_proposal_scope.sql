-- 같은 일정에서 시험을 다시 실행해도 이전 시험의 제안과 충돌하지 않게 실행별 범위를 둔다.
-- 실제 제안의 change/forecast 범위와 기존 유일 인덱스는 보존한다.
ALTER TABLE pending_changes DROP CONSTRAINT IF EXISTS pending_changes_scope_check;
ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_scope_check
    CHECK (proposal_scope IN ('change', 'forecast')
           OR proposal_scope ~ '^(change|forecast):sim:[0-9a-f-]{36}$');

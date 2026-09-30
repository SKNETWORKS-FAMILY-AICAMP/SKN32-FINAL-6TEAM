-- 035 — 보류 제안에 「바꾼 뒤에도 고를 수 있는 다른 안」 이유를 더한다. `[2026-09-29]` 사용자 제안 — ui 세션 전달
--
-- ★「다른 데로 바꿔 줘」로 한 곳으로 바꾼 뒤, 찾는 과정에서 나온 **다른 곳**(조건을 다 통과한 나머지 · 모자라면 조건을 푼 안)을
--   셋까지 같은 항목의 보류 제안으로 연다. 고르면 기존 「다른 안으로」(plan_swap)로 바꾸고, 답이 없으면 바꾼 것을 그대로 둔다.
--     other_options   바꾼 뒤의 다른 안 — 지금 것은 이미 적용돼 있다
-- ★다시 돌려도 안전하다 — 옛 제약을 지우고 넓힌 제약으로 다시 건다. 기존 행은 모두 옛 값이라 통과한다.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
        ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check;
    END IF;
    ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
        CHECK (reason IN ('ask_first', 'protected', 'safety_alert',
                          'indoor_unknown', 'indoor_unknown_options', 'relaxed', 'requested_options',
                          'other_options'));
END $$;

-- 035 — 보류 제안에 「바꾼 뒤에도 고를 수 있는 다른 안」 이유를 더한다. `[2026-09-29]` 사용자 제안 — ui 세션 전달
--
-- ★「다른 데로 바꿔 줘」로 한 곳으로 바꾼 뒤, 찾는 과정에서 나온 **다른 곳**(조건을 다 통과한 나머지 · 모자라면 조건을 푼 안)을
--   셋까지 같은 항목의 보류 제안으로 연다. 고르면 기존 「다른 안으로」(plan_swap)로 바꾸고, 답이 없으면 바꾼 것을 그대로 둔다.
--     other_options   바꾼 뒤의 다른 안 — 지금 것은 이미 적용돼 있다
-- ★다시 돌려도 안전하다 — 옛 제약을 지우고 넓힌 제약으로 다시 건다. 기존 행은 모두 옛 값이라 통과한다.
-- ☆`[2026-10-05]` 위 「다시 돌려도 안전하다」는 **틀린 말**이었다. 이 파일들은 번호 순서대로 **매번 전부** 다시 돌고(`migrate.py`),
--   각자 자기 시점의 값 목록으로 제약을 다시 건다. 뒤 마이그레이션(033~035)이 값을 넓힌 뒤에 032 가 좁은 목록을 다시 걸면
--   이미 들어 있는 `relaxed`·`requested_options`·`other_options` 행이 제약을 어겨 마이그레이션 전체가 멈춘다(CheckViolation).
--   그래서 **제약이 이미 이 파일의 값을 허용하면 건드리지 않는다**(좁히지 않는다). 새 DB 에서는 번호 순서대로 넓어진다.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check'
                    AND pg_get_constraintdef(oid) LIKE '%''other_options''%') THEN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
            ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check;
        END IF;
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
            CHECK (reason IN ('ask_first', 'protected', 'safety_alert',
                              'indoor_unknown', 'indoor_unknown_options', 'relaxed', 'requested_options',
                              'other_options'));
    END IF;
END $$;

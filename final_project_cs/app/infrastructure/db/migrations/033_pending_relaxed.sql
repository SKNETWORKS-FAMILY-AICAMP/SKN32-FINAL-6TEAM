-- 033 — 보류 제안에 「조건을 풀어 찾은 안」 이유를 더한다. `[2026-09-29]`
--
-- ★「다른 데로 바꿔 줘」가 같은 조건(같은 시각 · 반경)으로 0곳이면 「없어요」로 끝내지 않고, 조건을 하나씩 풀어
--   **실제로 되는 안**(시각을 늦추기 · 다음 일정 근처)을 계산해 **묻는다**(사용자 지적 — ui 세션 전달). 고객이 원한 조건을
--   바꾸는 안이라 바로 적용하지 않는다.
--     relaxed   조건을 푼 안 1·2 — 고르면 기존 「다른 안으로」(plan_swap)로 적용
-- ★다시 돌려도 안전하다 — 옛 제약을 지우고 넓힌 제약으로 다시 건다. 기존 행은 모두 옛 값이라 통과한다.
-- ☆`[2026-10-05]` 위 「다시 돌려도 안전하다」는 **틀린 말**이었다. 이 파일들은 번호 순서대로 **매번 전부** 다시 돌고(`migrate.py`),
--   각자 자기 시점의 값 목록으로 제약을 다시 건다. 뒤 마이그레이션(033~035)이 값을 넓힌 뒤에 032 가 좁은 목록을 다시 걸면
--   이미 들어 있는 `relaxed`·`requested_options`·`other_options` 행이 제약을 어겨 마이그레이션 전체가 멈춘다(CheckViolation).
--   그래서 **제약이 이미 이 파일의 값을 허용하면 건드리지 않는다**(좁히지 않는다). 새 DB 에서는 번호 순서대로 넓어진다.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check'
                    AND pg_get_constraintdef(oid) LIKE '%''relaxed''%') THEN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
            ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check;
        END IF;
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
            CHECK (reason IN ('ask_first', 'protected', 'safety_alert',
                              'indoor_unknown', 'indoor_unknown_options', 'relaxed'));
    END IF;
END $$;

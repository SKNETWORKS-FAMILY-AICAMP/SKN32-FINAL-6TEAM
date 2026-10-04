-- 032 — 보류 제안에 「바꿀까요?」(동의 먼저) 이유 두 개를 더한다. `[2026-09-29]`
--
-- ★실내·야외를 **모르는** 활동에 날씨 사건만 걸리면 대체안을 계산하지 않고 먼저 묻는다(사용자 결정 2026-09-29).
--   대체안 계산은 후보마다 바깥 점검을 부른다 — 동의한 뒤에만 계산한다.
--     indoor_unknown           「바꿀까요?」 — 안이 없다(options_json = [])
--     indoor_unknown_options   「바꿔 줘」 뒤 — 그때 계산한 안 1·2·3을 같은 제안에 채웠다
--   같은 항목·같은 기준 버전은 제안 하나라(UNIQUE) 두 번째 제안을 따로 열지 않고 이유만 바꾼다.
-- ★다시 돌려도 안전하다 — 옛 제약을 지우고 넓힌 제약으로 다시 건다. 기존 행은 모두 옛 값이라 통과한다.
-- ☆`[2026-10-05]` 위 「다시 돌려도 안전하다」는 **틀린 말**이었다. 이 파일들은 번호 순서대로 **매번 전부** 다시 돌고(`migrate.py`),
--   각자 자기 시점의 값 목록으로 제약을 다시 건다. 뒤 마이그레이션(033~035)이 값을 넓힌 뒤에 032 가 좁은 목록을 다시 걸면
--   이미 들어 있는 `relaxed`·`requested_options`·`other_options` 행이 제약을 어겨 마이그레이션 전체가 멈춘다(CheckViolation).
--   그래서 **제약이 이미 이 파일의 값을 허용하면 건드리지 않는다**(좁히지 않는다). 새 DB 에서는 번호 순서대로 넓어진다.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check'
                    AND pg_get_constraintdef(oid) LIKE '%''indoor_unknown_options''%') THEN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
            ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check;
        END IF;
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
            CHECK (reason IN ('ask_first', 'protected', 'safety_alert',
                              'indoor_unknown', 'indoor_unknown_options'));
    END IF;
END $$;

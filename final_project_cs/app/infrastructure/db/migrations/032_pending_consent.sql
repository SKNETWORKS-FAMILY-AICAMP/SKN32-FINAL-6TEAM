-- 032 — 보류 제안에 「바꿀까요?」(동의 먼저) 이유 두 개를 더한다. `[2026-09-29]`
--
-- ★실내·야외를 **모르는** 활동에 날씨 사건만 걸리면 대체안을 계산하지 않고 먼저 묻는다(사용자 결정 2026-09-29).
--   대체안 계산은 후보마다 바깥 점검을 부른다 — 동의한 뒤에만 계산한다.
--     indoor_unknown           「바꿀까요?」 — 안이 없다(options_json = [])
--     indoor_unknown_options   「바꿔 줘」 뒤 — 그때 계산한 안 1·2·3을 같은 제안에 채웠다
--   같은 항목·같은 기준 버전은 제안 하나라(UNIQUE) 두 번째 제안을 따로 열지 않고 이유만 바꾼다.
-- ★다시 돌려도 안전하다 — 옛 제약을 지우고 넓힌 제약으로 다시 건다. 기존 행은 모두 옛 값이라 통과한다.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
        ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check;
    END IF;
    ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
        CHECK (reason IN ('ask_first', 'protected', 'safety_alert',
                          'indoor_unknown', 'indoor_unknown_options'));
END $$;

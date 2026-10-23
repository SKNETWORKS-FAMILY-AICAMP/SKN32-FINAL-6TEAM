-- 034 — 여행 채팅 대화 기록 · 「후보만 알아봐 줘」 제안 이유. `[2026-09-29]` 결정 단위(사용자 승인 — ui 세션 전달)
--
-- ★대화 기록(`trip_chat_turns`) — 요청 해석(결정 단위)이 「그 식당」「거기」 같은 가리키는 말을 앞 대화로 풀려면 서버가
--   최근 몇 턴을 들고 있어야 한다. 전에는 웹이 대화를 브라우저에만 두었다(「아니 그 식당 세부정보 알려달라고」가 무관한
--   규정 조각으로 답했다). 고객 문장은 **가린 뒤** 저장한다(CLAUDE.md §1 — 원문 PII 는 masking 후 저장).
--   append-only 로 쓴다 — 고치지 않는다(기록이다).
-- ★보류 제안 이유 `requested_options` — 「다른 데 알아봐 줘 · 추천해 줘」는 바꾸지 않고 후보를 보여 **고르게** 한다.
-- ★다시 돌려도 안전하다.
-- ☆`[2026-10-05]` 위 「다시 돌려도 안전하다」는 **틀린 말**이었다. 이 파일들은 번호 순서대로 **매번 전부** 다시 돌고(`migrate.py`),
--   각자 자기 시점의 값 목록으로 제약을 다시 건다. 뒤 마이그레이션(033~035)이 값을 넓힌 뒤에 032 가 좁은 목록을 다시 걸면
--   이미 들어 있는 `relaxed`·`requested_options`·`other_options` 행이 제약을 어겨 마이그레이션 전체가 멈춘다(CheckViolation).
--   그래서 **제약이 이미 이 파일의 값을 허용하면 건드리지 않는다**(좁히지 않는다). 새 DB 에서는 번호 순서대로 넓어진다.

CREATE TABLE IF NOT EXISTS trip_chat_turns (
    turn_id     bigserial PRIMARY KEY,
    tenant_id   text        NOT NULL,
    trip_id     uuid        NOT NULL,
    role        text        NOT NULL CHECK (role IN ('customer', 'assistant')),
    text        text        NOT NULL,
    case_id     uuid        NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_chat_turns_trip_idx ON trip_chat_turns (tenant_id, trip_id, turn_id DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check'
                    AND pg_get_constraintdef(oid) LIKE '%''requested_options''%') THEN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
            ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check;
        END IF;
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
            CHECK (reason IN ('ask_first', 'protected', 'safety_alert',
                              'indoor_unknown', 'indoor_unknown_options', 'relaxed', 'requested_options'));
    END IF;
END $$;

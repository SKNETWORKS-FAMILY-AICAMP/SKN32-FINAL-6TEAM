-- 039 — 고객 연락처(복구 이메일 · 디스코드 웹훅). `[2026-10-01 사용자 지시 — ui 세션 전달]`
--
-- ★사용자 지시: 「리커버리 이메일 받는 곳에서 나중에 디스코드 웹훅 URL 도 받게 될 건데, 그게 추가되면 받을 수 있게 서버 구현해 두라」.
--   웹은 첫 시작 화면(약관 · 취향 · 복구 이메일)을 한 번만 받고 마이페이지에서 고친다. 이 표가 서버 쪽 저장 자리다.
-- ★웹훅 URL 은 **서버가 나중에 그 주소로 POST 하는 비밀값**(주소 자체가 권한 — 아는 사람은 누구나 그 채널에 글을 쓴다)이자 바깥 호출 통로다.
--   그래서 ①원문은 **암호화해서만** 저장한다(`discord_webhook_enc` — 키는 서버 설정에서 파생, `customer_profile.py`) ②조회에는 마스킹한 모양만
--   돌려준다(`discord_hint`) ③로그 · Case · 바깥함 · 오류 문구에 원문을 남기지 않는다.
-- ★`discord_status` — `untested`(저장만 함) · `ok`(시험 발송 성공) · `invalid`(웹훅이 없어졌거나 거부 — 401/404). 정본은 여행 계획서 링크이고 이 값은
--   「알림이 닿을 수 있나」의 참고다. `discord_tested_at` 은 마지막 시험 시도 시각(시험 발송 간격 제한을 DB 에서 센다 — 프로세스가 여럿이어도 맞다),
--   `discord_checked_at` 은 상태를 정한 시각.
-- ★고객이 지워지면 함께 지운다(`ON DELETE CASCADE`). 다시 돌려도 안전하다.

CREATE TABLE IF NOT EXISTS customer_profiles (
    tenant_id           text        NOT NULL,
    customer_id         uuid        NOT NULL REFERENCES customers (customer_id) ON DELETE CASCADE,
    recovery_email      text        NULL,
    discord_webhook_enc text        NULL,       -- 암호화한 웹훅 URL — 원문은 어디에도 없다
    discord_hint        text        NULL,       -- 마스킹한 모양(조회용): https://discord.com/api/webhooks/<번호 앞 4자리>…/••••
    discord_status      text        NOT NULL DEFAULT 'untested' CHECK (discord_status IN ('untested', 'ok', 'invalid')),
    discord_checked_at  timestamptz NULL,
    discord_tested_at   timestamptz NULL,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, customer_id)
);

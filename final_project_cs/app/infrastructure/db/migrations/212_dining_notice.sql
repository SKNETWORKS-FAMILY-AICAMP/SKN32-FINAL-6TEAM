-- 032  언제 묻고 언제 말하고 언제 입을 다무는가
--
-- 세 범위는 서로 다르다. 우리가 계속 써 온 기준이다.
--
--   판정  공짜다(SQL). 그래서 넓게 잡는다.
--   조회  돈과 남의 서버를 쓴다. 그래서 좁게 잡는다.
--   알림  사용자의 주의를 쓴다. 그래서 가장 좁게 잡는다.
--
-- 031 까지 앞의 둘을 갈랐고, 이 파일은 마지막 하나다.
--
-- 알림에서 지키는 것.
--
--   1  모름으로는 알리지 않는다. 읽지 못했다는 말은 사용자에게 쓸모가 없고,
--      「확인이 안 됩니다」를 받은 사람은 우리를 덜 믿게 된다.
--   2  좋은 소식은 알리지 않는다. 「웨이팅 없어요」는 행동을 바꾸지 않는다.
--      바꾸지 않을 말로 주의를 쓰면, 정작 바꿔야 할 때 읽히지 않는다.
--   3  같은 말을 두 번 하지 않는다.
--   4  일정을 바꾸지 않는다. 알림은 말이지 결정이 아니다.
--
-- 묻는 때도 여기서 정한다. 자동 조회는 방문 60분 전과 20분 전 두 번뿐이다.
-- 60분 전은 「오늘 거기 붐빈다」를, 20분 전은 「지금 몇 팀」을 위한 것이다.
-- 웨이팅의 신선도가 5분이므로 60분 전 값은 도착 시점에 이미 낡았다.
-- 그래서 두 번이고, 알림에 쓰는 숫자는 20분 전 것이다.

BEGIN;

-- ──────────────────────────────────────────────────────────────
-- 자동 조회가 물을 말
-- ──────────────────────────────────────────────────────────────
--
-- 사람이 매번 문장을 지어 주지 않는다. 자동으로 도는 동안에는 늘 이 말만
-- 나간다. 말이 고정되어야 무엇을 물었는지 나중에 따질 수 있고, 범위가
-- 넓어지는 것도 막힌다. 한 곳, 두 가지, 그 이상은 묻지 않는다.

CREATE OR REPLACE FUNCTION dining.ambient_prompt(p_place_uid uuid)
RETURNS text
LANGUAGE sql
STABLE
AS $fn$
    SELECT (SELECT name_ko FROM dining.dn_place WHERE place_uid = p_place_uid)
           || ' 현재 웨이팅 몇 팀인지 알아봐. 또는 영업 중인지 아닌지.'
$fn$;

COMMENT ON FUNCTION dining.ambient_prompt IS
    '자동 조회가 내보내는 고정 문장. 한 곳, 웨이팅과 영업 여부만 묻는다.';


-- ──────────────────────────────────────────────────────────────
-- 물을 때인가
-- ──────────────────────────────────────────────────────────────
--
-- 방문 60분 전과 20분 전. 창은 각각 5분이다. 감시 틱이 1분마다 돌아도
-- 같은 창에서 여러 번 묻지 않도록 하는 것은 031 의 재질문 억제가 맡는다.
-- 여기서는 「지금이 그 창인가」만 답한다.

CREATE OR REPLACE FUNCTION dining.watch_window(
    p_starts_at timestamptz,
    p_now       timestamptz DEFAULT now()
)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE
             WHEN p_starts_at - p_now BETWEEN interval '55 minutes'
                                          AND interval '60 minutes' THEN 'T-60'
             WHEN p_starts_at - p_now BETWEEN interval '15 minutes'
                                          AND interval '20 minutes' THEN 'T-20'
             ELSE NULL
           END
$fn$;

COMMENT ON FUNCTION dining.watch_window IS
    '자동 조회를 할 때인가. 방문 60분 전과 20분 전의 5분 창. 그 밖에는 NULL.';


-- ──────────────────────────────────────────────────────────────
-- 보낸 말의 원장
-- ──────────────────────────────────────────────────────────────
--
-- 무엇을 말했는지 남긴다. 같은 말을 두 번 하지 않기 위해서이고,
-- 나중에 「왜 이 알림이 갔나」를 답하기 위해서다.

CREATE TABLE IF NOT EXISTS dining.dn_notice (
    notice_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid   uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    target_at   timestamptz NOT NULL,
    kind        text NOT NULL,
    body        text NOT NULL,
    based_on    text,
    sent_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT dn_notice_kind_chk
        CHECK (kind IN ('closed', 'crowded')),
    -- 같은 방문, 같은 종류의 말은 한 번뿐이다.
    CONSTRAINT dn_notice_once UNIQUE (place_uid, target_at, kind)
);

COMMENT ON TABLE dining.dn_notice IS
    '사용자에게 실제로 나간 말. 같은 방문에 같은 종류는 한 번만 들어간다.';
COMMENT ON COLUMN dining.dn_notice.based_on IS
    '그 말의 근거가 된 관측. 왜 갔느냐를 나중에 답하기 위한 것.';


-- ──────────────────────────────────────────────────────────────
-- 몇 팀부터 말할 것인가
-- ──────────────────────────────────────────────────────────────
--
-- 이 값은 우리가 고른 것이지 측정한 것이 아니다. 측정하면 바꾼다.
-- 런던베이글뮤지엄이 41팀이었고 메이플탑이 0팀이었다. 그 사이 어딘가다.
-- 10팀을 고른 이유는 「줄을 서겠다는 결심이 필요한 수」이기 때문이고,
-- 그보다 적으면 알려도 사용자가 할 일이 없다.

CREATE OR REPLACE FUNCTION dining.crowded_from()
RETURNS integer LANGUAGE sql IMMUTABLE AS $fn$ SELECT 10 $fn$;

COMMENT ON FUNCTION dining.crowded_from IS
    '이 팀 수부터 붐빈다고 말한다. 우리가 고른 값이며 측정값이 아니다.';


-- ──────────────────────────────────────────────────────────────
-- 말할 것인가
-- ──────────────────────────────────────────────────────────────
--
-- 돌려주는 값은 언제나 판단의 근거를 함께 담는다. send 가 거짓일 때도
-- 이유를 적는다. 「왜 안 알렸나」도 답할 수 있어야 한다.
--
-- 판정은 건드리지 않는다. 여기서 나오는 것은 말 한 줄이고,
-- 일정은 그대로다. 명절 표시를 붙이되 일정을 바꾸지 않던 것과 같다.

CREATE OR REPLACE FUNCTION dining.notice_decision(
    p_place_uid uuid,
    p_target_at timestamptz,
    p_trial     boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $fn$
DECLARE
    v_name    text;
    v_wait    jsonb;
    v_open    jsonb;
    v_num     integer;
BEGIN
    SELECT name_ko INTO v_name FROM dining.dn_place WHERE place_uid = p_place_uid;
    IF v_name IS NULL THEN
        RETURN jsonb_build_object('send', false, 'reason', '모르는 장소');
    END IF;

    -- 이미 한 말은 다시 하지 않는다. 종류마다 따로 본다.
    IF EXISTS (SELECT 1 FROM dining.dn_notice n
                WHERE n.place_uid = p_place_uid AND n.target_at = p_target_at) THEN
        RETURN jsonb_build_object('send', false, 'reason', '이미 말했다');
    END IF;

    v_open := dining.live_state(p_place_uid, 'closure', p_trial);
    v_wait := dining.live_state(p_place_uid, 'waiting', p_trial);

    -- 1  닫혔다. 이것은 행동을 바꾼다. 가장 센 말이다.
    IF v_open IS NOT NULL AND v_open->>'state' = 'yes' THEN
        RETURN jsonb_build_object(
            'send', true, 'kind', 'closed',
            'body', v_name || ' 이 그 시간에 쉰다고 합니다. 다른 곳을 볼까요?',
            'based_on', v_open->>'source',
            'reason', '휴무를 확인했다');
    END IF;

    -- 2  붐빈다. 숫자가 있어야 말한다. 「많음」 같은 말로는 알리지 않는다.
    IF v_wait IS NOT NULL AND v_wait->>'state' = 'yes' THEN
        v_num := (v_wait->>'num')::integer;
        IF v_num IS NULL THEN
            -- 웨이팅이 있다는 것만 알고 몇 팀인지 모른다. 그 말로는 판단할 수 없다.
            RETURN jsonb_build_object('send', false, 'reason', '팀 수를 모른다');
        END IF;
        IF v_num >= dining.crowded_from() THEN
            RETURN jsonb_build_object(
                'send', true, 'kind', 'crowded',
                'body', v_name || ' 현재 웨이팅 ' || v_num || '팀입니다. '
                        || '조금 일찍 가시거나 다른 곳을 볼까요?',
                'based_on', v_wait->>'source',
                'reason', v_num || '팀은 ' || dining.crowded_from() || '팀 이상이다');
        END IF;
        -- 줄이 짧다. 좋은 소식이고, 좋은 소식은 알리지 않는다.
        RETURN jsonb_build_object('send', false,
            'reason', v_num || '팀은 알릴 만큼이 아니다');
    END IF;

    -- 3  모름. 여기서 끝난다. 「확인되지 않습니다」는 보내지 않는다.
    IF v_wait IS NULL AND v_open IS NULL THEN
        RETURN jsonb_build_object('send', false, 'reason', '아직 아무것도 모른다');
    END IF;
    RETURN jsonb_build_object('send', false, 'reason', '알릴 만한 것이 없다');
END;
$fn$;

COMMENT ON FUNCTION dining.notice_decision IS
    '말할 것인가. 안 보낼 때도 이유를 담는다. 모름과 좋은 소식으로는 보내지 않는다.';


-- ──────────────────────────────────────────────────────────────
-- 말했다고 적기
-- ──────────────────────────────────────────────────────────────
--
-- 보내는 일은 여기서 하지 않는다. 보냈다는 사실만 적는다.
-- 같은 방문에 같은 종류가 두 번 오면 조용히 넘긴다.

CREATE OR REPLACE FUNCTION dining.record_notice(
    p_place_uid uuid,
    p_target_at timestamptz,
    p_kind      text,
    p_body      text,
    p_based_on  text DEFAULT NULL
)
RETURNS uuid
LANGUAGE sql
AS $fn$
    INSERT INTO dining.dn_notice (place_uid, target_at, kind, body, based_on)
    VALUES (p_place_uid, p_target_at, p_kind, p_body, p_based_on)
    ON CONFLICT (place_uid, target_at, kind) DO NOTHING
    RETURNING notice_id
$fn$;

COMMENT ON FUNCTION dining.record_notice IS
    '보냈다는 사실만 적는다. 두 번째는 조용히 넘어가며 NULL 을 돌려준다.';

COMMIT;

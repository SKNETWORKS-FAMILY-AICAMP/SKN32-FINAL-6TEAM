-- 220  요식 알림 기록을 여행마다 나눈다 (2026-09-28 cs)
--
-- 왜.
--   212 의 dn_notice 는 「같은 식당 · 같은 시각 · 같은 종류는 한 번」이었다(UNIQUE place_uid, target_at, kind).
--   그런데 테넌트도 여행도 없어서, 두 여행자가 같은 식당을 같은 시각에 잡으면 **뒤 사람은 알림을 못 받았다.**
--   모든 조회에 tenant 조건을 붙인다는 코어 격리 규칙에도 어긋났다.
--
-- 무엇을.
--   1  tenant_id · trip_id 칸을 더한다(옛 행은 비어 있다 — 옛 호출은 그대로 돈다)
--   2  한 번만 규칙을 (tenant_id, trip_id, place_uid, target_at, kind) 로 바꾼다. NULL 도 같은 값으로 본다
--   3  여행을 받는 notice_decision · record_notice 를 더한다. 옛 모양(여행 없음)은 남겨 둔다
--
-- 보내기와의 관계.
--   이 표에 적는 것과 코어 알림함(outbox, trip.notice)에 넣는 것은 **한 트랜잭션**이어야 한다
--   (tick.py 의 on_notice). 그래야 두 번 가지도 않고 보내다 실패해 영영 안 가지도 않는다 —
--   알림함은 실패하면 다시 보내고, 같은 키는 두 번 안 들어간다(outbox UNIQUE).
--
-- 다시 돌려도 깨지지 않는다 — IF NOT EXISTS · IF EXISTS · CREATE OR REPLACE 만 쓴다.

ALTER TABLE dining.dn_notice ADD COLUMN IF NOT EXISTS tenant_id text;
ALTER TABLE dining.dn_notice ADD COLUMN IF NOT EXISTS trip_id   uuid;

COMMENT ON COLUMN dining.dn_notice.tenant_id IS '어느 테넌트의 여행에 간 말인가. 옛 행(220 전)은 비어 있다.';
COMMENT ON COLUMN dining.dn_notice.trip_id   IS '어느 여행에 간 말인가. 옛 행(220 전)은 비어 있다.';

ALTER TABLE dining.dn_notice DROP CONSTRAINT IF EXISTS dn_notice_once;

CREATE UNIQUE INDEX IF NOT EXISTS dn_notice_once_per_trip
    ON dining.dn_notice (tenant_id, trip_id, place_uid, target_at, kind) NULLS NOT DISTINCT;

COMMENT ON INDEX dining.dn_notice_once_per_trip IS
    '같은 여행 · 같은 식당 · 같은 시각 · 같은 종류의 말은 한 번뿐이다. 다른 여행은 따로 받는다.';


-- 말할 내용만 — 「이미 말했나」는 부르는 쪽이 범위에 맞게 본다.
-- 212 의 notice_decision 본문에서 「이미 말했다」 검사를 뺀 것과 같다.
CREATE OR REPLACE FUNCTION dining.notice_content(
    p_place_uid uuid,
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

    v_open := dining.live_state(p_place_uid, 'closure', p_trial);
    v_wait := dining.live_state(p_place_uid, 'waiting', p_trial);

    IF v_open IS NOT NULL AND v_open->>'state' = 'yes' THEN
        RETURN jsonb_build_object(
            'send', true, 'kind', 'closed',
            'body', v_name || ' 이 그 시간에 쉰다고 합니다. 다른 곳을 볼까요?',
            'based_on', v_open->>'source',
            'reason', '휴무를 확인했다');
    END IF;

    IF v_wait IS NOT NULL AND v_wait->>'state' = 'yes' THEN
        v_num := (v_wait->>'num')::integer;
        IF v_num IS NULL THEN
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
        RETURN jsonb_build_object('send', false,
            'reason', v_num || '팀은 알릴 만큼이 아니다');
    END IF;

    IF v_wait IS NULL AND v_open IS NULL THEN
        RETURN jsonb_build_object('send', false, 'reason', '아직 아무것도 모른다');
    END IF;
    RETURN jsonb_build_object('send', false, 'reason', '알릴 만한 것이 없다');
END;
$fn$;


-- 여행을 받는 판단. 「이미 말했다」를 그 여행 안에서만 본다.
CREATE OR REPLACE FUNCTION dining.notice_decision(
    p_place_uid uuid,
    p_target_at timestamptz,
    p_trial     boolean,
    p_tenant_id text,
    p_trip_id   uuid
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $fn$
BEGIN
    IF EXISTS (SELECT 1 FROM dining.dn_notice n
                WHERE n.place_uid = p_place_uid AND n.target_at = p_target_at
                  AND n.tenant_id IS NOT DISTINCT FROM p_tenant_id
                  AND n.trip_id   IS NOT DISTINCT FROM p_trip_id) THEN
        RETURN jsonb_build_object('send', false, 'reason', '이미 말했다');
    END IF;
    RETURN dining.notice_content(p_place_uid, p_trial);
END;
$fn$;

COMMENT ON FUNCTION dining.notice_decision(uuid, timestamptz, boolean, text, uuid) IS
    '여행 하나에 대해 말할 것인가. 다른 여행에 이미 한 말은 이 여행을 막지 않는다.';


-- 여행을 받는 기록. 충돌 대상은 dn_notice_once_per_trip 이다.
CREATE OR REPLACE FUNCTION dining.record_notice(
    p_place_uid uuid,
    p_target_at timestamptz,
    p_kind      text,
    p_body      text,
    p_based_on  text,
    p_tenant_id text,
    p_trip_id   uuid
)
RETURNS uuid
LANGUAGE sql
AS $fn$
    INSERT INTO dining.dn_notice (place_uid, target_at, kind, body, based_on, tenant_id, trip_id)
    VALUES (p_place_uid, p_target_at, p_kind, p_body, p_based_on, p_tenant_id, p_trip_id)
    ON CONFLICT DO NOTHING
    RETURNING notice_id
$fn$;

COMMENT ON FUNCTION dining.record_notice(uuid, timestamptz, text, text, text, text, uuid) IS
    '여행 하나에 보냈다는 사실을 적는다. 같은 여행의 두 번째는 NULL. 알림함 넣기와 같은 트랜잭션에서 부른다.';

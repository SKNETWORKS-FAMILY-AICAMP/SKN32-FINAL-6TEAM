-- 현장 확인 (제휴 전제 시험 구현)
-- 작성 2026-09-21.
--
-- 무엇인가.
--   일정이 틀어져 대체 후보를 고를 때, 그 한 곳만 실제로 확인해 보는 길이다.
--   200곳을 순회하지 않는다. 필요한 순간에 필요한 곳만 본다.
--
-- 왜 DB 에 두는가.
--   확인 자체는 밖에서 한다. 여기 두는 것은 셋뿐이다.
--     1. 무엇을 물어야 하는지      check_prompt()
--     2. 돌아온 답을 어디에 쌓을지  dn_live_check
--     3. 그 답을 언제까지 믿을지    live_ttl(), v_live_check_fresh
--   조회 수단을 DB 가 모르게 둔다. 나중에 공식 API 로 갈아끼울 때
--   바깥만 바꾸면 되고 판정 쪽은 건드리지 않는다.
--
-- 지키는 것.
--   조회는 더해주는 것이지 없으면 못 도는 것이 아니다.
--   실패하면 모름이다. 없음으로 바꾸지 않는다 (DN-C5).
--   운영 판정에 쓰지 않기로 한 출처의 답은 저장은 하되 판정 뷰에서 뺀다.


-- ──────────────────────────────────────────────────────────────
-- 출처 등록
-- ──────────────────────────────────────────────────────────────
--
-- auto_map_check 는 사람이 네이버를 열어 보던 일을 기계가 대신한 것이다.
-- 등급은 operator_check 아래, tourapi_kor_food 위다.
-- 눈으로 확인한 것보다는 덜 믿고, 원문 문자열보다는 더 믿는다.
--
-- catchtable_trial 은 빈자리와 웨이팅용이며 production_allowed 가 false 다.
-- 공식 접근 경로가 막혀 있어 제휴 전에는 운영 판정에 쓰지 않는다.
-- 시연에서는 켜되 화면과 발표에 「제휴 전제 시험 구현」이라고 적는다.

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('auto_map_check',   '지도 자동 확인',  'operator', 'content', true,
     '사람의 확인을 기계가 대신한다. 유효기간이 짧다.'),
    ('catchtable_trial', '캐치테이블 시험', 'operator', 'content', false,
     '제휴 전제 시험 구현. 운영 판정에 쓰지 않는다.')
ON CONFLICT (source_code) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       source_kind = EXCLUDED.source_kind,
       storage_mode = EXCLUDED.storage_mode,
       production_allowed = EXCLUDED.production_allowed,
       note = EXCLUDED.note;


-- ──────────────────────────────────────────────────────────────
-- 확인 한 건
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dining.dn_live_check (
    check_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid    uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    source_code  text NOT NULL REFERENCES dining.dn_source(source_code),
    topic        text NOT NULL,
    asked_at     timestamptz NOT NULL DEFAULT now(),
    target_at    timestamptz,
    outcome      text NOT NULL,
    value_state  text NOT NULL,
    value_num    integer,
    value_detail text,
    evidence     text,
    ttl_seconds  integer NOT NULL,
    checked_by   text NOT NULL,
    CONSTRAINT dn_live_check_topic_chk
        CHECK (topic IN ('hours', 'closure', 'vacancy', 'waiting')),
    CONSTRAINT dn_live_check_outcome_chk
        CHECK (outcome IN ('ok', 'not_found', 'blocked', 'timeout', 'error')),
    CONSTRAINT dn_live_check_state_chk
        CHECK (value_state IN ('yes', 'no', 'unknown')),
    -- 확인에 실패했는데 값이 있다고 적는 것을 막는다. 모름은 모름이다.
    CONSTRAINT dn_live_check_fail_is_unknown_chk
        CHECK (outcome = 'ok' OR value_state = 'unknown'),
    CONSTRAINT dn_live_check_num_chk
        CHECK (value_num IS NULL OR value_num >= 0),
    CONSTRAINT dn_live_check_ttl_chk
        CHECK (ttl_seconds BETWEEN 60 AND 604800)
);

COMMENT ON TABLE dining.dn_live_check IS
    '현장 확인 한 번의 결과. 규칙이 아니라 관측이므로 dn_hours_rule 과 섞지 않는다.';
COMMENT ON COLUMN dining.dn_live_check.outcome IS
    '조회가 성립했는가. ok 가 아니면 value_state 는 반드시 unknown 이다.';
COMMENT ON COLUMN dining.dn_live_check.value_num IS
    '웨이팅 팀 수처럼 수로 답하는 것에만 쓴다. 0 은 대기 없음이며 모름이 아니다.';
COMMENT ON COLUMN dining.dn_live_check.ttl_seconds IS
    '이 관측을 언제까지 믿을지. 빈자리는 분 단위, 영업시간은 하루다.';

CREATE INDEX IF NOT EXISTS dn_live_check_lookup_idx
    ON dining.dn_live_check (place_uid, topic, asked_at DESC);


-- 주제별 유효기간
-- 빈자리는 금방 뒤집힌다. 영업시간은 하루쯤 간다.
CREATE OR REPLACE FUNCTION dining.live_ttl(p_topic text)
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE p_topic
             WHEN 'hours'   THEN 86400
             WHEN 'closure' THEN 86400
             WHEN 'vacancy' THEN 300
             WHEN 'waiting' THEN 300
             ELSE 300
           END
$fn$;


-- 아직 믿을 수 있는 관측만
-- 운영 판정에 쓰지 않기로 한 출처는 여기서 뺀다.
-- 저장은 되어 있으므로 시연 화면은 표를 직접 읽으면 된다.
CREATE OR REPLACE VIEW dining.v_live_check_fresh AS
SELECT c.*
FROM dining.dn_live_check c
JOIN dining.dn_source s ON s.source_code = c.source_code
WHERE s.production_allowed
  AND c.outcome = 'ok'
  AND c.asked_at + make_interval(secs => c.ttl_seconds) > now();

COMMENT ON VIEW dining.v_live_check_fresh IS
    '판정에 쓸 수 있는 관측만. 시험 출처와 실패한 조회와 기한이 지난 것을 뺀다.';


-- ──────────────────────────────────────────────────────────────
-- 무엇을 물을 것인가
-- ──────────────────────────────────────────────────────────────
--
-- DB 가 아는 것으로 판정을 마치고, 남은 물음만 밖으로 넘긴다.
-- 이미 확인한 것은 다시 묻지 않는다.

CREATE OR REPLACE FUNCTION dining.check_prompt(
    p_place_uid uuid,
    p_starts_at timestamptz,
    p_include_vacancy boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $fn$
    WITH want AS (
        -- 명절이 끼면 영업시간과 휴무 둘 다 흔들린다
        SELECT 'closure' AS topic
         WHERE dining.needs_holiday_check(p_place_uid, p_starts_at)
        UNION
        SELECT 'hours'
         WHERE dining.needs_holiday_check(p_place_uid, p_starts_at)
            OR dining.open_at_slot(p_place_uid, p_starts_at,
                                   p_starts_at + interval '1 hour') IS NULL
        UNION
        SELECT 'vacancy' WHERE p_include_vacancy
        UNION
        SELECT 'waiting' WHERE p_include_vacancy
    ),
    todo AS (
        -- 기한 안에 이미 답이 있는 것은 다시 묻지 않는다
        SELECT w.topic FROM want w
        WHERE NOT EXISTS (SELECT 1 FROM dining.v_live_check_fresh f
                           WHERE f.place_uid = p_place_uid AND f.topic = w.topic)
    ),
    ask AS (
        SELECT array_agg(topic ORDER BY topic) AS topics FROM todo
    )
    SELECT CASE WHEN a.topics IS NULL THEN NULL ELSE
        jsonb_build_object(
          'place_uid', p_place_uid,
          'name',      (SELECT name_ko FROM dining.dn_place WHERE place_uid = p_place_uid),
          'target_at', p_starts_at,
          'topics',    to_jsonb(a.topics),
          'timeout_seconds', 8,
          'sentence',  concat_ws(' ',
                         dining.search_query(p_place_uid),
                         to_char(p_starts_at AT TIME ZONE 'Asia/Seoul', 'MM월 DD일 HH24시'),
                         '기준으로',
                         (SELECT string_agg(
                            CASE t WHEN 'hours'   THEN '영업시간'
                                   WHEN 'closure' THEN '휴무 여부'
                                   WHEN 'vacancy' THEN '지금 빈자리'
                                   WHEN 'waiting' THEN '현장 웨이팅'
                            END, ', ' ORDER BY t)
                            FROM unnest(a.topics) AS t),
                         '확인해줘.'))
        || coalesce(dining.map_links(p_place_uid), '{}'::jsonb)
      END
    FROM ask a
$fn$;

COMMENT ON FUNCTION dining.check_prompt IS
    '물을 것이 없으면 NULL 이다. sentence 는 사람이 읽어도 되고 확인기에 그대로 넣어도 된다.';


-- ──────────────────────────────────────────────────────────────
-- 답을 받는다
-- ──────────────────────────────────────────────────────────────
--
-- 확인기가 실패해도 이 함수는 성공한다. 실패를 실패로 적는 것도 기록이다.
-- 같은 곳에 계속 매달리지 않으려면 실패도 남아 있어야 한다.

CREATE OR REPLACE FUNCTION dining.record_live_check(
    p_place_uid    uuid,
    p_source_code  text,
    p_topic        text,
    p_outcome      text,
    p_value_state  text DEFAULT 'unknown',
    p_value_num    integer DEFAULT NULL,
    p_value_detail text DEFAULT NULL,
    p_evidence     text DEFAULT NULL,
    p_target_at    timestamptz DEFAULT NULL,
    p_checked_by   text DEFAULT 'auto'
)
RETURNS uuid
LANGUAGE plpgsql
AS $fn$
DECLARE
    v_id uuid;
    v_state text := p_value_state;
BEGIN
    -- 조회가 성립하지 않았으면 값이 무엇으로 왔든 모름으로 적는다
    IF p_outcome <> 'ok' THEN
        v_state := 'unknown';
    END IF;

    INSERT INTO dining.dn_live_check
        (place_uid, source_code, topic, target_at, outcome, value_state,
         value_num, value_detail, evidence, ttl_seconds, checked_by)
    VALUES
        (p_place_uid, p_source_code, p_topic, p_target_at, p_outcome, v_state,
         CASE WHEN p_outcome = 'ok' THEN p_value_num END,
         p_value_detail, left(p_evidence, 500),
         -- 실패는 짧게만 기억한다. 한 번 막혔다고 하루를 포기하지 않는다.
         CASE WHEN p_outcome = 'ok' THEN dining.live_ttl(p_topic) ELSE 120 END,
         p_checked_by)
    RETURNING check_id INTO v_id;

    RETURN v_id;
END;
$fn$;

COMMENT ON FUNCTION dining.record_live_check IS
    '확인기가 실패해도 이 함수는 성공한다. 실패를 실패로 적는 것도 기록이다.';


-- 관측 한 줄 읽기
-- 없으면 NULL 이다. 부르는 쪽은 NULL 을 모름으로 다루면 된다.
CREATE OR REPLACE FUNCTION dining.live_state(
    p_place_uid uuid,
    p_topic     text
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $fn$
    SELECT jsonb_build_object(
             'state',      f.value_state,
             'num',        f.value_num,
             'detail',     f.value_detail,
             'source',     f.source_code,
             'checked_at', f.asked_at,
             'expires_at', f.asked_at + make_interval(secs => f.ttl_seconds))
    FROM dining.v_live_check_fresh f
    WHERE f.place_uid = p_place_uid AND f.topic = p_topic
    ORDER BY f.asked_at DESC
    LIMIT 1
$fn$;

COMMENT ON FUNCTION dining.live_state IS
    'NULL 은 확인한 적이 없거나 기한이 지났다는 뜻이며, 닫혔다는 뜻이 아니다.';

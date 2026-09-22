-- 031  시험 갈래를 본 갈래에서 가른다
--
-- 026 은 갈래가 하나였다. 「판정에 쓸 수 있는 관측」 하나로 두 가지 일을
-- 동시에 했고, 그래서 둘 다 어긋났다.
--
--   1  시험 출처(catchtable_trial)의 답은 어디에도 닿지 않았다.
--      제휴 전 본 서비스에서는 그것이 맞다. 그러나 시험 구현에서는
--      웨이팅 41팀을 읽어 놓고도 쓰지 못한다는 뜻이었다.
--
--   2  더 나쁜 것. 「다시 물어야 하나」를 같은 뷰로 판단했다.
--      그 뷰는 production_allowed 와 outcome='ok' 를 요구하므로
--      시험 출처의 답도, 실패한 조회도 영영 「안 물었다」로 남는다.
--      사람이 손으로 도는 동안은 드러나지 않지만, 감시 틱에 물리는 순간
--      같은 곳을 끝없이 다시 묻는다. 실패를 짧게 기억하려고 둔 120초 TTL 이
--      억제에 한 번도 쓰이지 않고 있었다.
--
-- 그래서 셋으로 가른다. 물음의 성격이 다르면 범위도 달라야 한다.
--
--   판정(본)   v_live_check_fresh        좁게.  건드리지 않는다
--   판정(시험) v_live_check_fresh_trial  출처 등급을 묻지 않는다
--   조회       v_live_check_asked        넓게.  성패도 출처도 가리지 않는다
--
-- 본 갈래의 판정은 이 파일에서 한 글자도 바뀌지 않는다.

BEGIN;

-- ──────────────────────────────────────────────────────────────
-- 시험 갈래의 판정
-- ──────────────────────────────────────────────────────────────
--
-- 본 갈래와 다른 점은 하나다. 출처 등급을 묻지 않는다.
-- 기한과 성패는 그대로 따진다. 시험이라고 해서 낡은 값이나 실패한 조회를
-- 값으로 쓰지는 않는다.

CREATE OR REPLACE VIEW dining.v_live_check_fresh_trial AS
SELECT c.*
FROM dining.dn_live_check c
WHERE c.outcome = 'ok'
  AND c.asked_at + make_interval(secs => c.ttl_seconds) > now();

COMMENT ON VIEW dining.v_live_check_fresh_trial IS
    '시험 갈래의 판정용. 출처 등급을 묻지 않는다. 기한과 성패는 그대로 따진다.';


-- ──────────────────────────────────────────────────────────────
-- 다시 물어야 하나
-- ──────────────────────────────────────────────────────────────
--
-- 조회는 돈과 남의 서버를 쓴다. 그래서 판정보다 넓게 잡는다.
-- 막혔든 터졌든 시험 출처든, 최근에 물었으면 또 묻지 않는다.
-- 실패한 조회의 TTL 은 120초라 곧 풀린다. 영영 막는 것이 아니라 잠깐 쉰다.

CREATE OR REPLACE VIEW dining.v_live_check_asked AS
SELECT c.*
FROM dining.dn_live_check c
WHERE c.asked_at + make_interval(secs => c.ttl_seconds) > now();

COMMENT ON VIEW dining.v_live_check_asked IS
    '최근에 물어본 것. 판정이 아니라 재질문을 막는 데 쓴다.';


-- ──────────────────────────────────────────────────────────────
-- 관측 한 줄 읽기 — 갈래를 고를 수 있게
-- ──────────────────────────────────────────────────────────────
--
-- 026 의 두 칸짜리를 지우고 세 칸짜리로 다시 만든다. 기본값이 false 라
-- 예전처럼 두 칸으로 부르던 곳은 그대로 본 갈래를 본다.
-- 같은 이름의 두 칸짜리를 남겨 두면 어느 것을 부를지 정해지지 않는다.

DROP FUNCTION IF EXISTS dining.live_state(uuid, text);

CREATE OR REPLACE FUNCTION dining.live_state(
    p_place_uid uuid,
    p_topic     text,
    p_trial     boolean DEFAULT false
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
             'trial',      p_trial,
             'checked_at', f.asked_at,
             'expires_at', f.asked_at + make_interval(secs => f.ttl_seconds))
    FROM (
        SELECT * FROM dining.v_live_check_fresh       WHERE NOT p_trial
        UNION ALL
        SELECT * FROM dining.v_live_check_fresh_trial WHERE p_trial
    ) f
    WHERE f.place_uid = p_place_uid AND f.topic = p_topic
    ORDER BY f.asked_at DESC
    LIMIT 1
$fn$;

COMMENT ON FUNCTION dining.live_state IS
    '없으면 NULL 이다. p_trial 이 참이면 시험 출처까지 본다. 기본은 본 갈래다.';


-- ──────────────────────────────────────────────────────────────
-- 무엇을 물을 것인가 — 재질문만 고친다
-- ──────────────────────────────────────────────────────────────
--
-- 026 과 같되 todo 가 보는 뷰가 다르다. 무엇을 물을지 고르는 규칙은
-- 그대로이고, 「이미 물었나」의 기준만 넓어진다.

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
        -- 최근에 물어본 것은 답이 무엇이었든 다시 묻지 않는다.
        -- 판정에 쓸 수 있느냐와 또 물어야 하느냐는 다른 물음이다.
        SELECT w.topic FROM want w
        WHERE NOT EXISTS (SELECT 1 FROM dining.v_live_check_asked f
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
    '물을 것이 없으면 NULL 이다. 최근에 물어본 주제는 답이 무엇이었든 빠진다.';

COMMIT;

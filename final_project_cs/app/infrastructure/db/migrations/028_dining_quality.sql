-- 품질 측정 (설계 v3 의 D-08)
-- 작성 2026-09-22.
--
-- 왜 필요한가.
--   고쳤는데 좋아졌는지 말할 수 없으면 고친 것이 아니다.
--   실행 로그만으로는 알 수 없다. 입력이 매번 달라서 어제 8% 오늘 6% 가
--   고쳐서인지 쉬운 자료가 들어와서인지 구분되지 않는다.
--   같은 입력에 버전만 바꿔 돌려야 차이가 개선이 된다.
--
-- 그래서 셋으로 나눈다.
--   dn_truth           정답. 고정이며 사람이 확인한 것만 들어온다
--   dn_quality_run     실행 한 번. 버전이 붙는다
--   dn_quality_result  그 실행의 건별 결과
--
-- 지표 둘을 섞지 않는다.
--   parse    원문을 제대로 읽었는가.   우리가 고칠 수 있다
--   reality  원문이 실제와 맞는가.     우리가 고칠 수 없다
--   한 표에 두되 metric 으로 가른다. 섞으면 관광공사가 틀린 것이
--   우리 오류율로 들어온다.
--
-- 모름을 틀림으로 세지 않는다.
--   정답이 없거나 판정이 unknown 인 건은 분모에서 뺀다.
--   그러지 않으면 정답을 늘릴수록 점수가 떨어지는 일이 생긴다.


-- ──────────────────────────────────────────────────────────────
-- 정답 한 건
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dining.dn_truth (
    truth_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid    uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    metric       text NOT NULL,
    check_kind   text NOT NULL,
    check_key    text NOT NULL DEFAULT '',
    expected     jsonb NOT NULL,
    source_text  text,
    evidence     text NOT NULL,
    entered_by   text NOT NULL,
    verified_at  timestamptz NOT NULL,
    note         text,
    retired_at   timestamptz,
    CONSTRAINT dn_truth_metric_chk CHECK (metric IN ('parse', 'reality')),
    CONSTRAINT dn_truth_kind_chk CHECK (check_kind IN (
        'weekday_hours', 'break', 'last_order', 'closure',
        'record_status', 'attribute', 'open_at')),
    CONSTRAINT dn_truth_one UNIQUE (place_uid, metric, check_kind, check_key)
);

COMMENT ON TABLE dining.dn_truth IS
    '사람이 확인한 정답만 들어온다. 추측은 넣지 않는다. 넣을 수 없으면 행을 만들지 않는다.';
COMMENT ON COLUMN dining.dn_truth.metric IS
    'parse 는 원문을 제대로 읽었는가, reality 는 원문이 실제와 맞는가. 섞어 세지 않는다.';
COMMENT ON COLUMN dining.dn_truth.evidence IS
    '무엇을 보고 정했는지. 네이버 지도, 전화 확인, 원문 재독 같은 것.';

CREATE INDEX IF NOT EXISTS dn_truth_lookup_idx
    ON dining.dn_truth (metric, check_kind) WHERE retired_at IS NULL;


-- ──────────────────────────────────────────────────────────────
-- 실행 한 번
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dining.dn_quality_run (
    run_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rules_version text NOT NULL,
    metric        text NOT NULL,
    tool          text NOT NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    note          text,
    CONSTRAINT dn_quality_run_metric_chk CHECK (metric IN ('parse', 'reality'))
);

COMMENT ON COLUMN dining.dn_quality_run.rules_version IS
    'dn_hours_rule.rules_version 과 같은 문자열. 이 값이 안 바뀌면 비교할 것이 없다.';


CREATE TABLE IF NOT EXISTS dining.dn_quality_result (
    run_id   uuid NOT NULL REFERENCES dining.dn_quality_run(run_id) ON DELETE CASCADE,
    truth_id uuid NOT NULL REFERENCES dining.dn_truth(truth_id),
    actual   jsonb,
    verdict  text NOT NULL,
    detail   text,
    PRIMARY KEY (run_id, truth_id),
    CONSTRAINT dn_quality_result_verdict_chk
        CHECK (verdict IN ('match', 'mismatch', 'unknown'))
);

COMMENT ON COLUMN dining.dn_quality_result.verdict IS
    'unknown 은 판정이 나오지 않았다는 뜻이며 틀렸다는 뜻이 아니다. 분모에서 뺀다.';


-- ──────────────────────────────────────────────────────────────
-- 집계
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW dining.v_quality_summary AS
SELECT r.rules_version,
       r.metric,
       r.started_at,
       r.run_id,
       count(*)                                        AS 정답건수,
       count(*) FILTER (WHERE q.verdict = 'match')      AS 맞음,
       count(*) FILTER (WHERE q.verdict = 'mismatch')   AS 틀림,
       count(*) FILTER (WHERE q.verdict = 'unknown')    AS 모름,
       -- 모름은 분모에서 뺀다
       round(100.0 * count(*) FILTER (WHERE q.verdict = 'match')
             / nullif(count(*) FILTER (WHERE q.verdict <> 'unknown'), 0), 1) AS 정확도
FROM dining.dn_quality_run r
JOIN dining.dn_quality_result q ON q.run_id = r.run_id
GROUP BY r.run_id, r.rules_version, r.metric, r.started_at;

COMMENT ON VIEW dining.v_quality_summary IS
    '정확도의 분모는 판정이 난 건수다. 모름을 틀림으로 세면 정답을 늘릴수록 점수가 떨어진다.';


-- 두 버전 사이에 무엇이 바뀌었나
-- 총량만 보면 고친 것과 깨진 것이 상쇄되어 보이지 않는다.
CREATE OR REPLACE FUNCTION dining.quality_delta(
    p_prev text,
    p_cur  text,
    p_metric text DEFAULT 'parse'
)
RETURNS TABLE (
    change     text,
    name_ko    text,
    check_kind text,
    check_key  text,
    prev       text,
    cur        text,
    expected   jsonb,
    actual_cur jsonb
)
LANGUAGE sql
STABLE
AS $fn$
    WITH last_run AS (
        SELECT DISTINCT ON (rules_version) rules_version, run_id
        FROM dining.dn_quality_run
        WHERE metric = p_metric AND rules_version IN (p_prev, p_cur)
        ORDER BY rules_version, started_at DESC
    ),
    a AS (SELECT q.* FROM dining.dn_quality_result q
          JOIN last_run l ON l.run_id = q.run_id WHERE l.rules_version = p_prev),
    b AS (SELECT q.* FROM dining.dn_quality_result q
          JOIN last_run l ON l.run_id = q.run_id WHERE l.rules_version = p_cur)
    SELECT CASE
             -- 모름은 맞음도 틀림도 아니다. 먼저 갈라낸다.
             WHEN a.verdict = 'unknown' AND b.verdict = 'unknown'               THEN '그대로 모름'
             WHEN a.verdict = 'unknown' AND b.verdict = 'match'                 THEN '모름에서 맞음'
             WHEN a.verdict = 'unknown' AND b.verdict = 'mismatch'              THEN '모름에서 틀림'
             WHEN a.verdict = 'match'    AND b.verdict = 'unknown'              THEN '맞음에서 모름'
             WHEN a.verdict = 'mismatch' AND b.verdict = 'unknown'              THEN '틀림에서 모름'
             WHEN a.verdict = 'mismatch' AND b.verdict = 'match'                THEN '고쳐짐'
             WHEN a.verdict = 'match'    AND b.verdict = 'mismatch'             THEN '깨짐'
             WHEN a.verdict = 'match'                                           THEN '그대로 맞음'
             WHEN a.verdict IS NULL OR b.verdict IS NULL                        THEN '한쪽만 봄'
             ELSE '그대로 틀림'
           END,
           p.name_ko, t.check_kind, t.check_key,
           coalesce(a.verdict, '(없음)'), coalesce(b.verdict, '(없음)'),
           t.expected, b.actual
    FROM dining.dn_truth t
    JOIN dining.dn_place p ON p.place_uid = t.place_uid
    LEFT JOIN a ON a.truth_id = t.truth_id
    LEFT JOIN b ON b.truth_id = t.truth_id
    WHERE t.retired_at IS NULL AND t.metric = p_metric
      AND (a.truth_id IS NOT NULL OR b.truth_id IS NOT NULL)
    ORDER BY 1, p.name_ko
$fn$;

COMMENT ON FUNCTION dining.quality_delta IS
    '깨진 것을 먼저 본다. 고친 셋과 깨진 하나는 총량으로는 상쇄되어 보이지 않는다.';


-- 아직 정답이 없는 곳
-- 정답셋을 어디부터 늘려야 하는지 알려준다.
CREATE OR REPLACE VIEW dining.v_truth_gap AS
SELECT p.place_uid, p.name_ko, p.area,
       (SELECT count(*) FROM dining.dn_truth t
         WHERE t.place_uid = p.place_uid AND t.retired_at IS NULL) AS 정답수,
       EXISTS (SELECT 1 FROM dining.v_hours_rule_active r
                WHERE r.place_uid = p.place_uid) AS 규칙있음
FROM dining.dn_place p
ORDER BY 4, p.area, p.name_ko;

-- 특이사항 한 줄
-- 작성 2026-09-22.
--
-- 후보를 보여줄 때 「이 집은 이런 점을 알아두세요」를 붙인다.
-- 판정은 여는가 아닌가만 답하는데, 사람이 실제로 알고 싶은 것은 그보다 많다.
--
-- 지어내지 않는다.
--   메모마다 근거가 있어야 한다. 근거가 없으면 그 메모는 만들지 않는다.
--   「오전 11시쯤이 한가합니다」 같은 말은 혼잡도 자료가 있어야 할 수 있다.
--   표본 200곳의 원문에 혼잡·대기·붐빔 표현은 0건이었다. 그래서 쓰지 않는다.
--
-- 무엇으로 만드는가 (전부 원장에 있는 것)
--   라스트오더   98곳에 값이 있다
--   브레이크     연속한 두 구간 사이
--   대표메뉴     관광공사 firstmenu
--   요일 차이    요일마다 구간이 다른 곳
--   자정 넘김    close_min 이 1440 이상
--   매장 속성    카드·주차·포장 중 확인된 것
--   명절         holiday_context
--   원문 문구    구조로 담지 못했지만 사람에게 쓸모 있는 말
--
-- 방문 시각에 따라 달라진다.
--   같은 집이라도 열자마자 가는 것과 마감 직전에 가는 것은 알아야 할 것이 다르다.


-- 원문에서 구조로 담지 못한 쓸모 있는 문구
-- 표본에 많지는 않다. 「재료 소진 시 마감」 한 곳, 「문의」 한 곳이다.
-- 적지만 이런 문구는 사람이 꼭 알아야 하는 것이라 흘리지 않는다.
CREATE OR REPLACE FUNCTION dining.source_notes(p_place_uid uuid)
RETURNS text[]
LANGUAGE sql
STABLE
AS $fn$
    WITH t AS (
        SELECT regexp_replace(
                 coalesce(sr.raw_json ->> 'opentimefood', '') || ' ' ||
                 coalesce(sr.raw_json ->> 'restdatefood', ''),
                 '<[^>]+>', ' ', 'g') AS txt
        FROM dining.dn_source_record sr
        WHERE sr.place_uid = p_place_uid
        LIMIT 1
    ),
    hit AS (
        SELECT '재료가 떨어지면 일찍 닫을 수 있다' AS note FROM t
         WHERE txt ~ '소진|재료.*마감|조기.*마감|떨어지면'
        UNION ALL
        SELECT '방문 전 전화로 확인하라고 적혀 있다' FROM t
         WHERE txt ~ '문의'
        UNION ALL
        SELECT '예약이 필요할 수 있다' FROM t
         WHERE txt ~ '예약.*필수|사전.*예약|예약제'
        UNION ALL
        SELECT '영업시간이 바뀔 수 있다고 적혀 있다' FROM t
         WHERE txt ~ '변동|유동|상이|다를 수'
    )
    SELECT array_agg(note) FROM hit
$fn$;

COMMENT ON FUNCTION dining.source_notes IS
    '원문에 있는 말만 옮긴다. 없는 말을 만들지 않는다.';


-- 그 시각 그 집에 붙일 메모
-- 각 메모는 text 와 kind 와 source 를 갖는다. 근거 없이 뜨는 줄이 없어야 한다.
CREATE OR REPLACE FUNCTION dining.place_notes(
    p_place_uid uuid,
    p_starts_at timestamptz,
    p_limit int DEFAULT 4
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $fn$
DECLARE
    v_date   date;
    v_min    int;
    v_notes  jsonb := '[]'::jsonb;
    v_row    record;
    v_txt    text;
BEGIN
    v_date := (p_starts_at AT TIME ZONE 'Asia/Seoul')::date;
    v_min  := EXTRACT(HOUR   FROM p_starts_at AT TIME ZONE 'Asia/Seoul')::int * 60
            + EXTRACT(MINUTE FROM p_starts_at AT TIME ZONE 'Asia/Seoul')::int;

    -- 1. 마감이 임박했는가. 방문 시각에 가장 먼저 알아야 할 것이다.
    SELECT max(close_min) AS close_min,
           max(last_order_min) FILTER (WHERE last_order_state = 'present') AS lo
      INTO v_row
      FROM dining.day_intervals(p_place_uid, v_date)
     WHERE v_min >= open_min AND v_min <= close_min;

    IF v_row.lo IS NOT NULL THEN
        v_notes := v_notes || jsonb_build_object(
            'kind', 'last_order', 'source', 'ledger',
            'text', dining.min_to_hhmm(v_row.lo::smallint) || ' 라스트오더. 그 전에 주문해야 한다');
    ELSIF v_row.close_min IS NOT NULL AND v_row.close_min - v_min <= 60 THEN
        -- 라스트오더 값이 없을 때만 쓴다. 있으면 위 줄이 더 정확하다.
        v_notes := v_notes || jsonb_build_object(
            'kind', 'closing_soon', 'source', 'ledger',
            'text', dining.min_to_hhmm(v_row.close_min::smallint)
                    || ' 마감. 라스트오더는 적혀 있지 않아 더 이를 수 있다');
    END IF;

    -- 2. 명절. 아예 다른 시간에 열거나 닫을 수 있다.
    --    마감 다음으로 급하다. 뒤로 밀면 네 줄 제한에 잘려 나간다.
    IF dining.needs_holiday_check(p_place_uid, p_starts_at) THEN
        v_notes := v_notes || jsonb_build_object(
            'kind', 'holiday', 'source', 'ledger',
            'text', '명절이나 공휴일이라 영업시간이 다를 수 있다');
    END IF;

    -- 3. 브레이크타임. 그 시간에 가면 헛걸음한다.
    SELECT a.close_min AS starts, b.open_min AS ends INTO v_row
      FROM dining.day_intervals(p_place_uid, v_date) a
      JOIN dining.day_intervals(p_place_uid, v_date) b ON b.seq = a.seq + 1
     LIMIT 1;
    IF v_row.starts IS NOT NULL THEN
        v_notes := v_notes || jsonb_build_object(
            'kind', 'break', 'source', 'ledger',
            'text', dining.min_to_hhmm(v_row.starts::smallint) || '~'
                    || dining.min_to_hhmm(v_row.ends::smallint) || ' 는 브레이크타임이다');
    END IF;

    -- 4. 자정을 넘기는가. 늦은 일정에서만 쓸모 있다.
    IF EXISTS (SELECT 1 FROM dining.day_intervals(p_place_uid, v_date)
                WHERE close_min > 1440) AND v_min >= 1200 THEN
        SELECT max(close_min) INTO v_row
          FROM dining.day_intervals(p_place_uid, v_date) WHERE close_min > 1440;
        v_notes := v_notes || jsonb_build_object(
            'kind', 'past_midnight', 'source', 'ledger',
            'text', '자정을 넘겨 ' || dining.min_to_hhmm((v_row.max - 1440)::smallint)
                    || ' 까지 한다');
    END IF;

    -- 5. 원문에 있던 말. 구조로 담지 못했지만 사람에게 쓸모 있다.
    FOR v_txt IN SELECT unnest(dining.source_notes(p_place_uid)) LOOP
        v_notes := v_notes || jsonb_build_object(
            'kind', 'source_note', 'source', 'tourapi_kor_food', 'text', v_txt);
    END LOOP;

    -- 6. 요일마다 다른가. 다른 날로 옮길 때 헷갈리는 지점이다.
    IF (SELECT count(DISTINCT (open_min, close_min))
          FROM dining.dn_hours_rule r
          JOIN dining.dn_hours_interval i ON i.rule_id = r.rule_id
         WHERE r.place_uid = p_place_uid AND r.retired_at IS NULL AND i.seq = 1) > 1 THEN
        v_notes := v_notes || jsonb_build_object(
            'kind', 'weekday_varies', 'source', 'ledger',
            'text', '요일마다 영업시간이 다르다');
    END IF;

    -- 7. 못 가게 만드는 속성. 「불가」로 확인된 것만 쓴다.
    --    가능한 것을 일일이 적으면 줄만 늘고 읽히지 않는다.
    FOR v_txt IN
        SELECT CASE a.attr_code
                 WHEN 'card_payment' THEN '카드를 받지 않는다고 되어 있다'
                 WHEN 'parking'      THEN '주차할 곳이 없다'
                 WHEN 'takeout'      THEN '포장이 되지 않는다'
               END
          FROM dining.v_attribute_active a
         WHERE a.place_uid = p_place_uid AND a.value_state = 'no'
           AND a.attr_code IN ('card_payment', 'parking', 'takeout')
    LOOP
        v_notes := v_notes || jsonb_build_object(
            'kind', 'attribute', 'source', 'ledger', 'text', v_txt);
    END LOOP;

    -- 8. 대표메뉴. 무엇을 먹을지 고르는 재료다.
    SELECT trim(split_part(sr.raw_json ->> 'firstmenu', '/', 1)) INTO v_txt
      FROM dining.dn_source_record sr
     WHERE sr.place_uid = p_place_uid AND sr.raw_json ->> 'firstmenu' <> ''
     LIMIT 1;
    IF v_txt IS NOT NULL AND v_txt <> '' THEN
        v_notes := v_notes || jsonb_build_object(
            'kind', 'menu', 'source', 'tourapi_kor_food',
            'text', '대표메뉴 ' || v_txt);
    END IF;

    -- 많이 보여 줄수록 안 읽힌다. 앞에서부터 자른다.
    -- 차례가 곧 중요도다. 마감이 제일 급하고 메뉴가 제일 한가하다.
    RETURN (SELECT jsonb_agg(x) FROM (
              SELECT x FROM jsonb_array_elements(v_notes) x LIMIT p_limit) t);
END;
$fn$;

COMMENT ON FUNCTION dining.place_notes IS
    '메모마다 근거가 있다. 혼잡도처럼 자료가 없는 것은 만들지 않는다. 차례가 곧 중요도다.';

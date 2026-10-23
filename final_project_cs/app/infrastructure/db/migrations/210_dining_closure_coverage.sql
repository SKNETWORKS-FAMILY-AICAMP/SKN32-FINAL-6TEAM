-- 휴무를 어디까지 아는가
-- 작성 2026-09-22.
--
-- 무엇이 문제였나.
--   휴무 규칙이 없는 것과 쉬는 날이 없는 것을 구분하지 못했다.
--   표본 200곳에서 연중무휴 121곳과 원문 자체가 없는 3곳이 똑같이
--   「안 쉰다」로 답하고 있었다. 계절 휴무처럼 원문은 있는데 규칙으로
--   담지 못한 3곳도 같은 답을 냈다.
--
--   모름을 없음으로 바꾸지 않는다(DN-C5)는 원칙을 휴무에서만 어기고 있었다.
--   영업시간에는 coverage 가, 브레이크에는 break_state 가, 라스트오더에는
--   last_order_state 가 있는데 휴무에만 그 칸이 없었다.
--
-- 판정을 바꾸지는 않는다.
--   is_closed_on 은 그대로 불리언이다. 모름을 휴무로 만들면 멀쩡한 집이
--   후보에서 사라지고, 모름을 판정 전체로 번지게 하면 대안까지 모름이 되어
--   고를 것이 없어진다. 명절을 다루는 방식과 같다 — 판정은 두고 표시를 얹는다.

CREATE TABLE IF NOT EXISTS dining.dn_closure_coverage (
    place_uid   uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    source_code text NOT NULL REFERENCES dining.dn_source(source_code),
    record_id   uuid REFERENCES dining.dn_source_record(record_id),
    state       text NOT NULL,
    source_text text,
    note        text,
    valid_from  date NOT NULL,
    retired_at  timestamptz,
    PRIMARY KEY (place_uid, source_code),
    CONSTRAINT dn_closure_coverage_state_chk
        CHECK (state IN ('present', 'none', 'unknown'))
);

COMMENT ON TABLE dining.dn_closure_coverage IS
    '출처 하나가 휴무를 어디까지 말해 주는가. 규칙이 없다는 것과 쉬는 날이 없다는 것은 다르다.';
COMMENT ON COLUMN dining.dn_closure_coverage.state IS
    'present 규칙 있음 · none 연중무휴로 확인됨 · unknown 원문이 없거나 담지 못함.';


-- 이 장소의 휴무를 어디까지 아는가
-- 출처가 둘 이상이면 확인된 쪽을 먼저 본다. 사람이 넣은 것이 원문보다 낫다.
CREATE OR REPLACE FUNCTION dining.closure_state(p_place_uid uuid)
RETURNS text
LANGUAGE sql
STABLE
AS $fn$
    SELECT coalesce(
      -- 규칙이 실제로 있으면 적재 기록과 무관하게 present 다.
      (SELECT 'present' WHERE EXISTS (
          SELECT 1 FROM dining.v_closure_rule_active c
           WHERE c.place_uid = p_place_uid)),
      (SELECT cc.state
         FROM dining.dn_closure_coverage cc
         JOIN dining.dn_source s ON s.source_code = cc.source_code
        WHERE cc.place_uid = p_place_uid AND cc.retired_at IS NULL
        -- 사람이 확인한 출처를 먼저 본다
        ORDER BY (s.source_kind = 'operator') DESC, cc.valid_from DESC
        LIMIT 1),
      'unknown')
$fn$;


-- 휴무를 확인해야 하는가
-- 참이면 「정기 휴무가 있는지 모른다」는 뜻이다. 쉰다는 뜻이 아니다.
CREATE OR REPLACE FUNCTION dining.needs_closure_check(p_place_uid uuid)
RETURNS boolean
LANGUAGE sql
STABLE
AS $fn$
    SELECT dining.closure_state(p_place_uid) = 'unknown'
$fn$;

COMMENT ON FUNCTION dining.needs_closure_check IS
    '참은 모른다는 뜻이며 쉰다는 뜻이 아니다. 판정은 그대로 두고 확인만 권한다.';


-- 커버리지 한눈에
CREATE OR REPLACE VIEW dining.v_closure_coverage AS
SELECT dining.closure_state(p.place_uid) AS state,
       count(*) AS 장소수
FROM dining.dn_place p
GROUP BY 1;

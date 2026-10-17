-- 232 — 등록한 여행 고치기(수정 모드): 등록한 여행을 확인 화면 접수로 다시 연다 `[2026-10-13 사용자 결정]`
--
-- ★왜. 등록한 여행 화면의 「일정 수정」은 계획 확인 화면의 기능(시각 · 일정 추가 · 장소 바꾸기 · 자동 추천 · 잠금 · 이동 수단 · 되돌리기)을
--   그대로 쓴다. 그 계산은 모두 접수(`trip_intakes` · `intake_claims`)에 붙어 있어서, 등록한 여행을 접수로 다시 열고
--   「완료」 때 같은 여행의 새 판을 쓴다(계약 `wiki/external/rest-endpoints.md` 「등록한 여행 고치기」).
-- ☆재실행해도 안전하다.

-- 어느 여행의 몇 판을 다시 열었나 · 접수에 넣지 않고 그대로 두는 일정(끝난 일정 · 활동/식사가 아닌 일정 · 예약 표에 묶인 일정)
ALTER TABLE trip_intakes ADD COLUMN IF NOT EXISTS reopen_trip_id uuid;
ALTER TABLE trip_intakes ADD COLUMN IF NOT EXISTS reopen_version integer;
ALTER TABLE trip_intakes ADD COLUMN IF NOT EXISTS reopen_frozen jsonb NOT NULL DEFAULT '[]'::jsonb;

-- closed — 다시 연 뒤 여행 판이 바뀌어(채팅 · 감시) 새 수정 접수로 갈음한 것. 값은 지우지 않고 남긴다
ALTER TABLE trip_intakes DROP CONSTRAINT IF EXISTS trip_intakes_status_check;
ALTER TABLE trip_intakes ADD CONSTRAINT trip_intakes_status_check
    CHECK (status IN ('reading', 'review', 'confirmed', 'fatal', 'closed'));

-- trip — 등록한 여행에서 가져온 값(고객이 고친 값 `customer` 과 구별한다)
ALTER TABLE intake_claims DROP CONSTRAINT IF EXISTS intake_claims_method_check;
ALTER TABLE intake_claims ADD CONSTRAINT intake_claims_method_check
    -- 전체 SQL을 재실행하므로 후속 905가 허용한 llm_agent를 중간에 금지하지 않는다.
    CHECK (method IN ('rule', 'llm_span', 'lookup', 'customer', 'trip', 'llm_agent'));

-- 여행 하나에 열린 수정 접수는 하나 — 동시에 두 번 열어도 둘이 생기지 않는다
CREATE UNIQUE INDEX IF NOT EXISTS trip_intakes_reopen_open_idx
    ON trip_intakes (tenant_id, reopen_trip_id) WHERE reopen_trip_id IS NOT NULL AND status = 'review';

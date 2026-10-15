-- 240 — 숙소 · 항공 원장(확장 에이전트) (2026-10-12) — ★번호는 임시다. 05 코어 담당이 정한다(`wiki/records/plans/2026-10-05_브랜치별_미반영_파일/00_안내.md`).
--
-- 왜.
--   숙소 · 항공 팀의 후보는 MCP(마이리얼트립 · Ignav · 구글)에서 온다 — DB 에 없다. 그래서
--   ① 「보여 준 후보」를 기억할 자리가 일정 항목 상세(`detail.shown`)뿐이라 후보를 보여 줄 때마다 일정 판이 하나 오르고,
--   ② 고객이 고른 숙소가 장소 표(`places`)에 없어 일정 항목이 `place_id` 로 가리키지 못했다(적용기가 장소 표에 없는 id 를 거부).
--   요식 팀이 원장(`dining.*`)을 두고 후보를 그 여행 전용 장소로 들여놓는 것(`instances/dining/nearby.py`)과 같은 모양으로 둔다.
--
-- 경계(029 와 같은 이유).
--   외부 서비스에서 받은 값은 **그 여행에만** 둔다 — 다른 고객 · 다른 여행에 재사용하지 않는다. 그래서 두 표 모두 여행 id 를 열쇠에 넣는다.
--   코어 표에 쓰는 것은 코어(`TripStore.adopt_places` — 여행 전용 행)가 하고, 여기는 연결과 기록만 쓴다.
--
-- 재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS lg_offer_shown (
    tenant_id   text        NOT NULL,
    trip_id     uuid        NOT NULL,
    item_key    text        NOT NULL,   -- 숙소 'lodging:<체크인>:<체크아웃>' · 항공 'flight:<출발>-<도착>:<날짜>' (항목 id 는 판마다 바뀐다)
    offer_key   text        NOT NULL,   -- 후보 key(예 'myrealtrip:1105545' · 'google:<이름>' · '<항공사> <편명> <날짜> <시각>')
    name        text        NOT NULL,
    source      text,                   -- 마이리얼트립 · 구글 호텔 · 판매처 이름
    link        text,
    price       numeric,                -- 숙소 1박 · 항공 일행 총액(조회 시점 참고값)
    case_id     uuid,
    shown_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, trip_id, item_key, offer_key)
);

CREATE TABLE IF NOT EXISTS lg_core_place_link (
    tenant_id     text        NOT NULL,
    core_place_id uuid        NOT NULL,   -- 들여놓은 여행 전용 장소(places.place_id, trip_scope = trip_id)
    trip_id       uuid        NOT NULL,
    offer_key     text        NOT NULL,
    source        text,
    link          text,
    linked_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, core_place_id)
);

COMMENT ON TABLE lg_offer_shown IS '숙소 · 항공 팀이 그 여행의 한 항목에 보여 준 후보(다음 「바꿔 줘」에서 뺀다). 여행 전용 — 재사용하지 않는다.';
COMMENT ON TABLE lg_core_place_link IS '고객이 고른 MCP 숙소 후보를 들여놓은 여행 전용 장소와 그 후보(출처 · 링크)의 연결.';

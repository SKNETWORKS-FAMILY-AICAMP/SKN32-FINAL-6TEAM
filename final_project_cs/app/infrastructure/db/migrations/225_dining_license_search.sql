-- 225  인허가(사업자 등록) 식당 — 이름으로 찾기 위한 별도 표 (2026-10-05 사용자 지시 「인허가 목록 넓으면 좋다」)
--
-- 왜.
--   요식 원장은 관광공사 음식점 1,600곳 위주다. 서울에서 영업 중인 음식점은 인허가 자료(서울시 일반 · 휴게음식점)에 15만 곳이 넘는다.
--   고객이 일정에 쓴 식당이 원장에 없으면 이름 찾기가 「못 찾음」으로 끝났다.
--
-- 무엇을.
--   dining.dn_license_shop — 인허가 자료의 **영업 중** 가게 한 줄씩(상호 · 주소 · 업태 · 전화 · 허가일 · 좌표).
--   ★이름 찾기 전용이다. 대체 후보 · 영업 판정에는 쓰지 않는다 — 영업시간이 없고, 인허가의 「영업」은 영업 중이라는 증거가 못 된다
--     (신고가 늦다: 사람이 폐업으로 확인한 46곳 중 22곳이 인허가에는 영업이었다).
--   ★적재는 scripts/dining/load_license.py (raw 인허가 CSV → 이 표). 재적재 때마다 비우고 다시 채운다.
--
-- 다시 돌려도 깨지지 않는다.

CREATE TABLE IF NOT EXISTS dining.dn_license_shop (
    mgt_no         text PRIMARY KEY,                  -- 인허가 관리번호
    name_ko        text NOT NULL,
    name_key       text NOT NULL,                     -- 이름 찾기 키 — 소문자 · 한글 영숫자만(`ledger.find_place_by_name` 과 같은 규칙)
    road_address   text,
    jibun_address  text,
    area           text,                              -- 자치구
    category       text,                              -- 업태(한식 · 중국식 …)
    phone          text,
    lat            double precision,
    lng            double precision,
    approved_on    date,
    source_kind    text NOT NULL DEFAULT 'general',   -- general(일반음식점) | rest(휴게음식점)
    loaded_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dn_license_shop_name_key_idx ON dining.dn_license_shop (name_key text_pattern_ops);

COMMENT ON TABLE dining.dn_license_shop IS
    '인허가(사업자 등록) 영업 중 식당 — 이름 찾기 전용. 대체 후보 · 영업 판정에는 쓰지 않는다(영업시간 없음 · 인허가 영업은 증거가 못 됨).';

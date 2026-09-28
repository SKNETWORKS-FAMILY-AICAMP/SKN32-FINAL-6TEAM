-- 012 — 감시 관측 이력 (여행 지속관리 루프, 2026-09-10)
--
-- ★★**왜 이 표가 있나.** 이 제품의 존재 이유는 「8개월 만의 한 번」을 잡는
--   것이다. 장소 정보가 8개월째 안 바뀌었다는 사실은 **덜 봐도 된다는 뜻이
--   아니다** — 아무도 안 보고 있다가 그 한 번이 나면 고객의 여행이 망한다.
--   드문 변화일수록 감시가 없으면 아무도 모른다.
--
--   (2026-09-10 설계 정정. 처음엔 「거의 안 바뀌니 하루 1회면 된다」로 잡았다.
--    그것은 API 예산 논리였고, 제품 요구가 아니었다. 예산은 제약이지
--    목표가 아니다.)
--
-- ★**무엇을 자주 보는가**가 핵심이다. 카탈로그 2,063건 전체를 2분마다 볼
--   필요는 없다. **고객 계획서에 실제로 걸린 대상**만 보면 되고 그건 훨씬
--   적다. 그래서 감시 대상은 예약에서 나온다.

CREATE TABLE IF NOT EXISTS watch_observations (
    observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    -- 무엇을 보고 있나. place / weather / flight / holiday …
    target_kind   text NOT NULL,
    -- 그 종류 안에서의 식별자. place_id · "lat,lon@YYYYMMDDHH" · 편명 …
    target_id     text NOT NULL,
    source        text NOT NULL,
    -- ★변화 판정의 기준. 관측값에서 **판정에 쓰는 부분만** 뽑아 해시한다.
    --   전체를 해시하면 공급자가 무관한 필드를 건드릴 때마다 오탐이 난다.
    fingerprint   text NOT NULL,
    payload       jsonb NOT NULL,
    observed_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, target_kind, target_id, observed_at)
);

CREATE INDEX IF NOT EXISTS watch_observations_latest_idx
    ON watch_observations (tenant_id, target_kind, target_id, observed_at DESC);

-- 감지한 변화. ★**관측과 따로 둔다** — 관측은 매번 쌓이고 변화는 드물다.
--   한 표에 두면 「무엇이 바뀌었나」를 찾을 때마다 관측 더미를 뒤져야 한다.
CREATE TABLE IF NOT EXISTS watch_changes (
    change_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    target_kind   text NOT NULL,
    target_id     text NOT NULL,
    source        text NOT NULL,
    before_json   jsonb,
    after_json    jsonb NOT NULL,
    -- 무엇이 달라졌는지 사람이 읽을 한 줄. ★지어내지 않고 실제 필드 차이에서 만든다.
    summary       text NOT NULL,
    -- 이 변화가 걸린 고객·예약. ★없으면 알릴 대상이 없다는 뜻이고 그것도 기록한다.
    affected_bookings jsonb NOT NULL DEFAULT '[]'::jsonb,
    detected_at   timestamptz NOT NULL DEFAULT now(),
    -- 통지 상태. ★「닿았나」는 사양에 없다(v11 §1) — 보냈는지만 남긴다.
    notified_at   timestamptz,
    notify_error  text
);

CREATE INDEX IF NOT EXISTS watch_changes_pending_idx
    ON watch_changes (tenant_id, notified_at, detected_at DESC);

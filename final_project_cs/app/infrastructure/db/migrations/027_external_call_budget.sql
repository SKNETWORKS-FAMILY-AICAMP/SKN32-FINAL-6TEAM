-- 027 — 바깥 유료 API 호출 예산 (구글 무료 한도를 **무조건** 넘지 않게) · 2026-09-25 사용자 지시
--
-- ★★왜. 프로세스 안 속도 제한기(`ratelimit.py`)는 **프로세스마다 새로 센다.** 되잡기 작업은 `--once` 로
--   매분 새 프로세스가 뜨므로 한도가 매번 처음부터 찬다 — 사실상 제한이 없었다(2026-09-25 발견).
--   무료 한도는 결제 계정 전체의 **월 합계**라서 DB 에 남겨 모든 프로세스가 같이 세야 한다.
--
-- ★부르기 **전에** 한 칸을 확보한다(`used < cap` 일 때만 +1). 확보 못 하면 부르지 않는다.
--   실패한 호출도 한 칸을 쓴 것으로 센다 — 과금 여부를 추측하지 않고 **보수적으로** 센다.
-- ★구글 요금 계정 단위라 tenant 로 나누지 않는다(테넌트가 늘어도 한 결제 계정이다).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS external_call_budget (
    meter      text NOT NULL,          -- 예: google_places_details_enterprise
    period     text NOT NULL,          -- 'month:2026-09' · 'day:2026-09-25'
    used       integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    cap        integer NOT NULL CHECK (cap >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meter, period),
    CHECK (used <= cap)
);

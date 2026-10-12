-- 057 — 후보의 이유 문장(모델이 쓴 것) 저장. `[2026-10-07 사용자 결정 — uiux 전달]`
--
-- ★왜. 후보 카드의 이유 한 문장을 **모델이 확인된 값으로만** 쓰게 하되(사용자 지시), 같은 값이면 같은 문장을 다시 쓰지 않고 **저장해 쓴다** — 요청 자리에서 모델을 매번 부르면
--   느리고, 같은 후보가 같은 말을 해야 화면이 흔들리지 않는다. 모델이 실패하거나 문장이 검사(`reasons.guard`)를 못 넘으면 저장하지 않고 틀 문장을 쓴다.
-- ★열쇠 `facts_sha` = 프롬프트 버전 + **모델에게 준 사실**(후보 이름 · 단 · 거리 · 영업 · 여유 · 일정에 있는 장소 이름)의 해시 — 사실이 바뀌면 문장도 새로 쓴다.
--   사용자 식별 값은 들어가지 않는다(장소 이름과 숫자뿐).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS candidate_reasons (
    tenant_id  text NOT NULL,
    facts_sha  text NOT NULL,
    sentence   text NOT NULL,
    model      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, facts_sha)
);

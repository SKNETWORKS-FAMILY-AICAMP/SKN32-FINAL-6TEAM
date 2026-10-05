-- 049 — 제공처가 「한도 초과」를 알린 줄 표시. `[2026-10-05 사용자 지시 「월한도는 니가 체크해서 넣어」 — 포털의 월 한도는 조회 API 가 없다]`
--
-- ★왜. ITS 월 한도의 크기는 국가교통정보센터 **로그인 후** 인증키 상세정보에만 있고 조회 API 를 못 찾았다(2026-10-05). 숫자를 추측해 넣으면 틀릴 때 감시가 이유 없이 멈추거나 헛호출이 계속된다
--   (한도가 차 있던 날 우리는 하루 800~900건을 헛호출했다 — 9/30 937건 · 10/2 825건). 대신 **제공처가 「한도 초과」를 알려 주면** 그 기간 줄에 표시한다:
--     exhausted_at   제공처가 한도 초과를 알린 시각 — 그날 한국 자정까지 그 소스를 부르지 않는다(다음 날 첫 호출이 한 번 시험한다)
--     learned_cap    그때까지 센 사용 수 = **제공처가 실제로 허락한 한도의 관측값**(보고 스크립트가 보여 준다)
-- ★달이 바뀌면 새 줄이라 자동으로 풀린다. 재실행 안전.

ALTER TABLE external_call_budget ADD COLUMN IF NOT EXISTS exhausted_at timestamptz;
ALTER TABLE external_call_budget ADD COLUMN IF NOT EXISTS learned_cap  integer CHECK (learned_cap >= 0);

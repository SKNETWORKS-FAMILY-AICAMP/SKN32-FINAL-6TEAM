-- 047 — 호출 예산에 「실패 수」와 「거절 수」를 더한다. `[2026-10-05 사용자 지시 — 이동 세션 인계 「키별 호출 횟수 DB 추적」]`
--
-- ★왜. 027 의 `external_call_budget` 은 줄마다 `used`(부른 횟수)와 `cap`(상한)만 있었다 — 부른 것 중 몇 번이 실패였는지, 한도 때문에 몇 번을 못 불렀는지 알 수 없어
--   「이 키에 여유가 얼마나 남았나」를 볼 수 없었다. 소스(=키)마다 하루·월 줄에 아래 둘을 더 센다.
--     failed    부른 뒤 쓸 수 있는 답을 못 받은 횟수(시간 초과 · 연결 오류 · http 오류 · 응답 모양 이상 …). `used` 의 부분집합이다 — 실패도 한 칸 쓴 것으로 센다.
--     rejected  한도(이 표의 `cap`)가 차서 **부르지 않은** 횟수. `used` 에는 안 들어간다(부르지 않았으므로).
-- ★기존 줄은 둘 다 0 으로 채워진다. 재실행해도 안전하다.

ALTER TABLE external_call_budget ADD COLUMN IF NOT EXISTS failed   integer NOT NULL DEFAULT 0 CHECK (failed >= 0);
ALTER TABLE external_call_budget ADD COLUMN IF NOT EXISTS rejected integer NOT NULL DEFAULT 0 CHECK (rejected >= 0);

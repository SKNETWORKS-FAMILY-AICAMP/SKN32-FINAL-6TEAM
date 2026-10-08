-- 051 — 로딩 중 질문의 답을 접수에 모아 둔다 (`POST /v1/web/trip-intakes/{id}/survey`). `[2026-10-06 사용자 지시 · uiux 인계]`
--   기획 `wiki/records/plans/2026-10-05_설문_계획서에서_읽고_로딩에서_묻기_기획.md` 「서버 몫」 1.
--
-- ★왜 접수 행에 두나. 로딩 화면(계획을 읽는 동안)에서 한 문항씩 바로 저장하는데, 그때는 아직 여행이 없다 — 등록(`confirm` · `plan`) 때
--   여기 모은 답을 설문(`constraints.survey`)에 합친다. 답은 **고른 선택지 번호 그대로**(`{"preferred_mobility": "taxi"}`) 두고, 설문의 모양(`priority_details.mobility = ["taxi"]`)으로
--   바꾸는 것은 합칠 때 한 곳(`components/intake/survey_answers.py`)이 한다.
-- ★같은 문항을 다시 보내면 **덮어쓴다**(마지막 값이 이긴다) — 화면이 앞 질문으로 돌아가 고칠 수 있다.
-- ★`updated_at` 은 건드리지 않는다 — 읽기가 멈췄는지 가르는 기준(`reap_stalled`)이라, 답을 저장할 때마다 갱신하면 멈춘 접수가 멈춘 줄 모른다.
-- ★접수가 지워지면 같이 지워진다(행 안의 칸이다). 재실행 안전.

ALTER TABLE trip_intakes ADD COLUMN IF NOT EXISTS survey jsonb NOT NULL DEFAULT '{}'::jsonb;

-- 907 — 계획 접수의 **빠른 거름 기록**과 로딩 중 질문의 **이 접수에서 물을 목록**을 접수 행에 둔다. `[2026-10-19 사용자 지시 · 사용자 결정]`
--   설계 `final_project_cs/wiki/records/plans/2026-10-19_로딩설문_읽은칸빼고_빈칸만묻기.md`(§1~§3 질문 · §5 빠른 거름)
--   계약 `wiki/external/rest-endpoints/web-intakes.md` 「설문 질문」 · 「접수 입구의 빠른 거름」
--
-- ★`screened` — 빈 글 · 여행 단서가 하나도 없는 글을 모델 읽기 전에 돌려보낸 접수의 걸린 규칙(`{code: empty | off_topic, rule}`).
--   거른 접수는 읽지 않고 곧바로 확인 화면 상태(`review`)가 되며 로딩 설문을 내지 않는다. 원문은 글 원본 줄(`intake_sources`)에 남는다 — 사후에 오판을 센다.
--   비어 있으면(NULL) 거르지 않은 접수다(옛 접수 모두 포함).
-- ★`survey_plan` — 로딩 중 질문은 계획서에서 읽은 칸을 빼고 빈 칸만 묻는다. 목록이 접수마다 다르고 **두 번에 정한다**(접수 직후 · 이해 단계 결과 뒤).
--   그때그때 다시 계산하면 첫 조회 뒤에 고객이 답한 문항이 「이미 답함」으로 목록에서 사라져 화면의 `i / N` 이 흔들린다.
--   그래서 정한 목록(`{version, phase, asked[], skipped_by_reading[]}`)을 남기고, 둘째는 뒤에 붙이기만 한다(`components/intake/survey_answers.py` `loading_questions`).
--   비어 있으면 첫 조회가 정한다. 묶음 버전(`version`)이 지금과 다르면 새로 정한다.
-- ★두 칸이 없는 DB(907 이 안 올라감)도 접수 · 조회는 막지 않는다 — 거름 기록 없이 같은 상태로 만들고, 목록은 저장 없이 그때그때 계산한다(경고).
-- ☆재실행해도 안전하다 — ADD COLUMN IF NOT EXISTS.

ALTER TABLE trip_intakes ADD COLUMN IF NOT EXISTS screened jsonb;
ALTER TABLE trip_intakes ADD COLUMN IF NOT EXISTS survey_plan jsonb;

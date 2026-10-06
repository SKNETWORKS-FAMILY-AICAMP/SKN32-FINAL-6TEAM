-- 053 — 로딩 중 질문의 **답 이력**: 어떤 질문 묶음(버전)의 어떤 문구·선택지에 무엇을 골랐고 서버가 그것을 어떤 값으로 해석했나 (추가만 한다)
--   `[2026-10-06 uiux 요청 · 맞춤 질문 의논 §7]` `wiki/records/plans/2026-10-06_맞춤_질문_생성_방향_의논.md`
--
-- ★왜 표를 따로 두나. 051 은 답을 **고른 선택지 번호 그대로** 접수 행(`trip_intakes.survey`)에 둔다 — 지금 상태뿐이다. 그런데 질문 문구 · 선택지 목록 ·
--   「선택지 → 구조화 값」 매핑은 서버가 소유하고 나중에 바뀐다(질문 묶음 버전). 번호만 있으면 묶음이 바뀐 뒤에 **옛 답을 새 매핑으로 잘못 읽는다.**
--   그래서 저장하는 그때의 묶음 버전 · 문구 · 라벨 · 슬롯 · 해석한 값을 같이 남기고, 등록할 때는 **저장 때 해석한 값**으로 설문을 만든다.
-- ★`question_id`(화면이 아는 문항 번호)와 `slot`(구조화 값이 들어가는 자리 — 예: `preferred_mobility`)은 **다른 칸**이다. 지금은 우연히 같은 이름이지만 앞으로 문항 번호를 새로 만들어도 슬롯은 같을 수 있다.
-- ★`on_disruption` · `pace` 같은 직접 값(질문 목록에 없는 것)도 같은 입구로 오므로 한 줄로 남긴다 — `question_text` · `option_label` 은 비고 `slot` = 그 이름이다.
-- ★같은 문항을 다시 보내면 **줄이 하나 더 쌓인다**(덮어쓰지 않는다). 지금 답 = 문항마다 `seq` 가 가장 큰 줄. 순서는 `seq` 가 정한다(시각만으로는 같은 순간의 앞뒤가 안 정해진다).
-- ★접수가 지워지면 같이 지워진다(`ON DELETE CASCADE`). 그 밖에는 **고치지 않는다**(UPDATE 는 트리거가 막는다).
-- ☆재실행해도 안전하다 — CREATE … IF NOT EXISTS · 트리거는 먼저 지우고 다시 만든다.

CREATE TABLE IF NOT EXISTS trip_intake_survey_answers (
    answer_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq              bigserial   NOT NULL,
    tenant_id        text        NOT NULL,
    intake_id        uuid        NOT NULL REFERENCES trip_intakes (intake_id) ON DELETE CASCADE,
    -- 화면이 아는 문항 번호와 고른 선택지 번호(`POST …/survey` 의 `{문항: 선택지}`)
    question_id      text        NOT NULL,
    option_id        text        NOT NULL,
    -- 서버가 그때 해석한 결과: 구조화 값이 들어갈 자리(슬롯)와 값
    slot             text        NOT NULL,
    value            text        NOT NULL,
    -- 그때 화면에 보인 글(질문 묶음이 바뀌어도 무엇을 보고 골랐는지 남는다). 직접 값은 비어 있다
    question_text    text,
    option_label     text,
    -- 그때의 질문 묶음 버전(`survey_answers.QUESTION_SET_VERSION`)
    bundle_version   text        NOT NULL,
    answered_at      timestamptz NOT NULL DEFAULT now()
);

-- 한 접수의 문항마다 최신 답을 읽는 자리(등록 때 설문 만들기 · 이력 조회)
CREATE INDEX IF NOT EXISTS idx_trip_intake_survey_answers_intake ON trip_intake_survey_answers (tenant_id, intake_id, question_id, seq DESC);

CREATE OR REPLACE FUNCTION trip_intake_survey_answers_no_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'trip_intake_survey_answers 는 추가만 한다 (% 불가)', TG_OP;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trip_intake_survey_answers_no_change ON trip_intake_survey_answers;
CREATE TRIGGER trip_intake_survey_answers_no_change BEFORE UPDATE ON trip_intake_survey_answers
    FOR EACH ROW EXECUTE FUNCTION trip_intake_survey_answers_no_update();

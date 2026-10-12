-- 301  활동 장소 실내외 — 처음 한 번 정해 저장한다(D-CS-015 개정 2 · 구현 계획 1.8 · 멘토 피드백 10-08)
-- 작성 2026-10-12.
--
-- 한 장소에 정한 쪽마다 한 줄 — 관광공사 분류 · LLM · 고객 · 운영자. 읽을 때는 우선순위가 가장 높은 줄을 쓴다:
--   operator(사람 수정) > customer(고객 답) > llm > class(관광공사 분류)
-- 낮은 줄은 지우지 않고 남긴다 — 누가 언제 무엇으로 정했는지 되짚기 위해서다.
-- 관광공사 분류가 바뀌면(재적재) class · llm 줄만 지우고 다시 정한다. customer · operator 는 남긴다.
-- ★모름은 저장하지 않는다 — 줄이 없으면 모름이다. 코어 places 표는 바꾸지 않는다.

CREATE TABLE IF NOT EXISTS activity.ac_indoor (
    content_id       text NOT NULL REFERENCES activity.ac_place(content_id) ON DELETE CASCADE,
    decided_by       text NOT NULL,
    outdoor          boolean NOT NULL,
    model            text,
    prompt_version   text,
    quote            text,
    decided_case_id  text,
    decided_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (content_id, decided_by),
    CONSTRAINT ac_indoor_by_chk  CHECK (decided_by IN ('class', 'llm', 'customer', 'operator')),
    CONSTRAINT ac_indoor_llm_chk CHECK (decided_by <> 'llm' OR (model IS NOT NULL AND quote IS NOT NULL))
);

COMMENT ON TABLE activity.ac_indoor IS
    '장소 실내외 — 정한 쪽마다 한 줄. 우선순위 operator > customer > llm > class. 모름은 줄이 없다.';
COMMENT ON COLUMN activity.ac_indoor.quote IS
    'llm 일 때 근거 인용 — 입력 원문(장소명 · 분류 · 소개글)에 실제로 있는 글만(인용 검증을 통과한 값).';

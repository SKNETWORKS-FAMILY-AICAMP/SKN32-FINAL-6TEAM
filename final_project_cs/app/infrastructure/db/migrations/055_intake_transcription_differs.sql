-- 055 — 사진 · 스캔을 받아쓴 글에서 **같은 줄을 두 번 다르게 읽은 곳** (`intake_sources.differs_json`) `[2026-10-06 사용자 지시 — 계획 읽기 값 변조 줄이기]`
--   리포트 `wiki/records/reports/2026-09-28_계획읽기_평가셋60_리포트.md` 「남은 것」 — 값 변조 12/350 = 3.4% 가 전부 사진 · 스캔 받아쓰기의 **글자 오독**이었다.
--   받아쓰기(전체 · 위 반쪽 · 아래 반쪽)를 서로 맞춰 보는데, 지금 검사(`missing_json`)는 **빠진 줄**만 잡고 **바뀐 글자**는 못 잡는다.
--
-- ★한 칸 `[{"line": 줄 번호(전체 받아쓴 글 기준 · 1부터), "text": 전체 받아쓰기의 줄, "other": 반쪽 받아쓰기의 비슷한 줄, "half": "top"|"bottom", "ratio": 닮은 정도}]`.
--   읽은 값(제목 · 예약번호)이 이 줄에서 나왔으면 「확인 필요」로 표시한다(`pipeline.read_source`) — 고객이 확인하기 전에는 확정 값으로 쓰지 않는다.
-- ★`missing_json`(빠진 줄)과 따로 둔다 — 그 칸은 화면이 이미 읽고 있어 모양을 바꾸지 않는다. 기존 접수는 `[]` 로 채워진다(그때는 이 검사가 없었다).
-- ☆재실행해도 안전하다 — IF NOT EXISTS.

ALTER TABLE intake_sources ADD COLUMN IF NOT EXISTS differs_json jsonb NOT NULL DEFAULT '[]'::jsonb;

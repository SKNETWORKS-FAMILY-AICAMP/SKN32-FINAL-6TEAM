-- 2026-10-16 사용자 지시 — 계획서 접수를 **지우기 전에 백업**한다(「7일 뒤 삭제하면 안 되고 우선 DB 에 다 저장」).
--
-- ★왜. 고객이 입력한 계획서 원문 · 우리가 읽은 값 · 고객이 고친 값은 계획 읽기의 골든셋 재료다. 그런데 여행 삭제 · 게스트 정리(7일) · 회원 정리가
--   `trip_intakes` 를 지우면 자식 표(`intake_sources` · `intake_claims` · `intake_reviews` · 설문 답 · 시험 출처)까지 CASCADE 로 사라졌다.
-- ★무엇을. 접수 한 건 = 백업 한 행. 접수 행과 자식 표의 행을 **있는 그대로**(`to_jsonb`) 한 덩어리(`snapshot`)로 담는다 —
--   표에 칸이 늘어도 백업 코드를 고치지 않게. 원본 파일(사진 · PDF)은 DB 에 없어(저장 위치만) 백업에도 위치만 남는다.
-- ★원래 고객 · 여행과 외래키로 잇지 않는다 — 고객 행 · 여행 행이 지워져도 백업은 남아야 한다. 그래서 칸 이름도 `source_…` 다
--   (여행 번호 칸 `trip_id` 를 가진 표는 여행 삭제 목록에 있어야 한다는 시험이 있다 — 이 표는 **일부러** 남기는 표다).
-- ★얼마나 두나. 관리 화면 설정 `retention.intake_backup_days`(0 = 지우지 않음)를 정리 작업이 **지울 때** 읽는다 —
--   설정을 바꾸면 이미 쌓인 백업에도 새 기간이 적용된다(`intake/backup.py`).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS intake_backups (
    backup_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          text NOT NULL,
    intake_id          uuid NOT NULL,          -- 원래 접수 번호(원본은 지워졌을 수 있다)
    source_customer_id uuid,                   -- 원래 고객 번호(외래키 없음)
    source_trip_id     uuid,                   -- 등록된 여행 또는 다시 연 여행(외래키 없음)
    reason             text NOT NULL,          -- 왜 지워지기 전이었나 — trip_delete · guest_cleanup · member_cleanup
    received_at        timestamptz,            -- 원래 접수 시각
    snapshot           jsonb NOT NULL,         -- {intake, sources, claims, reviews, survey_answers, test_scenarios}
    backed_up_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, intake_id)
);
CREATE INDEX IF NOT EXISTS intake_backups_age_idx ON intake_backups (tenant_id, backed_up_at);

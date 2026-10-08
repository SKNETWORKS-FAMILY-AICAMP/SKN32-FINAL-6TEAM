-- 운영 앱(운영자 콘솔)의 **읽기 전용** DB 계정. `[2026-09-29]` 운영자 콘솔 분리 1단계 — 사용자 지시 · Codex 합의
--
-- ★왜. 운영 화면은 목록·상세·통계를 DB 에서 직접 읽는다(`app/presentation/ui/routes.py`). 운영 앱이 본 계정을 쓰면
--   운영 앱이 뚫렸을 때 쓰기까지 열린다. 읽는 표만 SELECT 로 준다 — 쓰기는 DB 가 거부한다.
--   쓰기(승인·위임·바깥함)는 운영 앱이 **고객 API** 를 scope 키로 부른다. 웹 제한값 운영 API 는 따로 본 계정을 쓴다.
-- ★다음 단계는 이 직접 읽기를 API 로 옮기는 것이다(Codex 합의).
--
-- 쓰는 법(관리자 계정으로, 비밀번호는 psql 변수로 넘긴다 — 이 파일·git 에 적지 않는다):
--   psql -h 127.0.0.1 -p 5433 -U postgres -d acop_cs -v ops_ro_password="'<비밀번호>'" -f scripts/sql/ops_readonly_role.sql
-- 그다음 운영 앱의 `.env` 에:
--   ACOP_OPS_READ_DATABASE_URL=postgresql://acop_ops_ro:<비밀번호>@127.0.0.1:5433/acop_cs
-- ☆재실행해도 안전하다(있으면 비밀번호만 바꾸고 권한을 다시 준다).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'acop_ops_ro') THEN
        CREATE ROLE acop_ops_ro LOGIN;
    END IF;
END $$;

ALTER ROLE acop_ops_ro WITH LOGIN PASSWORD :ops_ro_password NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER ROLE acop_ops_ro SET default_transaction_read_only = on;

DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO acop_ops_ro', current_database()); END $$;
GRANT USAGE ON SCHEMA public TO acop_ops_ro;
-- 운영 화면이 읽는 표만(2026-09-29 `routes.py` 의 FROM · JOIN 을 세었다 — 7개)
GRANT SELECT ON customer_cases, case_events, action_requests, feedback_analytics_reports,
                knowledge_documents, knowledge_chunks, outbox TO acop_ops_ro;

-- 223  요식 적재 전용 DB 계정 (2026-09-28 cs, 사용자 결정 — DB 는 떼지 않고 권한만 나눈다)
--
-- 왜.
--   요식 표가 코어 DB 로 들어왔다. 요식 적재 도구(scripts/dining/rebuild.py)가 코드 실수 하나로 코어 데이터를
--   지울 수 있었다(기본 동작이 「DB 를 지우고 새로 만들기」였다 — 코드로도 막았다, holds_live_core).
--   DB 권한으로 한 번 더 막는다: 이 계정은 요식 칸에만 마음대로 쓰고, 코어는 장소 표에 넣고 고치는 것까지만 한다.
--
-- 이 계정이 할 수 있는 것
--   dining 칸   표·순서값·함수 전부(읽기·넣기·고치기·지우기·비우기). 표를 만들거나 바꾸는 것은 못 한다(주인이 아니다)
--   public      places 읽기·넣기·고치기(요식 식당을 코어로 올리기·동기화, 221·222) · trips·tenants 읽기(코어 DB 인지 보기)
-- 못 하는 것
--   DB 만들기·지우기 · 코어 표 지우기·비우기 · 여행·고객·일정 고치기 · 표 구조 바꾸기
--
-- 파일 이름에 `_dining_` 을 넣지 않았다(223_ops_loader_role) — 요식 시험 DB(코어 표 없음)가 이 파일을 올리지 않게.
-- 다시 돌려도 깨지지 않는다.

DO $do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dining_loader') THEN
        CREATE ROLE dining_loader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO dining_loader', current_database());
END
$do$;

COMMENT ON ROLE dining_loader IS '요식 적재 전용. dining 칸만 쓰고 코어는 places 넣기·고치기까지(223).';

-- dining 칸이 없는 DB(요식 적재 전)에서도 돌아야 한다
DO $do$
BEGIN
    IF to_regnamespace('dining') IS NOT NULL THEN
        GRANT USAGE ON SCHEMA dining TO dining_loader;
        GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON ALL TABLES IN SCHEMA dining TO dining_loader;
        GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA dining TO dining_loader;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA dining TO dining_loader;
        -- 앞으로 코어 마이그레이션이 만드는 요식 표에도
        ALTER DEFAULT PRIVILEGES IN SCHEMA dining
            GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON TABLES TO dining_loader;
        ALTER DEFAULT PRIVILEGES IN SCHEMA dining GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO dining_loader;
        ALTER DEFAULT PRIVILEGES IN SCHEMA dining GRANT EXECUTE ON FUNCTIONS TO dining_loader;
    END IF;
END
$do$;

GRANT USAGE ON SCHEMA public TO dining_loader;
GRANT SELECT, INSERT, UPDATE ON public.places TO dining_loader;
GRANT SELECT ON public.trips, public.tenants TO dining_loader;

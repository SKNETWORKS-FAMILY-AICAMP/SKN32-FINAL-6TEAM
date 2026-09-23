-- ★버그사냥 2026-08-17 (라운드 06) — max_active_runs_per_case: 1 가드레일이
--   애플리케이션 레벨에서만 있었다. SELECT ... FOR UPDATE 는 "이미 있는 행"만
--   잠근다 — active 행이 아직 하나도 없을 때 두 start_run() 이 동시에 들어오면
--   둘 다 빈 결과를 보고 둘 다 INSERT 할 수 있었다(실측: DB 에 이걸 막는
--   제약이 전혀 없었다). partial unique index 로 DB 가 최종 방어선이 되게 한다.
CREATE UNIQUE INDEX IF NOT EXISTS agent_runs_one_active_per_case
    ON agent_runs (tenant_id, case_id)
    WHERE status IN ('active', 'running', 'resuming');

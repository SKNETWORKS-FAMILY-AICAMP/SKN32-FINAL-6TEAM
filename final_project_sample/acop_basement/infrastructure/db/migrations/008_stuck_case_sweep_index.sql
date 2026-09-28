-- ★sweeper 가 60초마다 훑는 질의를 위한 인덱스 (2026-09-03).
--
--   `classification_sweeper`·`routing_sweeper` 는 "이 상태에 오래 머문 Case" 를
--   찾는다. 인덱스가 없으면 `cases_tenant_customer_idx`(tenant_id, customer_id)
--   를 타고 **테넌트의 Case 를 전부 읽은 뒤** status·updated_at 으로 거른다
--   (실측한 EXPLAIN 이 그랬다). Case 가 쌓일수록 매분 그 비용을 낸다.
--
-- ★**부분 인덱스**로 둔다. 훑는 대상은 진행 중인 두 상태뿐이고, 그 행은 정상
--   운영에서 몇 건 안 된다. 완료된 Case 까지 색인하면 인덱스가 테이블만큼
--   커지는데 sweeper 는 그걸 한 번도 읽지 않는다.
CREATE INDEX IF NOT EXISTS cases_stuck_sweep_idx
    ON customer_cases (tenant_id, status, updated_at)
    WHERE status IN ('classifying', 'routing');

-- ★`routing_sweeper` 의 `NOT EXISTS (agent_runs ...)` 는 지금 agent_runs 를
--   순차 탐색한다. 기존 `agent_runs_one_active_per_case` 는 **활성 상태만**
--   담는 부분 인덱스라 여기에 안 쓰인다 — 우리는 "어떤 상태든 run 이 있었나" 를
--   묻기 때문이다.
CREATE INDEX IF NOT EXISTS agent_runs_tenant_case_idx
    ON agent_runs (tenant_id, case_id);

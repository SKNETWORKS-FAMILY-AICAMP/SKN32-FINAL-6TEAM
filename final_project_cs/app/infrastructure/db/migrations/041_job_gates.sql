-- 041 — 상시 작업 안의 「주기 문」. `[2026-10-03 사용자 결정 — 감시 주기를 팀이 정한 3분으로]`
--
-- ★왜. 되잡기 작업(`sweepers`)은 **1분마다** 도는데(멈춘 Case 되잡기 · 일정 출발 안내가 늦지 않게), 그 안의 **감시**(여행 외부 정보 점검 — 기상 · 재난문자 ·
--   교통 · 대기)는 팀 결정(D-017 · D-020)이 **3분**이다. 일꾼은 **회차마다 새 프로세스**(`--once`)라 프로세스 안의 메모리로는 「마지막으로 언제 돌았나」를 못 기억한다
--   (응답 캐시가 매분 비는 것과 같은 이유). 그래서 마지막 실행 시각을 DB 에 둔다.
-- ★`claim` 은 원자적이다 — 같은 시각에 일꾼 둘이 떠도 **하나만** 이긴다(`INSERT … ON CONFLICT DO UPDATE … WHERE`). 이긴 쪽만 감시를 돈다.
-- ★이 표는 **시각만** 안다 — 무엇을 했는지는 모른다. 다시 돌려도 안전하다.

CREATE TABLE IF NOT EXISTS job_gates (
    tenant_id    text NOT NULL,
    gate         text NOT NULL,
    last_run_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, gate)
);

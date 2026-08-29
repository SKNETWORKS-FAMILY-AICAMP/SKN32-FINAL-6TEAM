# S-BASEMENT-03-TENANT-DEDUPE — outbox tenant 격리 복원 + idempotency 필드충돌 + graph edge 최신화

## 0. 배경

`final_project_sample/acop_basement/` (참고용, **절대 수정 금지**) 와
`final_project_cs/app/` 실제 내용 대조에서 발견된 3건. 서로 다른 파일
이지만 규모가 작아 한 작업으로 묶는다.

### 1) outbox dedupe 의 tenant 경계 소실 (제일 중요)

- `app/infrastructure/messaging/outbox.py`, `app/core/transition.py`
  두 곳 모두 outbox insert 시 `ON CONFLICT` 제약이 `(topic, dedupe_key)`
  로만 걸려 있다 — sample 은 `(tenant_id, topic, dedupe_key)` 세 컬럼
  전부다. **다른 tenant 끼리 같은 topic+dedupe_key 조합이면 서로의
  outbox 행에 충돌/영향을 줄 수 있다.** `CLAUDE.md` §1 "모든 query 에
  tenant_id 조건을 적용한다" 원칙 위반이다.
- DB 제약(UNIQUE 인덱스) 자체가 tenant_id 를 포함하도록 새 마이그레이션이
  필요하다(sample 의 `infrastructure/db/migrations/005_outbox_dedupe_key_tenant_scoped.sql`
  참고 — 읽기만 하고, cs 의 마이그레이션 넘버링 규칙에 맞게 새 파일을
  만들어라, cs 는 지금 001·002 까지만 있다).
- 코드의 `ON CONFLICT` 절과 관련 쿼리도 세 컬럼 기준으로 고쳐라.

### 2) idempotency 필드 경계 충돌

- `app/core/idempotency.py` 가 여러 필드를 그냥 이어붙여서
  (`f"{a}{b}{c}{d}"`) 해시한다 — `("ab","c")` 와 `("a","bc")` 가 같은
  해시가 될 수 있다. sample 은 각 필드를 먼저 개별 해시한 뒤 결합한다.
  같은 방식으로 고쳐라.

### 3) graph edge 타입 최신화

- `app/infrastructure/graphstore/sql_adapter.py` 의 `subgraph()` 가
  6종 edge type 만 쓰는데, `neighbors()` 는 DoD-21 이후 9종(has_issue,
  governed_by, handled_by 포함)을 쓴다. `subgraph()` 도 같은 9종
  `EDGE_TYPES` 를 쓰도록 맞춰라. 지금 프로덕션 호출자가 없는 dormant
  코드라 위험은 낮지만, 있는 김에 고쳐라.

## 1. 검증

- 각 항목 재현 테스트(수정 전 실패 확인 후 수정) 추가.
- tenant 격리 테스트는 특히 중요하다 — 서로 다른 tenant 가 같은
  topic+dedupe_key 로 publish 했을 때 **둘 다 독립적으로 성공**하는지
  직접 테스트해라(`tests/security/` 의 기존 tenant 격리 테스트 패턴을
  따라라).
- `python -m pytest -q -m "not live"` 결과를 리포트에 붙여라(359 passed
  기준 변화 명시). `tests/security -q` 도 별도로 돌려서 결과를 붙여라.

## 2. 쓰기 대상

- `app/infrastructure/messaging/outbox.py`
- `app/core/transition.py`
- `app/core/idempotency.py`
- `app/infrastructure/graphstore/sql_adapter.py`
- `app/infrastructure/db/migrations/003_outbox_tenant_scoped_dedupe.sql`
  (신규 — **이 번호(003)는 이 작업 전용으로 미리 배정됐다.** 병렬로 도는
  다른 작업이 004(agent_runs 유니크니스), 005(outbox 해결 워크플로)를
  쓴다 — 겹치지 않는다. 그대로 003 을 써라.)
- 관련 테스트 파일들
- `docs/reports/2026-08-24_S-BASEMENT-03-TENANT-DEDUPE_리포트.md` (신규)

## 3. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- 마이그레이션 파일 번호가 다른 작업과 충돌하지 않는지 실행 직전에
  꼭 확인해라(병렬로 다른 마이그레이션 작업이 진행 중일 수 있다)

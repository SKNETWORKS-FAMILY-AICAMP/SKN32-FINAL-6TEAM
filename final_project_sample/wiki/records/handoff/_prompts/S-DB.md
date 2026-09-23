# Codex 작업 지시 — 스트림 S-DB (스키마 · 마이그레이션 · seed)

당신은 A-COP 프로젝트의 **S-DB 스트림**을 담당한다.

## 0. 먼저 읽을 것 (필수)

1. `RULE.md` — §1(근거) · §3.1(하드코딩 금지) · §3.2(폴백 금지) · §3.3(YAGNI) · §3.4(리포트 의무)
2. `CLAUDE.md` — §0.3(상태는 transition_case 로만) · §1(tenant 격리, PII)
3. `wiki/records/handoff/05_분업_규칙.md` — **소유 디렉터리**
4. `wiki/records/handoff/02_DB_스키마.md` — ★**이번 작업의 계약. DDL 은 여기 그대로다**
5. `app/core/contracts.py`, `app/core/transition.py`, `app/domain/events.py` — 이미 구현된 Core.
   **읽어라. 고치지 마라.** 당신이 만들 스키마 위에서 이 코드가 돈다
6. `../A-COP_구현계획서_v5.md` §8(DDL), §6(동시성) — 읽기 전용. **절대 수정 금지**

## 1. 소유 범위 — 여기에만 쓴다

```
app/infrastructure/db/**
scripts/seed.py
tests/integration/db/**
wiki/records/reports/ , wiki/records/history/   (자기 리포트 파일만 추가)
```

★`app/core/**`, `app/domain/**`, `knowledge/**`, `app/presentation/**` 를 **건드리지 마라.**
다른 스트림이 동시에 작업 중이다. 건드리면 그쪽 작업이 사라진다.

## 2. 만들 것

### 2-1. 마이그레이션 — `app/infrastructure/db/migrations/`

`wiki/records/handoff/02_DB_스키마.md` §1 의 DDL을 **그대로** 적용하는 마이그레이션.

- alembic 을 써도 되고, 번호가 붙은 순수 SQL 파일 + 러너여도 된다.
  **단순한 쪽을 골라라** (YAGNI). 어느 쪽이든 아래를 만족해야 한다:
  - `python -m app.infrastructure.db.migrate` 한 번으로 빈 `acop` DB 에 전체 스키마가 선다
  - **재실행해도 깨지지 않는다** (이미 적용된 것은 건너뛴다)
  - `CREATE EXTENSION IF NOT EXISTS pgcrypto;` 와 `vector;` 를 마이그레이션이 만든다
    (손으로 치지 않는다 — 마이그레이션이 유일한 경로여야 재현된다)
- ★**컬럼을 임의로 더하거나 빼지 마라.** v5 §8 DDL 그대로다.
- ★**UNIQUE 제약 3개를 빠뜨리지 마라.** 이것이 정합성의 실체다(`02` §2):
  - `case_events UNIQUE(case_id, aggregate_version)`
  - `action_requests UNIQUE(tenant_id, idempotency_key)`
  - `outbox UNIQUE(topic, dedupe_key)`
- 인덱스 3종(hnsw / cases_tenant_customer / events_case_version)도 포함.

### 2-2. 연결 — `app/infrastructure/db/session.py`

- DSN 은 `app.core.settings.get_settings().database_url` 에서 읽는다.
  ★**하드코딩 금지.** `.env` 형식은 `postgresql+psycopg://...` 이다 —
  psycopg 로 직접 연결할 때는 `+psycopg` 를 떼야 한다(`scripts/check_env.py` 참고).
- `transition_case(conn, ...)` 는 **psycopg `Connection`** 을 받는다. 여기에 맞는
  connection 획득 함수를 제공한다 (context manager 권장).
- ★**연결 실패를 삼키지 마라.** 예외를 그대로 올린다. "실패하면 빈 값" 금지.

### 2-3. 저장소 — `app/infrastructure/db/repository.py`

Core 와 다른 스트림이 쓸 읽기·쓰기 함수. **최소한만** 만든다(YAGNI).

- `create_case(...)` — 새 Case 를 `status='new'`, `version=0` 으로 insert (★이것만이 Case 생성 경로)
- `get_case(tenant_id, case_id)` / `list_cases(tenant_id, customer_id, ...)`
- `get_case_events(tenant_id, case_id)`
- action / approval / prompts / llm_calls 의 기본 CRUD

★**절대 만들지 마라**: `customer_cases` 를 임의로 UPDATE 하는 헬퍼.
상태 변경은 `app/core/transition.py:transition_case()` 만이 진입점이다(CLAUDE.md §0.3).
`case_events` 의 UPDATE/DELETE 함수도 만들지 마라 — append-only 다.

★**모든 조회에 `tenant_id` 조건을 넣어라.** 조건 없는 조회는 보안 결함이다.

### 2-4. seed — `scripts/seed.py`

`wiki/records/handoff/02_DB_스키마.md` §4 의 표대로. 시나리오 근거가 되는 데이터를 반드시 포함한다:

- **시나리오 1**: 구독을 해지했는데 그 뒤 결제가 발생한 고객이 최소 1명
- **시나리오 2**: 플랜은 Pro 인데 entitlement 는 Free 로 남아 있는 고객이 최소 1명 + 관련 incident 1건
- 가상 SaaS 는 **Nimbus** (플랜: Free / Pro / Business), tenant_id 는 `demo`

구독·결제·entitlement·incident mock 테이블은 v5 §8 DDL 에 없다.
**필요한 만큼만** 새 테이블로 추가하되, 마이그레이션에 넣고 리포트에 **왜 추가했는지 적어라.**
(v5 §8 의 13개 테이블은 그대로 두고 그 옆에 붙이는 것이다)

- `python -m scripts.seed` 로 실행. **재실행해도 중복이 쌓이지 않게** 한다.
- ★실제 결제 provider 연동은 v5 §3 Out 이다. 전부 mock 이다.

### 2-5. 통합 테스트 — `tests/integration/db/`

실제 `acop` DB 에 붙어서 도는 테스트. 최소 아래 4개:

1. **스키마** — 13개 테이블 + UNIQUE 3종 + 인덱스 3종이 실제로 있는지 조회로 확인
2. **transition 왕복** — `create_case` → `transition_case(CREATED)` → `transition_case(CLASSIFIED)`
   가 되고, `customer_cases.version` 과 `case_events.aggregate_version` 이 일치
3. ★**version 충돌** — 같은 `expected_version` 으로 두 번 전이 시도 → 두 번째는 `StateConflict`
4. ★**outbox 중복 차단** — 같은 `(topic, dedupe_key)` 로 두 번 발행 → 행은 1개

## 3. 환경 (실측 2026-08-12 — 추측하지 말고 이대로 쓴다)

| 항목 | 값 |
|---|---|
| PostgreSQL | 16.14, `127.0.0.1:5433`, user `postgres`, **암호 없음(trust)** |
| DB | **`acop`** (이미 생성돼 있다) |
| psql | `%USERPROFILE%\anaconda3\envs\pgv\Library\bin\psql.exe` — **PATH 에 없다** |
| extension | `vector 0.8.3`, `pgcrypto 1.3` — available 하지만 **아직 미설치** |
| Docker | **없음.** compose 로 DB 를 띄우려 하지 마라 |
| 파이썬 | 3.12.7 (anaconda base). `psycopg[binary] 3.3.4` 설치됨 |

★**다른 프로젝트 DB(`insurance_*`, `mall_vec`)를 건드리지 마라.**

## 4. 완료 조건 — 실제로 실행하고 출력을 리포트에 붙인다

```powershell
python -m app.infrastructure.db.migrate
python -m app.infrastructure.db.migrate      # 재실행해도 깨지지 않아야 한다
python -m scripts.seed
python -m scripts.check_env                  # extension 2건이 OK 로 바뀌어야 한다
python -m pytest tests/integration/db -q
$psql = "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -c "\dt"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -c "\dx"
```

★**추정으로 쓰지 마라.** 실패하면 실패했다고 쓰고 무엇이 실패했는지 원문을 붙여라(RULE.md §1.2).

## 5. 리포트 (필수)

`wiki/records/reports/2026-08-12_S-DB_스키마_마이그레이션_리포트.md`:

1. 작업 목표 — 실행계획서 P2
2. 만든 파일 목록
3. **검증 결과** — §4 명령의 **실제 출력 원문**
4. ★**v5 §8 에 없는 테이블을 추가했다면 무엇을 왜 추가했는지**
5. 미해결 이슈 · 다음 작업 제안

`wiki/records/history/2026-08-12_S-DB.md` 에 `RULE.md` §4.3 형식으로 이력을 추가한다.

## 6. 하지 말 것

- ❌ 소유 범위 밖 파일 생성·수정 (특히 `app/core/**`, `app/domain/**`)
- ❌ `customer_cases` 를 UPDATE 하는 repository 헬퍼
- ❌ `case_events` UPDATE / DELETE
- ❌ `tenant_id` 조건 없는 조회
- ❌ DSN·포트·경로 하드코딩
- ❌ 연결 실패 시 빈 값 반환 / SQLite 로 대체
- ❌ v5 §8 DDL 의 컬럼·제약 임의 변경
- ❌ 계획서 md 파일 수정
- ❌ 테스트 없이 "동작함" 이라고 쓰기

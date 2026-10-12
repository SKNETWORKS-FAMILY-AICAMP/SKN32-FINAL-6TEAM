# Codex 작업 지시 — 스트림 S-DB **수정 작업 (seed 미달 + 테스트 오염)**

당신은 A-COP 프로젝트의 **S-DB 스트림**이다. 1차 작업의 **일부만** 고친다.

## 0. 1차 작업 판정 결과

**통과한 것 (그대로 두어라. 손대지 마라):**

- `app/infrastructure/db/migrations/001_schema.sql` — v5 §8 DDL 14개 테이블 정확
- UNIQUE 제약 3종 **전부 확인됨**
  (`case_events_case_id_aggregate_version_key`, `action_requests_tenant_id_idempotency_key_key`,
  `outbox_topic_dedupe_key_key`)
- 인덱스 3종 확인됨 · extension 2종 설치됨 · 마이그레이션 재실행 안전
- `repository.py` 에 금지된 `UPDATE customer_cases` / `case_events` 변경 헬퍼 **없음** — 좋다
- `tests/integration/db/test_db_integration.py` 4개 테스트 통과 (StateConflict · outbox 중복 차단 포함)

**거부된 것 — 이번에 고칠 대상:**

### 결함 1. seed 데이터가 계약의 1/10 수준이다

`wiki/records/handoff/02_DB_스키마.md` §4 가 정한 건수와 실측:

| 대상 | 계약 | **실측** | |
|---|---:|---:|---|
| customer (tenant=demo) | 10 | **2** | ❌ |
| 구독 mock | 10 | **2** | ❌ |
| 결제 이력 mock | 30+ | **1** | ❌ |
| entitlement mock | 10 | **1** | ❌ |
| incident mock | 3 | **1** | ❌ |

실측 명령:
```powershell
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'customers='||count(*) from customers where tenant_id='demo'"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'payments='||count(*) from payments"
```

★**왜 건수가 계약인가.** 이 seed 위에서 평가 golden 60건과 VOC 일일 급증 탐지가 돈다.
급증 판정식은 `오늘 count >= max(5, 1.5 × 최근7일 평균)` 이다(`06_가드레일_수치.md` §4).
결제 1건·고객 2명으로는 **급증도 golden 도 만들 수 없다.**
"시나리오가 되는 최소 데이터"로 줄이는 것은 범위 삭감이다(RULE.md §3.6-3).

### 결함 2. 통합 테스트가 실 DB 를 오염시킨다

테스트를 몇 번 돌린 뒤 실측: `tenants` **19행**, `customers` **20행**.
테스트가 만든 tenant/customer 를 정리하지 않는다.

★그러면 `select count(*) from customers` 같은 검증이 **무의미해진다.**
실제로 이번 검수에서 seed 건수를 세는 데 방해가 됐다.

## 1. 소유 범위 — 여기에만 쓴다

```
scripts/seed.py
tests/integration/db/**
app/infrastructure/db/migrations/   ← mock 테이블 컬럼 추가가 필요한 경우만 (새 번호 파일로)
wiki/records/reports/ , wiki/records/history/       ← 자기 리포트만
```

★`app/core/**`, `app/domain/**`, `knowledge/**`, `scripts/check_env.py`,
`scripts/check_corpus.py` 를 **건드리지 마라.** 다른 스트림이 작업 중이다.
★`001_schema.sql` 을 **수정하지 마라.** 이미 적용됐다. 바꿀 게 있으면 `002_*.sql` 을 새로 만든다.

## 2. 할 일

### 2-1. `scripts/seed.py` — 계약 건수를 채운다

tenant `demo` 기준:

| 대상 | 건수 | 요구사항 |
|---|---:|---|
| customer | **10** | `cust_01` ~ `cust_10` |
| subscription | **10** | Free/Pro/Business 섞기. 해지(`ended_at` 있음) 최소 3건 |
| payment | **30 이상** | 최근 **14일**에 걸쳐 분포시킨다 (VOC 일일 집계가 날짜를 쓴다) |
| entitlement | **10** | 고객당 1건 |
| incident | **3** | 권한 동기화 장애 포함 |

★**시나리오 데이터는 반드시 포함한다:**

1. **시나리오 1** — 구독을 해지했는데 **`ended_at` 이후에 `paid_at` 인 payment 가 존재**하는 고객 최소 1명
2. **시나리오 2** — `subscriptions.plan='Pro'` 인데 `entitlements.plan='Free'` 인 고객 최소 1명
   + 그와 연결된 incident 1건

★**재실행해도 중복이 쌓이지 않아야 한다.** 현재 구현이 그런지 확인하고, 아니면 고쳐라
(`ON CONFLICT DO NOTHING` 또는 고정 external_id 기준 upsert).

현재 mock 테이블 컬럼 (실측 — 이걸 쓴다):
```
subscriptions: subscription_id, tenant_id, customer_id, plan, status, started_at, ended_at
payments:      payment_id, tenant_id, customer_id, subscription_id, amount_cents, status, paid_at
entitlements:  entitlement_id, tenant_id, customer_id, plan, source, updated_at
incidents:     incident_id, tenant_id, customer_id, case_id, summary, status, created_at
```
컬럼을 더해야 하면 `002_*.sql` 마이그레이션으로 추가하고 **왜 필요한지 리포트에 적어라.**

### 2-2. 테스트 격리

- 통합 테스트는 **테스트 전용 tenant_id**(예: `test_<uuid>`)를 쓴다
- fixture teardown 에서 **자기가 만든 행을 전부 삭제**한다
  (FK 순서 주의: 자식 → 부모)
- ★**`demo` tenant 의 행을 절대 지우지 마라.** seed 데이터다
- 기존 4개 테스트의 **검증 내용은 그대로 유지**한다. 격리만 추가한다

### 2-3. 오염된 기존 행 정리

지금 DB 에 남아 있는 테스트 잔여 tenant 들을 지우는 **일회성 정리**를 수행한다.
`demo` 를 제외한 tenant 와 그 하위 행을 삭제한다. 무엇을 몇 건 지웠는지 리포트에 적어라.

## 3. 완료 조건 — 실제로 실행하고 출력을 붙인다

```powershell
python -m scripts.seed
python -m scripts.seed                       # 재실행 — 건수가 늘면 안 된다
python -m pytest tests -q                    # 전체. 기존 57건이 계속 통과해야 한다
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'demo_customers='||count(*) from customers where tenant_id='demo'"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'subscriptions='||count(*) from subscriptions"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'payments='||count(*) from payments"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'entitlements='||count(*) from entitlements"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'incidents='||count(*) from incidents"
# 시나리오 1 — 해지 후 결제
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select count(*) from subscriptions s join payments p using(subscription_id) where s.ended_at is not null and p.paid_at > s.ended_at"
# 시나리오 2 — 플랜/entitlement 불일치
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select count(*) from subscriptions s join entitlements e on e.customer_id=s.customer_id where s.plan <> e.plan"
```

기대: `tenants=1`, `demo_customers=10`, `subscriptions=10`, `payments>=30`,
`entitlements=10`, `incidents=3`, 시나리오1 `>=1`, 시나리오2 `>=1`.

★**테스트를 돌린 뒤에도 `tenants=1` 이어야 한다.** 그게 격리가 됐다는 증거다.

## 4. 리포트

`wiki/records/reports/2026-08-12_S-DB_seed보강_테스트격리_리포트.md`:

1. 작업 목표 — 1차 판정의 결함 1·2
2. 변경 파일 목록
3. **§3 명령의 실제 출력 원문 전체** (테스트 실행 전후의 `tenants` 건수 포함)
4. 정리한 오염 행 건수
5. `002_*.sql` 을 만들었다면 무엇을 왜

`wiki/records/history/2026-08-12_S-DB_fix.md` 에 `RULE.md` §4.3 형식 이력 추가.

## 5. 하지 말 것

- ❌ `001_schema.sql` 수정
- ❌ `demo` tenant 데이터 삭제
- ❌ 소유 범위 밖 파일 수정
- ❌ 기존 4개 테스트의 검증 내용 약화 (격리만 추가한다)
- ❌ 건수를 "시나리오에 충분한 만큼"으로 줄이기
- ❌ 명령을 돌리지 않고 건수를 추정해서 쓰기

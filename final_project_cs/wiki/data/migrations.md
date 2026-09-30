---
type: guide
title: 마이그레이션
description: 마이그레이션 파일과 순서. 재실행이 안전하다. 2026-09-10 기준 작업 트리 13개 · git 9개
status: draft
tags: [data]
owners: [human:미배정]
domain: commerce
domain_note: 코드가 아직 커머스다 — 여행 전환 층 5(DB 도메인 표 19표 중 여행 표 0개) 미완. 문서는 코드를 정확히 적고 있다. 코드가 옮겨지면 이 문서도 같이 옮긴다 — program/plan/A-COP_여행전환_현황_2026-09-09.md
---

# 마이그레이션

`app/infrastructure/db/migrations/`

## 6개 — 지금은 13개다

`[실측 2026-09-10]` **마이그레이션은 작업 트리 13개 · git 9개**이고 `pending/` 에 미추적 `011_drop_commerce_domain.sql` 이 하나 있다. 여행 표는 `010_domain_travel.sql`(`places`·`bookings`·`supplier_bookings`)·`011_place_catalog.sql` 에 있다. **아래 표는 커머스 시절 목록이다** — 제목은 6개인데 표는 7행이고, 실제는 그 뒤로 더 늘었다.

`[실측]`

| 파일 | 무엇 | 왜 나중에 |
|---|---|---|
| `001_schema.sql` | Core 테이블 14종 | 기반 |
| `002_domain_commerce.sql` | orders · order_items · shipments · returns | 도메인 |
| `003_outbox_tenant_scoped_dedupe.sql` | outbox 중복 제거를 tenant 범위로 | 격리 결함 수정 |
| `004_agent_runs_active_uniqueness.sql` | 동시 실행 방지 | 동시성 결함 수정 |
| `005_outbox_resolution.sql` | outbox 해소 상태 | 운영 중 필요해짐 |
| `006_products_catalog.sql` | products | Catalog Team 착수 |
| **`007_returns_order_item.sql`** | **`returns.order_item_id`** | **환불 금액 추정 결함 수정** |

**003·004·007이 결함 수정에서 나왔다.** 처음 설계에 없던 제약이 운영·테스트에서 발견돼 추가됐다.

### ★ 007 — 환불 금액을 지어내던 것을 막았다

`[실측]` 2026-09-01. [D-001](../../../wiki/decisions/D-001-payment-ownership.md) 1-A 후속.

`returns` 에는 `order_id`·`reason_code`·`quantity` 만 있었다. **"주문 X 에서 3개 반품"은 알지만 어느 품목인지를 몰랐다.**

그래서 환불 금액을 이렇게 계산하고 있었다.

```python
amount = total * int(quantity) // item_count   # 주문 총액의 균등 분할
```

**품목 값이 서로 다르면 이 액수는 근거가 없다.** 할인이 걸려 있어도 마찬가지다.

#### NULL 을 허용한 게 핵심이다

**이미 쌓인 반품 행에는 품목 정보가 없다.** 지금 와서 채우면 그건 지어낸 값이다.

> `NULL` 은 **"모른다"**이고, 모르면 다품목 주문에서 **금액을 만들지 않고 사람에게 넘긴다.**

**빈 값을 그럴듯한 값으로 메우지 않는다.** [D-005](../../../wiki/decisions/D-005-write-gate.md)와 같은 원칙이다.

## 계획서보다 테이블이 5개 많다

`[실측]` 2026-09-01 기준.

| | 테이블 |
|---|---|
| 계획서 v8 §22 DDL 전문 | **14** |
| 실제 migrations | **19** |

**차이 5개가 다 도메인 쪽이다.**

```
orders · order_items · shipments · returns   (002)
products                                     (006)
```

**계획서 §22 는 Core 스키마만 적고 있다.** 도메인 커머스 테이블은 검증 쇼핑몰 연계가 결정되면서 나중에 붙었다.

`[미확보]` **§22 를 갱신할지 "Core 만"이라고 명시할지 정해지지 않았다.** 지금은 §22 만 읽은 사람이 테이블 수를 14로 안다.

## 재실행이 안전하다

전부 `CREATE TABLE IF NOT EXISTS` · `CREATE INDEX IF NOT EXISTS`다.

**여러 번 돌려도 같은 결과다.** 개발 중에 반복 실행하게 되므로 중요하다.

## 빠뜨리면 무너지는 제약 셋

`[실측]` handoff 계약이 "★빠뜨리면 시스템이 무너지는 제약 3개"로 따로 표시한 것들.

```sql
case_events     UNIQUE (case_id, aggregate_version)
action_requests UNIQUE (tenant_id, idempotency_key)
outbox          UNIQUE (tenant_id, topic, dedupe_key)
```

★`[정정 2026-09-07]` `outbox` 는 오래 `UNIQUE (topic, dedupe_key)` 로 적혀 있었다.
`003_outbox_tenant_scoped_dedupe.sql` 이 `tenant_id` 를 넣은 뒤에도 여러 문서가 옛
제약을 실었다. 살아 있는 DB 에서 `pg_constraint` 를 읽어 확인한 값이 위의 것이다
(`outbox_tenant_topic_dedupe_key_key`). 경위는 [outbox.md](../actions/outbox.md).

| 제약 | 없으면 |
|---|---|
| `case_events` | 같은 버전 이벤트가 두 번 들어가 상태가 갈린다 |
| `action_requests` | 같은 요청이 두 번 실행된다 |
| `outbox` | 같은 메시지가 두 번 발행된다 |

**애플리케이션 로직만으로는 동시성을 못 막는다.** DB 제약이 최종 방어선이다.

→ [../actions/idempotency.md](../actions/idempotency.md)

### `places` 의 유일성이 둘로 갈렸다 `[2026-09-27 · 029]`

`[실측]` `029_trip_scoped_places.sql` 이 `places_tenant_id_name_kind_key` 를 지우고 **부분 유일 색인 둘**로 바꿨다
(`acop_cs` 의 `pg_indexes` 로 확인).

```sql
places_shared_name_kind_uq  UNIQUE (tenant_id, name, kind)             WHERE trip_scope IS NULL
places_trip_name_kind_uq    UNIQUE (tenant_id, trip_scope, name, kind) WHERE trip_scope IS NOT NULL
```

- **왜.** 관광공사 콘텐츠랩 「로컬서버 저장 금지」·카카오 운영정책 제5조 — 외부 서비스에서 받은 장소 값을 공용 표에 쌓아
  다른 고객에게 재사용하지 않는다. 그런데 감시·대체 일정은 항목의 `place_id` 로 `places` 를 읽는다(15개 파일 48곳) —
  그래서 행은 만들되 **그 여행 전용**(`trip_scope` = 여행 id)으로 둔다.
- **누가 그렇게 넣나.** `places[].attributes.source` 가 `tour_api`·`kakao`·`google_places` 인 등록(`trip_api.EXTERNAL_PLACE_SOURCES`).
  일정 생성기의 관광공사 후보와 계획 읽기의 조회 결과가 여기에 든다.
- **누가 무엇을 보나.** `TripStore.places()` — 인자 없으면 공용만(일정 생성기 후보 · 에이전트 도구), `trip_id` 를 주면
  공용 + 그 여행 전용, 여러 여행을 도는 감시는 `every_trip=True` 로 읽고 여행마다 `visible_to` 로 거른다.
- ★`ON CONFLICT` 는 부분 색인의 조건까지 적어야 맞는다 — `ON CONFLICT (tenant_id, name, kind) WHERE trip_scope IS NULL`.
- `[2026-09-28]` 끝난 여행의 전용 행은 되잡기 `trip_places` 가 비운다(좌표·외부 식별자, 이름은 남긴다 — 설계서 §4-5 3번). 그 전 공용 행 5개에
  관광공사 출처 칸이 남아 있는 것도 그대로다.

### 장소 별칭 `place_aliases` `[2026-09-28 · 030]`

`[실측]` `030_place_aliases.sql` — (테넌트, 정규화한 원문) → 다시 찾을 이름. 계획 읽기 장소 찾기의 2단계(설계서 §4-1).
★**고객이 쓴 글 → 고객이 고친 글만** 담는다(둘 다 고객 글) — 관광공사·카카오가 준 이름·좌표는 담지 않는다(약관). 별칭은 다시 찾을 이름일
뿐이고 값은 매번 조회한다. 확인 화면에서 장소 이름을 고치면 쌓이고(`intake.pipeline.remember_alias`), 기본값은 코드의
`SEED_ALIASES`(남산타워 → N서울타워 등)다 — 고객이 고친 것이 이긴다.

### 웹 남용 방어 `web_usage` · `runtime_limits` · `runtime_limit_events` `[2026-09-28 · 031]`

`[실측]` `031_web_guard.sql` — 웹의 비싼 작업(계획 읽기 · 일정 짜기 · 확인 · 여행 만들기 · 채팅)과 키 발급을 **DB 에서 모든 프로세스가 같이** 센다
(`web_usage`, 027 `external_call_budget` 과 같은 방식). 주소는 원문이 아니라 `HMAC(서버 비밀키, 날짜|주소)` 만 남고 48시간 뒤 지운다.
운영자가 바꾼 제한값은 `runtime_limits`, 판 번호는 `runtime_limit_state`, 바꾼 기록은 `runtime_limit_events`(**트리거로 고치기·지우기 금지**).
기본값·범위는 가드레일 `web_guard` 가 정본이다. 코드 `app/modules/travel_ops/web_guard.py` · `web_limits_api.py`.
★적용: 전체 실행기(`app/infrastructure/db/migrate.py`)가 아니라 이 파일만 적용했다(2026-09-28) — 폴더에 다른 세션의 작업 중
마이그레이션(200번대 요식)이 함께 있어 전체를 돌리면 그것까지 적용된다.

### 보류 제안 이유 `relaxed` `[2026-09-29 · 033]`

`[실측]` `033_pending_relaxed.sql` — `pending_changes.reason` 제약에 `relaxed`(조건을 풀어 찾은 안 — 시각 늦추기 · 다음 일정 근처)를 더한다. 「다른 데로 바꿔 줘」가 같은 조건으로 0곳일 때 되는 안을 **묻는** 제안이다(`itinerary_changes.relaxed_options` · `trip_desk._ask_relaxed`). 옛 제약을 지우고 넓혀 다시 거는 방식이라 다시 돌려도 안전하다. ★적용: 이 파일만 적용했다(2026-09-29) — 031 과 같은 이유.

### 보류 제안 이유 `other_options` `[2026-09-29 · 035]`

`[실측]` `035_pending_other_options.sql` — `pending_changes.reason` 제약에 `other_options`(바꾼 뒤에도 고를 수 있는 다른 안)를 더한다. 「다른 데로 바꿔 줘」로 한 곳으로 **바꾼 뒤** 조건을 다 통과한 나머지 · 모자라면 조건을 푼 안을 셋까지 같은 항목의 제안으로 연다 — 고르면 그 안으로(`plan_swap`), 답이 없으면 바꾼 것을 그대로 둔다(`itinerary_changes.plan_fresh_alternate` · `trip_desk.fresh_alternate`). 옛 제약을 지우고 넓혀 다시 거는 방식이라 다시 돌려도 안전하다. (034 가 `requested_options` 를 더했다 — 이 절 위에 따로 적지 않았다.) ★적용: 이 파일만 적용했다(2026-09-29, 제약 조회로 확인) — 031 과 같은 이유.

### 관광공사 목록 운영시간 `catalog_hours` `[2026-09-29 · 036]`

`[실측]` `036_catalog_hours.sql` — 새벽 작업(`catalog_hours.prefill`, `run_sweepers --only catalog_hours`)이 관광공사 목록(`place_catalog`)의 활동 운영시간을 읽어 두는 표. 키 (tenant_id, source, content_id). 칸: 요일별 운영시간 `hours_week` · 읽은 방법 `hours_read` · 원문 `hours_origin`(이용시간 · 쉬는 날) · 문의 전화 · 읽을 때의 목록 수정 시각 `source_modified_at`(목록 값과 다르면 다시 읽는다) · `read_at`. 사실 정보만 적는다(사진 · 소개글 없음 — 2026-09-28 사용자 결정). 활동 「다른 데로 바꿔」는 요청 자리에서 관광공사를 부르지 않고 이 표를 읽는다(`catalog_pool`). ★적용: 이 파일만 적용했다(2026-09-29) — 031 과 같은 이유.

## 인덱스

`[실측]` 조회 격리를 받치는 인덱스.

```sql
orders_tenant_customer_idx     (tenant_id, customer_id)
shipments_tenant_customer_idx  (tenant_id, customer_id)
returns_tenant_customer_idx    (tenant_id, customer_id)
```

주석이 규칙을 밝힌다.

```sql
-- ★조회는 항상 tenant_id + customer_id 로 좁힌다(설계 원칙 §1).
```

## extension

```
vector     임베딩 vector(1536)
pgcrypto   gen_random_uuid()
```

**둘 다 없으면 001이 실패한다.**

## 환경 주의

`[실측]` **PostgreSQL이 Windows 서비스가 아니다.** conda env `pgv`에서 뜬 프로세스다. 재부팅 후 안 떠 있을 수 있다.

```
127.0.0.1:5433
```

`psql`이 PATH에 없다. → [../operations/local-setup.md](../operations/local-setup.md)

**Docker가 설치돼 있지 않다.** `docker/compose.yml`로 DB를 띄우는 전제는 이 기계에서 성립하지 않는다. 로컬 PG를 쓰고 compose 파일은 재현용으로만 남긴다.

## 임베딩 차원을 바꾸려면

```sql
knowledge_chunks.embedding vector(1536)   -- text-embedding-3-small
```

**모델을 바꾸면 DDL과 적재분을 함께 바꿔야 한다.** 차원이 다르면 기존 임베딩을 다 버려야 한다.

## 스키마를 바꾸려면

| 함께 해야 할 것 |
|---|
| 영향받는 Team 확인 |
| 계약(`contracts.py`) 대조 |
| 회귀 테스트 |
| handoff 문서 갱신 |

`[실측]` `app/core/contracts.py`는 `wiki/records/handoff/01_계약_Pydantic.md`의 **구현체다. 둘이 어긋나면 결함이다.**

## 관계

- [schema.md](schema/index.md) — 테이블 의미
- [tenancy.md](tenancy.md) — 격리
- [../operations/local-setup.md](../operations/local-setup.md) — DB 기동
- [../actions/idempotency.md](../actions/idempotency.md) — UNIQUE 제약의 역할

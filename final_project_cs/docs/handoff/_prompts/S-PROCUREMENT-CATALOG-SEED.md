# S-PROCUREMENT-CATALOG-SEED — 상품 카탈로그 테이블 + 실데이터 seed + `procurement.quote` 실 DB 조회화

## 0. 배경 — 조사로 확인된 사실 (Claude가 이번에 직접 확인함)

`app/modules/customer_ops/procurement_order_payment.py`의
`procurement.quote` 분기(line 137-149)는 지금 DB를 전혀 조회하지
않는다:

```python
if task.capability == "procurement.quote":
    ...
    pricing = task.context.current_state.get("pricing") or task.context.current_state.get("price")
```

`task.context.current_state`에 호출자가 `pricing`을 미리 넣어줘야만
동작한다 — `tests/unit/teams/test_procurement_order_payment.py`도
`pricing={"sku-1": 1200}`를 직접 주입해서 테스트한다. DB 라운드트립이
전혀 없다.

DB 쪽엔 상품 마스터/카탈로그 테이블이 아예 없다
(`app/infrastructure/db/migrations/001_schema.sql`,
`002_domain_commerce.sql` 확인 완료). `order_items`
(`002_domain_commerce.sql`:24-32)에 `sku`·`name`·`quantity`·`unit_cents`가
있지만 이건 **특정 주문 시점의 라인아이템 스냅샷**이지, SKU→현재가격을
독립적으로 조회할 수 있는 카탈로그가 아니다.

`app/tools/read_tools.py::ReadToolbox.call()`의 dispatch table
(line 102-108)엔 `read.order`/`read.shipment`/`read.policy`/
`read.return`/`read.account`만 있고 `read.catalog`가 없다. Team
manifest의 `allowed_tools`(line 35)도 마찬가지다.

`scripts/seed.py`에 이미 `CATALOG`라는 5개 SKU 리스트(line 27-33,
`SKU-TEE-01` 등)가 있지만 **독립 테이블로 저장되지 않고**
`order_items`를 채우는 데만 재사용된다.

실데이터: `../datasets/commerce/coupang_order_history/processed/orders.jsonl`에
실제 크롤링된 한국어 상품명 + 가격이 있다(PII 없음, `pii_hashes`
비어있음, `region` 수준만). 예: "도브 뷰티 크림 바 비누, 90g, 2개입"
4,100원, "해태 허니버터칩, 120g, 1개" 2,420원. 이 파일을 직접 열어서
실제 상품명·가격을 골라 써라(아래 예시는 참고용이고 이 파일이
정본이다).

## 1. 할 일

### 1.1 새 테이블 — `app/infrastructure/db/migrations/006_products_catalog.sql`

```sql
CREATE TABLE IF NOT EXISTS products (
    product_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   text NOT NULL,
    sku         text NOT NULL,
    name        text NOT NULL,
    unit_cents  int  NOT NULL,
    status      text NOT NULL DEFAULT 'active',  -- active / discontinued
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sku)
);
CREATE INDEX IF NOT EXISTS products_tenant_idx ON products (tenant_id);
```

이 정의를 그대로 써도 되고, `001_schema.sql`의 기존 테이블 관례(컬럼
타입·인덱스 스타일)와 맞춰 미세 조정해도 된다 — 단 `UNIQUE
(tenant_id, sku)`와 tenant 인덱스는 유지해라(`CLAUDE.md` §1 tenant
격리 원칙).

### 1.2 seed 데이터 — `scripts/seed.py` 갱신

- `../datasets/commerce/coupang_order_history/processed/orders.jsonl`을
  읽어서(9개 행, 8개 고유 상품 — `preprocess_stats.json` 확인) 실제
  상품명·가격으로 `products`에 8~9행을 넣어라. SKU 코드가 원본 데이터엔
  없으니 `SKU-CPG-01`처럼 새로 붙여도 된다.
- 기존 `CATALOG` 상수(5개, `SKU-TEE-01` 등)도 `products`에 함께
  넣어서 가격대 다양성(초저가·초고가)과 `status='discontinued'`
  케이스를 최소 1개는 커버해라(실데이터 8~9개만으론 이 edge case가
  안 나올 수 있다).
- `order_items`를 채우는 기존 로직은 이제 이 `products` 테이블에서
  SKU를 읽어와 채우도록 고쳐라(지금처럼 하드코딩 튜플을 중복해서
  갖고 있지 마라 — 한 곳에서만 정의한다).
- 재실행 안전(idempotent)하게 만들어라 — 기존 `scripts/seed.py`가
  이미 이 관례를 따르는지 확인하고 그대로 맞춰라.

### 1.3 `read.catalog` tool 추가 — `app/tools/read_tools.py`

`order()`/`shipment()` 메서드 패턴을 따라 `catalog()` 메서드를
추가해라:

```python
def catalog(self, scope: ToolContext, *, sku: str | None = None, **_: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
    ...
```

- `sku`가 주어지면 해당 SKU 한 건을(없으면 `None`), 없으면 tenant의
  전체 카탈로그를 반환해라(정확한 시그니처는 다른 메서드들과 일관되게
  네가 판단해라 — `order()`가 단건, `shipment()`가 목록을 반환하는
  패턴을 참고해라).
- 쿼리는 반드시 `tenant_id` 조건을 포함해라(`CLAUDE.md` §1).
- `functions` dispatch dict(line 102-108)에 `"read.catalog": self.catalog`를
  추가해라.

### 1.4 `procurement_order_payment.py` 갱신

- `manifest.allowed_tools`에 `"read.catalog"`를 추가해라(line 35).
- `procurement.quote` 분기(line 137-149)를 고쳐서, `read.catalog`로
  SKU 가격을 실제로 조회하게 해라. **완전히 갈아엎지 마라** — 기존
  `task.context.current_state.get("pricing")` 주입 경로는 **override로
  유지**해라(우선순위: 명시적으로 주입된 pricing이 있으면 그걸 쓰고,
  없으면 `read.catalog`로 DB 조회한다 — 기존 테스트가 이 경로에
  의존하니 깨지면 안 된다). SKU가 카탈로그에 없으면(discontinued거나
  존재하지 않으면) **지어내지 말고** `escalated`로 보내라(`CLAUDE.md`
  §0.1 "근거 없으면 답하지 않는다" 원칙 — 다른 Team의 기존 실패 처리
  패턴을 참고해라).

## 2. 검증

- `tests/unit/teams/test_procurement_order_payment.py`에
  `FakeTools.catalog` 케이스를 추가해서 기존 주입 경로(pricing이
  이미 있음)와 새 DB 조회 경로(주입 없음, catalog에서 찾음) 둘 다
  테스트해라. SKU가 카탈로그에 없는 경우(escalated) 케이스도 추가해라.
- 새 통합 테스트 `tests/integration/db/test_procurement_catalog.py`
  (또는 적당한 위치)를 추가해서, 실제로 seed된 `products` 행을 상대로
  `procurement.quote`가 종단으로 동작하는지(주입 없이) 확인해라.
- 마이그레이션 재실행 안전성 확인(`python -m
  app.infrastructure.db.migrate`를 두 번 실행해도 에러 없어야 한다).
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (396 passed 기준 변화 명시).

## 3. 쓰기 대상

- `app/infrastructure/db/migrations/006_products_catalog.sql` (신규)
- `scripts/seed.py`
- `app/tools/read_tools.py`
- `app/modules/customer_ops/procurement_order_payment.py`
- `tests/unit/teams/test_procurement_order_payment.py`
- `tests/integration/db/test_procurement_catalog.py` (신규 또는 적당한 위치)
- `docs/reports/2026-08-24_S-PROCUREMENT-CATALOG-SEED_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- 마이그레이션 번호 006 이 다른 병렬 작업과 겹치는지 실행 직전에
  확인해라(이 문서 작성 시점엔 005까지만 있다)
- `order.verify`/`order.create`/`order.modify`/`order.cancel`/
  `payment.status` 등 다른 capability 분기는 건드리지 마라 —
  `procurement.quote` 분기만 고친다
- 재고·배송·컴플라이언스 데이터를 지어내지 마라 — 이번 작업은
  가격 카탈로그 하나만 다룬다

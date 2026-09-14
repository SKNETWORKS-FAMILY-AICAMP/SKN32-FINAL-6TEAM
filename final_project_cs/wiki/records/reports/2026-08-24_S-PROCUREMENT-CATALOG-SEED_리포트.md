# S-PROCUREMENT-CATALOG-SEED 구현 리포트

## 결과

상품 카탈로그 테이블과 실데이터 seed를 추가하고, `procurement.quote`의 가격 근거를 실제 DB 카탈로그 조회로 연결했다.

- 신규 `products` 테이블: tenant별 SKU 유니크 제약과 tenant 인덱스 포함
- seed: `../datasets/commerce/coupang_order_history/processed/orders.jsonl`의 9행을 UTF-8 JSONL로 읽어 실상품명·가격을 저장
- seed 결과: 실상품 9행 + 데모 상품 5행 = `products` 14행
- 데모 상품에 초저가(`100` cents), 고가(`89_000` cents), `discontinued` 1건 포함
- `order_items`는 이제 `products`에서 조회한 활성 상품을 사용
- seed 재실행은 `(tenant_id, sku)` upsert로 안전
- `read.catalog`은 모든 조회에 `tenant_id` 조건을 포함
- `procurement.quote`는 명시적 `pricing`/`price` 주입을 우선하고, 없을 때만 SKU로 `read.catalog`을 조회
- 카탈로그 상품이 없거나 `discontinued`이면 `quote_catalog_product_missing`으로 escalation

## 변경 파일

- `app/infrastructure/db/migrations/006_products_catalog.sql`
- `scripts/seed.py`
- `app/tools/read_tools.py`
- `app/modules/customer_ops/procurement_order_payment.py`
- `tests/unit/teams/test_procurement_order_payment.py`
- `tests/integration/db/test_procurement_catalog.py`

## 검증

- `python -m app.infrastructure.db.migrate`: 1회 실행 성공
- 동일 명령 2회 실행: 모두 성공, 재실행 오류 없음
- `python -m scripts.seed`: 성공 (`products=14`, `customers=10`, `orders=30`, `order_items=30`, `shipments=20`, `returns=2`)
- procurement 단위 테스트: `11 passed`
- 신규 DB 종단 테스트: `1 passed`
- 컴파일 검증: 성공

전체 `python -m pytest -q -m "not live"` 결과:

`376 passed, 3 failed, 20 errors, 3 deselected, 2 warnings`

요청된 기준치 `396 passed`와 직접 비교하면, 이번 실행에서는 환경 오류 때문에 396 passed 상태를 재현하지 못했다. 카탈로그 변경으로 인한 새 테스트 실패는 확인되지 않았다.

전체 기준의 3개 실패는 기존 RAG 테스트가 OpenAI embeddings 네트워크 호출을 시도했으나 실행 환경에서 네트워크가 차단된 문제였다. 20개 에러는 기존 E2E 테스트의 pytest 임시 디렉터리(`AppData/Local/Temp/pytest-of-playdata2`) 접근 권한 오류였다. 새 카탈로그 단위·통합 테스트는 위와 같이 별도 실행에서 통과했다.

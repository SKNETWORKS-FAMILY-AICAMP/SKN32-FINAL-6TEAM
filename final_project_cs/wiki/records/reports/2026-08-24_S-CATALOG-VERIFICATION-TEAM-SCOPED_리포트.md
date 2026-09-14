# S-CATALOG-VERIFICATION-TEAM-SCOPED 구현 리포트

## 결과

Catalog & Verification Team을 A2A가 아닌 LOCAL Team으로 등록했다. `ports.team_executor: local`은 유지했고, `final_project_sample/`은 수정하지 않았다. 기존 `order.verify`와 충돌하지 않도록 다음 capability를 사용했다.

- `catalog.lookup_sku`
- `catalog.verify_listing`
- `catalog.compliance_check`

## 구현 내용

- `ReadToolbox.order_items()`를 추가하고 `read.order_items` dispatch를 등록했다.
  - `order_id`가 있으면 해당 주문의 line item을 조회한다.
  - 없으면 고객의 최신 주문 1건의 line item을 조회한다.
  - 모든 경로에 `tenant_id`를 적용하고, `orders.customer_id`를 조인해 주문 소유권을 제한한다.
- `CatalogVerificationTeam`을 추가했다.
  - SKU 조회 결과를 evidence로 남긴다.
  - SKU가 없으면 존재한다고 추정하지 않고 “찾을 수 없음”을 응답한다.
  - 주문 line item과 고객 주장 SKU/상품명을 대조하며 불일치 시 `listing_mismatch`로 escalation한다.
  - compliance 데이터는 만들지 않고 항상 `compliance_data_unavailable`로 escalation한다.
- `config/project.yaml`에 active Team을 등록했다.

## 검증

신규 단위 테스트:

```text
python -m pytest tests/unit/teams/test_catalog_verification.py -q
5 passed, 1 warning
```

조립 확인:

```text
python -m pytest tests/unit/teams/test_catalog_verification.py tests/unit/test_composition_root.py tests/unit/test_project_composition.py -q
21 passed, 2 failed, 2 warnings
```

신규 테스트 5개와 capability 중복 없는 실제 Registry 조립은 통과했다. 실패한 2건은 기존 테스트가 active Team을 정확히 5개로 고정해 새 `catalog_verification` 등록을 반영하지 않은 assertion이다.

전체 비-live 실행:

```text
python -m pytest -q -m "not live"
378 passed, 6 failed, 20 errors, 3 deselected, 2 warnings
```

S-PROCUREMENT-CATALOG-SEED 직전 리포트 기준은 `376 passed, 3 failed, 20 errors, 3 deselected, 2 warnings`였다. 이번 실행에서 신규 테스트 5개가 통과했고, 기존 Team 수 고정 assertion 2건과 introspection의 “all five teams” assertion 1건이 새 Team 등록으로 추가 실패했다. 나머지 RAG 3건은 실행 환경의 OpenAI 네트워크 차단, e2e 20 errors는 pytest 임시 디렉터리 권한 문제로 확인됐다.

추가로 변경 파일은 Python compile 검사를 통과했고, Registry에서 `catalog` case가 `catalog_verification`으로 resolve되는 것을 직접 확인했다.

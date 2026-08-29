# S-CATALOG-VERIFICATION-TEAM-SCOPED — 6번째 Team, 범위 축소판 (LOCAL 등록)

## 0. 배경 — 왜 축소판인가

`../program/plan/A-COP_구현계획서_v8.md`(읽기만 해라)는 6번째 Team으로
"Catalog & Verification (A2A Remote)"를 명시한다. 조사 결과 두 가지
현실적 제약이 확인됐다:

1. **A2A 라우팅이 아직 없다.** `app/composition.py::build_team_executor`는
   레지스트리 전체에 대해 executor 하나(local 또는 a2a)만 고른다 —
   Team별로 local/remote를 섞는 구조가 지금 코드에 없다. 이 계약은
   **A2A 라우팅 설계를 별도 후속 작업으로 미루고**, 이 Team을 지금
   있는 다른 5개처럼 **LOCAL로 등록**한다. `config/project.yaml`의
   `ports.team_executor: local`은 그대로 둔다.
2. **재고·컴플라이언스 데이터가 전혀 없다.** 있는 건 `order_items`
   (주문 시점 SKU 스냅샷)와, 오늘 다른 계약(S-PROCUREMENT-CATALOG-SEED)이
   막 추가한 `products`(가격 카탈로그, `read.catalog` tool로 이미
   조회 가능 — `app/tools/read_tools.py` 확인해라, 이미 있다)뿐이다.
   컴플라이언스 데이터는 **지어내지 않는다** — 그 capability는 존재를
   명시하되 항상 정직하게 거부하는 스텁으로 만든다.

## 1. capability 설계 — 이름 충돌 주의

`procurement_order_payment`(이미 활성)가 `order.verify`를 이미
선점하고 있다. **같은 이름을 쓰면 `build_registry()`가
`CompositionError`(중복 capability)를 던진다** — 다른 이름을 써라:

- `catalog.lookup_sku` — SKU 존재·가격·상태(active/discontinued) 조회.
  이미 있는 `read.catalog` tool(`app/tools/read_tools.py`, 오늘
  S-PROCUREMENT-CATALOG-SEED가 추가함 — 파일을 열어서 정확한
  시그니처를 확인해라)을 그대로 재사용해라. SKU가 없으면 지어내지
  말고 "not found"를 정직하게 답한다(거부/escalate가 아니라 "그런
  SKU 없음"이라는 사실 자체가 유효한 응답이다 — 혼동하지 마라).
- `catalog.verify_listing` — 고객이 주장하는 상품/SKU가 실제 주문의
  `order_items`와 일치하는지 대조한다("고객은 A를 샀다고 하는데
  주문엔 B로 찍혀있다" 같은 케이스를 잡는다). 이건 **order_items
  라인아이템 상세**가 필요한데 지금 어떤 tool도 이걸 노출하지
  않는다 — §2 참고.
- `catalog.compliance_check` — **항상 정직하게 거부하는 스텁이다.**
  실행하면 무조건 `outcome="escalated"`,
  `failure_code="compliance_data_unavailable"`,
  `warnings=["컴플라이언스 데이터가 아직 없어 확인할 수 없습니다"]`
  같은 형태로 응답해라(다른 Team의 기존 escalate 패턴을 참고해서
  일관되게 만들어라). **절대 컴플라이언스 결과를 지어내지 마라** —
  `CLAUDE.md` §0.1 "근거 없으면 확정 답변을 만들지 않는다" 정면 적용
  사례다.

## 2. `read.order_items` tool 신규 추가 — `app/tools/read_tools.py`

★**중요**: 이 파일은 오늘 다른 계약(S-PROCUREMENT-CATALOG-SEED)이 막
`catalog()` 메서드를 추가했다. 시작하기 전에 그 계약이 완료됐는지
`git log`나 파일 내용으로 먼저 확인해라(이미 `def catalog(` 이
있으면 완료된 것이다) — 그 메서드나 `functions` dict의 다른 항목은
건드리지 말고, **네 것만 추가해라.**

`order()`/`shipment()` 패턴을 따라 새 메서드를 추가해라:

```python
def order_items(self, scope: ToolContext, *, order_id: str | None = None, **_: Any) -> list[dict[str, Any]]:
    ...
```

- `order_id`가 주어지면 그 주문의 라인아이템만, 없으면 고객의 최근
  주문(들)의 라인아이템을 반환해라(정확한 범위는 `order()`가 최신
  주문 1건만 보는 것과 일관되게 네가 판단해라).
- `tenant_id`(그리고 가능하면 `customer_id`로 주문 소유권까지) 조건을
  반드시 포함해라(`CLAUDE.md` §1).
- `functions` dispatch dict에 `"read.order_items": self.order_items`를
  추가해라.

## 3. Team 모듈 신규 — `app/modules/customer_ops/catalog_verification.py`

기존 5개 Team(예: `return_refund.py`, `fulfillment_logistics.py`)의
구조를 그대로 따라라 — `TeamManifest`, `TeamModule`(또는 동등한
프로토콜), `TeamTask`를 받아 `TeamResult`를 반환하는 `execute()`.

```python
manifest = TeamManifest(
    team_id="catalog_verification",
    display_name="Catalog & Verification Team",
    contract_name="a_cop.team_task",
    supported_contract_versions=["1.0"],
    capabilities=["catalog.lookup_sku", "catalog.verify_listing", "catalog.compliance_check"],
    accepted_case_types=["catalog"],
    required_context=["case_state", "policy", "db_facts", "history"],
    allowed_tools=["read.catalog", "read.order_items", "read.policy"],
    knowledge_scope=["catalog"],
    max_steps=6,
    active=True,
    implementation_revision="2026-08-24",
)
```

정확한 필드는 다른 Team의 실제 manifest와 `app/core/contracts.py`의
`TeamManifest` 정의를 대조해서 맞춰라(위는 참고용 초안이다).

- `catalog.lookup_sku`: `read.catalog` 호출 → 있으면 사실을 evidence로
  담아 `respond`, 없으면 "SKU를 찾을 수 없다"는 사실을 evidence로
  담아 `respond`(거짓으로 있다고 하지 않는다 — 없다는 것도 정직한
  답이다).
- `catalog.verify_listing`: `read.order_items` + 고객이 주장한
  SKU/상품명(`task.context.current_state`에서 읽어라 — 다른 Team이
  `current_state`를 읽는 방식을 참고해라)을 대조해서 일치/불일치를
  evidence로 남긴다. 불일치면 `escalated`로 보내라(사람이 봐야 하는
  상황이다).
- `catalog.compliance_check`: §1에서 설명한 대로 항상 정직한 거부.

## 4. `config/project.yaml` 등록

```yaml
- team_id: catalog_verification
  active: true
  implementation_ref: app.modules.customer_ops.catalog_verification:CatalogVerificationTeam
```

(정확한 클래스명은 네가 §3에서 실제로 만든 이름과 일치시켜라.)
`ports.team_executor`는 **건드리지 마라** — `local` 그대로 둔다.

## 5. 검증

- 새 단위 테스트 `tests/unit/teams/test_catalog_verification.py` —
  기존 Team 테스트(`test_return_refund.py` 등)의 `FakeTools`/`make_task`
  패턴을 그대로 따라라. 세 capability 각각 최소 1개 성공 케이스 +
  `catalog.lookup_sku`의 "SKU 없음" 케이스 + `catalog.verify_listing`의
  "불일치→escalated" 케이스 + `catalog.compliance_check`의 "항상
  escalated" 케이스.
- `python -m pytest tests/unit/test_composition_root.py
  tests/unit/test_project_composition.py -q` — 새 Team이 Registry에
  중복 capability 충돌 없이 조립되는지 확인해라(기존 회귀 테스트가
  이미 이런 걸 잡는 구조다).
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (S-PROCUREMENT-CATALOG-SEED 적용 후 숫자를 기준으로 변화 명시 —
  정확한 기준 숫자는 실행 직전 리포트 디렉터리에서 가장 최근
  숫자를 확인해라).

## 6. 쓰기 대상

- `app/tools/read_tools.py` (§2 새 메서드만 추가 — 기존 메서드 건드리지 마라)
- `app/modules/customer_ops/catalog_verification.py` (신규)
- `config/project.yaml`
- `tests/unit/teams/test_catalog_verification.py` (신규)
- `docs/reports/2026-08-24_S-CATALOG-VERIFICATION-TEAM-SCOPED_리포트.md` (신규)

## 7. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `ports.team_executor`를 `a2a`로 바꾸지 마라 — A2A 라우팅은 이
  계약의 범위가 아니다(별도 설계 필요, §0 참고)
- `order.verify`나 다른 Team이 이미 쓰는 capability 이름을 재사용하지
  마라
- 재고·배송·컴플라이언스 데이터를 지어내거나 임의로 채우지 마라 —
  `catalog.compliance_check`는 반드시 정직한 거부 스텁이어야 한다
- `app/tools/read_tools.py`의 `catalog()` 메서드(오늘 다른 계약이
  만든 것)를 고치거나 지우지 마라 — 네 것(`order_items()`)만 추가한다

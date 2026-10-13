# Commerce Agent 표면 설계: MCP·UCP·AP2

## 결론

현재 v7에는 소비자 개인 AI가 쇼핑 기능을 쓰는 표면이 없다. MCP는 **CS MCP**로만 계획되어 있고, Commerce MCP는 새로 설계해야 한다. 두 표면은 서버 구현을 공유할 수 있지만, 공개 표면과 권한 계약은 나눈다. CS는 본인 Case 중심이고 Commerce는 상품·장바구니·주문이라는 자산과 주문 상태를 다루므로 인증 주체와 side effect 경계가 다르다.

| 표면 | 무엇 | 현재 상태 |
|---|---|---|
| CS MCP | 내 Case 조회, 문의 접수 | v7에 read-only 3 tool로 계획됨 |
| **Commerce MCP** | 상품 검색·장바구니·주문·배송조회 | **계획 없음** |

공통 Gateway, scope, audit, Context Broker, Core 2를 쓰되 MCP server와 tool namespace는 `cs.*`와 `commerce.*`로 분리한다. 주문·결제·환불·주문상태 변경은 v7 원칙대로 MCP에서 직접 실행하지 않고 REST/내부 Action과 승인 경로로 보낸다.

## 1. Commerce Tool 초안

| Tool | 구분 | v7 단계 | 실행 경계 |
|---|---|---|---|
| `commerce.search_products` | 읽기 | read | 가격·재고 시각·상품 식별자를 함께 반환 |
| `commerce.get_product` | 읽기 | read | canonical product id와 옵션을 반환 |
| `commerce.get_inventory` | 읽기 | read | 조회 시각과 판매 가능 수량을 표시 |
| `commerce.get_price` | 읽기 | read | 통화·세금·할인 적용 여부를 명시 |
| `commerce.list_my_orders` | 읽기 | read | 본인 ownership과 scope 확인 |
| `commerce.get_delivery_status` | 읽기 | read | 주문·배송 식별자와 provider evidence 대조 |
| `commerce.add_to_cart` | 쓰기 | reversible operational write | 별도 scope, idempotency, audit, 장바구니 소유권 |
| `commerce.update_cart` | 쓰기 | reversible operational write | 수량·옵션 재검증, 주문 생성 전 되돌릴 수 있어야 함 |
| `commerce.remove_from_cart` | 쓰기 | reversible operational write | 별도 scope와 idempotency |
| `commerce.create_order` | 쓰기 | financial/order-state side effect | MCP 직접 실행 금지. ActionProposal→승인→Core 2 |
| `commerce.cancel_order` | 쓰기 | financial/order-state side effect | 취소 가능 상태·금액·주문 소유권을 실행 직전 대조 |
| `commerce.request_return` | 쓰기 | financial/order-state side effect | 법정 청약철회와 정책 후보를 코드·사람 승인으로 분리 |

`add_to_cart`는 되돌릴 수 있지만 소비자 의도와 장바구니 소유권을 기록한다. `create_order`를 장바구니 쓰기와 합쳐 한 번에 실행하지 않는다. 결제·환불·주문상태·권한 변경은 v7의 financial/order-state 경계를 유지한다.

## 2. UCP와의 정합

시장격차 문서에 따르면 UCP는 **Shopping service / Capabilities / Extensions**의 계층이고, 2026-03 업데이트에서 Cart와 Product Discovery가 추가되어 현재 5개 capability다. AP2와 호환되며 API·A2A·MCP로 통합할 수 있다고 설명된다. 이는 지금 UCP를 구현하라는 요구가 아니라, 내부 Tool 이름과 반환 계약을 나중에 매핑할 수 있게 하자는 설계 근거다.

| UCP 계층·capability | 우리 표면 | 현재 판단 |
|---|---|---|
| Shopping service | `commerce.*` Gateway와 상품·주문 service | 내부 canonical resource를 먼저 만든다 |
| Product Discovery | `search_products`, `get_product` | Commerce MCP 후보 |
| Cart | `add_to_cart`, `update_cart`, `remove_from_cart` | reversible write로 제한 |
| 2026-01에 제시된 기존 3개 capability | 가격·재고·주문/배송 projection으로 대응 | 원문 capability 명칭을 추가 확인하기 전 이름을 확정하지 않는다 |
| Extensions | 옵션, 배송, 반품, 근거·tenant metadata | 내부 schema에 extension 영역을 둔다 |

우리의 `order_id`, `product_id`, `variant_id`, `currency`, `quantity`, `inventory_as_of`, `evidence_ref`를 안정된 필드로 둔다. 이후 UCP capability를 붙일 때 Adapter가 이 필드를 UCP schema로 변환하며, Core·Case·Action 계약은 바꾸지 않는 방향이다.

## 3. AP2 연결점

AP2는 에이전트 구매를 서명된 Mandate 세 종류인 **Intent / Cart / Payment**로 표현하고 W3C Verifiable Credentials를 사용한다는 사실이 연구 문서에 있다. 우리 설계에서의 연결은 다음과 같다.

- Intent: 소비자 AI가 어떤 상품·조건을 찾는지의 요청과 scope.
- Cart: `cart_id`, 상품 식별자, 옵션, 수량, 가격 snapshot.
- Payment: 결제수단·결제 위임의 증명과 승인 결과.

v7의 `ActionProposal`은 AP2 Mandate를 대체하지 않는다. 나중에 결제 위임을 열면 Mandate version, actor, scope, expiration, 서명 검증 결과를 Core 2의 실행·audit에 연결해야 한다. MVP에서는 결제 위임, 서명된 Payment Mandate, 무인 결제를 하지 않는다. 주문·결제는 Mock/Sandbox와 사람 승인 범위로 제한한다. Mandate/Outcome의 외부 write도 v7 기준상 새 MCP로 열지 않는다.

## 4. 소비자 에이전트 주문의 할루시네이션 방어

에이전트의 자연어 답을 사실로 보지 않고, 실행 직전 코드가 ActionProposal과 현재 자료를 대조한다.

| 대상 | 대조 원천 | 불일치 시 |
|---|---|---|
| 금액 | 현재 가격·할인·통화 snapshot, 장바구니 합계, 결제/주문 projection | 실행 거부 또는 `waiting_approval`; 임의 보정 금지 |
| 수량 | cart의 line item, 재고 조회 시각, 주문 허용 수량 | 재조회 후 재승인; 부족하면 주문하지 않음 |
| 상품 식별자 | canonical `product_id`·`variant_id`, 옵션·판매 상태 | 이름만 일치하면 불충분. 식별자 없는 제안은 거부 |
| 주문 상태 | PostgreSQL Source of Truth와 provider evidence | 상태가 이미 변했으면 `unknown`/escalated |
| 반품·취소 가능성 | 코드 결정표, 주문일·배송일·상태·정책 evidence | LLM 판정이 아닌 규칙·승인 경로로 처리 |

가격·수량·상품 식별자는 Context Pack에서 읽었다는 사실만으로 충분하지 않다. proposal의 시각·scope·idempotency key를 붙이고 Core 2가 재조회한다. 실패하면 side effect를 실행하지 않고 근거와 mismatch를 audit에 남긴다.

## 5. v7 §28 엑셀 요약 문구 수정안

기존 문장 뒤에 다음 한 문장을 붙인다.

> Personal AI는 CS MCP로 Case를 조회·접수하고, 별도 Commerce MCP로 상품·장바구니·주문·배송 리소스에 접근하되 주문·결제·환불 같은 재무·주문상태 side effect는 v7의 승인·idempotency·audit 경계를 거친다.

이는 UCP/AP2를 이미 구현했다고 말하지 않고, 향후 API·A2A·MCP Adapter를 붙일 수 있는 표면만 명시한다.

## 6. 범위와 실소요

| 구분 | 실소요 | 포함 |
|---|---:|---|
| 생성 | 2~3일 | namespace, Tool schema, resource 필드, scope·ownership 표, UCP 대응 문서 |
| 검증·통합 | 2~3일 | read contract, cart idempotency·rollback, 금액/수량/식별자 mismatch fixture, 기존 MCP 회귀 |
| 대기 | 1일 | Commerce 데이터·배송 상태 fixture와 owner 승인 |

이번 범위에서 빼는 것은 UCP native server, AP2 서명·Payment Mandate, 실제 PG 결제·자동 환불, 주문 생성 MCP direct write, 새 REST endpoint, 별도 Commerce Team의 전면 구현이다. 기존 CS MCP 3개와 v7의 REST 5개 계약을 깨지 않으며, Commerce는 read surface와 cart 계약을 설계하고 주문 side effect는 내부 Action/Mock으로만 검증한다.

# A-COP 예제 Team 모듈 확충 설계

## 1. 결론

계획서 §8-B의 6개 Team을 기준으로 설계한다. 현재 구현·등록 상태는 `voc_store_manager` 하나다. `response_generation_review`는 구현되어 있지만 Registry가 선택할 수 없는 상태다. 나머지 4개는 신규 설계 대상이다.

| Team | 상태 | 핵심 조치 |
|---|---|---|
| VOC & Store Manager | 구현·등록됨 | 기존 동작을 유지하고 계약 테스트·프롬프트·데모 fixture를 보완 |
| Response Generation & Review | 구현됨·미등록 | 등록하고 `accepted_case_types`와 prompt 등록을 보완 |
| Procurement + Order & Payment | 신규 설계 | 주문·결제 제안과 승인 경계 구현 |
| Fulfillment & Logistics | 신규 설계 | 배송 상태 조회와 물류 후속 조치 제안 구현 |
| Return & Refund | 신규 설계·Mock | 실제 쇼핑몰 대신 결정·제안·승인 흐름을 fixture로 검증 |
| Catalog & Verification | 신규 설계·A2A Remote | Agent Card와 A2A Adapter를 통한 원격 실행 구현 |

여기서 “현재 확인”은 `final_project_cs` 코드와 설정 또는 이번 밤 현황 스냅샷에서 확인한 내용이다. “설계”는 계획서 §7, §8-B와 현재 계약을 바탕으로 제안하는 값이다.

## 2. 공통 계약과 Registry 해석

현재 `TeamModule`은 `manifest: TeamManifest`와 `async execute(task: TeamTask) -> TeamResult`를 요구한다. `TeamManifest`의 실제 필드는 `team_id`, `display_name`, `capabilities`, `accepted_case_types`, `required_context`, `allowed_tools`, `knowledge_scope`, `active`, `implementation_revision` 등이다.

`TeamRegistry.resolve(case_type, intent)`는 먼저 `accepted_case_types`로 후보를 좁힌다. `intent`가 있으면 capability가 intent와 같거나 `intent + "."`로 시작하는 Team을 우선한다. 최종 후보는 정확히 하나여야 한다. 따라서 case type을 여러 Team이 공유할 때는 intent를 반드시 분류 결과에 포함하고, intent가 없는 경로에서는 충돌이 생기지 않도록 case type을 분리한다.

현재 `project.yaml`의 등록 형태는 다음과 같다.

```yaml
teams:
  - team_id: voc_store_manager
    active: true
    implementation_ref: app.modules.customer_ops:VocStoreManagerTeam
```

실제 Team은 side effect를 실행하지 않는다. 주문 생성, 결제, 환불, 배송 변경과 같은 요청은 `ActionProposal`로만 반환한다. `approval_required=True`인 제안이 있으면 `next_action=wait_for_approval`, `wait_reason=human_approval`을 함께 반환해야 한다. 답변이 있으면 evidence가 있어야 한다.

## 3. Team별 확충 설계

### 3.1 VOC & Store Manager

**현재 확인.** `VocStoreManagerTeam`이 구현되어 있고 `project.yaml`에 활성 등록되어 있다. `team_id`는 `voc_store_manager`, 표시명은 `VOC & Store Manager Team`이다. capability는 `voc.aggregate`, `voc.escalate`이며 `accepted_case_types=["other"]`이다. `required_context`는 `case_state`, `policy`, `db_facts`, `history`이고, `allowed_tools`는 `read.policy`다. knowledge scope는 `order`, `shipping`, `return`, `exchange`다.

**남은 일.** Team 본체를 새로 만들 필요는 없다. 다음을 보완한다.

- 반복 complaint와 VOC 집계에 대한 golden fixture 및 contract test를 추가한다.
- 현재 구현의 `read.policy` 직접 호출이 Context Broker 중심 원칙과 충돌하지 않는지 정리한다. 전환 기간에는 manifest의 allowed tool을 유지하되, 최종 경로는 ContextPack의 policy evidence를 우선 사용한다.
- prompt가 필요해지는 LLM 경로를 추가할 때 `prompts/voc_store_manager/answer.v1.md`와 `answer.repair.v1.md`를 등록한다.

**TeamResult.** 일반 VOC는 `outcome=completed`, `next_action=respond`, evidence와 안내 answer를 반환한다. 유사 complaint가 2건 이상이면 `voc.escalate` ActionProposal을 내고 `outcome=waiting`, `next_action=wait_for_approval`로 둔다. 현재 구현도 이 형태를 사용하며, 제안은 `approval_required=True`, `risk_level=low`다.

### 3.2 Response Generation & Review

**현재 확인.** `ResponseGenerationReviewTeam`은 구현되어 있다. `team_id`는 `response_generation_review`, capability는 `response.generate_review`, `required_context`는 네 종류 전체, allowed tool은 `read.policy`, knowledge scope는 `response_review`다. 구현은 생성 후 금칙어·PII·사실 불일치 검사를 하고 최대 4회 재시도한다.

**남은 일.** 단순 config 한 줄만으로는 충분하지 않다. 현재 manifest의 `accepted_case_types=[]`라서 `resolve`가 이 Team을 선택할 수 없다. `response` 같은 전용 case type을 정하고 manifest를 보완한 뒤 등록해야 한다. 또한 `response.generate`, `response.review_tone` prompt key의 active row를 prompt registry에 넣고, 생성 성공·PII 검출·재시도 소진 fixture를 등록한다. 기존 구현의 결과 매핑은 이미 `answer`, `decisions`, `warnings`, `escalated` 결과로 계약에 맞는다.

**설계 manifest.**

- team_id: `response_generation_review`
- 표시명: `Response Generation & Review Team`
- capabilities: `response.generate_review`
- accepted_case_types: `response`
- intent: `response` 또는 `response.generate_review`
- required_context: `case_state`, `policy`, `db_facts`, `history`
- allowed_tools: `read.policy`
- knowledge_scope: `response_review`

**TeamResult.** 검사를 통과하면 `completed + respond`와 근거 있는 answer를 반환한다. tone 경고는 `warnings`에 남기고 confidence를 낮춘다. PII, 검증 실패, 재시도 소진은 `escalated + escalate`다. 이 Team은 side effect 제안을 내지 않는다.

**필요 prompt.** `prompts/response_generation_review/answer.v1.md`, `answer.repair.v1.md`, `tone_review.v1.md`. 코드의 prompt key는 각각 `response.generate`, 재시도용 `response.generate`의 repair 입력, `response.review_tone`으로 매핑한다.

### 3.3 Procurement + Order & Payment

**설계 manifest.** 주문·결제 의도를 하나의 Team이 처리하되 capability namespace를 분리한다.

- team_id: `procurement_order_payment`
- 표시명: `Procurement + Order & Payment Team`
- capabilities: `procurement.quote`, `order.verify`, `order.create`, `payment.status`
- accepted_case_types: `procurement`, `order`, `payment`
- intent: `procurement`, `order`, `payment`
- required_context: `case_state`, `policy`, `db_facts`, `history`
- allowed_tools: `read.order`, `read.account`, `read.policy`
- knowledge_scope: `catalog`, `pricing`, `order`, `payment`, `procurement`

Registry는 `order + order.create`, `payment + payment.status`처럼 intent를 함께 받아 이 Team을 선택한다. Catalog Remote도 `order`를 받으므로 `order.verify`와 `catalog.lookup`을 명시적으로 구분한다.

**TeamResult.** 가격·재고·결제 상태를 확인하면 evidence와 함께 `completed + respond`로 결과를 준다. 주문 생성 제안은 `action_type=order.create`, 결제 승인은 `payment.authorize`, 결제 확정은 `payment.capture`를 사용한다. Action Gateway vocabulary는 `order.create`, `payment.authorize`, `payment.capture`, `shipment.investigate`, `shipment.reroute`, `shipment.replace`, `return.request`, `refund.request`, `voc.escalate`로 고정한다. 기존 코드와 계약 테스트가 사용하는 `refund.request`와 namespace·동사 형식을 유지해 idempotency key와 audit의 action type이 흔들리지 않게 한다. 금액·수량·배송지·결제수단이 포함되거나 주문 상태를 바꾸는 제안은 `approval_required=True`, `risk_level=high`, `next_action=wait_for_approval`로 반환한다. 사실이 부족하면 `wait_for_input`과 required input schema를 반환한다. 주문 생성 자체는 실행하지 않는다.

**필요 prompt.** `prompts/procurement_order_payment/answer.v1.md`, `answer.repair.v1.md`, `proposal.v1.md`. proposal prompt는 금액·수량·주문 ID를 evidence에 대조할 값을 구조화하는 용도이며, 최종 검증은 코드와 Core가 담당한다.

### 3.4 Fulfillment & Logistics

**설계 manifest.**

- team_id: `fulfillment_logistics`
- 표시명: `Fulfillment & Logistics Team`
- capabilities: `fulfillment.track`, `shipment.status`, `shipment.exception`
- accepted_case_types: `fulfillment`, `shipping`, `shipment`
- intent: `fulfillment`, `shipment`, `shipping`
- required_context: `case_state`, `db_facts`, `history`, `policy`
- allowed_tools: `read.order`, `read.shipment`, `read.policy`
- knowledge_scope: `order`, `shipping`, `warehouse`, `delivery_exception`

**TeamResult.** 배송 상태와 tracking evidence를 제시하면 `completed + respond`다. 배송 지연·분실·주소 오류처럼 후속 조치가 필요하면 `shipment.investigate`, `shipment.reroute`, `shipment.replace` 중 가능한 제안을 낸다. 주소·수취인·배송 상태를 변경하는 제안은 `approval_required=True`, `risk_level=medium` 이상으로 하고 승인 대기로 전환한다. 운송장이나 주문이 없으면 확정 답변 대신 `escalated` 또는 추가 입력 대기를 반환한다. 배송 시스템을 Team이 직접 호출하거나 갱신하지 않는다.

**필요 prompt.** `prompts/fulfillment_logistics/answer.v1.md`, `answer.repair.v1.md`, `exception.v1.md`.

### 3.5 Return & Refund

**설계 manifest.** 계획서의 Mock Team이다.

- team_id: `return_refund`
- 표시명: `Return & Refund Team`
- capabilities: `return.check_eligibility`, `return.request`, `refund.calculate`
- accepted_case_types: `return`, `refund`, `exchange`
- intent: `return`, `refund`, `exchange`
- required_context: `case_state`, `policy`, `db_facts`, `history`
- allowed_tools: `read.order`, `read.return`, `read.policy`
- knowledge_scope: `order`, `return`, `refund`, `exchange`, `policy`

**Mock의 범위.** 실제 쇼핑몰 API, 결제사, 반품 택배를 호출하지 않는다. 주문·반품·환불 상태와 사유 코드는 고정 fixture에서 읽고, eligibility 판정·환불 금액 계산·승인 경로·실패 경로를 실제 계약으로 검증한다. 따라서 Mock은 fake side effect를 성공 처리하지 않는다. 실행 가능한 것처럼 보이는 요청도 ActionProposal에서 멈춘다.

**TeamResult.** 반품 가능 여부만 판단하면 `completed + respond`다. 반품 접수는 `return.request`, 환불은 `refund.request` 제안으로 표현한다. 환불 금액·결제수단·주문 상태를 변경하는 제안은 `approval_required=True`, `risk_level=high`, `wait_for_approval`다. 정책 증거가 없거나 주문 상태가 불일치하면 `escalated`다. 고객이 주문번호·상품·수량을 주지 않은 경우에는 `wait_for_input`이다.

**필요 prompt.** `prompts/return_refund/answer.v1.md`, `answer.repair.v1.md`, `eligibility.v1.md`, `proposal.v1.md`.

### 3.6 Catalog & Verification

**현재 확인.** `app/presentation/a2a/remote_agent.py`에 Catalog & Verification 원격 Agent fixture가 있다. Agent Card는 `catalog_verification`과 `catalog.lookup`, `order.verify`, accepted case types `catalog`, `order`를 광고한다. `A2ATeamExecutor`는 주입된 transport로 submit·poll하고, working·input-required·completed·failed를 canonical `TeamResult`로 매핑한다.

**설계 manifest.**

- team_id: `catalog_verification`
- 표시명: `Catalog & Verification`
- capabilities: `catalog.lookup`, `order.verify`
- accepted_case_types: `catalog`, `order`
- intent: `catalog`, `order.verify`
- required_context: `case_state`, `db_facts`, `history`, `policy`
- allowed_tools: `[]`. Remote Agent의 read-only capability는 Agent Card와 A2A 인증 범위로 관리하고 로컬 `TeamTask.allowed_tools`에는 넣지 않는다.
- knowledge_scope: `catalog`, `sku`, `variant`, `compliance`, `order`

**TeamResult.** 원격 artifact `verification_report`와 `evidence_manifest`를 받으면 remote_agent evidence와 함께 `completed + respond` 또는 다음 Team으로 `handoff`한다. SKU·variant·포장 단위가 부족하면 A2A의 `input-required`를 `waiting + wait_for_input`으로 매핑한다. 인증 실패·timeout·취소·artifact 누락은 성공으로 처리하지 않고 `escalated`로 정규화한다. 카탈로그 조회는 주문·결제 side effect를 만들지 않는다.

**A2A 등록 방식.** 현재 `TeamManifest`와 `TeamRegistry`에는 `execution_type`이 없다. 따라서 이 Remote Team은 현재 로컬 `implementation_ref`를 등록하는 방식으로 완성되지 않는다. 계획서가 제시한 Registry 확장 필드인 `execution_type: A2A`, `agent_card_url`, `a2a_endpoint`, `auth_scheme`를 추가하고, 등록 entry를 A2A adapter/capability resolver에 연결해야 한다. `A2ATeamExecutor`는 네트워크를 소유하지 않고 주입된 transport만 사용한다. Agent Card 발견은 `/.well-known/agent-card.json`, task 왕복은 `/a2a/tasks`와 poll endpoint를 사용한다. 로컬 Team은 `execution_type: LOCAL`과 `LocalTeamExecutor(registry)`로 직접 module을 호출하고, Remote Team은 `execution_type: A2A`와 `A2ATeamExecutor`로 canonical `TeamResult`를 만든다.

**필요 prompt.** 원격 Agent가 자체 prompt를 소유한다면 로컬 `answer.v1.md`는 필수가 아니다. A-COP에서 원격 결과를 해석하거나 handoff하는 경계를 둔다면 `prompts/catalog_verification/remote_result_review.v1.md`를 별도 등록한다. 로컬 prompt가 원격 검증을 재생성하지 않도록 한다.

## 4. 구현 순서

1. **Response Generation & Review** — 구현이 끝나 있어 accepted case type 보완, prompt 등록, config 등록, contract test로 가장 빨리 데모할 수 있다. 등록만으로 끝나지 않는 이유는 현재 `accepted_case_types=[]`이기 때문이다.
2. **Return & Refund Mock** — 외부 연동 없이 주문·반품·환불의 ContextPack, ActionProposal, 승인 대기를 보여줄 수 있다. 금융 side effect를 fixture로 격리할 수 있어 기준 Team으로 적합하다.
3. **Procurement + Order & Payment** — Return & Refund에서 만든 주문·금액·승인 검증 패턴을 재사용한다. 단독 조회는 가능하지만 주문 생성·결제는 Core Action Gateway와 함께 데모해야 한다.
4. **Fulfillment & Logistics** — 주문·배송 fixture가 필요하고 Procurement와 연결하면 시나리오가 좋아진다. 다만 `read.shipment`만으로 조회 데모는 독립 실행할 수 있다.
5. **VOC & Store Manager 보완** — 본체는 이미 구현·등록되어 있으므로 신규 Team 제작보다 fixture, prompt 경로, Context Broker 정합성, 반복 complaint 평가를 보완한다. 기존 등록을 활용해 전체 흐름의 회귀 기준으로 삼는다.
6. **Catalog & Verification** — 외부 A2A transport, 인증, poll, input-required, artifact, timeout·cancel 검증이 필요하다. 마지막에 두어야 local canonical 결과와 승인 경계를 먼저 고정할 수 있다.

## 5. 공통 뼈대

과도한 도메인 상속 계층은 만들지 않는다. 참조 구현에서 반복되는 것은 다음 네 가지다.

1. `TeamManifest` 작성과 capability·case type·scope의 정적 검증
2. `TeamTask`에서 evidence를 복사하고 tool/remote 결과를 표준 `Evidence`로 정규화하는 helper
3. degraded context, tool loop, policy 또는 사실 누락을 `TeamResult`로 변환하는 실패 helper
4. `ActionProposal`의 idempotency key, risk level, approval flag, rationale evidence ID를 채우는 builder

공통 뼈대는 상속 없이 조합형 유틸로 구현한다. `app/modules/customer_ops/team_utils.py`의 순수 함수로 `evidence_from_context`, `failure_result`, `approval_result`, `proposal`을 제공한다. Team이 `CustomerOpsTeamBase`의 생명주기나 상태에 결합되지 않아 Remote·Mock·Local 구현이 같은 계약을 선택적으로 재사용할 수 있다. capability 판정, 환불 가능 여부, 배송 예외, 응답 tone과 같은 업무 판단은 각 Team에 남긴다. `TeamModule.execute`의 시그니처와 `TeamResult` 검증은 그대로 둔다.

공통 prompt도 하나로 합치지 않는다. 각 Team의 `answer.v1.md`와 `answer.repair.v1.md`는 같은 파일명 규칙을 쓰되, prompt key와 knowledge scope는 Team별로 분리한다. 현재 코드의 `judge/*.txt`는 평가 prompt이고, 새 업무 prompt와 동일한 것으로 취급하지 않는다.

## 6. 등록·검증 완료 기준

- 각 active Team은 `TeamRegistry.register`를 통과하고 contract version `1.0`을 지원한다.
- 각 `case_type`과 intent 조합은 정확히 한 Team으로 resolve된다.
- 모든 answer에는 evidence가 있고, 모든 proposal의 rationale ID가 result evidence에 존재한다.
- 승인 대상 proposal은 반드시 `wait_for_approval`과 `human_approval`을 동반한다.
- Local Team은 side effect를 실행하지 않고 Local executor를 통해 호출된다.
- Remote Team은 Agent Card·인증·poll·input-required·artifact·timeout·cancel을 A2A adapter에서 처리하고 canonical `TeamResult`만 Core에 전달한다.
- Mock Team은 외부 API 성공을 가장하지 않고 fixture 기반 결과와 proposal까지만 반환한다.

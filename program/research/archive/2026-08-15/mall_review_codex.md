# A-COP 쇼핑몰 확장안 검토

## 결론

**조건부 채택**한다. 쇼핑몰은 v6를 대체하는 새 본체가 아니라 v6의 Case·Action·Approval·Port 경계를 검증하는 Commerce Reference Vertical로만 채택한다. 10주 안에 감당 가능한 범위는 Mock/Sandbox, Shadow, 팀 내부 저액·저위험 Live와 제한된 실제 문의·취소·반품 Case다. 일반 고객 대상 해외 구매대행·PG·무인 환불은 채택하지 않는다.

## 검토표

| # | 위치 | 문제 유형 | 무엇이 문제인가 | 근거(인용) | 수정 제안 | 심각도 |
|---:|---|---|---|---|---|---|
| 1 | 확장안 §6.2, v6 §7 | Team 경계 | 확장안은 Return & Refund Team이 Marketplace Return Adapter를 호출한다고 쓴다. v6는 Team이 side effect를 실행하지 않고 ActionProposal만 반환한다고 고정한다. | 확장안: “Return & Refund Team ... Marketplace Return Adapter 호출”. v6: “Team은 side effect를 실행하지 않고 ActionProposal만 반환한다.” | Team은 ReturnProposal만 반환하고 Controller가 Core 2에 ExecuteAction으로 위임한다. **확장안을 v6에 맞춘다.** | 치명적 |
| 2 | 확장안 §3.4, v6 §3-A·DoD 13 | MCP 충돌 | 확장안 Tool 초안에 주문·취소·반품·증빙 업로드 쓰기가 있다. v6 확정 범위는 MCP read-only 3개다. | 확장안: “create_order”, “request_return”. v6: “REST 5개 endpoint와 MCP read-only 3개 tool”. | MCP는 조회·상태·Case read만 두고 쓰기는 REST/내부 Action API로 둔다. | 치명적 |
| 3 | 확장안 §6.1, v6 §19 | Case lifecycle | ORDER_CREATED→CLOSED는 주문 상태이고 v6 공식 Case 상태가 아니다. 매핑과 전이 API가 없다. | 확장안: “ORDER_CREATED ... CLOSED”. v6: “상태 변경은 transition_case(...) 단일 진입점으로만 수행”. | 주문·결제·배송은 Shared State/도메인 projection으로 두고 Case는 v6 상태만 사용한다. | 높음 |
| 4 | 확장안 §4.5·§7.4, v6 §21·§22 | 상태·스키마 | REQUESTED, PROCURED, CUSTOMER_REFUND_PENDING 등 새 상태가 v6 Pydantic Enum·DDL·DoD와 통합되지 않았다. | 확장안: “REQUESTED→VERIFYING ... PROCURED”. v6 DDL은 case_status/action_status만 정의. | Commerce 상태는 별도 versioned Action/원장 계약으로 만들고 case_events와 연결한다. | 높음 |
| 5 | 확장안 §2, v6 §8-B·부록 A | Port 혼선 | v6 플랫폼 Port 3종은 MessageBusPort, GraphStorePort, TeamExecutorPort다. 확장안은 “Core는 MarketplacePort와 ReturnAdapterPort에만 의존”한다고 쓴다. | v6: “MessageBusPort ... GraphStorePort ... TeamExecutorPort”. 확장안: “Core는 MarketplacePort와 ReturnAdapterPort에만 의존”. | 기존 3종은 유지하고 Marketplace/Return은 Commerce provider adapter 경계로 정의한다. | 높음 |
| 6 | 확장안 §3.4, v6 §20·§21 | ActionProposal 우회 | 확장안은 쓰기 Tool이 scope·risk·approval token을 검사한다고만 한다. v6 흐름은 ActionProposal→Controller→Core2 ExecuteAction→ActionResult다. | 확장안: “쓰기 Tool은 모두 ... 검사”. v6: “Team→Core1 Controller→Core2 Action→Core1 State”. | 모든 쓰기를 ActionProposal·승인·ExecuteAction·ActionResult로 강제한다. | 높음 |
| 7 | 확장안 §7.3, v6 §20 | Adapter 미완성 | purchase와 request_refund는 side effect 메서드인데 승인·unknown·재시도·callback의 소유가 없다. | 확장안: “async def purchase(...)”, “async def request_refund(...)”. v6: “Provider timeout은 unknown이며 자동 재실행하지 않는다.” | Adapter는 Core 2가 소유하고 timeout은 unknown으로 남긴다. | 높음 |
| 8 | 확장안 §2·§9.2, v6 §22 | 새 컴포넌트 계약 누락 | Evidence, Dual Refund Ledger, Credit Ledger, Order/Shipment/Quote는 필요하지만 v6 DDL·Pydantic·DoD가 없다. | 확장안: “Dual Refund Ledger”, “Pilot Credit Ledger”. v6 DDL은 customer_cases, action_requests, outbox 등을 정의. | Commerce Extension에 계약·DDL·이벤트·소유 Core·DoD를 별도로 추가한다. | 높음 |
| 9 | 확장안 §6.2, v6 §16·§18 | 범위 과대 | 확장안은 6개 Agent Team을 제시하지만 v6는 착수 Team 2~3개를 기준선으로 삼는다. | 확장안: “필수 Agent Team 확장”. v6: “도메인 1개와 착수 Team 2~3개”. | Catalog/Procurement와 Order/Logistics를 모듈·Mock Adapter로 합치고 실제 Team은 2~3개만 만든다. | 치명적 |
| 10 | 확장안 §5.2·브리핑 §11 | 근거 없는 KPI | 요청 5회, 전환 40%, SLA 90%, 반품률 10%, 오상품 2%는 예시 수치인데 발표에서 기준처럼 보인다. | 확장안: “예시 기준”. v6: “운영 규모 미검증”. | 가설로 표시하고 분모·기간·표본·CI 없이 합격 기준으로 쓰지 않는다. | 중간 |
| 11 | 확장안 §12/브리핑 §12 | 신고·표시 의무 | 판매자·구매대행자·중개자 지위와 표시 주체가 미결정이다. 정부24는 소비자와 직접 상거래하는 통신판매업 신고를 안내하고 전자상거래법 제12·13조는 신고·신원·거래조건 제공을 규정한다. | 확장안: “판매자 vs 구매대행자”, “사업자·통신판매 신고”. [정부24 신고 안내](https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=11300000006), [전자상거래법](https://www.law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1029561435) | 확정 전에는 내부/클로즈드 베타만 한다. 실제 판매는 사업자·신고·약관·표시광고 확인 뒤에만 연다. **확인 필요.** | 치명적 |
| 12 | 확장안 §7.1·§7.4 | 청약철회와 LLM | 환불 자격 판단을 Team 흐름에 넣었지만 법정 철회와 하자·오배송·변심 구분, 입증, 기한이 없다. 공식 법령상 일반 철회 기간은 7일이고 환급은 요건에 따라 3영업일 이내다. | 확장안: “고객측 환불 자격 판단”, “법적 자격을 단독 확정하지 않는다”. [제17조](https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&joLsJoLnkSeq=1031805923), [제18조](https://www.law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1027063343) | LLM은 사실 추출·증거 누락·정책 후보만 제안한다. 가부는 결정표+사람 승인, 기한은 워커로 보장한다. 10주에는 변심/오배송/파손만 제한한다. | 치명적 |
| 13 | 확장안 §4.4·§8.3 | PG·정산·세무 | payment_fee는 있으나 PG 계약 주체, 취소·부분환불, 정산 대사, 카드정보 비보관, 세금계산서·현금영수증 흐름이 없다. | 확장안: “payment_fee”, “PG·환전 수수료”. [국세청 전자세금계산서 안내](https://webtv.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7787&mi=2461) | 실 PG는 계약·정산·세무 확인 후에만 열고, 10주에는 Sandbox/결제 mock과 가상 대사로 고정한다. 발급 주체는 확인 필요. | 치명적 |
| 14 | v6 §24, 확장안 §3·§7 | PII 충돌 | v6는 저장·LLM 전달 전 masking을 요구한다. 실제 배송은 원문 주소·연락처가 필요하고 확장안은 해외 제공을 전제로 한다. | v6: “PII는 저장·LLM 전달 전에 masking”. 확장안: “해외 판매처로 사진·주소·연락처가 전달되면 개인정보 국외이전 요건을 검토”. [개인정보위](https://m.pipc.go.kr/np/default/page.do?mCode=D060040010) | 원문 배송정보는 암호화 Vault에 최소 보관하고 Case에는 토큰만 둔다. 국외이전 근거·위탁·보호조치 확인 전 Live 금지. | 치명적 |
| 15 | 확장안 §4.2·§8.5 | 해외 통관 | 통관·규제품목·세액을 검증한다고 했지만 개인통관고유부호의 처리와 수입자 책임이 없다. 관세청은 이를 해외직구 개인물품 수입자 특정 부호로 안내한다. | 확장안: “통관 ... 개인통관정보 필요 여부”. [관세청 안내](https://www.customs.go.kr/kcs/na/ntt/selectNttInfo.do?bbsId=1362&mi=2891&nttSn=10142854) | 국내 저위험 품목 또는 Mock으로 축소한다. 해외는 read-only 검증·사람 전달까지만 한다. | 치명적 |
| 16 | 확장안 §7·브리핑 §6 | 오답 책임 | “저위험 Case 응답”과 사진 제출을 제시하지만 잘못된 배송·환불 안내의 책임자, 정정·분쟁·보상 절차가 없다. | 브리핑: “저위험 Case 응답”, “고객 환불+비용 회수”. 확장안: “사람이 정답·근거·허용 Action을 검수”. | 외부 발송 전 정책 근거·금지문구·사람 승인 검사를 두고 모든 발송·정정을 Audit한다. | 높음 |
| 17 | 확장안 §8.3·브리핑 §7 | 예산 오류 | 브리핑의 6×5만원+20×1만원+20×1만원+100만원은 170만원인데 180만원으로 표시한다. 구현명세의 6×5만원+20×10만원도 230만원인데 180만원으로 표시한다. | 브리핑: “전체 ... 180만원”. 구현명세: “6 × 50,000 + 20 × 100,000 = 1,800,000 KRW”. | Credit과 Reserve를 분리해 다시 계산하고 발표 수치를 통일한다. | 높음 |
| 18 | 구현명세 §8.5 vs 브리핑 §7 | Pilot 불일치 | 구현명세 Stage 3는 같은 기수 약 20명·1인 1만원·상한 30만원인데 브리핑은 같은 기수 20명과 추가 20명을 모두 실제 Pilot처럼 제시한다. | 구현명세: “같은 기수 약 20명 ... 전체 상한 30만원”. 브리핑: “같은 기수 약 20명”, “추가 약 20명”. | 발표에는 Stage 0~2만 확정, Stage 3·4는 Gate로 표시한다. | 높음 |
| 19 | 구현명세 §7.1·§7.4 vs 브리핑 §6 | 도식 모순 | 브리핑은 Return Policy 판단→Marketplace 제출→고객 환불+비용 회수로 보인다. 구현명세는 고객 환불과 Upstream Recovery를 독립 판단한다. | 브리핑: “고객 환불+비용 회수”. 구현명세: “공급처가 거절해도 고객에게 환불해야 하는 Case가 있을 수 있다.” | 두 Ledger를 병렬 분기로 그린다. | 높음 |
| 20 | 구현명세 §10.1 vs 브리핑 §10 | 권한 표현 오류 | 구현명세는 eBay 권한이 제한되고 credentials_status가 NOT_GRANTED, live_enabled가 false라고 했는데 브리핑은 Return 문서 존재만 보여 Live 가능처럼 보인다. | 구현명세: “credentials_status: NOT_GRANTED”, “live_enabled: false”. 브리핑: “Return·파일 업로드 문서”. | “문서 존재 ≠ 계정 권한 ≠ Live 가능”을 표시한다. | 높음 |
| 21 | 브리핑 §11 vs v6 §16 | 역할 불일치 | 브리핑의 6명 역할에는 평가 담당이 없다. v6는 검증·프론트 1명을 평가 harness·golden/holdout 전담으로 둔다. | 브리핑: “6명 수직 역할”. v6: “검증 & 프론트 1명 ... 평가 harness”. | Store Manager를 구현 Team이 아닌 운영 시나리오로 낮추고 평가 담당을 복원한다. | 높음 |
| 22 | 브리핑 §13 | 판정 과장 | “PASS WITH LIVE GATES”와 “PG·외부 API 권한 미결정”, “일반고객 결제 금지”가 한 블록에 있어 전체 PASS로 오독된다. | 브리핑: “아직 Gate”, “일반고객 결제 금지”, “최종 판정: PASS WITH LIVE GATES”. | “문서 반영 PASS / Live 운영 BLOCK”으로 분리한다. | 중간 |

## 범위 현실성

전면 실판매·해외조달·PG·외부 반품은 6명 10주의 대부분을 잠식하므로 불가하다. v6의 배치는 코어 2명·모델 3명·검증·프론트 1명이고 주차별 Core/Team/평가 작업이 이미 꽉 차 있다. Commerce 전담은 Catalog/Commerce 1명 5일, Access/Action 1명 5일, Runtime 1명 3일, 평가·프론트 1명 3일, 모델 2명은 Mock 시나리오·계약 테스트 병행을 상한으로 둔다.

| 대안 | 실제 Case 달성도 | 실소요 일수(추정) | 판단 |
|---|---|---:|---|
| Simulation Commerce: 상품·주문·배송·환불 Mock | Case lifecycle·WAIT/RESUME·ActionProposal·idempotency 검증이 높음 | 6명 8~10일 | 채택 |
| Shadow: 실제 상품정보 read-only, 구매는 사람 | 실제 공급처 변동을 일부 얻음 | 2명 5일 + 평가 5일 | Mock 뒤 제한 채택 |
| 클로즈드 베타: 팀/지인 5~10명, 국내 저위험 품목 | 실제 주문·문의·취소·반품 Case 생성 | 4명 5일 구축 + 2명 5일 운영 | 법률 Gate 통과 때만 |
| 결제 mock + Assisted Procurement | 승인·감사·실패 Case 검증, 실제 결제 분쟁은 불가 | 3명 5일 | 기준선으로 적합 |

## 3분류 요약

### 먼저 결정해야 할 것

- 판매자·구매대행자·중개자 중 거래모델을 정한다.
- 일반 고객 Live를 열지 내부·지인 베타로 제한할지 정한다.
- 국내 저위험 품목만 할지 해외 통관까지 할지 정한다.
- PG·정산·세무·국외이전 책임 주체를 정한다.
- v6의 MCP read-only와 Team side-effect 금지를 유지한다고 확정한다.

### 고쳐야 할 것

- 주문·환불 상태를 v6 Case lifecycle과 매핑한다.
- Commerce Pydantic·DDL·이벤트·DoD를 만든다.
- Team 직접 Adapter 호출을 제거하고 ActionProposal→승인→ExecuteAction으로 통일한다.
- PII Vault/토큰화와 배송 원문 접근을 설계한다.
- Pilot 수치·예산·HTML·MD의 Stage·역할·DoD를 통일한다.
- 환불 판단을 LLM 단독 결정에서 사람 승인+기한 워커로 바꾼다.

### 무시 가능

- Commerce 때문에 Graph DB를 새로 도입하는 일. v6의 SqlGraphAdapter로 충분하다.
- UCP-shaped manifest 세부 확장.
- Store Configurator/Commerce Factory 비전의 구현.
- 자동 영구 Catalog 승격.

## 최종 판단

확장안의 방향은 타당하지만, 실제 판매를 본체에 넣는 순간 부트캠프 프로젝트가 사업·법률·금전·PII 프로젝트로 변한다. **v6를 기준선으로 유지하고 Mock 중심의 조건부 Reference Vertical로 채택한다.** 일반 고객 실판매·해외 구매대행·무인 환불은 10주 범위에서 제외한다.

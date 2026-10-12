# v7 기준 Agent Team 최종 구성 판정

## 결론

v7의 VOC Team 승격은 현재 근거만으로 유지하기 어렵다. 7절이 말하는 “급증인가”가 7-A절의 고정 공식으로 완전히 결정되므로 FILTER-2를 충족하지 않는다. 다만 비정형 VOC 해석, 반복 불만의 원인 후보 정리, 누구에게 어떤 업무를 위임할지에 대한 제안까지 포함하면 VOC를 Team으로 유지할 여지는 있다. 이 경우 승격 근거는 급증 계산이 아니라 위임 제안과 운영 판단의 범위에 둬야 한다.

확장안의 6개 Team은 실제 문서에 있다. 다만 명칭은 사용자가 제시한 6개와 정확히 같지 않다. 확장안 427–436행은 `Catalog & Verification`, `Procurement`, `Order & Payment`, `Fulfillment & Logistics`, `Return & Refund`, `VOC & Store Manager`를 열거한다. 따라서 6팀 분할은 확장안에서 유래한 것으로 보이며, v7의 SaaS Team slot을 폐기한 것이 아니라 Commerce reference implementation에 병행 적용한 확장안이다.

최종 권고는 Commerce MVP에서 LOCAL Team 3개를 `Order & Payment`, `Fulfillment & Logistics`, `Return & Refund`로 두고, `Catalog & Verification`은 A2A Remote Team으로 검증하는 구성이다. VOC는 고정 공식 기반 배치/운영 모듈로 시작하고, 실제 위임 판단 골든셋이 확보될 때만 LOCAL Team으로 승격한다. v7의 기존 SaaS 기준선을 유지하는 경우에는 LOCAL `Billing`, `Technical`, `VOC`와 Catalog A2A를 유지하되, Commerce 6팀을 동시에 추가하지 않는다.

## 1. v7 VOC Team 승격 검증

v7 94행은 VOC가 이상징후, 반복 불만, 공급처·처리 성능을 보고 다른 Team에 위임 제안을 할 수 있다고 말한다. 96행은 입력을 `Case events·분류 결과·Action 결과`, 출력을 리포트·알림·위임 제안으로 규정한다. 이 내용만 보면 비정형 사건을 종합하고 다음 처리 주체를 선택하는 업무 판단이 있다.

그러나 108행은 급증을 다음 공식으로 고정한다.

`오늘 count >= max(5, 1.5 × 최근 7일 평균) AND 오늘 count - 최근 7일 평균 >= 3`

또한 z-score, embedding clustering, topic modeling을 쓰지 않는다고 명시한다. 따라서 “급증인가”는 규칙으로 적을 수 있고, 그 부분은 FILTER-2가 아니다. 7절의 “급증을 판단한다”는 표현과 7-A절의 “고정 임계값 배치” 사이에는 범위상의 내부 모순이 있다. 정확히는 VOC가 Team인 이유를 급증 판정에 두면 모순이고, 급증 결과를 입력으로 받아 후속 의미 해석·위임을 판단한다고 좁히면 모순이 완화된다.

유지 가능한 근거는 다음과 같다.

- 고객 문장·리뷰·Case history에서 반복 불만의 원인 후보와 영향 대상을 정리하는 FILTER-1.
- 같은 급증이라도 배송, 상품, 반품, 공급처 성능 중 어느 축의 문제인지 판단하는 FILTER-2.
- 리포트 생성, 운영자 알림, 대상 Team의 `delegation_proposal`을 함께 구성하는 FILTER-3.
- 누구에게 알릴지, 어떤 증거를 요구할지, 재실행할지에 대한 권한·지식·Tool 경계.

따라서 권고는 “VOC Team 유지”가 아니라 “VOC Team 조건부 유지”다. MVP에서는 고정 집계 배치와 리포트/알림을 모듈로 두고, 위임 대상·우선순위·필요 증거·재시도 판단의 골든셋이 생기면 Team으로 승격한다.

## 2. 6팀 분할의 출처와 지위

확장안 3–7행은 현재 판매 본체를 SaaS형 `A-COP CS / Customer Operations Platform`으로 두고, 쇼핑몰은 주문·배송·반품·환불까지 확장 적용하는 Reference Implementation/Testbed라고 설명한다. 즉 Commerce는 SaaS의 대체가 아니라 검증용 도메인 확장이다.

| 확장안의 Team | v7의 직접 대응 | 지위 |
|---|---|---|
| Catalog & Verification | Catalog & Verification A2A Remote Team | 직접 대응. v7 120행, 290행, 561행의 Remote 후보와 일치한다. |
| Procurement | v7에는 독립 slot으로 고정되지 않음 | 확장안의 Commerce capability. v7 290행은 Procurement+Order & Payment 통합 착수를 제안한다. |
| Order & Payment | v7 SaaS의 Billing과 일부 대응 | 도메인은 달라졌지만 결제·주문 상태·승인·idempotency 경계는 공통 기반을 사용한다. |
| Fulfillment & Logistics | v7에는 직접 slot 없음 | Commerce 확장안의 외부 배송 대기·재진입 capability다. |
| Return & Refund | v7 Billing의 환불과 일부 대응 | 확장안에서 독립 정책·증빙·외부 Case 경계로 세분화된다. |
| VOC & Store Manager | v7 VOC/Feedback Analytics | 가장 직접적인 대응. v7 94–110행의 VOC Team/배치 구조가 확장안에서 Store Manager까지 넓어진다. |

v7의 명시적 LOCAL slot은 127행의 `Billing / Technical / VOC`이고, 120행에는 `Catalog & Verification` A2A Remote가 있다. 따라서 확장안은 v7의 SaaS Team slot을 수정한 최종 목록이 아니라, 같은 Case·Registry·TeamResult 계약 위에 Commerce domain을 병행한 설계다.

## 3. 6팀별 판정

판정은 “FILTER 하나 이상”과 “정답셋·임의 배정 비의존·코어 루프”의 동시 충족을 1단계로 적용하고, 통과 후보에만 네 축 중 최소 둘의 차이를 적용했다. 이 기준은 동일한 연구 문서 521–524행에 정리되어 있다. 현실적 LOCAL Team 상한은 3개로 본다(같은 문서 539–544행).

| Team | 1단계 | 2단계 | 최종 판정 |
|---|---|---|---|
| Customer Operations & Complaint | 비정형 문의·불만 분류와 상황별 조회 조합은 통과 가능. 정답셋과 Case 루프도 기존 계약으로 만들 수 있다. | 통과한 하위 도메인의 권한·외부 대기·지식·실패 정책을 모두 포괄하는 우산 명칭이다. 독립된 두 축이 아니라 여러 Team의 합집합이다. | 별도 Team 아님. Case intake/routing과 기존 Order·Return·Fulfillment·VOC의 공통 표면으로 둔다. |
| Catalog & Procurement | 상품명·옵션·규제·가격의 비정형 해석, 외부 Catalog/Marketplace 도구 조합, Quote→검증→승인 루프가 있다. | Catalog 검증은 외부 판매처/공급처 대기와 Catalog 지식, 모호한 Variant 실패 정책이 분명히 다르다. | Team급. v7처럼 A2A Remote가 맞다. Procurement는 별도보다 Catalog와 묶거나 Order와 합쳐 평가하는 편이 MVP에 맞다. |
| Order & Payment | 주문 문장 해석, 주문·결제 상태 조회·취소·부분취소·승인 조합, `unknown` 재진입이 있다. | PG/결제 provider 대기, 금전 실행 권한, 결제 ledger 지식, timeout 시 자동 재실행 금지 정책이 Fulfillment/Return과 다르다. | Team급. Commerce MVP 핵심 LOCAL 후보다. |
| Fulfillment & Logistics | 배송 지연·분실·통관의 비정형 사유와 운송장·외부 조회 조합, callback 대기 루프가 있다. | Carrier/통관 대기, 물류 지식, 배송 상태 권한, timeout·재조회·escalation 정책이 다르다. | Team급. Order와 구분 가능하다. |
| Return, Refund & Evidence | 반품 사유·증빙 해석, 주문 원장·정책·외부 반품 adapter 조합, 추가 증빙→대기→재개 루프가 있다. | 고객/판매자/마켓플레이스의 반품 Case 대기, 증빙·환불 정책 지식, 반품 상태와 고객 환불 ledger의 이중 상태, 증빙 부족·재검 정책이 다르다. | Team급. Order & Payment와 분리할 근거가 충분하다. |
| VOC & Store Manager | 비정형 리뷰·문의와 이슈 종합은 통과 가능하나 고정 급증 배치만 보면 FILTER-2가 탈락한다. | 위임 제안을 실제 capability로 넣을 때에만 권한·지식·대상 Team·재시도 경계가 두 축 이상 달라진다. | 조건부 Team. MVP는 배치/운영 모듈, Phase 2 Team 승격을 권고한다. |

Order & Payment와 Return, Refund & Evidence는 네 축에서 분리 가능하다. 다만 별도 Team 두 개를 넣는 것과 다른 Team을 함께 유지하는 것은 별도 문제다. Commerce MVP에서 두 개를 모두 LOCAL로 넣으려면 세 번째 LOCAL을 Fulfillment로 제한하고 VOC를 배치 모듈, Catalog를 A2A Remote로 두어야 한다. v7의 `Billing/Technical/VOC`를 그대로 유지하면서 Commerce 3개를 추가하는 것은 상한을 넘으므로 권고하지 않는다.

## 4. jh 마케팅 확장안 판정

jh DOCX 7–21행의 트랙 C와 25–32행의 트랙 D를 기준으로 판정했다.

| 항목 | 1단계 판정 | 2단계/지위 |
|---|---|---|
| C① 관심사 추출 | 고객 문장이라는 비정형 입력과 검색어 도구 조합으로 FILTER-1/3. 키워드·상품군 골든셋은 만들 수 있다. | 별도 Team 아님. VOC의 입력 정규화/리포트 산출물. 시장 트렌드와 매출 정답을 혼동하면 안 된다. |
| C② 수요 신호 종합 | “없나요” 문맥과 Catalog 부재·검색 실패를 구분하는 FILTER-1/2. Catalog snapshot과 사람 라벨로 사실 판정 정답은 만들 수 있다. | 별도 Team 아님. VOC 출력 또는 Catalog fact signal이다. “수요가 실제로 발생했다”는 시장 정답은 별도다. |
| C③ 연간 소비 패턴 | 시간축 비교·비정형 원인 해석·검색 트렌드 조합으로 FILTER-2/3 가능. | 단일 snapshot으로는 계절성을 학습할 수 없다. 여러 기간의 동일 상품·카테고리·노출·프로모션·판매량·문의량을 축적해야 한다. 그 전에는 “계절 패턴”이 아니라 관측된 시점 차이다. 별도 Team 아님. |
| C④ 세트 상품 기획 | 동시구매 집계와 문의 관계 조합으로 FILTER-3 가능. | 동시구매는 연관성 정답이지 추천 적중 정답이 아니다. 구매 후 만족·클릭·전환·반품 감소 등의 평가 라벨 없이는 추천 Agent로 통과하지 못한다. 분석 tool/리포트로 제한한다. |
| C⑤ 기획전 제안 | 앞선 신호를 제약·근거와 종합하는 FILTER-2/3. 제안 루브릭 골든셋은 만들 수 있다. | VOC의 `report`/`delegation_proposal` 출력으로 둔다. 매출 효과 정답이 확보되기 전에는 Team을 새로 만들지 않는다. |
| D① 반품 사유 분석 | 반품 사유 텍스트·증빙 분류는 FILTER-1. 반품 사유 골든셋과 상태 등급 라벨이 있으면 통과한다. | Return, Refund & Evidence Team의 내부 capability다. VOC Team으로 분류하면 반품 원장·증빙 권한 경계를 흐린다. |
| D② 재고 누적 감지 | 임계값 감지는 고정 규칙이다. FILTER-2가 없다. | 배치/룰이다. VOC가 알림을 소비하거나 출력할 수는 있지만 Team은 아니다. |
| D③ 리퍼브 기획전 제안 | 반품 상태·수량·가격·정책·판매자 동의를 조합하는 FILTER-2/3 가능. | Return Team 결과를 VOC/Store Manager가 제안으로 종합하는 구조가 적절하다. 별도 Team은 아니다. |

따라서 “8개 모두가 VOC Team의 출력 유형”이라는 가설은 절반만 맞다. C①·C②·C③·C⑤와 D③은 VOC의 리포트/alert/delegation proposal로 흡수할 수 있다. D①은 Return Team 내부 판단이고 D②는 규칙 배치이며 C④는 정답이 없는 연관성 분석이다. 이 8개를 새 Team으로 늘리지 않는 결론은 유지하되, 모두를 VOC의 출력이라고 부르는 것은 부정확하다.

## 5. 실데이터가 바꾸는 것

실제 스마트스토어 주문·반품·취소·교환·리뷰 데이터가 확보되면 정답셋 부재로 보류했던 일부 판정은 되살아난다. 단, 데이터가 있다는 사실만으로 Agent Team이 되는 것은 아니다. 라벨·시간축·업무 루프·권한 경계가 함께 있어야 한다.

### Olist의 지위

Olist를 주 데이터로 쓰는 판정은 대체된다. 실제 데이터가 주문·반품·취소·교환·리뷰를 제공하면 실제 데이터가 primary source가 되어야 한다. 다만 Olist의 관계형 거래 골격과 외부 benchmark 지위는 유지할 수 있다. 즉 Olist는 schema/관계 mapping fixture와 비교 기준으로 남고, 한국 정책·판매자 운영·실제 리뷰 분포는 스마트스토어 데이터로 덮는다. 연구 문서 211–216행의 “Olist 골격, 정책은 tenant config와 통제 합성 데이터” 원칙은 “실데이터가 없을 때의 기준선”으로 재해석한다.

### 되살아나는 항목

- 주문·취소·반품·교환 상태 분류와 환불 가능성: 실제 상태 전이와 처리 결과로 골든셋을 만들 수 있다.
- 리뷰·문의 이슈 분류와 반복 불만: 사람 라벨, 후속 처리 결과, 재문의 여부를 연결하면 VOC의 비정형 판단이 강화된다.
- 배송 지연·반품 사유·교환 사유: 실제 외부 상태와 결과가 있어 Fulfillment/Return 골든셋이 생긴다.
- 동시구매: 상품쌍 집계는 되살아나지만 추천 적중 정답은 여전히 별도 라벨 또는 온라인 평가가 필요하다.
- 계절성: 여러 월·시즌의 관측치가 충분하면 되살아난다. 단일 snapshot이면 되살아나지 않는다.

반대로 “검색되지 않은 상품이 시장 수요가 있다”, “기획전이 성공한다”, “세트 추천이 맞다”는 결론은 실거래 데이터만으로 자동 정답이 되지 않는다. 클릭·전환·반품·재구매 등 outcome 라벨이 필요하다.

### 판매자 관점의 Team 제약

데이터 소유자가 입점 판매자라면 Team의 권한은 해당 판매자의 주문·상품·재고·리뷰와 판매자 정책에 한정된다. 플랫폼 전체 수요, 다른 판매자의 매출, PG 내부 실패 원인, 택배사 내부 운영, 소비자원·플랫폼 중재 결과를 사실처럼 추론할 수 없다. 이 경계 때문에 `Customer Operations & Complaint`를 플랫폼 중재 Team으로 만들 수 없고, 외부 주체가 실제로 callback을 주는 경우에만 외부 대기 축을 계약에 넣을 수 있다. 판매자 동의·상품 소유·반품 재고 소유도 Context와 ActionProposal의 필수 조건이 된다.

### 개인정보 처리 원칙

v7의 tenant/customer scope, Context Broker, Team의 read 직접 호출 금지, Core 2의 승인·idempotency·audit 경계를 실데이터에도 그대로 적용한다( v7 90–92행, 488–492행, 970–983행). 원칙은 다음과 같다.

- 원천 데이터는 목적·tenant·보존기간을 정하고 최소 필드만 수집한다.
- 고객명·전화·주소·배송지·주문 메모 등 PII는 저장·LLM 전달 전에 가명화/마스킹하고, join key는 별도 보호 저장소에서 관리한다.
- ContextPack에는 필요한 최소 증거만 넣고, Team별 knowledge scope와 action scope를 강제한다. 원문 PII를 VOC 전체 집계나 다른 판매자 Context로 넘기지 않는다.
- 리뷰·문의의 자유문은 prompt injection과 개인정보 포함 가능성을 함께 검사하고, 원문 접근·마스킹 결과·모델 실행·외부 전송을 audit한다.
- 집계 alert는 재식별 위험이 있는 소수 집단을 노출하지 않도록 최소 집계 기준을 둔다. 외부 전송은 명시적 목적·승인·adapter 범위 안에서만 한다.
- 보존기간 종료 시 원문을 삭제하고 평가용 골든셋에는 비식별화된 fixture와 해시만 남긴다. `team_branch/sh/**`는 개인정보 경계로 취급하며 본 판정에서는 열람하지 않는다.

## 6. 최종 Team 구성 권고

아래 표는 Commerce Reference MVP를 기준으로 한다. v7 SaaS baseline과 Commerce MVP를 하나의 실행 목록으로 합치지 않는다.

| 실행 경로 | Team | Capability | 외부 대기 주체 | 권한 경계 | 필요한 골든셋 축 |
|---|---|---|---|---|---|
| LOCAL MVP | Order & Payment | 주문 조회, 결제 상태, 취소/부분취소 제안, 상태 재진입 | PG·마켓플레이스 주문 API | 주문·결제 상태 변경은 Controller→Core 2→승인 | intent, 주문/결제 상태, 중복·부분취소, `unknown`, 승인 위반 |
| LOCAL MVP | Fulfillment & Logistics | 배송 추적, 지연·분실·통관 분기, 선제 알림 제안 | 택배사·통관·판매자 소명 | 배송 조회와 알림 제안만 Team, 상태 변경·보상은 Core 2 | 배송 상태, 지연 사유, callback, SLA, 재조회·timeout |
| LOCAL MVP | Return, Refund & Evidence | 반품/교환 사유, 증빙, 정책 판정, 환불/반품 제안 | 고객, 판매자, 마켓플레이스 반품 adapter | 반품 Case와 고객 refund ledger 분리; 환불 실행은 승인 | 사유·증빙, 주문 item match, 정책 버전, 추가 증빙, 재검, 환불 자격 |
| A2A Remote MVP | Catalog & Verification | 상품·SKU·가격·규제·Variant 검증, Quote artifact | 공급처·외부 Catalog/Marketplace | catalog snapshot·quote만 반환; 구매/등록 side effect 금지 | 상품 존재, Variant, 가격·정책, input-required, artifact, 인증·실패·취소 |
| Phase 2 LOCAL 후보 | VOC & Store Manager | 비정형 VOC 원인 후보, 우선순위, 알림·위임 제안 | 내부 운영자와 대상 Team | 직접 호출·직접 side effect 금지; Controller를 통한 delegation proposal | 급증 오탐/미탐, 원인 축, 대상 Team, 위임 근거, 재시도·중복 알림 |
| Phase 2 후보 | Procurement | Quote 승인 후 공급처 구매·대체·재시도 | 공급처·Marketplace | 구매 실행은 승인·idempotency·금액 한도 | quote, 가격 변경, 공급처 취소, 대체, timeout, 중복 구매 |

이 구성은 LOCAL 3개라는 현실적 상한을 지킨다. Catalog는 A2A Remote이므로 LOCAL 상한과 실행 경로가 다르지만, 평가셋·인증·실패·artifact 축을 별도로 부담한다. Procurement는 v7 290행처럼 MVP에서는 Order와 통합하거나 Catalog 후속 capability로 두고 Phase 2로 미룬다.

v7 SaaS를 먼저 착수해야 한다면 권고는 별도다. LOCAL `Billing`, `Technical`, `VOC/Feedback Analytics`와 A2A `Catalog & Verification`을 유지하고, Commerce의 Order·Fulfillment·Return을 추가하지 않는다. 두 기준선을 동시에 MVP에 넣어 4개 이상의 LOCAL Team을 만드는 것은 평가 여력과 상한을 모두 위반한다.

## 근거 파일과 행

- `A-COP_구현계획서_v7.md`: 7절 88–110행(VOC), 120–148행(LOCAL/A2A slot), 286–292행(필요 Team과 착수 Team), 488–492행(권한 경계), 545행(외부 재시도), 554–562행(A2A 후보).
- `A-COP_확장안_구현명세_B2B중심_2026-08-15.md`: 3–7행(B2B 본체와 Commerce reference 지위), 427–436행(실제 6개 Team), 1089–1097행(확장 Registry 목록), 1160–1168행(Return/Evidence), 1203행 이후 구현 전략.
- `program/research/20260814_1111_통합분석_A-COP_아이디어_통합분석.md`: 80–129행(배정형 Team과 배치 모듈), 164–185행(마케팅·추천 판정), 211–228행(Olist·평가셋), 521–550행(확정 판정 기준과 상한).
- `team_branch/jh/에이전트_확장_방안.docx`: OOXML 문단 7–21행(트랙 C), 25–32행(트랙 D). 렌더링은 환경의 `pdf2image` 및 LibreOffice 부재로 완료하지 못했으며, 내용 판정은 DOCX XML 추출에 근거한다.
- 지정된 `program/research/A-COP_아이디어_통합분석.md`는 워크스페이스에 존재하지 않았다. 동일 분석 문서인 `program/research/20260814_1111_통합분석_A-COP_아이디어_통합분석.md`를 사용했다.

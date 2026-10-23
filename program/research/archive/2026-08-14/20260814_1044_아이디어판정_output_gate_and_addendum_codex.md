# 출력 검증을 어디에 둘 것인가 — 세 안 비교와 uh addendum 판정

## 결론

혼합안을 채택한다.

- GEN·REV는 등록형 Team Module로 둘 수 있다. 안 B의 모듈화 주장은 타당하다.
- 그러나 모든 출력이 B Team을 거쳐야 한다는 뜻은 아니다. 전수 관문은 Controller의 불변 orchestration 계약으로 보장하고, GEN·REV Team은 그 관문을 구현하는 교체 가능한 provider로 둔다.
- 고객에게 실제로 전달되는 답변을 `reply` ActionProposal로 일괄 승격하지 않는다. 안 A는 돈·권한·외부 변경처럼 실행·승인·idempotency가 필요한 reply에 선택적으로 적용한다.
- 단순 조회·안내·L0 자동 종결은 `TeamResult.answer`를 사용하되, 생성·검토 결과와 근거·정책 버전·프롬프트/모델 실행 기록을 `case_events`와 `llm_calls`에 남긴다. 이는 Action 감사와 별개의 출력 감사다.
- 안 C의 결정론적 검사는 공통 마지막 안전선으로 채택한다. 다만 C만으로는 근거 연결·정책 버전·재현성·감사 추적을 충족하지 못한다.

즉, 기본 경로는 `Team 결과 → GEN → REV → Controller 출력 정책 → (필요한 경우 reply ActionProposal) → 전달/종결`이다. REV의 차단 결과는 Team의 side effect가 아니라 `TeamResult`의 판정과 Controller의 상태 전이로 집행한다.

## 1. v6 계약을 기준으로 한 전제

v6의 계약은 답변과 업무 변경을 이미 분리한다.

- `TeamResult.answer`는 최대 6000자의 고객 답변 자리이고 `confidence`, `evidence`, `warnings`를 함께 가진다.
- `ActionProposal`은 `action_type`, `arguments`, `approval_required`, `risk_level`, `rationale_evidence_ids`, `idempotency_key`를 가진다.
- Team은 side effect를 실행하지 않고 제안만 반환한다. 실제 실행은 Controller가 Core 2에 `ExecuteAction`으로 위임한다.
- Core 2가 `action_requests`, `action_approvals`, `audit_logs`와 Action 상태기계 `proposed → pending_approval → approved → executing → succeeded|failed|unknown|cancelled`를 소유한다.
- Case 상태기계에는 `running → resolved`와 `running → waiting_approval`가 모두 있다. 따라서 답변 생성과 Action 승인을 Case 상태 하나로 뭉치면 L0 자동 종결과 충돌한다.
- `team_tasks`, `agent_runs`, `llm_calls`, `case_events`는 Team 실행·LLM 호출·Case 사건을 기록할 위치다. 출력이 현재 감사 경로에서 빠져 있다는 것이 문제의 출발점이다.

## 2. 세 안 비교

| 안 | v6에 맞는 점 | 장점 | 단점·실패 조건 | 판정 |
|---|---|---|---|---|
| A. `reply` ActionProposal | 기존 Action 상태·승인·idempotency·Core 2를 그대로 사용 | 외부로 나가는 변경을 하나의 감사·재시도·중복방지 모델로 통합하기 쉽다. 답변을 실제 발송 작업으로 다룰 수 있다. | 모든 답변을 `pending_approval`로 만들면 L0 자동 종결이 죽는다. `approval_required=false`를 허용하면 Action 테이블에 있지만 승인 없이 실행되는 별도 의미가 필요하다. 단순 안내까지 돈·권한 변경과 같은 상태기계에 넣는 과잉이 생긴다. | 선택적 채택 |
| B. 출력 관리 Team 등록 | v6의 Registry·`TeamExecutorPort`·`TeamResult`·capability routing과 일치 | Core 수정 없이 모듈을 등록해 확장한다. 모델·프롬프트·검색·평가 하네스를 Team이 소유한다. GEN·REV를 LOCAL/A2A로 교체하기 쉽다. | Team은 side effect가 없어 차단을 집행하지 못한다. Controller가 “반드시 GEN·REV 결과를 받은 뒤 전달”을 강제하지 않으면 capability routing이 전수 관문을 보장하지 않는다. 비결정적 LLM을 안전 게이트로 쓰면 같은 입력의 판정이 흔들리고 golden 평가·재현성이 약해진다. 등록만으로 해결되지 않는 공통 invariant가 생긴다. | 조건부 채택 |
| C. Controller 검증 함수 | `TeamResult`를 조립한 뒤 바로 검사 가능 | 가장 작고 빠르다. 금칙어·PII·스키마·인용 존재 여부처럼 결정론적 검사를 안정적으로 수행한다. | 현재 `case_events`·`llm_calls`와 연결된 출력 감사가 자동으로 생기지 않는다. 복잡한 정책 판단·근거 선택·재생성 전략이 Controller에 쌓인다. 테스트와 확장 경계가 약해진다. | 공통 결정론 검사로 채택 |

### 안 B는 언제 성립하는가

“기존 컴포넌트를 고치는 것보다 등록으로 확장하는 편이 모듈화에 맞다”는 주장은 v6의 Team 설계에 비춰 타당하다. v6가 Team 수를 상한으로 두지 않고 Registry 레코드, `TeamManifest`, `TeamExecutorPort`, 표준 `TeamResult`를 확장점으로 둔 이유와 맞는다. GEN과 REV의 내부 prompt, 모델, retrieval, 재시도 로직을 Core에 import하지 않는 것도 이 주장을 강화한다.

단, B를 단순히 “REV Team을 등록했으니 안전하다”로 해석하면 실패한다.

1. 전수 관문 문제: GEN·REV는 ORD·LOG처럼 capability에 따라 선택하는 업무 Team이 아니라 고객 출력 전수 관문이다. 따라서 routing 결과에 의존하면 안 된다. Controller가 모든 `answer != null`에 대해 canonical output pipeline을 호출하고, 성공하지 않은 출력은 전달하지 않도록 해야 한다.
2. 차단 문제: Team은 side effect를 못 내므로 REV가 차단할 수 없다. REV는 `approved/rejected`, 위반 코드, 수정 지시를 반환하고 Controller가 `respond`를 중단하거나 GEN 재생성·사람 에스컬레이션·Case event 기록을 해야 한다. 실제 메시지 발송은 별도 delivery Action 또는 기존 외부 채널 Action이 수행한다.
3. 재현성 문제: LLM REV를 유일한 안전 게이트로 두면 temperature, 모델 버전, prompt, 정책 문서 버전, 검색 결과에 따라 결과가 바뀐다. REV LLM은 후보 설명·의미 판단에 사용하되, 금칙어·PII·필수 evidence·정책 버전·허용 금액·출력 스키마는 C의 결정론 규칙으로 차단한다. `llm_calls`와 prompt hash를 기록하고 seed/temperature/모델을 고정한다.
4. 평가 문제: 등록형 Team이어도 전수 통과율, false accept, false reject, citation precision, PII 누출률, 재현율을 별도 golden/holdout으로 평가해야 한다. “등록 가능”과 “관문으로 충분히 검증됨”은 다른 조건이다.

따라서 B는 구현 경계로는 맞지만, 안전 불변식을 Registry 설정에만 맡길 수는 없다. `required_output_gate` 같은 manifest 선언을 참고할 수는 있으나 최종 보장은 Controller 계약에 둔다.

## 3. 안 A가 정말 필요한가

### 일괄 적용은 과잉이다

모든 고객 문장을 Action으로 만들면 `action_requests`가 메시지 표현과 업무 side effect를 동시에 담게 된다. `approval_required=false`는 “승인 없이 Core 2가 실행하는 reply Action”이라는 뜻이 되는데, 그러면 승인 없는 실행·감사·idempotency의 의미를 별도로 정의해야 한다. 단순 답변마다 Action row와 상태 전이를 만들면 L0 자동 종결이 사실상 `waiting_approval`를 거치거나, 예외적으로 승인 없는 Action이라는 우회 경로를 갖게 된다.

v6의 `running → resolved`를 살리려면 다음을 구분해야 한다.

- 조회·FAQ·배송 상태 안내: `TeamResult.answer` + output audit 후 `resolved`. Action 없음.
- 환불·쿠폰 발급·구독 변경·권한 변경·보상금 지급: 제안과 고객에게 보낼 결과가 실제 업무 변경에 종속되면 `ActionProposal`을 만들고 Core 2 승인·idempotency·audit를 사용한다.
- “승인 결과를 고객에게 통지”하는 발송 자체: 채널·재시도·중복방지가 필요하면 `send_reply` 같은 delivery Action으로 분리할 수 있다. 모든 초안이 아니라 발송 작업만 Action이다.

### 그래도 A가 범용적으로 옳은 경우

reply가 단순 문자열이 아니라 외부 시스템에 영향을 주는 업무 명령이면 A가 옳다. 예를 들어 “환불 완료”, “쿠폰을 발급했다”, “구독을 해지했다”는 문장은 사실상 Action 결과를 고객에게 알리는 projection이다. 이때는 `reply` 자체보다 `ActionProposal`의 evidence·승인·provider 결과·idempotency에 답변의 근거를 결박하는 것이 중요하다.

일반적인 CS·워크플로 제품도 보통 모든 텍스트를 승인 대상으로 만들지 않는다. 자동 응답은 confidence/정책/민감도 규칙으로 자동 발송하고, 환불·보상·계정 변경·법적 문구 같은 고위험 작업은 human approval 또는 별도 작업 큐를 둔다. 핵심은 “고객에게 보이는가” 하나가 아니라 외부 상태를 바꾸는가, 규제·금전·권리 위험이 있는가, 발송 중복을 막아야 하는가다.

### 출력 감사는 Action 감사와 분리한다

Action이 아닌 답변도 감사가 불필요한 것은 아니다. 최소한 `case_events`에 `answer_generated`, `answer_reviewed`, `answer_delivered` 사건을 append하고, `llm_calls`의 prompt/model/response 기록과 연결한다. `policy_version`, `evidence_ids`, `review_result`, `output_hash`, `delivery_id`를 payload에 넣는다. 개인정보 보존 정책상 원문을 남길 수 없으면 redacted text와 hash를 남긴다. 이것이 C만 채택할 때 생기는 감사 공백을 메운다.

## 4. 최소 변경 목록

새 핵심 컴포넌트를 만들지 않는 조건에서 v6에 필요한 변경은 다음과 같다.

1. `TeamResult`에 별도 top-level 필드를 크게 늘리지 않고, `decisions` 또는 새 `output_review` 구조에 `review_status`, `violation_codes`, `policy_version`, `evidence_ids`, `output_hash`를 표준화한다. 계약 버전은 `1.1`로 올리거나 호환 가능한 optional field로 둔다.
2. GEN·REV를 Registry에 등록한다. GEN은 `generate_response`, REV는 `review_response` capability를 갖되, Controller의 output pipeline에서 전수 호출한다. 일반 capability routing의 선택 사항으로 취급하지 않는다.
3. Controller에 `assemble_and_gate_output` 단계를 추가한다. 순서는 근거·정책 버전 결박 → GEN → 결정론 C 검사 → REV → 결정론 재검사 → 전달/재생성/에스컬레이션이다. 재생성은 기존 loop guard와 별도 output rejection counter를 합산하고 상한 초과 시 `escalated`로 보낸다.
4. 결정론 검사를 기존 Tool/API Gateway 또는 Controller의 작은 pure function으로 둔다. PII, 금칙어, schema, 필수 근거, 금액·권리 불변 검사를 포함한다. REV Team이 이를 중복 구현하지 않게 한다.
5. Action `reply` enum은 일괄 도입하지 않는다. 외부 발송/업무 변경이 실제 Action인 tenant·channel에서만 `send_reply` 또는 `reply`를 등록하고, `approval_required`의 의미를 “발송 승인 필요 여부”로 명시한다. 저위험 자동 발송은 `false`일 수 있지만 Action 상태·idempotency·audit는 유지한다.
6. `case_events`와 `llm_calls`에 출력 감사 연결을 추가한다. Core 1이 생성·검토 사건을 기록하고, Core 2 Action이 있는 경우 두 audit correlation id를 연결한다.
7. 평가 하네스에 L0 자동 종결, 고위험 reply 승인, REV 반려 재생성, 결정론 검사 우회 시도, 동일 입력 반복성, LOCAL/A2A canonical 결과 일치 테스트를 추가한다.

## 5. uh addendum: Agent Test 필터와 기존 기준

uh의 FILTER-1~3은 기존 세 기준을 대체하지 않는다. 역할이 다르다.

| 기준 | 묻는 질문 | 판정에서의 역할 |
|---|---|---|
| 정답셋 존재 | 결과를 무엇과 비교해 채점할 수 있는가 | 평가 가능성의 필수 조건 |
| 임의 배정 의존 | 입력·경로의 핵심 값이 가짜인가 | 인과 타당성·데이터 신뢰성의 탈락 조건 |
| 코어 루프 필요 | 접수→판단→제안→응답→승인/종결에 필요한가 | 제품 범위 우선순위 |
| FILTER-1 비정형 입력 | 자연어·사진·영수증을 해석해야 하는가 | Agent/멀티모달 필요성의 증거 |
| FILTER-2 규칙으로 못 적는 판단 | 예외·재량·맥락 판단인가 | LLM/Agent 판단 필요성의 증거 |
| FILTER-3 상황별 도구 조합 | 도구를 선택·연쇄하고 결과를 종합하는가 | orchestration 필요성의 증거 |

합친 기준은 다음과 같다.

`Agent 채택 = (FILTER 1/2/3 중 하나 이상) AND (정답셋·대리 평가셋 확보) AND (임의 배정 없이 재현 가능한 입력) AND (코어 루프 또는 명시적 운영 가치)`.

FILTER는 “AI가 필요한가”를 보완하고, 기존 세 기준은 “만들어도 되는가·평가할 수 있는가”를 결정한다. FILTER를 통과해도 정답셋이 없거나 임의 배정에 의존하면 채택하지 않는다. 반대로 FILTER가 약해도 코어 루프의 결정론 계산·감사·승인 기능이면 일반 tool/rule로 채택할 수 있다.

## 6. 채택 4건 판정

| addendum 항목 | 판정 | 확정안에 붙는 위치 | 조건 |
|---|---|---|---|
| 쿠폰 경제성 what-if | 채택. Agent가 필요한 부분은 상황별 도구 선택·대화형 질문·결과 설명이고, 산수는 결정론 tool이다. | 판매자/플랫폼 운영 Team의 `what_if_coupon` tool, GEN 응답, dashboard/report | 국내 실효 효과가 아니라 외부 데이터 기반 사전분포·보수/중간/낙관 preset으로 표시. 실제 tenant 원가·수수료·쿠폰 예산을 우선 사용한다. |
| 최저가 보상제 | 조건부 채택. 접수 사진과 상품 동일성·예외 규정·어뷰징 판단은 FILTER-1~3을 모두 충족한다. | Case 접수→VLM/추출→L2 정책 판정→`compensation` ActionProposal→Core 2 승인 | 증빙 원본·추출 필드·정책 버전·동일성 evidence를 남긴다. 자동 지급은 하지 않고 risk에 따라 HITL을 둔다. |
| 미충족 수요 로깅 | 채택. 포착은 L0 상담/검색 보강이고, 집계·대시보드는 배치/SQL이다. | `catalog_absent` 또는 동등한 Case event와 Feedback Analytics/판매자 dashboard | “상품 없음”과 “검색 실패/표현 불일치”를 분리한다. 카탈로그 조회 결과와 검색어·정규화 category·속성·가격대를 구조화한다. |
| 맥락 승계 상담원 연결 | 채택. Agent 기능은 요약·민감도·담당 큐 선택이며, 연결은 workflow/handoff다. | `handoff` TeamResult, `case_events`, 운영자 큐, `ContextPack` 요약 | 원문·근거·이미 한 조치·대기 사유·다음 질문을 전달하고, 누락/PII를 REV/C가 검사한다. 단순 라우팅은 규칙으로 남긴다. |

### 미충족 수요 제안의 통합

uh, 사용자의 고도화 아이디어 3번, jh 트랙 C-②는 같은 신호 원천을 독립적으로 제안했다. 이는 중복 기능 세 개가 아니라 하나의 canonical signal pipeline으로 통합해야 한다.

`고객 발화/검색어 → 카탈로그·검색 결과 대조 → {catalog_absent, search_miss, ambiguous} 분류 → category/attribute/price_band 구조화 → case_event → 배치 집계 → 두 출구`

- 플랫폼 출구: 기획전·상품 구색·신규 공급 판단.
- 판매자 출구: 온보딩 시장 벤치마크와 판매자 대시보드.

원천 이벤트 ID와 기간·tenant·카테고리 키를 공유하고, 출구별 ranking만 다르게 한다. “없다”를 확인하지 못한 문의를 `catalog_absent`로 세면 안 된다. 이 통합은 jh의 집계와 uh의 L0 포착을 연결하며, 사용자의 “상품 없음 vs 못 찾음”을 상태값으로 명시한다.

## 7. 쿠폰 시뮬레이션 데이터 검증

네 자료는 같은 역할을 하지 않는다.

| 자료 | 쓸 수 있는 것 | 쓸 수 없는 것·제약 |
|---|---|---|
| dunnhumby The Complete Journey | 2,500가구, 2년 거래와 direct marketing history를 이용한 쿠폰/마케팅 반응의 방향성·사전분포 | 특정 국내 쇼핑몰의 쿠폰 탄력성·마진 효과를 대표하지 않는다. 공식 Source Files는 교육·연구 용도를 설명하고 다운로드·이용조건 확인이 필요하다. |
| Kaggle Predicting Coupon Redemption | 쿠폰 수령-상환 분류의 feature/benchmark 연습 | competition 데이터의 라이선스가 명확히 확인되지 않는 복제·재배포본일 수 있다. 실제 손익·증분효과보다 redemption label 중심이다. 상업·배포 사용 금지로 취급하고 권리 확인 전 제품 데이터에 넣지 않는다. |
| Rossmann Store Sales | 프로모션 플래그와 매출의 연관성, 시계열 feature engineering 보조 | 쿠폰 수령·상환과 원가·수수료가 없다. 공식 Kaggle competition 페이지는 “competition rules” 조건이다. 쿠폰 ROI나 인과적 promotion lift의 직접 근거가 아니다. |
| M5 Walmart | 가격·판매량 시계열과 가격 탄력성 연습, forecast tool 검증 | Walmart 미국 오프라인 상품 판매 데이터이며 쿠폰·마케팅 노출·원가·플랫폼 수수료가 없다. 가격 탄력성을 쿠폰 탄력성으로 치환할 수 없다. |

따라서 addendum의 한계 표기는 방향은 맞지만 충분하지 않다. 문서에는 “실제 국내 효과를 추정한다”가 아니라 “외부 데이터로 초기 preset의 범위와 민감도 테스트를 만든다”라고 써야 한다. 네 데이터에서 나온 계수는 `external_prior`이고, 운영 의사결정에는 tenant 실측 데이터 또는 명시적 synthetic scenario만 사용한다. 결과 화면에도 데이터셋·국가·기간·라이선스·변환식·불확실성 범위를 표시한다. dunnhumby와 Kaggle의 정확한 이용조건·재배포 가능성은 내려받은 버전의 license/competition terms를 보관하고 검토한 뒤 확정한다.

공식 페이지 기준으로 dunnhumby는 The Complete Journey를 2,500가구 2년 거래와 직접 마케팅 이력의 representation으로 설명한다([dunnhumby Source Files](https://www.dunnhumby.com/source-files/)). 사이트 이용조건은 자료의 지식재산권이 dunnhumby 및 제3자에게 있음을 명시하므로([dunnhumby Terms](https://www.dunnhumby.com/terms-and-conditions/)), “무료 공개”를 곧 상업적 재사용 허가로 쓰면 안 된다. Rossmann 공식 competition 데이터는 competition rules 조건이다([Kaggle Rossmann data](https://www.kaggle.com/c/rossmann-store-sales/data)). M5는 Walmart 미국 판매 예측용 자료이며, 공개 미러가 있더라도 원 competition 조건과 provenance를 확인해야 한다([M5 dataset mirror](https://doi.org/10.5281/zenodo.10203108)).

## 8. 최저가 보상제와 VLM EXT-2 부활

부분 부활은 정당하다. EXT-2를 다시 “범용 이미지 이해 기능”으로 살리는 것은 정당하지 않다.

최저가 보상제는 실제 Case 입력이 영수증·화면 캡처라는 비정형 증빙이고, 상품명·옵션·용량·가격·판매처·날짜 추출이 후속 정책 판정과 ActionProposal을 결정한다. 따라서 VLM은 코어 루프에 직접 붙는 증빙 추출 adapter로서 가치가 있다. 다만 VLM 출력은 evidence 후보일 뿐 확정 사실이 아니다. OCR/VLM confidence, 원본 hash, 추출 bounding box, 동일 상품 대조 결과, 정책 문서 버전을 저장하고 저신뢰·충돌 건은 사람에게 보낸다.

부활 범위는 `price_match_evidence_extraction` 하나로 제한한다. 임의 이미지 분류, 파손 판정, 일반 상품 추천 등 EXT-2의 나머지 범위를 되살리는 근거로 사용하지 않는다. 지급은 반드시 기존 `ActionProposal`과 Core 2 승인·idempotency·audit를 거친다.

## 최종 결정 요약

새로운 독립 “출력 관리 플랫폼”은 만들지 않는다. GEN·REV를 등록형 Team으로 추가하되, 전수 관문이라는 성격은 Controller 계약으로 고정한다. 결정론 검사는 C로 두고, 고위험 외부 변경·발송은 A의 Action 경로를 선택적으로 사용한다. 이 조합이 v6의 모듈화 원칙, L0 자동 종결, Core 1/Core 2 분리, 감사·idempotency 요구를 동시에 보존한다.

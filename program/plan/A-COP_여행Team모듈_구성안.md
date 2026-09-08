# A-COP 여행 도메인 Team 모듈 구성안

`[초안 2026-09-08]` 팀 결정(여행 CS 플랫폼, 인바운드 1순위)에 따라 Team 모듈을
다시 뽑는다. 근거는 `team_branch/me/여행/_최종주제_후보비교_v4_2026-09-08.md`,
`team_branch/me/travel-agent-business-review_v3.md`, 그리고 현행 코드다.

★**이 문서는 팀 모듈만 다룬다.** 코어·계약·일정은 구현계획서 몫이다.

---

## 0. 결론 먼저

| | 개수 | 무엇 |
|---|---:|---|
| 코어(basement) — **손대지 않음** | 12영역 | 생명주기·계약·Registry·Context Broker·대조 규칙 엔진·Controller·Outbox·Ports·운영 UI·A2A·방어 지표 |
| Team — **구조를 그대로 이어받음** | **5** | 기존 팀의 뼈대를 여행 객체로 갈아 끼운다 |
| Team — **새로 만듦** | **1** | Dining |
| Team — **등록만** | **2** | Lodging, Flight |
| Team — **폐기** | **0** | 없다. 여섯 팀 모두 대응 자리가 있다 |
| **MVP 필수** | **2** | Activity, Itinerary Review |

**여섯 팀 중 폐기가 하나도 없다는 것이 이 구성안의 핵심이다.** 처음에는
쇼핑몰 팀 셋(Procurement·Fulfillment·Catalog)을 버리는 것으로 봤는데, 코드를
열어 보니 셋 다 여행에 **같은 모양의 자리**가 있었다.

---

## 1. Team 을 무엇으로 나누나

**여행을 구성하는 객체 종류별로 나눈다.** 지역·상품·고객군으로 나누지 않는다.

| 나누는 기준 | 도시를 늘리면 | 언어를 늘리면 | 도메인을 넓히면 |
|---|---|---|---|
| **객체 종류별 (채택)** | 데이터만 추가 | 응답 소재만 추가 | Team 추가 |
| 지역별 (기각) | Team 추가 | Team 추가 | Team 추가 |

각 Team 은 자기 객체의 셋을 갖는다.

1. **검증 규칙** — 코드. 이 객체가 성립하는 조건
2. **감시 소스** — 이 객체가 바뀌었는지 어디서 아나
3. **재계획 후보 생성** — LLM. 바뀌었을 때 무엇으로 대체하나

**전체 일정 정합성(시간 충돌·예산·이동 여유)은 Team 이 아니라 코어 검증 층이 본다.**
Team 이 자기 객체만 보면 되도록 하려는 분리다.

★각 Team 안에서 **판정(코드)과 대안 생성(LLM)을 분리**하고, 생성한 대안은
판정을 다시 통과해야 통지된다. 지금 `response_generation_review` 팀이 생성과
검수를 다른 주체가 하도록 만든 원칙과 같다.

---

## 2. 기존 여섯 팀이 어디로 가나

`[실측 2026-09-08]` 현행 등록 팀은 여섯이다(`app/core/project_config.py`
`KNOWN_IMPLEMENTATION_REFS`).

| 현행 Team | 줄수 | 현행 capability | → 여행 Team | 무엇이 같아서 이어받나 |
|---|---:|---|---|---|
| `return_refund` | 396 | `return.check_eligibility` · `return.request` · `refund.calculate` | **Activity** | **취소 가능 판정 → 접수 → 환급액 계산**의 3단 구조가 같다. 반품 기한↔취소 기한, 반품 사유별 배송비 부담↔우천 취소 위약금율, 수량 초과 검증↔인원 초과 검증 |
| `fulfillment_logistics` | 163 | `fulfillment.track` · `shipment.status` · `shipment.exception` | **Mobility** | **움직이는 것을 추적하고 예외를 잡는** 구조가 같다. 배송 지연 판정↔환승·막차 지연 판정, 미수령 조사↔경로 이탈 |
| `catalog_verification` | 121 | `catalog.lookup_sku` · `catalog.verify_listing` · `catalog.compliance_check` | **Place Verification** | **외부 원장을 조회해 표시 내용이 맞는지 대조**하는 구조가 같다. A2A Remote 자리도 그대로 — 장소·운영 정보를 원격 검증으로 뺀다 |
| `response_generation_review` | 154 | `response.generate_review` | **Itinerary Review** | 생성과 검수를 다른 주체가 하는 원칙이 그대로다. 금지어·PII 검사가 **통지 문구 검사**로 바뀐다 |
| `procurement_order_payment` | 366 | `order.create` · `order.modify` · `order.cancel` · `payment.status` | **Booking Execution** | 예약 생성·변경·취소·결제 상태의 자리가 같다. **4단계로 미룬다** — 계약·권한이 있어야 열린다 |
| `voc_store_manager` | 101 | `voc.aggregate` · `voc.escalate` | **Trip Feedback** | 지금도 껍데기다(집계는 코어 1 소유). 여행에서도 껍데기로 유지 |

★**"이어받는다"는 코드를 복사한다는 뜻이 아니다.** 판정 3단 구조·감시 소스
연결부·ActionProposal 반환 모양을 뼈대로 쓰고, **판정 규칙과 어휘는 전부 새로
쓴다.** 어느 쪽인지 아래 4절에서 나눈다.

---

## 3. 전체 Team 목록 (개정판)

### A. 여행 객체 Team

| # | Team | 검증 규칙 | 감시 소스 | 재계획 | 출처 |
|---|---|---|---|---|---|
| 1 | **Activity** | 예약 시간·운영일·인원·날씨 조건·취소 기한·위약금율 | 운영 공지, 기상청 초단기예보, 예약 확인 | 같은 시간대 대체 액티비티, 날짜 이동, 환급 안내 | `return_refund` 뼈대 |
| 2 | **Dining** | 영업시간·휴무·예약 여부·동행 조건(아이·할랄·채식) | 영업 공지, Places 영업시간(오늘 포함 7일) | 인접 대안, 식사 시간 이동 | **신규** |
| 3 | **Mobility** | 구간 이동 시간·환승·막차·여유 시간 | 운행 정보, Routes API | 경로·순서 재배열 | `fulfillment_logistics` 뼈대 |
| 4 | **Lodging** | — | — | — | **등록만** |
| 5 | **Flight** | — | — | — | **등록만** |

### B. 횡단 Team

| # | Team | 하는 일 | 출처 |
|---|---|---|---|
| 6 | **Place Verification** | 장소 존재·운영 정보·표시 조건을 외부 원장과 대조. **A2A Remote** 로 뺀다 | `catalog_verification` 뼈대 |
| 7 | **Itinerary Review** | 통지 문구 생성과 검수를 분리. 금지 표현·확정 단정·확인 시각 누락을 잡는다 | `response_generation_review` 뼈대 |
| 8 | **Trip Feedback** | 여행 피드백 집계·급증 탐지. **껍데기** — 집계는 코어 1 소유 | `voc_store_manager` 뼈대 |

### C. 실행 Team

| # | Team | 하는 일 | 언제 |
|---|---|---|---|
| 9 | **Booking Execution** | 예약 생성·변경·취소·결제 상태 | **4단계.** 공급자 계약·권한 확보 후 |

**합계 9개.** 이 중 MVP 는 2개다(5절).

---

## 4. 그대로 쓰는 것 · 갈아 끼우는 것 · 새로 쓰는 것

`[실측]` 도메인 교체는 이 저장소가 **이미 한 번 한 일**이다 — sample(구독·결제)
→ cs(커머스). 무엇이 안 바뀌는지 `wiki/records/handoff/10_도메인_교체_가이드.md`
§2 에 표로 남아 있다. 이번이 **두 번째 교체**이고 같은 표를 따른다.

### 4-1. 그대로 쓴다 — 한 줄도 안 고친다

| 무엇 | 왜 도메인 무관인가 |
|---|---|
| Case 생명주기 · `transition_case()` | 상태 변경의 단일 진입점 |
| 계약 모델 `contracts.py` | `extra='forbid'`, Evidence 의무 |
| Team Registry · `allowed_tools` 강제 | |
| Context Broker (12,000 토큰) | |
| **대조 규칙 엔진** `core/verification.py` | **어휘는 선언 파일에서 온다** |
| Controller · WAIT/RESUME · 승인 | |
| Outbox (원자성·dedupe·`unknown`) | |
| Ports 6종 + `project.yaml` 조립 | |
| 운영 UI 4화면 · Composer | 상태 색·근거 표시는 도메인 무관 |
| A2A (Card·`input-required`·취소·인증) | |
| 방어 지표 5종 `eval/defense_metrics.py` | 분모 규칙은 도메인 무관 |

★**대조 규칙 엔진이 한 줄도 안 바뀌었다는 것이 지난 교체의 증거다.**
바뀐 것은 `app/modules/customer_ops/verification_policy.py` 라는 **어휘 파일**
하나였다(`payment_id → order_id`, `subscription_id → shipment_id` …).
이번에는 `order_id → booking_id`, `shipment_id → segment_id` 로 간다.

### 4-2. 갈아 끼운다 — 뼈대는 두고 어휘·규칙만

| 무엇 | 지금 | 여행 |
|---|---|---|
| 대조 선언 | `verification_policy.py` (커머스 어휘) | 여행 어휘로 교체 |
| 통지 문구 검사 | `response_review_policy.py` (금지어·PII) | 확정 단정·확인 시각 누락 검사 추가 |
| 코어 1 분류 라벨 | 주문·배송·반품·교환·기타 | **일정 제출 / 사건 신고 / 확인 요청 / 조정 거부 / 그 외** |
| Context Broker 적재 내용 | 주문 정보 | **여행 상태** (잠긴 예약·필수 조건·최신 일정 버전·다음 확인 시점) |
| 코어 2 Action | 주문 조회·배송 조회·환불 실행 | **장소·운영 조회 / 이동 시간 조회 / 기상 조회** (Mock 허용) |
| Composer 소재 | 한국어 CS 문구 | **영어 통지 문구** |
| 평가 정답 시나리오 | 쇼핑몰 골든셋 | **합성 여행 + 사건 시나리오** |

### 4-3. 새로 쓴다

| 무엇 | 왜 새로 쓰나 |
|---|---|
| Team 3개의 **판정 규칙** | 취소 기한·위약금율·기상 판단 시점·영업시간·막차. 커머스 규칙과 공통분모가 없다 |
| **감시 소스 연결** | 기상청 초단기예보·운영 공지·Places·Routes. 지금은 하나도 없다 |
| **선제 조정 루프** | 지금은 고객이 문의해야 Case 가 열린다. 여행은 **우리가 먼저 감지**해야 한다 |
| 여행 데이터 | TourAPI 장소 + 합성 여행 20~30건 + 사건 시나리오 10개 |

★**선제 조정 루프가 진짜 신규다.** 나머지는 어휘 교체에 가깝지만 이것은 구조가
없다. 지금 Case 는 **접수로 시작**하는데, 여행은 **감시로 시작**한다. 여행별
다음 확인 시점을 저장하고 주기 작업이 감시 소스를 재조회해 변화가 잡히면
Case 를 **우리가 연다.** `routing_sweeper` 가 이미 주기 작업으로 도는 구조가
있어 그 자리에 붙일 수 있다.

---

## 5. MVP 판정

`[추정]` 최종발표 10-26까지 7주. v4 §3-7 의 최소 범위에 맞춰 잘랐다.

| Team | MVP | 이유 |
|---|:---:|---|
| **Activity** | **필수** | 취소·환급 규정이 **문서로 존재**해 판정 규칙을 바로 쓸 수 있다. 예약금이 걸려 실패 비용이 크고, 시연에서 사건이 한눈에 보인다 |
| **Itinerary Review** | **필수** | 통지 문구가 확정 단정을 하면 제품 목표(할루시네이션 축소)가 무너진다. **선제 통지는 고객이 묻지 않았는데 우리가 보내는 것**이라 검수가 더 중요하다 |
| Dining | 2순위 | 변화가 잦고 대체가 쉬워 시연 가치는 높다. 다만 Activity 로 루프가 증명되면 같은 틀의 반복이다 |
| Mobility | 3순위 | 앞의 둘이 바뀌면 항상 영향을 받지만, **늦게 붙여도 코어 검증이 시간 충돌은 잡는다** |
| Place Verification | 3순위 | A2A Remote 시연이 부트캠프 요구사항이라 **발표 전에는 필요**하다. 기능 가치보다 요구사항 충족이 이유다 |
| Lodging · Flight | 등록만 | 잠긴 예약으로만 취급 |
| Trip Feedback | 등록만 | 껍데기 유지 |
| Booking Execution | 제외 | 계약·권한 의존. 4단계 |

### MVP 2개로 무엇을 보이나

```
액티비티 취소 감지 → 재계획안 생성 → 잠긴 예약·필수 조건 재검증
   → 통지 문구 검수 → 고객 에이전트에 선제 통지 → 거부 시 되돌림
```

**이 한 줄이 제품의 주장 전부다.** Team 을 더 붙이는 것은 같은 루프에 객체를
추가하는 일이지 새로운 증명이 아니다.

★**Team 을 늘리는 것보다 루프를 한 번 끝까지 도는 것이 먼저다.** Activity 만
있어도 감지→재계획→재검증→통지→거부→되돌림이 전부 돈다. Dining 을 먼저
붙이면 Team 이 둘인데 루프는 반쪽인 상태가 된다.

---

## 6. 남은 결정

| 항목 | 누가 |
|---|---|
| Place Verification 을 A2A Remote 로 뺄지, 로컬 Team 으로 둘지 | 팀 — 부트캠프 A2A 요구사항 확인 후 |
| 코어 1 분류 라벨 5종의 최종 문구 | 코어 1 |
| 선제 조정 루프를 `routing_sweeper` 에 붙일지 별도 sweeper 로 뺄지 | 코어 1 |
| 감시 소스 중 실제 연결 대상(기상청은 공개, 액티비티 운영 공지는 `[미확보]`) | 도시 선정 후 표본 조사 |
| Activity 판정 규칙의 원본 규정 범위 | 후보 B 조사 재사용 + 인바운드 액티비티 약관 추가 수집 |

---

## 관계

- `program/plan/A-COP_구현계획서_v9.md` §7·§8-B — 현행 Team 구성 원칙
- `wiki/records/handoff/10_도메인_교체_가이드.md` — 무엇이 안 바뀌는지
- `team_branch/me/여행/_최종주제_후보비교_v4_2026-09-08.md` §3-7 — MVP 최소 범위
- `team_branch/me/travel-agent-business-review_v3.md` §8 — 참조 인프라 구성

---
type: guide
title: Teams
description: 업무 책임 단위. Registry 등록형이라 추가해도 Core가 안 바뀐다
status: draft
domain: travel
---

# Teams

`app/modules/customer_ops/`

**Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.** Registry 등록만으로 끝나야 한다.

★**[2026-09-08] 도메인이 여행으로 바뀌었다**(계획서 v10). 이 폴더에 **두 세대가 같이 있다** — 계약·경계·Registry 문서는 도메인을 모르므로 그대로 쓰고(이게 교체가 가능한 이유다), 여행 Team 4종은 명세만 있고, 쇼핑몰 Team 6종은 MVP 경로에서 빠졌으나 문서를 남긴다. 여행 Team은 지역 상품이 아니라 **여행을 구성하는 객체 종류**로 나눈다(v11 §5).

## 읽기 순서

1. [team-contract.md](team-contract/index.md) — 무엇을 구현해야 하는가
2. [team-boundary.md](team-boundary.md) — **무엇을 하면 안 되는가**
3. [team-registry.md](team-registry.md) — 어떻게 등록되는가

## 계약·구조

| 문서 | 답하는 질문 | 코드 |
|---|---|---|
| [team-contract.md](team-contract/index.md) | `TeamTask` / `TeamResult` 모양 | `app/core/contracts.py` |
| [team-boundary.md](team-boundary.md) | Team이 하면 안 되는 것 셋 | — |
| [build-order.md](build-order.md) | 어느 순서로 만드나 | — |
| [common-utils.md](common-utils.md) | 공통 뼈대 (미구현) | — |
| [team-registry.md](team-registry.md) | capability → Team 해석 | `app/core/registry.py` |
| [remote-team-a2a.md](remote-team-a2a.md) | A2A Remote Team 실행 | `app/core/remote_team/` |
| [response-review-design.md](../records/legacy/teams/response-review-design.md) | **GEN→REV 내부 설계와 검증 4항목** | `response_review_policy.py` |

## 여행 Team — 명세만 있다 `[실측 2026-09-09]`

**코드가 없다.** `app/modules/` 에 파일이 없고 `config/project.yaml` 에도 등록돼 있지 않다. 아래는 무엇을 만들어야 하는가다.

| Team | MVP | 무엇을 판정하나 | 재계획 |
|---|---|---|---|
| [activity.md](activity.md) | **필수** | 예약 시간·운영일·인원·날씨 조건·취소/환급 규정 | 같은 시간대 대체 · 날짜 이동 · 환급 안내 |
| [booking-handoff.md](booking-handoff.md) | **필수** | 승인이 필요한 건 특정, 대안·차액 정리 | 변경 링크. **자동 실행은 `tier=='simulated'` 한정** |
| [dining.md](dining.md) | 4주차 | 영업시간·휴무·예약 여부·동행 조건(아이·할랄·채식) | 인접 대안 · 식사 시간 이동 |
| [mobility.md](mobility.md) | 5주차 | 구간 이동 시간·환승·막차·여유 | 경로·순서 재배열 |
| Lodging / Flight | 등록만 | 잠긴 예약으로만 취급한다 | — |
| Place Verification | **원격이 생겼다. 등록은 0건** | 장소 존재·운영 정보를 외부 원장과 대조. **A2A Remote** | `[실측 2026-09-10]` 아래 |

### ★ [2026-09-10] Place Verification — 상대는 생겼고 아직 안 붙었다

`[실측]` **미해결이 아니게 됐다.** `app/presentation/a2a/travel_remote_agent.py`(202줄)와 통합 테스트 7건이 생겼다.

| 항목 | 실측 |
|---|---|
| 엔드포인트 | 다섯 — Agent Card 발견 · Task 제출 · 상태 조회 · 추가 입력 재개 · 취소. **커머스 원격과 같은 계약**이라 executor 가 그대로 돈다 |
| 광고하는 것 | `team_id: place_verification` · `capabilities: place.lookup`·`place.verify_hours` · `accepted_case_types: place` |
| 테스트 7건 | Agent Card 광고 · `input-required` 왕복 · 필수값 누락 거부 · 잘못된 토큰 401 · 원격 실패 → escalate · 마감 초과 중단 · 취소를 실패와 구분 |
| **`config/project.yaml` 등록** | **0건** |

★**왜 만들었나 — 부를 상대가 없어졌기 때문이다.** 2026-09-09 에 등록을 여행으로 갈면서 `catalog_verification` 이 빠졌고, **엔드포인트 다섯은 그대로인데 A2A 로 부를 대상이 하나도 없는 상태**가 됐다.

★**왜 하필 장소 검증인가.** A2A 로 뗄 값이 있는 일은 **바깥 원장을 조회해 우리 표시와 대조하는 것**이다. 이 일은 **우리 DB 를 안 봐도 되므로 원격으로 떼기에 실제로 적합하다** — 억지로 뗀 것이 아니다.

★**시뮬레이터다.** 실제 장소 원장(TourAPI·Places)에 붙지 않는다. **증명하는 것은 왕복과 계약이지 장소 데이터의 정확성이 아니다.**

`[실측]` **등록이 0건이라 지금 이 원격을 부를 수 없다.** [D-015](../../../wiki/decisions/D-015-implementation-catalog.md) 가 말하는 것과 같은 모양이다 — **만들어진 것과 카탈로그에 있는 것이 또 갈렸다.**

`[미확보]` **v11 §5 에 이 Team 이 없다.** 계획서에 넣는 일은 계획서 담당 몫이다.

`[실측]` 뼈대로 베낄 쇼핑몰 Team — Activity ← `return_refund`, Mobility ← `fulfillment_logistics`, Place Verification ← `catalog_verification`. **Dining·Booking Handoff 는 신규다.**

★**모든 Team 이 `business_subject` 규칙을 지켜야 한다** — 그 Action 이 바꾸는 대상 객체 id 를 넣고, 특정 안 되면 escalate 한다. `case_id` 폴백을 두지 않는다. 지금 옳게 하는 Team 은 `fulfillment_logistics` 하나뿐이다. 각 Team 페이지의 같은 이름 절 참고.

**셋을 갖는다** — ① 검증 규칙 ② 감시 소스 ③ 재계획 후보. 판정은 코드가, 대안 생성은 LLM이 하고 **생성한 대안은 판정을 다시 통과해야 통지된다.** ★**전체 일정 정합성은 Team이 아니라 코어 검증 층이 본다** — 재계획 후보는 제안이지 확정이 아니다. [mobility.md](mobility.md)가 그 시험대다.

## 지난 도메인의 Team — 코드도 문서도 여기 없다

`[실측 2026-09-10]` **커머스 Team 일곱은 코드가 삭제되고 문서는 [records/legacy/teams/](../records/legacy/teams/) 로 옮겼다.**

| | 2026-09-09 | **2026-09-10** |
|---|---|---|
| `config/project.yaml` 등록 | 빠졌다 (소스는 남아 있었다) | — |
| `app/modules/customer_ops/` | 남아 있었다 | **작업 트리에서 제거** (커밋 전) |
| 커머스 A2A 원격 (`remote_agent.py`) | 남아 있었다 | **삭제됨.** 자리를 `travel_remote_agent.py` 가 물려받았다 |
| wiki 문서 7건 | `wiki/teams/` 에 있었다 | **`wiki/records/legacy/teams/` 로 이동** |


★**「삭제됨」의 범위를 정확히 적는다.** `[실측 2026-09-10]` **작업 트리에서는 파일이 없고 git 에는 아직 있다** — 삭제가 커밋되지 않았다(다른 세션의 진행 중 작업). **되돌려지면 이 표가 틀린다.**

★**둘은 삭제가 아니라 이동이다.** `feedback.py`(인라인 분류)와 `verification_policy.py` 는 `app/modules/travel_ops/` 로 옮겨졌다 — 인라인 분류는 남고 **라벨만 교체된다**(v11 §5-A).

★**문서를 지우지 않고 옮긴 이유.** 판정의 **이유**가 도메인 무관이라 여행 Team 이 같은 문제를 다시 만난다. 그리고 도메인이 되돌아가면 그 판정을 다시 하게 되는데 **그걸 다시 논의하지 않으려고** 남긴다. → [records/legacy/index.md](../records/legacy/index.md)

★**뼈대를 물려받은 관계는 [activity](activity.md)·[mobility](mobility.md)·Place Verification 쪽에 적혀 있다.** 구조를 베꼈다는 뜻이고 **판정 규칙과 도메인 데이터는 전량 신규다**(v11 §0-2).

`[실측]` **인라인 분류(`feedback.py`)는 남는다.** 라벨만 교체됐다 — `itinerary_submit` 일정 제출 / `incident_report` 사건 신고 / `confirm_request` 확인 요청 / `adjust_reject` 조정 거부 / `other` 그 외 (v11 §5-A).

★**라우팅은 한 축이 아니라 둘이다**(v11 §5-B) — `case_type`(객체 종류, `issue_code` 접두에서 뽑는다) + `intent`(요청 종류). **요청 종류 다섯만으로는 여섯 팀 어디에도 안 간다**는 것이 2026-09-09 실행으로 확인됐다.

## Team이 하지 않는 것 셋

**이게 경계의 실체다.**

| 규칙 | 왜 |
|---|---|
| side effect를 실행하지 않는다 | 승인 경계 우회, 이중 실행, 감사 누락을 막는다 |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |
| 다른 Team을 직접 호출하지 않는다 | 의존 그래프가 생기면 교체가 불가능해진다 |

상세는 [team-boundary.md](team-boundary.md).

## Team의 read 도구

`[실측]` Team별 `allowed_tools`

| Team | 허용 도구 |
|---|---|
| Procurement + Order & Payment | `read.order`, `read.account`, `read.policy`, `read.catalog` |
| Return & Refund | `read.order`, `read.return`, `read.policy` |
| Fulfillment & Logistics | `read.order`, `read.shipment`, `read.policy` |
| Catalog & Verification | `read.catalog`, `read.order_items`, `read.policy` |
| Response Review | `read.policy` |

**결제 조회 도구는 없다.** Team 이름에 "Payment"가 있지만 실제 권한은 없다. → [D-001](../../../wiki/decisions/D-001-payment-ownership.md)

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-TEAM-001` | Team manifest는 프로토콜을 구현한다 | automated |
| `INV-CS-TEAM-002` | manifest의 scope는 정확히 선언된다 | automated |
| `INV-CS-TEAM-003` | Team은 side effect를 실행하지 않는다 | **review** |
| `INV-CS-TEAM-004` | Team은 read 도구를 직접 호출하지 않는다 | **review** |
| `INV-CS-TEAM-005` | Team은 다른 Team을 직접 호출하지 않는다 | **review** |

`[미확보]` **003~005가 자동 판정이 아니다.** 설계의 핵심 규칙인데 사람이 리뷰에서 잡아야 한다.

## sample의 Team

`final_project_sample`에 Billing/Technical 2종이 있다. **10주 착수 목록에 없다.**

Team-플러그인 아키텍처가 실제로 동작한다는 증거(Core 격리 위반 0)로만 남긴다.

## 인접 영역

- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Team을 호출하는 쪽
- [../context/index.md](../context/index.md) — Team의 입력을 만드는 곳
- [../actions/action-proposal.md](../actions/action-proposal.md) — Team의 출력이 가는 곳
- [../../../wiki/architecture/core-vs-team.md](../../../wiki/architecture/core-vs-team.md) — Team 자격 판정
---

## 조립 선언은 따로 본다

컴포넌트·모듈·Port·인스턴스를 어떻게 가르고 조립 선언에 무엇을 적는지는 [composition.md](composition.md) 에 있다. **Team 목록과 낡는 이유가 다르다** — 이 문서는 도메인이 바뀌면 낡고, 그쪽은 계약이 바뀌면 낡는다.

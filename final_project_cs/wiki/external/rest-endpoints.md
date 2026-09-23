---
type: contract
title: 엔드포인트별 요청·응답 계약
description: Case 다섯 경로 + outbox 해소 + 여행 API 다섯 경로의 필드·제약·상태 전이. rest-api.md 가 300줄을 넘어 떼어 냈다
status: draft
tags: [api, contract]
domain: travel
domain_note: "[2026-09-14] 여행 API 가 생겼다(`/v1/trips/*` 다섯 + `/plan/{trip_id}`). ★[2026-09-22] **일정 생성** `POST /v1/trips/plan` 이 늘었다 — **v11 §4-A(「계획 생성은 우리 일이 아니다」)를 뒤집는 경로**이며 사용자 지시로 만들었다(리포트 `../records/reports/2026-09-22_2205_일정생성기_v11-4A를_뒤집는다.md`). [2026-09-22] 토큰 링크가 하나 늘었다 — `/booking-change/{booking_id}`(업체 예약 변경 링크, DoD-16·17). [2026-09-22] 위임을 주고 거두는 `/v1/delegations/*` 넷이 늘었다(DoD-18·19) — 전에는 모듈 함수뿐이라 운영자가 손으로 SQL 을 쳐야 했다. Case 경로의 예시 값(배송·환불)은 커머스 시절 그대로다 — 필드 계약은 도메인과 무관해 유효하다"
---

# 엔드포인트별 요청·응답 계약

`[실측]` [rest-api.md](rest-api.md) 에서 분리했다. **경로 다섯 개의 필드 단위 계약이다.**

## `POST /v1/cases` 요청·응답 필드

`[실측]`

요청:

| 필드 | JSON 타입 | 예시 | 필수 여부 |
|---|---|---|---|
| `request_id` | string | `"req_01"` | 필수 |
| `idempotency_key` | string | `"idem_01"` | 선택 — 보내면 **그 값을 쓴다** |
| ~~`tenant_id`~~ | — | — | `[정정 2026-09-10]` **없다.** 요청 몸통에서 지웠다 — 테넌트는 인증(`principal.tenant_id`)에서만 온다. 보내면 `extra="forbid"` 라 거부된다(`app/presentation/api/cases.py:29-40`) |
| `customer_id` | string (**UUID**) | `"3f2c…"` | 필수 — `[정정 2026-09-10]` 예시가 `"cust_01"` 이었는데 UUID 가 아니라 거부된다 |
| `message` | string | `"배송완료로 떴는데 상품을 못 받았어요"` | `[미확보]` |
| `channel` | string | `"personal_ai"` | `[미확보]`; `personal_ai \| mcp \| web \| api` 중 하나 |
| `subject_ref` | object \| null | `{"kind":"trip","id":"<uuid>"}` | 선택 — `[결정 2026-09-17]` 이 Case 가 **무엇에 대한 것인지**. 아래 절 |

### `subject_ref` — Case 가 가리키는 대상 `[결정 2026-09-17]`

Case 버전만으로 여행 일정을 관리하려면 Case 가 「어느 여행의 어느 항목」인지 알아야 한다(v11 §4-B 「Case 에 `trip_id`」). 코어는 도메인 어휘를 모르므로 **이름이 중립인 칸 하나**로 받는다.

| 칸 | 타입 | 필수 | 뜻 |
|---|---|---:|---|
| `kind` | string | 예 | 대상 종류(도메인 어휘 — 여행은 `trip`) |
| `id` | UUID | 예 | 대상 id |
| `part_id` | UUID \| null | 아니오 | 대상 안의 한 부분(여행은 일정 항목 `item_id`) |
| `base_version` | int \| null | 아니오 | 고객이 **본** 대상 버전 — 그 사이 바뀌었으면 적용하지 않는다 |
| `request` | object \| null | 아니오 | 화면 버튼처럼 **구조가 정해진 요청**(여행은 `{"type":"change","choice":…}`·`{"type":"rollback","to_version":n}`). 자유 문장이면 비운다 |

- ★**서버가 확인한다.** 조립이 주입한 **대상 확인기**가 그 대상이 이 테넌트·이 고객의 것인지 본다. 아니면 `404 not_found`(있는지도 말하지 않는다). 확인기가 없는 조립에서 `subject_ref` 를 보내면 `422 subject_ref_unsupported` — **조용히 무시하지 않는다.**
- 확인기는 **라우팅 힌트**(대상 부분의 종류)를 돌려줄 수 있다. 두 종류다.
  - **확인된 힌트** — 클라이언트가 `part_id` 를 지정했고 서버가 그 항목을 확인했다. 그 종류는 사실이라 **분류보다 우선한다**(화면 버튼이 보낸 문장에 분류가 아무 접두나 붙여도).
  - **짐작한 힌트** — `part_id` 가 없어 확인기가 「가장 최근에 바뀐 항목」으로 짐작했다. 분류가 **객체 접두를 못 붙였을 때만**(`issue_code` 에 `_` 가 없을 때 — 예: `other`) 쓴다.
- ★**문장 해석이 분류보다 먼저다** `[2026-09-17]`. 조립이 **대상 해석기**(`app/core/subjects.py` `SubjectInterpreter`)를 주입했으면, 대상이 정해진 고객 Case 는 분류 직전(트랜잭션 밖)에 문장을 해석한다. 해석이 담당을 내면 **확인된 힌트**로 기록해 분류 접두보다 우선한다. 해석 결과는 분류와 **같은 `CLASSIFIED` 이벤트**의 `state_patch` 로 `state_json.interpretation` 에 남고, Team 은 그것을 다시 추출하지 않고 쓴다.
  - 여행: 신고 종류로 담당을 정한다 — 늦음·휴무 → dining, 품절 → activity, 바꿔 줘·되돌려 줘 → 지정한 항목(없으면 가장 최근에 바뀐 항목)의 종류. 그 밖(`other`)은 힌트를 내지 않고 분류로 간다. 구조가 정해진 `request` 는 모델을 부르지 않는다.
  - 해석기가 예외를 내면 `interpretation.error` 로 남기고 분류 경로로 간다(삼키지 않는다).
  - 왜: 실제 gemma4:12b 로 재 보니(문장마다 3회, 같은 결과) 신고 추출은 7문장 모두 맞는데 분류 접두는 3문장이 빗나가 사람에게 넘어갔다 — [이식 검증](../records/evidence/CASE-VERSION-ITINERARY_이식검증.md).
- 저장 자리는 `customer_cases.state_json.subject_ref` 이고, Team 은 `ContextPack.current_state.subject_ref` 로 받는다(계약 칸 추가 없음 — `current_state` 는 dict).

성공 응답 상태 코드는 `201`이다.

| 응답 필드 | JSON 타입 | 예시 |
|---|---|---|
| `case_id` | string | `"case_01"` |
| `status` | string | `"classifying"` |
| `version` | number | `1` |
| `intent` | string | `"shipping"` |
| `issue_code` | string | `"shipping_delivered_not_received"` |
| `sentiment` | string | `"negative"` |
| `links.self` | string | `"/v1/cases/case_01"` |

`[정정 2026-09-10]` **클라이언트가 `idempotency_key` 를 보내면 그 값을 쓴다.** 안 보냈을 때만 서버가 `request_id` 로 계산한다(`cases.py:106-111`). 「서버가 재계산하며 클라이언트 값은 재료일 뿐」은 2026-09-01 이전 동작이다. 같은 키로 재요청하면 새 Case를 만들지 않고 기존 결과를 그대로 반환한다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:47-67`

## `GET /v1/cases` 쿼리 계약

`[실측]`

| 쿼리 필드 | 필수 | 기본값·제약 |
|---|---:|---|
| `customer_id` | 예 | 호출자의 소유 범위 검사 |
| `status` | 아니오 | `[미확보]` 허용값 |
| `limit` | 아니오 | 기본값 `20`, 최대 `100` |
| `cursor` | 아니오 | `[미확보]` 형식 |

호출자의 tenant·customer 범위 밖 Case를 반환하지 않는다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:68-71`

## `GET /v1/cases/{case_id}` 응답 계약

`[실측]`

| 필드 | 형태·예시 |
|---|---|
| `case_id` | `"case_01"` |
| `status` | `"waiting_approval"` |
| `version` | `7` |
| `answer` | `"환불 요청을 준비했습니다."` |
| `pending_actions[]` | `{"action_id":"a_01","action_type":"refund.request","approval_required":true}` |
| `evidence[]` | `{"source_type":"policy","source_id":"doc_04#c12","claim":"..."}` |

`evidence`는 masked 상태로 반환한다. 원문 PII를 응답에 싣지 않으며, `answer`가 있는데 `evidence`가 비어 있으면 계약 위반이다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:73-84`

## 추가 메시지 resume 제약

`[실측]`

| 항목 | 제약 |
|---|---|
| 상태 전이 | `waiting_input` → `resuming` |
| resume token 저장 | 원문이 아니라 hash만 저장 |
| TTL | `24h` |
| 사용 횟수 | 일회성 |
| 중복 처리 | 동일 `event_id` 재처리는 idempotent |
| TTL 만료 | 자동 진행 금지; `escalated` + 운영자 알림 |

`[미확보]` 원본은 이 endpoint의 요청 body 필드 이름을 밝히지 않는다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:86-90`

## 승인 요청·감사 계약

`[실측]`

요청:

```json
{"decision":"approved","approver_id":"op_01","note":"정책 확인함"}
```

| 필드 | 제약 |
|---|---|
| `decision` | `approved \| rejected` |
| `approver_id` | `[미확보]` 필수 여부·타입 제약 |
| `note` | `[미확보]` 필수 여부·길이 제약 |

승인 event와 before/after hash를 audit에 기록한다. audit에는 API key 원문이나 결제 식별자 원문을 기록하지 않는다. 승인 후 실행은 idempotent해야 하며 동일 요청 10회에 side effect는 1회다.

근거: `wiki/records/handoff/03_REST_MCP_인터페이스.md:92-99`

## `POST /v1/outbox/{message_id}/resolve` 계약

`[실측]` `app/presentation/api/outbox.py`. 2026-08-24 추가 — 이 문서가 "다섯 경로"라고 적혀 있던 동안 빠져 있었다.

**`unknown`으로 남은 발행 건을 사람이 봤고 판단했다는 기록이다.** 재처리하지 않는다.

| 항목 | 계약 |
|---|---|
| scope | `action:approve` |
| 요청 body | `resolution`: `confirmed_delivered` \| `confirmed_not_delivered` · `note`(1자 이상) · `resolved_by`(1자 이상). `extra="forbid"` |
| 대상 행 | `status='unknown'` **이고** `resolved_at IS NULL` 인 행만. tenant 조건 포함 |
| 바뀌는 것 | `resolved_at`·`resolved_by`·`resolution_note`·`resolution` **만**. `status`는 `unknown` 그대로, provider 발행 없음 |
| `422` | `note_required` · `resolved_by_required` (공백만 있어도) |
| `409 invalid_status` | 행은 있는데 `unknown`이 아니거나 이미 해소됨 |
| `404` | 행이 없거나 다른 tenant |

**"기록만"이 설계다.** 해소했다고 시스템이 대신 재시도하면 `unknown`을 만든 이유(돈이 나갔는지 모름)가 무너진다. → [../actions/outbox.md](../actions/outbox.md)

## 여행 API — `/v1/trips/*` · `/plan/{trip_id}`

`[실측 2026-09-14]` `app/modules/travel_ops/trip_api.py`. 라우터는 도메인 폴더에 있고
`composition.build_domain_routers()` 가 앱에 넣는다 — presentation 은 도메인을 import 하지
못한다(INV-CS-ARCH-001). 확정 시나리오 하루를 이 경로로 흘리는 시험:
`tests/e2e/test_trip_api.py`.

| 경로 | scope | 하는 일 |
|---|---|---|
| ★`POST /v1/trips/plan` `[2026-09-22]` | `trip:write` | **일정 생성** — 요청(도시·날짜·인원·제약·자유 문장)에서 초안을 만들어 판정을 통과시킨 뒤 돌려준다. `register:true` 면 이어서 등록한다. 아래 절 |
| `POST /v1/trips` | `trip:write` | 일정 등록. 버전 1 + **생성 통지**(계획서 링크가 처음 나가는 자리, v11 §6-B) |
| `GET /v1/trips/{trip_id}` | `trip:read` | 최신 버전 · 항목별 「다른 안」 · 버전 이력 · `plan_url` |
| `POST /v1/trips/{trip_id}/reports` | `trip:write` | 고객 신고 `delay`(`minutes`) · `closed` · `stock_out`(`products`) |
| `POST /v1/trips/{trip_id}/items/{item_id}/alternate` | `trip:write` | 재요청 ① — 들고 있던 다른 안으로 교체(`base_version`, `choice`) |
| `POST /v1/trips/{trip_id}/rollback` | `trip:write` | 재요청 ② — 옛 버전을 **새 버전으로** 다시 쓴다(`base_version`, `to_version`) |
| `GET /plan/{trip_id}?t=…` | 없음(토큰) | 여행계획서 링크. 로그인 없음, 여행별 HMAC 토큰. 늘 최신 버전(DoD-25). `&format=json` |
| ★`GET /booking-change/{booking_id}?t=…` `[2026-09-22]` | 없음(토큰) | **업체 예약 변경 링크**. 로그인 없음, **예약별** HMAC 토큰. 아래 절 · `&format=json` |


### ★`POST /v1/trips/plan` — 일정을 **우리가 만든다** `[2026-09-22]`

`[실측 2026-09-22]` `app/modules/travel_ops/planner.py` · 라우트는 `trip_api.py`.
시험 [`tests/e2e/test_trip_planner.py`](../../tests/e2e/test_trip_planner.py)(19) ·
[`tests/unit/travel/test_planner.py`](../../tests/unit/travel/test_planner.py)(13).

★★**이 경로는 v11 §4-A 를 뒤집는다.** 기준선은 「계획 생성은 우리 일이 아니다 — 외부
에이전트가 만든 일정을 받아 검증한다」였다. 사용자 지시로 생성기를 우리가 만들었고, 계획서는
읽기 전용이라 고치지 않았다. 무엇을 왜 뒤집었고 이 생성기가 **못 하는 것**이 무엇인지는
[리포트](../records/reports/2026-09-22_2205_일정생성기_v11-4A를_뒤집는다.md)에 있다.

| 규칙 | 계약 |
|---|---|
| 받는 것 | `request_id` · `customer_id` · `city`(서울만) · `start_date` · `days`(1~7) · `party_size`(1~4) · `locale` · `title` · `constraints`(`payment`·`budget_krw`) · `preferences`(자유 문장) · `register`(기본 `false`) |
| 내는 것 | `draft`(**`POST /v1/trips` 가 받는 그대로** — `places`+`items`+`routes`) · `planner` · `candidates` · `checks` · `coverage` · `calls` · **`rag`** |
| ★★**판정** | 초안은 **등록이 쓰는 그 판정기**(`check_itinerary`)를 통과해야만 나온다. 위반이 나오면 고쳐서 다시 판정하고(최대 3회, `MAX_REPAIR_ROUNDS`) 끝내 못 고치면 `422 plan_infeasible` + 위반·완화 조건·시도한 고침. **판정을 건너뛰는 길이 없다** — `register:true` 면 등록이 같은 판정기를 한 번 더 돌린다 |
| **장소 출처** | ①우리 DB `places` ②`place_catalog`(TourAPI 지역 동기화분) ③TourAPI 실시간은 ②가 **비었을 때만**. 지어내지 않는다. 좌표를 모르는 장소는 후보에서 뺀다 |
| ★**모르는 값** | 카탈로그 장소는 영업시간·가격이 **없다.** 비워 두므로 판정이 그 칸을 **보지 않는다**. `coverage` 가 「영업시간 n/N · 가격 n/N · 구 n/N」로 분자/분모를 적는다 — 모름은 통과가 아니다 |
| ★**LLM 의 몫** | **순서뿐이다.** 모델은 후보 목록의 **줄 번호**만 내고, 시각·좌표·가격·이름은 서버가 채운다. 목록에 없는 값은 버린다. 모델이 없거나 죽으면 규칙 순위로 짜고 `planner.mode=rules`+`note` 로 말한다. ★모델을 불렀는데 **쓴 값이 하나도 없으면** `mode` 가 `rules` 로 내려간다(`from_model`/`items` 로 분자/분모) — 조용한 폴백을 막는다 |
| ★**`rag` — 요청을 규정에 붙인다** `[2026-09-22]` | 고객의 말로 **여행 코퍼스**를 검색한다(scope `travel_activity`·`travel_dining`·`travel_access`·`travel_weather`, top 5). 찾은 조각은 ①모델이 순서를 짤 때 **바탕**으로 보이고 ②응답에 `evidence`(`source_type: policy` · `source_id` · `scope` · `score` · `excerpt`)로 실린다. ★★**후보를 거르지는 않는다** — 규정 문장과 장소 속성을 기계로 맞출 방법이 아직 없다. 고객이 아무 말도 안 하면 요청 요약으로 묻고 그 사실을 `asked` 에 적는다. **0건이거나 못 읽었으면 `note` 가 그렇게 말하고 초안은 그대로 나간다**(규정은 초안의 성립 조건이 아니다 — 성립은 `check_itinerary` 가 본다) |
| **선호** | 키워드 대조다(모델 아님). 실내/야외 · 아이 동반 · 싫다고 한 것. 싫다고 한 것은 **탈락**이지 감점이 아니다. 한계 — 요리 분류 표가 없어 **이름으로만** 거른다 |
| 멱등 | `register:true` 는 `/v1/trips` 와 **같은 멱등 키**(`trips.request_key`). 같은 `request_id` 가 다시 오면 **모델도 부르지 않고** 이미 만든 여행을 `{"status":"duplicate","created":false,"trip":…}` 로 돌려준다 |
| ★`register` 기본값 | **`false`.** 등록은 상태를 만들고 **통지를 내보낸다**(계획서 링크가 처음 나가는 자리). 초안을 보자고 부른 요청이 조용히 고객에게 링크를 보내면 안 된다 |
| 거절 | `422 city_not_supported`(서울만) · `422 out_of_product_scope`(7일·4인) · `422 not_enough_candidates`(필요 수와 가진 수를 같이 적는다) · `422 plan_infeasible`(위반 + 완화 조건 + 시도한 고침) · `422 day_overflow`(고치다 하루 마감 21:30 을 넘겼다 — 판정기는 이 값을 모른다) · `422 plan_short`(우리 쪽 결함 — 항목이 덜 짜였다. **짧아진 채로 내주지 않는다**) |
| 바깥 호출 | **TourAPI 0회**가 정상이다(카탈로그를 읽는다). `calls.tour_api`·`calls.model` 로 센다 |

**아직 못 하는 것** — 실제 예약·가격 확인, 서울 밖 도시, 이동 항목(`mobility`)과 경로 소요.
항목 사이 여유는 **직선거리 ÷ 도보 80m/분 `[추정]`**이고 실제 경로를 조회하지 않는다.
자세한 목록은 리포트 §「이 생성기가 못 하는 것」.

### `GET /booking-change/{booking_id}` — 업체 건을 넘기는 링크 `[2026-09-22]`

`[실측]` `app/modules/travel_ops/change_link.py` · 라우트는 `trip_api.py`. v11 §4-C · §12 DoD-16·17.

**업체 예약은 우리가 바꾸지 않는다.** 우리 일정 버전은 먼저 고쳐 두고, 업체 쪽 건은 고객이 직접 진행하도록 넘긴다. 그 인계를 빈손으로 하지 않으려고 **바뀔 항목 · 대안 · 차액**을 한 장에 정리해 주는 것이 이 링크다.

| 규칙 | 계약 |
|---|---|
| 토큰 | 여행이 아니라 **예약 한 건**에 붙는다. `HMAC(secret, "booking-change:{tenant}:{booking_id}")[:32]` — **저장하지 않고** 맞춰 볼 때 다시 계산한다. ★계획서 토큰과 **접두가 다르다**(`plan:` vs `booking-change:`) — 같으면 계획서 토큰으로 예약 화면이 열린다 |
| 틀린 토큰 | `404`(있는지도 말하지 않는다). 없는 예약도 `404` |
| 인증·승인 | **없다.** 이 경로는 아무것도 쓰지 않는다 — 읽기만 하고, 링크가 곧 자격이다. 승인이 필요한 것은 우리 예약을 `change_requested` 로 옮기는 기록 쪽이다(`booking.change` 적용기) |
| 테넌트 | 예약이 **어느 테넌트 것인지 먼저 찾아** 그 테넌트로 토큰을 맞춘다(계획서 링크와 같은 예외 — 이 한 줄만 테넌트 조건 없이 읽고, 얻는 것은 테넌트 문자열 하나다) |
| 응답에 없는 것 | `customer_id` — 링크를 받은 사람에게 내부 id 를 보이지 않는다 |
| **바뀔 항목** | `bookings`(booking_no·kind·status·starts_at·party_size·amount_cents) + `places.name` + `supplier_bookings`(supplier·supplier_ref). 그 예약에 걸린 일정 항목의 제목·시각도 함께 |
| **대안** | 그 예약에 걸린 **일정 항목의 `detail.alternates`** — 감시 루프가 재계획할 때 들고 둔 「다른 안」이다. ★여기서 **새로 계산하지 않는다**(고객이 계획서에서 본 것과 다른 안이 뜨면 안 된다). 1차 소스 `itinerary_items.booking_id`, 대체 소스 같은 장소(`bookings.place_id`). 둘 다 없으면 **대안 0건**이고 그렇게 적는다 |
| ★★**차액** | 양쪽 **1인 가격**(`places.attributes.price_krw`) 차 × 인원. 같은 소스끼리 뺀다 — 실제 결제액(`amount_cents`, 원의 100배)은 **따로** 「지금 결제된 금액」으로 보인다 |
| ★★값을 모를 때 | **지어내지 않는다.** 한쪽 가격이라도 없으면 `difference_krw`=`null` + `difference_unknown`(어느 쪽을 몰라서인지)이고 화면은 「확인되지 않았습니다」로 적는다. 0원으로도 추정으로도 채우지 않는다(v11 결정 15 · 근거 없는 문장 금지) |
| 분모를 적는다 | `difference_basis` — 「1인 가격 차 × 인원 N명」. 인원을 모르면 그것도 적는다 |
| 기록 | 승인 뒤 `booking.change` 적용기가 이 링크를 인계 메시지(`outbox` topic `booking.handoff`)의 `change_url`·`text` 에 싣는다. **무엇을 왜 넘겼는지가 그 한 줄이다** |

시험: [`tests/e2e/test_booking_change_link.py`](../../tests/e2e/test_booking_change_link.py)(4) — 세 값이 보이는가 · 틀린 토큰은 404 · **차액을 모를 때 지어내지 않는가** · 실제 공급자 원장이 안 바뀌는가.

| 규칙 | 계약 |
|---|---|
| 멱등 — 등록 | `request_id` → 서버 키(`trips.request_key`, 부분 UNIQUE). 같은 키·같은 몸통이면 기존 여행(`created:false`), **다른 몸통이면 `409 idempotency_key_reused`** |
| 멱등 — 신고·재요청 | 원인 칸에 `request_id` 를 남긴다. 같은 요청이 다시 오면 `{"status":"duplicate","version":n}` — 일정을 또 밀지 않는다 |
| 낡은 쓰기 | 재요청은 고객이 **본** `base_version` 위에만 쓴다. 다르면 `409 stale_itinerary`(+현재 `version`) |
| 기타 `409` | `no_alternate` · `unknown_choice`(+`choices`) · `conflicts_next` · `alternate_invalid`(다시 점검해 깨짐) · `invalid_version` |
| ★**등록 판정** `[2026-09-21]` | 받을 때 **보낸 값으로** 판정한다(v11 DoD-2). 불가능하면 `422 itinerary_infeasible` + `violations[]` — 각 칸은 `code`·`items`(seq)·`reason`·`remedy`(완화 조건, DoD-3). 거절하면 **아무것도 저장하지 않는다.** 보는 것: 시간 역전 · 겹침 · 이동 항목이 계획 수단 소요보다 짧음 · **구가 다른데** 이동 0분 · 영업시간·브레이크 · 결제 수단 · 예산(인원 곱) |
| ★모르는 칸은 판정하지 않는다 | 영업시간·결제·예산·경로 소요가 보낸 값에 없으면 통과시킨다(결정 15 — 지어내지 않는다). 그 자리는 감시 루프가 실제 소스로 다시 본다 |
| 장소 | 테넌트 안 `(name, kind)` 가 이미 있으면 **그것을 쓴다.** 보낸 속성은 빈 칸만 채운다 — 카탈로그 값을 덮지 않는다 |
| 되돌림 | 되살린 항목은 `customer_pinned` — 감시 루프가 다시 자동으로 바꾸지 않는다 |
| 시각 | 시간대 없이 오면 서울 시각(대상 도시가 서울 하나, v11 §1) |
| 링크 토큰 | 틀리면 `404`(있는지도 말하지 않는다). 응답에 `customer_id` 를 싣지 않는다 |

`[미구현]` 고객 **자유 문장** → Case → 분류 → 여기로 잇는 배선(지금 신고는 구조화된 몸통) ·
계획서의 고객 언어 생성(결정 14, 지금은 한국어 원문).

### `routes{<키>}.options[].uses` — 이동 수단이 지나는 대상의 표기 `[결정 2026-09-23]`

`uses` 는 그 수단이 **지나가는 대상**을 적는 칸이다. 감시 루프 · 출발 안내 · 재계획 · Mobility Team 이
이 값을 운행·통제 사건과 **문자열로 대조**한다(`trip_watch_cases.py:126` · `trip_reminders.py:225` ·
`replan.py:204` · `itinerary_changes.py:152`). ★**표기가 다르면 사건이 있어도 못 잡는다** — 오류도 안 난다.
그래서 이 칸은 보내는 쪽이 알아서 쓰는 자유 문자열이 아니라 **계약**이다.

★이것은 **바깥 계약**이다. 외부 에이전트가 쓰므로 사람이 읽는 공식 표기를 쓴다. 우리 쪽 이동 데이터가
내부에서 다른 표기(예: 노선명 두 자리 `02호선`)로 정규화하더라도, **그 변환은 그 모듈의 입구에서 한다** —
외부가 내부 키 규칙을 알게 만들지 않는다.

| 수단 | 형식 | 예 |
|---|---|---|
| 지하철 | `<노선명>:<역명>` | `2호선:잠실` · `3호선:경복궁` · `4호선:서울역` · `경의중앙선:용산` · `공항철도:홍대입구` |
| 버스 | `버스:<노선번호>` | `버스:2224` · `버스:N26` |
| 도로 | `도로:<도로명 전체>` | `도로:세종대로` · `도로:올림픽대로` |
| 도보 | 따로 적지 않는다 — 지나는 큰길을 `도로:` 로 | `도로:세종대로` |

**지하철**
- 노선명은 공식 이름. 1~9호선은 `N호선`(`02호선` ✗). 그 밖은 `경의중앙선`·`공항철도`·`신분당선`·`수인분당선`.
- 역명은 끝의 「역」을 뺀다(`잠실역` → `잠실`). 괄호 병기도 뺀다(`경복궁(정부서울청사)` → `경복궁`).
  ★**역 이름 자체가 「서울역」이면 그대로 `서울역`** 이다(`서울` ✗).
- **탄 역 · 갈아탄 역 · 내린 역**만 적는다. 지나치기만 하는 역의 무정차는 그 이동에 영향이 없다.
  갈아탄 역은 **두 노선으로 각각** 적는다 — 어느 노선의 무정차든 환승이 깨진다
  (`2호선:을지로3가` · `3호선:을지로3가`).

**버스** — 노선번호를 적는다. 정류장 이름·동네 이름(`버스:성수동`)은 쓰지 않는다. 우회·결행 정보는
노선 단위로 나온다. 버스 구간이 지나는 주요 도로도 `도로:` 로 **함께** 적는다 — 도로 통제는 버스도 막는다.

**도로** — 경찰청 UTIC 돌발정보의 도로명을 **전체 이름**으로 적는다. `[실측]` 대조가 **포함 여부**다 —
UTIC 의 도로명(`roadName`)이나 사건 제목(`incidentTitle`)에 그 이름이 들어 있으면 걸린다
(`app/infrastructure/travel/utic.py:177`). 짧게 줄이면(`도로:대로`) 무관한 사건까지 걸린다.
택시 구간도 같다.

**도보** — `도보:` 는 쓰지 않는다. 걷는 길을 막는 것은 집회·행사 통제이고, 그것은 도로 통제 정보로 들어온다.
큰길을 지나지 않는 짧은 도보는 `uses: []`.

`[실측 2026-09-23]` **지금 실제로 감시되는 것**

| 대상 | 상태 |
|---|---|
| `도로:` | UTIC 돌발정보로 감시한다 |
| 지하철 · 버스 | **우리 코드에 연결된 실시간 소스가 없다.** 감시는 이 대상을 「사건 없음」이 아니라 **확인 못 한 대상**(`unsupported`)으로 센다. 소스가 붙으면 이 표기로 대조한다 — 그래서 지금부터 맞춰 적는다. 후보: 서울교통공사 지하철알림정보(data.go.kr 15144070 — 무정차 안내, 서울교통공사 관할만, 역명이 본문 자유 텍스트) `[미연결]` |

`[미반영]` 이 계약과 어긋나는 것 — 코드 담당 몫이다.
- 확정 시나리오 `app/modules/travel_ops/scenarios/seoul_day_taiwan_friends.json` 의 `버스:성수동`(구역)·`도보:서울역`,
  환승역 `2호선`/`3호선` 한쪽만 적은 구간.
- **등록할 때 형식을 검사하지 않는다.** 표에 없는 모양(`잠실역`·`02호선`·`버스:성수동`)이 와도 받는다 — 받으면
  나중에 조용히 못 잡는다. 거절(`422`)할지 경고할지는 정하지 않았다.
- 길게 보면 이 칸은 외부가 쓰지 않는 것이 맞다 — 경로 조회(`read.route`)가 생기면 `uses` 는 **우리가 조회해서
  만든다.** 지금은 D-CS-005(ODsay 미사용)에 따라 경로 정의를 외부가 들고 오므로 표기를 공개한다.

## 위임 — `/v1/delegations/*` `[2026-09-22]`

`[실측]` `app/modules/travel_ops/delegation_api.py`. 라우터는 도메인 폴더에 있고
`composition.build_domain_routers()` 가 앱에 넣는다(여행 API 와 같은 이유 — presentation 은
도메인을 import 하지 못한다, INV-CS-ARCH-001). v11 §12 DoD-18·19.

**전에는 이 경로가 없었다.** 위임 범위 판정과 `delegations` 표는 있는데 **주고 거두는 자리가
없어** 운영자가 손으로 SQL 을 쳐야 했다 — 「위임은 언제든 철회할 수 있다」가 말뿐이었다.

| 경로 | scope | 하는 일 |
|---|---|---|
| `GET /v1/delegations` | `delegation:read` | 테넌트의 위임 전부 + **지금 맡기는 범위**(`limits`) + 집계 |
| `GET /v1/delegations/{customer_id}` | `delegation:read` | 한 고객의 상태 · 누적 사용액 · **주고 거둔 이력**(021) |
| `POST /v1/delegations/{customer_id}/grant` | `delegation:write` | 맡긴다. 다시 주면 철회가 풀린다(`regranted:true`) |
| `POST /v1/delegations/{customer_id}/revoke` | `delegation:write` | 거둔다. 판정은 **적용 순간**이라 승인 뒤에 거둬도 그 건은 열리지 않는다 |

| 규칙 | 계약 |
|---|---|
| ★**scope 를 `action:approve` 와 나눈다** | 승인은 **제안 한 건**에 "이 변경을 해도 된다" 이고, 위임은 **서 있는 권한**이다 — 한 번 주면 거둘 때까지 그 고객의 모든 자동 실행이 한계 안에서 열린다. 영향 범위가 다르면 나누는 것이 이 저장소의 방식이다(`composer:admin`·`ops:reload` 가 같은 기준으로 갈라졌다). 읽기/쓰기도 나눈다 — 현황을 보는 사람이 문을 열지는 못한다 |
| 요청 몸통 | `actor_id`(1자 이상) · `note`(1자 이상). `extra="forbid"`. **공백만 보내면 `422`** — 근거 없이 위임 상태를 바꾸지 않는다(`/v1/outbox/{id}/resolve` 와 같은 계약) |
| `404` | 다른 테넌트의 고객이거나 없는 고객. **있는지도 말하지 않는다** |
| ★`409 no_live_delegation` | 거둘 위임이 없다. **「거뒀다」고 답하지 않는다** — 200 으로 넘기면 운영자가 "눌렀으니 됐겠지" 로 간다. 이미 막혀 있다는 사실은 응답의 `state` 가 말한다 |
| 응답에 없는 것 | `external_id`·`email_hash` — 고객 식별자를 `customer_id` 밖으로 늘리지 않는다 |
| 한계 값 | 만들지 않고 **읽어서 이름표만 붙인다**(`limits[].label`·`value`). 정본은 `config/guardrails.yaml` `travel.delegation`(RULE.md §3.1). 화면이 여행 어휘를 모르고도 그릴 수 있게 하려는 것이다 |
| ★이력 | 주기·거두기가 `delegation_events`(마이그레이션 [021](../../app/infrastructure/db/migrations/021_delegation_audit_trail.sql))에 **덧붙는다**. `delegations` 한 행은 다시 주기가 덮으므로 그것만으로는 「누가 거뒀나」가 사라진다 |

운영 화면은 `/ui/delegations` 다 — 이 경로를 **같은 프로세스 안에서** 불러 서버에서 그린다.

시험: [`tests/integration/api/test_delegation_api.py`](../../tests/integration/api/test_delegation_api.py)(12) ·
[`tests/integration/api/test_ui_delegation_screen.py`](../../tests/integration/api/test_ui_delegation_screen.py)(8).

## 관계

- [rest-api.md](rest-api.md) — 경계와 원칙
- [auth-boundary.md](auth-boundary.md) — scope
- [../actions/idempotency.md](../actions/idempotency.md) — 멱등 키

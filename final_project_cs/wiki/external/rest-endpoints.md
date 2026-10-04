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
| 받는 것 | `request_id` · `customer_id` · `city`(서울만) · `start_date` · `days`(1~7) · `party_size`(1~4) · `locale` · `title` · `constraints`(`payment`·`budget_krw`·`survey`·`density`) · `preferences`(자유 문장) · `register`(기본 `false`) |
| 내는 것 | `draft`(**`POST /v1/trips` 가 받는 그대로** — `places`+`items`+`routes`) · `planner` · `candidates` · `checks` · `coverage` · `calls` · **`rag`** |
| ★★**판정** | 초안은 **등록이 쓰는 그 판정기**(`check_itinerary`)를 통과해야만 나온다. 위반이 나오면 고쳐서 다시 판정하고(최대 3회, `MAX_REPAIR_ROUNDS`) 끝내 못 고치면 `422 plan_infeasible` + 위반·완화 조건·시도한 고침. **판정을 건너뛰는 길이 없다** — `register:true` 면 등록이 같은 판정기를 한 번 더 돌린다 |
| **장소 출처** | ①우리 DB `places` ②`place_catalog`(TourAPI 지역 동기화분) ③TourAPI 실시간은 ②가 **비었을 때만**. 지어내지 않는다. 좌표를 모르는 장소는 후보에서 뺀다 |
| ★**모르는 값** | 카탈로그 장소는 영업시간·가격이 **없다.** 비워 두므로 판정이 그 칸을 **보지 않는다**. `coverage` 가 「영업시간 n/N · 가격 n/N · 구 n/N」로 분자/분모를 적는다 — 모름은 통과가 아니다 |
| ★**LLM 의 몫** | **순서뿐이다.** 모델은 후보 목록의 **줄 번호**만 내고, 시각·좌표·가격·이름은 서버가 채운다. 목록에 없는 값은 버린다. 모델이 없거나 죽으면 규칙 순위로 짜고 `planner.mode=rules`+`note` 로 말한다. ★모델을 불렀는데 **쓴 값이 하나도 없으면** `mode` 가 `rules` 로 내려간다(`from_model`/`items` 로 분자/분모) — 조용한 폴백을 막는다 |
| ★**`rag` — 요청을 규정에 붙인다** `[2026-09-22]` | 고객의 말로 **여행 코퍼스**를 검색한다(scope `travel_activity`·`travel_dining`·`travel_access`·`travel_weather`, top 5). 찾은 조각은 ①모델이 순서를 짤 때 **바탕**으로 보이고 ②응답에 `evidence`(`source_type: policy` · `source_id` · `scope` · `score` · `excerpt`)로 실린다. ★★**후보를 거르지는 않는다** — 규정 문장과 장소 속성을 기계로 맞출 방법이 아직 없다. 고객이 아무 말도 안 하면 요청 요약으로 묻고 그 사실을 `asked` 에 적는다. **0건이거나 못 읽었으면 `note` 가 그렇게 말하고 초안은 그대로 나간다**(규정은 초안의 성립 조건이 아니다 — 성립은 `check_itinerary` 가 본다) |
| ★**영업시간 — 관광공사 원문을 요일별로** `[2026-09-28 사용자 결정]` | 판정 전에 고른 장소의 운영시간 원문(`detailIntro2`)을 읽어 `attributes.hours_week`(`{mon: {open, close, last_entry} | "closed", …}`)로 옮긴다(`place_hours.py`). 단순한 원문(「HH:MM~HH:MM」·「매주 X요일」·「연중무휴」)은 규칙, 나머지는 모델이 옮기되 **원문에 글자 그대로 있는 인용**이 붙은 시각·요일만 받는다. 계절마다 다르면 가장 짧은 시간대, 공휴일 조건은 펴지 않고 `hours_read.conditions` 에 원문으로 남긴다. 관광공사 식별자가 없는 장소는 같은 이름·종류로 찾고 좌표가 500m 안일 때만 읽는다. 판정기가 그날의 시간을 본다 — 새 위반 `closed_day`(쉬는 날) · `after_last_entry`(입장·주문 마감 뒤), 생성기는 그 장소를 그날 그 시각에 여는 곳으로 바꾼다. 결과 `planner.hours = {asked, read, by_rule, by_model, unknown, failed}`. **최종 판정은 당일 새벽 구글 확인**(이제 활동도 본다 — 닫혔으면 같은 시각 1.5km 안의 그 시각에 연다고 아는 활동으로). ☆전에는 실제 일정 38항목 중 영업시간을 아는 항목이 0개라 「일~목 휴무」인 곳이 월요일 09:00 에 들어갔다 |
| ★**하루 곳 수 — 설문 16번** `[2026-09-24]` | `constraints.survey.pace`(여유/보통/빡빡)를 **등록과 같은 함수**(`apply_survey`)로 밀도 목표(0.40/0.55/0.70)로 바꾼다. 하루 활동 수는 표로 박지 않고 **1~4곳으로 하루를 실제로 짜서**(이동 포함) `measure_density` 로 재고, 목표를 넘지 않고 판정도 통과하는 **가장 많은 수**를 고른다. 결과는 `planner.density.days[]`(`activities`·`candidates`·`actual_density`·`target_density`·`tried[]`). 밀도 목표가 없으면 하루 2곳이고 `note` 가 그렇게 말한다. 틀린 설문은 `422 invalid_survey` |
| ★**아침 식사** `[2026-09-28]` | 날마다 **하루 여는 시각**(`travel.day_window.default_start`, 08:00)에 아침 식사 1건(60분)을 두고 첫 활동은 그 뒤(이동 + 여유, 대개 09:00 이후). 후보는 ①08:00~09:00 에 연다고 **알려진** 식당 ②영업시간을 **모르는** 식당 순 — 그 뒤에 연다고 알려진 곳은 넣지 않는다. 모르는 곳은 그날 새벽 식당 확인(`dawn_check`, 03:00)이 여는지 보고, 닫혔으면 그 경로가 다시 짠다. 점심·저녁 몫을 건드리지 않고 **남는 식당만큼만** 아침 몫으로 떼어 둔다. 아침 뒤 첫 식사가 점심이다. 항목 `detail.planner.meal = "breakfast"`·`hours_known`. 결과 `planner.breakfast = {wanted, days[{date, place, hours_known, note}]}` — 후보가 모자란 날은 넣지 않고 `note` 에 그렇게 적는다. `constraints.breakfast: false` 면 짜지 않는다(첫 활동 09:00). ☆전에는 08~09시를 비워 두기만 하고 아침을 짜지 않았다 |
| ★**이동 항목** `[2026-09-24]` | 같은 날 장소 사이마다 `mobility` 항목을 넣는다 — **출발 = 다음 일정 시작 − 이동 시간 − 여유 10분**. 이동 알림은 이 출발 시각에 나간다. 경로 정의는 `routes["move-n"]` 이고 계획 수단 `estimate` 의 `eta_min` 이 추정 이동 시간, `uses` 는 비운다(노선을 모른다) |
| **선호** | 키워드 대조다(모델 아님). 실내/야외 · 아이 동반 · 싫다고 한 것. 싫다고 한 것은 **탈락**이지 감점이 아니다. 한계 — 요리 분류 표가 없어 **이름으로만** 거른다 |
| 멱등 | `register:true` 는 `/v1/trips` 와 **같은 멱등 키**(`trips.request_key`). 같은 `request_id` 가 다시 오면 **모델도 부르지 않고** 이미 만든 여행을 `{"status":"duplicate","created":false,"trip":…}` 로 돌려준다 |
| ★`register` 기본값 | **`false`.** 등록은 상태를 만들고 **통지를 내보낸다**(계획서 링크가 처음 나가는 자리). 초안을 보자고 부른 요청이 조용히 고객에게 링크를 보내면 안 된다 |
| 거절 | `422 city_not_supported`(서울만) · `422 out_of_product_scope`(7일·4인) · `422 not_enough_candidates`(필요 수와 가진 수를 같이 적는다) · `422 plan_infeasible`(위반 + 완화 조건 + 시도한 고침) · `422 day_overflow`(고치거나 이동 자리를 내다 하루 마감 22:00 을 넘겼다 — 판정기는 이 값을 모른다) · `422 invalid_survey` · `422 plan_short`(우리 쪽 결함 — 항목이 덜 짜였다. **짧아진 채로 내주지 않는다**) |
| 바깥 호출 | **TourAPI 0회**가 정상이다(카탈로그를 읽는다). `calls.tour_api`·`calls.model` 로 센다 |

**아직 못 하는 것** — 실제 예약·가격 확인, 서울 밖 도시, **실제 경로 소요**.
`[2026-09-24]` 이동 항목은 넣지만 이동 시간은 **직선거리 ÷ 도보 80m/분 `[추정]`**(60분 상한)이고 실제 경로를 조회하지 않는다
(구글 경로 키 자리만 있다). 여유 10분은 여유 답과 상관없이 같다 — **우리가 고른 값**이다.
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

### `constraints.survey` — 여행 시작 설문 `[2026-09-24]`

결정 [D-020](../../../wiki/decisions/D-020-trip-survey-and-ask-first.md) · 구현 `app/modules/travel_ops/survey.py`.
`POST /v1/trips`(과 `/v1/trips/plan` 의 등록)이 받는다. **없어도 된다** — 없으면 지금까지와 똑같이 동작한다.

| 칸 | 모양 | 판정에 |
|---|---|---|
| `version` | `"2026-09-24.v1"` (필수) | — |
| `on_disruption` | `replace`(기본) · `ask_first` | ★**쓴다** — 15번. `ask_first` 흐름은 다음 작업 |
| `pace` | `relaxed` · `moderate` · `packed` | ★**쓴다** — 16번 → 밀도 목표 0.40 · 0.55 · 0.70 |
| `theme` · `party` · `preferred_mobility[]` · `domestic` · `priority[]`(`food`·`activity`·`mobility`) · `priority_details{영역: [..]}` · `indoor_outdoor{dining·activity: indoor·outdoor·any}` · `theme_details[]` | 문자열·목록 | **받기만 한다** — 세부 값은 담당 팀이 정한다. 반영했다고 말하지 않는다 |

- 모르는 칸·틀린 값 → **`422 invalid_survey`** + `problems[]`(field·reason). 여행이 **안 생긴다.**
- `pace` 가 있고 사용자가 `density` 를 **안 줬으면**: 여행 날짜마다 하루 활동 시간 **08:00~22:00**(팀 기본값, `travel.day_window`)으로
  밀도를 잰다. `density` 를 줬는데 목표가 없으면 목표만 채운다. **사용자가 준 값이 이긴다.** 무엇을 채웠는지 `constraints.derived` 에 남는다.

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
| 버스 | `버스:<노선명>` — **서울시 노선 API 의 노선명 그대로** | `버스:2224` · `버스:N26` · `버스:01A` · `버스:110A고려대` · `버스:청계A01` · `버스:서대문02대` · `버스:서울01출근` |
| 도로 | `도로:<도로명 전체>` | `도로:세종대로` · `도로:올림픽대로` |
| 도보 | 따로 적지 않는다 — 지나는 큰길을 `도로:` 로 | `도로:세종대로` |

**지하철**
- 노선명은 공식 이름. 1~9호선은 `N호선`(`02호선` ✗). 그 밖은 `경의중앙선`·`공항철도`·`신분당선`·`수인분당선`.
- 역명은 끝의 「역」을 뺀다(`잠실역` → `잠실`). 괄호 병기도 뺀다(`경복궁(정부서울청사)` → `경복궁`).
  ★**역 이름 자체가 「서울역」이면 그대로 `서울역`** 이다(`서울` ✗).
- **탄 역 · 갈아탄 역 · 내린 역**만 적는다. 지나치기만 하는 역의 무정차는 그 이동에 영향이 없다.
  갈아탄 역은 **두 노선으로 각각** 적는다 — 어느 노선의 무정차든 환승이 깨진다
  (`2호선:을지로3가` · `3호선:을지로3가`).

**버스** — 노선명을 적는다(서울시 노선 API 의 노선명 그대로 — 끝의 A/B, A/B + 지명, 지역명 + A번호·대/소, 출근·퇴근 전용 포함).
정류장 이름·동네 이름(`버스:성수동`)은 쓰지 않는다. `[2026-09-28]` 전에는 A/B·A번호·대/소·출퇴근 모양을 몰라 실제 노선 59개를
거절했다(Mobility 쪽 보고) — 거절된 버스 후보가 오류 없이 빠진 채 와서 남산 순환 01A·01B 가 대안에서 조용히 사라졌다.
시험 `tests/unit/travel/test_route_uses_bus.py`. 우회·결행 정보는
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

`[반영 2026-09-23]` 이 계약을 코드가 지킨다.
- ★**등록이 형식을 검사한다** — `POST /v1/trips`·`POST /v1/trips/plan`(`register:true`) 둘 다 같은 본문을 지난다.
  틀리면 **`422 invalid_route_uses`** 이고 `problems[]` 에 **틀린 값 전부**를 `route`·`option`·`value`·`reason`
  으로 싣는다(첫 하나에서 멈추지 않는다). **경고가 아니라 거절**로 정했다 — 받아 두고 경고하면 보낸 쪽이 모르고,
  모르는 채로 그 구간의 사건을 놓친다. 구현 `app/modules/travel_ops/route_uses.py` ·
  시험 `tests/e2e/test_route_uses_contract.py`. 검사를 붙이기 **전에** 틀린 표기 셋(`잠실역`·`02호선:잠실`·
  `버스:성수동`)이 전부 **201 로 받아들여지는 것**을 먼저 봤다.
  ★**모양만 본다** — 그 역이 그 노선에 있는지, 그 번호의 버스가 실제로 있는지는 안 본다(우리 쪽에 노선 자료가 없다).
- 확정 시나리오를 맞췄다 — `버스:성수동` 두 곳 → `버스:2016`·`버스:2224`(+ `도로:아차산로`), `bus_sejong` 에
  `버스:7022`, 환승역 두 노선 각각(`을지로3가`·`충무로`), `도보:서울역` → `[]`. 번호·도로의 근거는
  [2026-09-23_경로_uses_표기_검사.md](../records/evidence/2026-09-23_경로_uses_표기_검사.md).
- 길게 보면 이 칸은 외부가 쓰지 않는 것이 맞다 — 경로 조회(`read.route`)가 생기면 `uses` 는 **우리가 조회해서
  만든다.** 지금은 D-CS-005(ODsay 미사용)에 따라 경로 정의를 외부가 들고 오므로 표기를 공개한다.

### 일정 응답의 `warnings[]` — 「살펴볼 점」 `[2026-10-03]`

`[반영 2026-10-03]` 일정 응답(`POST /v1/trips` · `GET /v1/trips/{trip_id}` · 웹의 같은 응답)의 `warnings[]` 는 **거절이 아니라 알림**이다. 두 가지가 한 목록에 든다 —
밀도 경고(`density_exceeded` · `density_unmeasurable`, D-019)와 **일정 품질 경고**(아래). 같은 모양이다: `code` · `date`(서울 날짜) · `reason` · `remedy` (+ 품질 경고는 가리키는 항목 순번 `items[]`).
거절은 따로 있다 — 위반(겹침 · 닫힌 곳 · 이동 시간 부족 …)이 하나라도 있으면 `422 itinerary_infeasible`. **위반이 없는 일정은 경고가 몇 개든 등록된다**(`INV-CS-ACT-008`).

| `code` | 뜻 | 기준(`config/guardrails.yaml` `travel.quality`) |
|---|---|---|
| `same_place_twice` | 그날 같은 곳이 두 번 들어 있다 | 활동은 생성기와 같은 규칙(같은 주소 · 30m · 이름 첫 낱말), 식당은 같은 가게(장소 id · 원장 id · 이름)만 |
| `meal_missing` | 하루가 점심(11:30~14:00) 또는 저녁(17:30~20:30) 창을 통째로 덮는데 식사 항목이 없고 **식사할 틈(창 안의 가장 긴 빈 시간)도 60분이 안 된다** `[2026-10-03 적대 검토 — 틈이 크면 점심을 자유 시간으로 둔 일정이라 안 알린다]` | `meal_windows` · `meal_min_items`(하루 항목이 2개 미만이면 부분 일정으로 보고 안 봄) · `meal_min_gap_minutes` 60 |
| `route_zigzag` | 그날 활동 장소를 도는 길이가 가장 짧은 순서의 1.5배 이상이고 3km 이상 더 멀다. `better_order[]` 가 더 짧은 순서 | `zigzag.min_stops` 3 · `max_stops` 8 · `min_extra_m` · `ratio` |
| `past_day_end` | 그날 마지막 일정이 하루 마감 뒤에 끝난다(늦게 끝나는 항목을 모두 `items` 로) `[체크리스트 T13]`. **활동 · 식사만 센다**(숙소 · 항공 · 이동 제외). 사용자가 하루 시간을 직접 준 여행(`constraints.density`)은 밀도 계산이 창 밖을 이미 말하므로 건너뛴다 | `travel.day_window.default_end`(22:00 — 일정 짜기와 같은 값) |
| `last_order_tight` | 식당에 도착해 마지막 주문까지 20분이 안 된다 — 라스트오더를 **알 때**(영업 종료 앞 · 브레이크 앞은 `last_order_before_break_min` 값이 있을 때만) `[체크리스트 O4]`. 영업 안 함 · 브레이크에 걸침 같은 **위반이 이미 있는 식사는 말하지 않는다** | `replan.ORDER_MARGIN_MIN` 20 — 대체 식당을 고를 때와 같은 규칙(`replan.last_order_shortfall`) |
| `last_order_unknown` | 라스트오더를 **모르는데** 식사가 영업 종료 · 브레이크 시작 1시간 안에 끝난다 — 「마지막 주문을 확인해 주세요」 `[체크리스트 O4]`. 마감이 23:59 로 읽힌 곳(자정 · 새벽 마감)은 진짜 닫는 시각을 모르니 안 센다 | `replan.LAST_ORDER_WARN_MIN` 60 |
| `quality_check_skipped` | **점검 하나가 죽어서 못 했다** — 장소 값(영업시간 · 브레이크)이 읽을 수 없는 모양일 때. 나머지 경고는 그대로 나가고 이 경고가 `rules[]` 에 못 한 점검 이름을 싣는다(「경고 없음」이 「점검 안 함」으로 보이지 않게). 서버 로그에도 남는다 `[2026-10-03 적대 검토]` | — |

★**일정에 있는 값만으로 센다**(바깥 조회 없음, 구현 `itinerary_quality.py`). 한계: ①식사는 `kind == "dining"` 만 센다 — 외부가 다른 이름을 쓰면 끼니가 없다고 잘못 알릴 수 있다 ②좌표 없는 활동은 `route_zigzag` 에서 뺀다 ③시간이 정해진 일정(예약 · 고객 고정)이 둘 이상인 날은 `route_zigzag` 를 안 본다 ④**같은 날 안에서만** 센다 — 첫날 궁궐을 셋째 날에 또 넣는 일정은 `same_place_twice` 가 못 잡는다 ⑤장소 값만 본다 — 요식 원장이 라스트오더를 아는 식당도 일정에 그 값이 없으면 `last_order_unknown` 이 나올 수 있다 ⑥값은 **우리가 고른 것**이다(측정 안 함 — 체크리스트 v2 §7 의 결함일 비율로 조정).

## 보류 제안 — `/v1/trips/{trip_id}/proposals*` `[2026-09-24]`

`[실측]` `app/modules/travel_ops/trip_api.py` · 저장 `pending_changes`(마이그레이션 024) · 결정 [D-020](../../../wiki/decisions/D-020-trip-survey-and-ask-first.md).
감시가 일정 문제를 찾았거나 **고객이 늦음·휴무를 신고했는데**(`[2026-09-25]` `/reports` · `/messages`) **바로 바꾸지 않고
묻는 경우**(설문 15번 「먼저 물어봐줘」, 또는 「변경 안 할 일정」 항목 자체를 바꿔야 할 때) 이 자리에 제안이 쌓인다.
그때 신고 응답은 `{"status": "asked", "proposal_id", "reason", "item", "notice"}` 이고 일정은 **바뀌지 않는다.**
같은 신고가 다시 오면 `"already": true` 로 같은 제안을 돌려준다.

| 경로 | scope | 뜻 |
|---|---|---|
| `GET /v1/trips/{trip_id}/proposals` | `trip:read` | 그 여행의 제안 전부. `status` = `open` · `chosen` · `kept` · `expired` · `superseded` |
| `POST /v1/trips/{trip_id}/proposals/{proposal_id}/choose` | `trip:write` | 몸통 `{"key": "<options[].key>"}` 로 그 안을 적용, `{"key": null}` 이면 **원래 일정 유지**(`kept`) |

- 제안 한 건: `proposal_id` · `item_id` · `base_version` · `reason`(`ask_first` · `protected`) · `protected_by` · `safety` ·
  `expires_at`(= 그 일정 끝) · `causes` · `options[]`(`key` · `rank` · `name` · `starts_at`, 1순위가 우리 최적안).
- **먼저 고른 쪽이 이긴다** — 이미 정해졌으면 `409 already_decided`, 제안 뒤 판이 바뀌었으면 `409 stale`, 없는 제안은 `404`.
  거절 상세는 `error.detail` 아래에 있다. ★거절되면 **일정은 아무것도 바뀌지 않는다**(한 트랜잭션).
- ★`[2026-10-03 결함 인계]` **못 고르는 상태가 된 제안은 그 자리에서 닫는다.** 그 일정이 이미 끝났으면(`expires_at` 이 지났다 — 감시가 아직 못 닫았어도) `409 expired` + 제안 `expired`, 기준 버전이 낡았으면 `409 stale` + 제안 `superseded`. 닫은 기록은 남는다(전에는 열린 채 계속 보였다). 반대로 **고른 안이 지금 안 맞아**(재점검 불통과 · 모르는 안 키) 거절되면 제안은 **열린 채** 남는다 — 같은 제안에서 다른 안을 고를 수 있어야 하는 **의도**다.
- 답이 없으면 그 일정이 끝날 때 `expired` — **원래 일정대로 간다.** 닫는 일은 감시 반복이 한다(시나리오 감시와 Case 감시 둘 다).

## 웹(고객 브라우저) — `/v1/web/*` `[2026-09-24]`

`[실측]` `app/modules/travel_ops/trip_api.py` · 키 `app/modules/travel_ops/web_session.py` · 저장 `web_user_keys`(마이그레이션 025).
★서버용 scope 키(테넌트 전체)를 브라우저에 넣지 않는다. 웹은 **사용자 식별 키** 하나로 **그 사용자 본인의 여행만** 연다.

| 경로 | 인증 | 뜻 |
|---|---|---|
| `POST /v1/web/session` | 없음 | 첫 방문 — 사용자와 키를 만든다. 응답 `user_key` 는 **이번에만** 나온다 |
| `POST /v1/web/session/rotate` | 키 | 새 키. **옛 키는 바로 무효** |
| `GET /v1/web/trips` | 키 | 내 여행 목록 |
| `POST /v1/web/trips` | 키 | 등록 — `/v1/trips` 와 같은 몸통에서 **`customer_id` 를 빼고** 보낸다(보내면 `422 customer_id_not_allowed`, 키가 정한다) |
| `GET /v1/web/trips/{trip_id}` | 키 | 여행 조회 |
| `GET /v1/web/trips/{trip_id}/proposals` · `POST …/{proposal_id}/choose` | 키 | 위 보류 제안과 같은 규칙 |
| `POST /v1/web/trips/{trip_id}/messages` | 키 | 「에이전트에게 변경 요청」 — 자유 문장. `/v1/trips/{id}/messages` 와 같은 처리 (★`[2026-09-28]` 둘 다 **시나리오용 여행 버전**(`handle_trip_message`)이다 — `/v1/cases` 의 Case 버전과 답 코드가 두 벌이다. Case 버전으로 합칠 계획: `records/reports/2026-09-28_웹채팅이_시나리오용_여행버전을_탄다_리포트.md`) · ★`[2026-09-28]` **응답에 늘 `answer`(고객에게 보일 문장)가 있다** — 질문은 이 여행 일정의 사실 + 문턱(`travel.question.min_policy_score`)을 넘은 규정 조각(출처와 함께)으로 답하고 (`status: answered`, `reason: question_answered`, 근거 `basis{item, policy_hits, sources}`), ★`[2026-09-28 사용자 결정]` 규정 조각 **원문은 싣지 않고** 그 절에 써 둔 **고객용 문장**(`customer_answers`)만 싣는다. 찾지 못하면 무엇을 못 찾았는지 말하고 이 여행의 사실과 할 수 있는 요청으로 답한다(`answered`, `basis.unmatched: true`) — **사람 대기로 남기지 않는다**(사람 대기 `escalated` 는 규정 검색이 없거나 오류일 때만, `question_needs_policy_answer`). 잡담·모호한 말(`other`)은 할 수 있는 요청과 이 여행의 사실로 답한다(`answered`, `not_a_trip_report`). ★**이 여행의 사실을 묻는 말**(하루 요약 · 일정 상세 · 다음 일정 · 예약 표시 · 주소 · 운영시간 · 이동 — 화면 빠른 질문 문장 포함)은 규정 검색 없이 **여행 기록으로** 답한다(`answered`, `reason: trip_fact_answered`, `report: {type: question, fact: day|detail|next|booking|address|hours|move}`, `basis: {kind, writer: "template", day, item, lookups}`) — 모델 추출 전에 규칙으로 가리고, 바꾸는 말(바꿔·늦어·되돌려·닫았어요 …)이 섞이면 받지 않는다. ★`[2026-09-29]` **분류(모델)가 실패해도 이 답은 나간다** — `status: answered` · `reason: trip_fact_answered` · `classification_failed: true` · `case_status: escalated`(분류 실패는 그대로 기록, 모델 장애를 운영이 본다). ★웹 입구는 **분류를 기다리지 않는다** — 사실 질문이면 곧바로 답하고 `classification_pending: true`, 분류·담당·완료 기록은 응답 뒤에서 한다(식은 모델에서 34초 → 규칙 답만). 답은 Case 기록에 처음부터 실려 같은 요청을 다시 보내면 그 답이 나간다. 에이전트 입구(`/v1/trips/{id}/messages`)는 지금처럼 분류까지 기다린다. 전에는 잠든 원격 모델의 느린 첫 호출로 분류가 실패하면 「하루 요약」까지 「분류하지 못했어요」로 끝났다. 주소·운영시간은 저장하지 않고 물을 때 관광공사 상세를 읽어 **원문 그대로** 싣는다(6시간 캐시, 못 읽으면 `lookups.failed` 와 「모르겠어요」). 예약은 `booking_id`·`detail.booking`·`detail.reserved` 가 있으면 「있음」, 없으면 「예약 기록 없음」(안 했다는 뜻이 아니다). 규정 질문의 검색 갈래에 `travel_cancellation`·`travel_mobility` 를 더했다(전에는 빠져 있었다). 못 알아들은 말·분류 실패도 그 이유와 할 수 있는 요청을 싣는다. 중복 요청은 앞 답을 다시 싣는다. **어느 경우에도 일정은 바꾸지 않는다**(변경은 늦음·휴무·되돌리기 등 신고만) |
| `POST /v1/web/trips/{trip_id}/reports` · `POST …/items/{item_id}/alternate` | 키 | ★`[2026-10-02]` 에이전트 입구(`/v1/trips/{id}/reports` · `…/alternate`)와 **같은 처리**(신고 지연·휴무·품절 · 다른 안으로 — 요청 몸통도 같다), **그 사용자 본인의 여행만**(남의 것 404). 모델을 안 거치는 구조화 입구다 — 개인 AI(MCP)가 쓴다([MCP 도구](mcp-tools.md)). 남용 방어는 채팅과 같은 `message` 로 센다 |
| `POST /v1/web/warmup` | 키 | ★`[2026-09-29]` **모델 예열** — 화면이 여행·채팅 칸을 열 때 부른다(식은 모델의 첫 채팅이 34초 걸렸다). 몸통 없음. 응답 `{status: "warm" \| "warming" \| "unavailable", model, last_attempt: null \| {ok, seconds, at, reason?}, deduped?}` — 이미 올라가 있으면 `warm`(아무것도 안 함), 1분(`web_guard.warmup.dedupe_seconds`) 안 되풀이는 `warming` + `deduped: true`(다시 안 부름), 그 밖엔 응답 뒤 한 토큰 생성으로 깨우고 `warming`. **`last_attempt.ok=false` 면 모델 서버가 못 올린 것**(`reason` 에 서버가 준 이유 — 예: GPU 메모리 부족). 실제로 부를 때만 남용 방어 `warmup` 으로 센다(한도가 켜져 있으면 429/503) |
| `GET /v1/web/trips/{trip_id}/notices` | 키 | 나간 알림 전부. `type` = `guidance`(하루 시작·다음 일정·이동) · `proposal_request` · `safety_alert` · `change_notice` |

- ★`[2026-10-04]` **브라우저는 키 대신 쿠키 세션을 쓴다** — 아래 「브라우저 세션 쿠키」. 이 절의 `키` 칸은 **쿠키 세션 또는 키**로 읽는다(둘이 같이 오면 `400 ambiguous_credentials`). `X-User-Key` 는 에이전트(MCP)와 옮겨 가는 동안의 옛 호출자용이다.
- 키는 헤더 **`X-User-Key`** 로 보낸다. 형식 `acop_u_…`. 없거나 틀리거나 거둔 키는 모두 `401`(어느 쪽인지 말하지 않는다).
- **남의 여행은 `404`** — 있는지도 말하지 않는다. 서버용 scope 키로는 웹 경로가 열리지 않는다(`401`).
- 서버는 키 원문을 저장하지 않는다(SHA-256 만). 웹은 키를 브라우저 저장소에 두고, 사용자에게 **따로 보관하라고 한 번 보여 준다.**
  브라우저 저장소는 그 페이지의 모든 스크립트가 읽을 수 있으므로 **새는 것을 전제로** 두고, 새면 `rotate` 로 끊는다.
- 브라우저 출처는 설정 `ACOP_WEB_ALLOWED_ORIGINS`(쉼표로 여럿, 기본 `http://127.0.0.1:3100,http://localhost:3100`)만 받는다.
- 키 없이 열린 `POST /v1/web/session` 은 **주소마다 한 시간에 20개**까지(`security.web_session_issue_per_hour`,
  운영 API 로 바꿀 수 있다 — 아래). 넘으면 `429 too_many_sessions` + `Retry-After`(다음 정시까지 초). 이미 가진 키로 하는 일은 막지 않는다.
  ★`[2026-09-28]` **DB 에서 센다**(`web_usage`, 마이그레이션 031) — 재시작·여러 프로세스에도 이어진다. 주소는 원문이 아니라
  `HMAC(서버 비밀키, 날짜|주소)` 로만 남고 48시간 뒤 지운다. 역방향 프록시 뒤라면 설정 `ACOP_TRUSTED_PROXIES`(쉼표)에 적힌
  주소에서 온 요청만 `X-Forwarded-For` 의 원 주소를 믿는다(비어 있으면 연결 주소).

### 남용 방어 — 횟수 제한 · 사람 확인 `[2026-09-28]`

`[실측]` `app/modules/travel_ops/web_guard.py` · `web_limits_api.py` · `app/infrastructure/turnstile.py` · 저장 `web_usage` ·
`runtime_limits` · `runtime_limit_events`(마이그레이션 031). 계획 `records/plans/2026-09-28_2130_웹_남용방어_실행계획.md`.

**비싼 작업 횟수 제한.** 대상 — `POST /v1/web/trip-intakes`(`intake`) · `…/{id}/plan`(`plan`) · `…/{id}/confirm`(`confirm`) ·
`POST /v1/web/trips`(`trip_create`) · `POST /v1/web/trips/{id}/messages`(`message`). 키(사용자)당 · 주소당 · 서비스 전체의 **하루**(KST) 횟수.
- ★**기본 꺼짐**(`web_guard.limits_enabled: false` — 개발 단계, 사용자 결정 2026-09-28). 꺼져 있어도 **세기는 한다**(운영 API 의 오늘 사용량).
- 켜지면 입력 검사를 통과한 뒤 · 일을 시작하기 전에 한 칸을 확보한다. 일이 실패해도 한 번으로 센다.
- 키·주소 한도 → `429 usage_limit` + `Retry-After`(다음 KST 자정까지 초), 본문 `{limit: per_key|per_ip, action, used, cap, retry_after_seconds}`.
- 서비스 전체 한도 → `503 service_daily_cap` + `Retry-After`. 사용자 잘못이 아니라 가른다.
- 제안 기본값과 산정 근거는 `config/guardrails.yaml` `web_guard.limits` 주석(전부 `[추정]`).

**사람 확인(Cloudflare Turnstile).** `POST /v1/web/session`(헤더 `X-Turnstile-Token` 또는 JSON `{"turnstile_token"}`) ·
`POST /v1/web/trip-intakes`(폼 칸 `turnstile_token`). 서버가 `siteverify` 에 비밀키·토큰·원 주소를 보내 확인한다.
- 설정 `ACOP_TURNSTILE_SECRET` 이 있으면 **늘 확인한다.** 토큰이 없거나 실패 → `403 human_check_failed`(`reasons` = Cloudflare `error-codes`).
  Cloudflare 에 닿지 못하면 → `503 human_check_unavailable`(통과시키지 않는다). `ACOP_TURNSTILE_HOSTNAMES`(쉼표)를 두면 `hostname` 도 본다.
- 비밀키가 없으면: `ACOP_TURNSTILE_REQUIRED=true` 또는 `ACOP_ENV=prod` 면 **서버가 뜨지 않는다**. 아니면(개발) 확인을 건너뛰고
  응답에 `human_check: "skipped"` 를 싣는다. 확인했으면 `human_check: "passed"`.
- 개발 시험 키(Cloudflare 공개, `[확인 2026-09-28]` developers.cloudflare.com/turnstile/troubleshooting/testing): 비밀키
  `1x0000000000000000000000000000000AA` 항상 통과 · `2x0000000000000000000000000000000AA` 항상 실패 ·
  `3x0000000000000000000000000000000AA` 「이미 쓴 토큰」. 시험 사이트키는 토큰 `XXXX.DUMMY.TOKEN.XXXX` 를 낸다.
  토큰은 5분 유효 · 한 번만 확인된다 · 최대 2,048자.

**빈 키 정리 — `[2026-10-04]` 걷었다.** 옛 규칙(여행 0건인 키만 · 기본 꺼짐 — 2026-09-29 「키는 그 사용자를 알아보는 유일한 수단이라 지우지 않는다」)을 **게스트 정리**가 대신한다 — 아래 「게스트 · 여행 삭제 · 게스트 정리」. 같은 되잡기 단계가 48시간 지난 주소 줄과 35일 지난 사용량 줄도 지운다.

**운영 API — 제한값 보기·바꾸기.** ★`[2026-09-29]` **운영 앱**(127.0.0.1:8070, [D-CS-008](../decisions/D-CS-008-ops-console-separate-app.md))에 있다 — 고객 API 앱(8042)에는 없다(404). 바꾼 값은 DB 라 고객 앱이 30초 안에 읽는다. scope `limits:read`(보기) · `limits:write`(바꾸기). ★scope 키를 브라우저에 두지 않는다 —
운영자 로그인을 확인한 **콘솔 서버**가 부르고 `actor`(운영자 id)를 싣는다. API 는 그 값을 믿는다(한계 — 감사 줄에 키 id 도 남긴다).

```
GET   /admin/limits                      scope limits:read
  200 {"revision": 3, "applies_within_seconds": 30,
       "limits": [{"name": "web.intake.per_key_day", "label": "…", "unit": "회", "type": "int",
                   "value": 4, "default": 4, "min": 1, "max": 100000,
                   "source": "default"|"override", "updated_at": null|"…", "updated_by": null|"…"}, …],
       "usage_today": {"day": "2026-09-28", "all": {"intake": 3, "plan": 1, …}}}   // 키·주소별은 싣지 않는다

PATCH /admin/limits                      scope limits:write
  요청 {"expected_revision": 3, "actor": "운영자 id", "reason": "…(필수)",
        "changes": {"web.limits_enabled": true, "web.plan.per_key_day": null}}      // null = 기본값으로
  200 GET 과 같은 모양(revision + 1)
  409 stale_revision {current_revision} · 422 unknown_limit | out_of_range | wrong_type | reason_required | actor_required
  401/403 scope

GET   /admin/limits/events?limit=50      scope limits:read
  200 {"events": [{"at", "revision", "actor", "key_id", "name", "old", "new", "reason"}, …]}   // 새것부터
```
- 이름: `web.limits_enabled` · `web.<intake|plan|confirm|trip_create|message|warmup>.<per_key_day|per_ip_day|service_day>` ·
  `web.session.per_ip_hour` · `web.guest_idle_hours` · `web.member_idle_hours` · `web.session_max_hours` · `web.guest_cleanup_enabled`(★`[2026-10-04]` 옛 `web.idle_key_*` 를 대신한다). 기본값·범위는 가드레일, 바꾼 값은 `runtime_limits`.
- 바꾼 값은 각 프로세스가 최대 30초 캐시해 늦게 반영된다(`applies_within_seconds`). 감사 줄(`runtime_limit_events`)은 고치지도 지우지도 못한다(트리거).
- 시험 `tests/e2e/test_web_api.py` 10건.

### 소셜 로그인 — `/v1/web/auth/*` `[2026-10-03]` (구글 먼저)

`[실측]` 구현 `app/modules/travel_ops/web_auth_api.py`(HTTP) · `web_auth.py`(저장 · 규칙) · `app/infrastructure/oauth_providers.py`(업체와 말하기) · 저장 마이그레이션 043 · 시험 `tests/e2e/test_web_social_login.py`(17) ·
`tests/unit/travel/test_oauth_providers.py`(15). 계약의 출처는 ui 세션의 [백엔드 요청서](../records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md)이고 웹 화면은 이 모양 그대로 연결돼 있다. 설정 · 콘솔 절차는 [google-login-setup.md](../operations/google-login-setup.md).
★**소셜 로그인은 「키를 받아 오는 또 하나의 길」이다** — 키와 모든 `/v1/web/*` 인증(`X-User-Key`)은 바뀌지 않는다. 계정을 사용자에 **붙여** 두면 키를 잃어도 · 새 기기에서도 그 계정으로 같은 사용자의 여행을 연다.

| 경로 | 키 | 뜻 |
|---|---|---|
| `GET /v1/web/auth/providers` | 없음 | `{providers: [{id}]}` — **설정이 끝난 업체만**(클라이언트 ID · 비밀값이 둘 다 있어야 한다). 하나도 없으면 **빈 목록**(404 가 아니다) |
| `POST /v1/web/auth/{provider}/start` | `link` 만 필수 | `{mode: login\|link, client_nonce(무작위 32~256자), turnstile_token?}` → `{authorize_url}`. 업체 없음 404 `provider_not_enabled` · nonce 짧음 422 `invalid_client_nonce` · `link` 에 키 없음 401 · **키 없는 `login` 은 사람 확인**(Turnstile — 토큰 없으면 422 `human_check_required`, 틀리면 403, 머리말 `X-Turnstile-Token` 도 받는다 · 비밀키가 없는 개발 환경은 건너뛴다) |
| `GET /v1/web/auth/{provider}/callback?code&state` | — | **브라우저 이동 전용** — 업체가 돌려보내는 곳. 어떤 결과든 **웹으로 302**: `{웹 주소}/auth/done?ticket=…` 또는 `?error=` (`cancelled` 고객이 취소 · `denied` 업체가 거절 · `already_linked_elsewhere` · `failed` 그 밖 전부). 머리말 `Cache-Control: no-store` · `Referrer-Policy: no-referrer` |
| `POST /v1/web/auth/exchange` | 없음 | `{ticket, client_nonce}` → `{outcome: signed_in\|created\|linked, provider, trips, user_key?, notice?}`. `signed_in` · `created` 일 때만 `user_key`(**이 기기용 새 키**). 만료 · 재사용 · nonce 불일치 · 모르는 표는 모두 410 `ticket_invalid`(어느 쪽인지 가르지 않는다) |
| `GET /v1/web/auth/links` | 키 | `{links: [{provider, linked_at}]}` — 계정 이름 · 이메일은 없다 |
| `DELETE /v1/web/auth/{provider}` | 키 | 연결 해제(키와 여행은 그대로) → 200 `{links}`(남은 연결). 안 붙어 있으면 404 `not_linked` |

- **한 바퀴**: `start`(시작 기록 저장) → 업체 로그인 화면 → `callback`(`state` 를 한 번만 꺼내 코드를 고유 번호로 바꾸고 연결 · 일회용 표) → `exchange`(표를 한 번만 받고 키 발급).
- ★**`user_key` 는 「현재 유효한 키」가 아니라 이 기기용 새 키다** `[계약 보정]` — 키 원문은 해시로만 저장돼 다시 돌려줄 수 없다. 옛 키를 거두면(`rotate`) 다른 기기가 끊기므로 키를 **하나 더한다**(`web_session.add_key`). 한 사용자의 유효한 키는 `security.web_auth_keys_per_user`(10)개까지 — 넘으면 가장 오래된 키부터 거둔다.
- **보안**: ①로그인 CSRF 막기 — 표는 시작한 브라우저가 만든 `client_nonce` 의 해시와 같이 저장되고 교환할 때 같은 값이 와야 한다(틀린 시도는 표를 태우지 않는다) ②`state` · PKCE(`S256`) · OIDC `nonce` — `state` 는 서버가 만들고 해시만 저장, 한 번만 · 10분(`security.web_auth_state_seconds`), 표는 60초(`web_auth_ticket_seconds`)
  ③**ID 토큰은 업체 공개키(JWKS)로 서명 · 발급자 · 대상 · 만료 · nonce 를 모두 확인**한다(RS256 만 — 다른 알고리즘 · 서명 없는 토큰 거절) ④돌려보낼 웹 주소는 **서버 설정**(`ACOP_WEB_ORIGIN`, 비면 `ACOP_WEB_ALLOWED_ORIGINS` 의 첫 값 — 없으면 콜백이 503 `web_origin_not_configured`)이고 요청 값(`return_to` 등)으로 바꿀 수 없다
  ⑤저장은 업체 이름과 `sub` 의 **HMAC 해시**(`secret_key` 로)뿐 — 이메일 · 이름 · 사진은 요청도 저장도 안 한다(스코프 `openid`) ⑥한 업체 계정은 **한 사용자에게만** — 다른 사용자에게 있으면 `link` 는 `already_linked_elsewhere`, **합치지 않는다** ⑦`start` · `exchange` 는 주소당 한 시간 `security.web_auth_per_ip_hour`(30)번씩(**늘 켜져 있다**, 429 `too_many_auth` + `Retry-After`) ⑧키 없는 `login` 이 새 사용자를 만들 때는 키 발급과 같은 한도(`too_many_sessions`)를 거친다 — 걸리면 `?error=failed`.
- 계정이 붙은 사용자는 **회원**이라 게스트 정리가 지우지 않는다(시험으로 확인). CORS 는 `DELETE` 를 연다(웹이 다른 출처일 때 연결 해제).
- `[미확보]` ①실제 구글과 이어 본 기록 — 클라이언트 ID · 비밀값이 있어야 한다(없으면 `providers` 가 빈 목록) ②카카오 · 네이버 · 디스코드는 구현하지 않았다(`oauth_providers.configured()` 에 업체 한 줄 + 설정 칸이다 — 카카오 · 네이버가 OIDC `sub` 를 주는 설정이 우리 앱 종류에서 되는지는 확인 전) ③운영 배포 주소 — 콜백 주소 등록에 필요하다.

### 브라우저 세션 쿠키 — `/v1/web/auth/session*` `[결정 2026-10-04 사용자]`

`[실측]` 시험 `tests/e2e/test_web_cookie_session.py`(27) · 결정 기록 [D-CS-011](../decisions/D-CS-011-browser-session-cookie.md). 구현 `app/modules/travel_ops/web_cookie.py`(저장 · 규칙) · `web_auth_api.py`(HTTP) · 저장 마이그레이션 044 `web_sessions`.
★**브라우저는 키를 저장소에 두지 않는다.** 로그인 상태는 서버가 내려주는 **HttpOnly 쿠키 하나**다 — 페이지의 스크립트(지도 SDK · 확장 · XSS)가 읽지 못한다. 키(`X-User-Key`)는 **에이전트(MCP)와 옛 호출자용**으로 남는다(웹이 옮겨 가는 동안 둘 다 받는다).
★「로그인하면 다시 인증하면 되니 토큰을 오래 들고 있을 이유가 없다 · 로그인 안 한 게스트는 세션을 잃어도 받아들인다」가 사용자 결정이다 — 복구 수단은 없다.

| 경로 | 인증 | 뜻 |
|---|---|---|
| `POST /v1/web/auth/session` | 쿠키 없음 | 게스트 세션을 만든다 → `201` + `Set-Cookie`. 이미 유효한 쿠키가 있으면 새로 안 만들고 현재 세션을 `200` 으로 돌려준다. **사람 확인(Turnstile)과 주소당 한 시간 발급 한도는 `POST /v1/web/session` 과 같다**(`human_check_required` 422 · `too_many_sessions` 429) |
| `POST /v1/web/auth/adopt` | `X-User-Key` 만(쿠키 없음) | 옛 키 사용자를 **쿠키 세션으로 옮긴다** → `201` + `Set-Cookie`. 키는 거두지 않는다(에이전트가 쓸 수 있다). 웹은 성공하면 저장소의 키를 지운다. 틀린 키 `401` · 주소당 한 시간 한도(`too_many_auth`) |
| `GET /v1/web/auth/me` | 쿠키 | 현재 세션 — `{kind: guest\|member, csrf_token, idle_expires_at, absolute_expires_at, guest_idle_hours?}`. `guest_idle_hours` 는 게스트일 때만(화면이 「이 기기에서 N시간 안 쓰면 사라져요」를 보이게). 쿠키가 없거나 만료면 `401 unauthenticated` |
| `POST /v1/web/auth/logout` | 쿠키 + CSRF | 서버의 세션 행을 거두고 쿠키를 지운다 → `200 {status: "signed_out"}`. 게스트가 로그아웃하면 그 여행은 다시 열 수 없다(보존 시간이 지나면 지워진다) |
| `POST /v1/web/auth/exchange` **(확장)** | 없음 | 몸통에 `session: "cookie"` 를 더하면 `signed_in` · `created` 일 때 **키 대신 쿠키 세션**을 준다(`Set-Cookie`, 응답에 `user_key` 없음, `kind: "member"` · `csrf_token` 가 실린다). 요청에 게스트 쿠키가 함께 오면 그 세션은 **거두고** 새로 발급한다(세션 고정 공격 방지). 몸통에 없거나 `"key"` 면 지금까지처럼 `user_key` 를 준다 |

**쿠키.** 값은 무작위 256비트(서버에는 SHA-256 해시만). 운영(공개 주소가 `https`) = 이름 `__Host-tripilot_sid` · `Secure` · `HttpOnly` · `SameSite=Lax` · `Path=/` · **`Domain` 없음**. 개발(`http`) = 이름 `tripilot_sid_dev` · `Secure` 없음 — 나머지 같다(`__Host-` 는 `Secure` 가 있어야 한다). `Max-Age` = 절대 수명 — ★`[2026-10-04 사용자 결정]` **게스트 쿠키에는 `Max-Age` 가 없다**(브라우저 세션 쿠키 — 브라우저를 닫으면 브라우저가 지운다. ChatGPT 로그아웃 상태와 같은 모양). 회원 쿠키만 `Max-Age`(절대 수명)가 있다. 게스트가 구글 계정을 `link` 하면 `exchange`(`session:"cookie"`) 응답이 **같은 쿠키 값을 `Max-Age` 와 함께 다시** 내리고 몸통은 `kind: member`. 이름·`Secure` 여부는 `ACOP_PUBLIC_BASE_URL` 이 정한다.
`SameSite=Lax` 인 까닭: 구글 로그인에서 돌아오는 첫 이동에 `Strict` 쿠키가 안 붙는다(제안 — 조사 합의).

**누구인지 가르는 순서**(`/v1/web/*` 전부 — 한 곳에서). ① 쿠키와 `X-User-Key` 가 **같이 오면 `400 ambiguous_credentials`**(조용히 고르지 않는다) ② 쿠키만 → 세션 행을 찾아 **유휴·절대 수명**을 확인(만료·거둠·없음은 모두 `401 unauthenticated` + 쿠키 삭제 `Set-Cookie`) ③ 키만 → 지금까지처럼(CSRF 면제 — 브라우저가 자동으로 붙이지 않는다) ④ 둘 다 없으면 `401`.
**수명**(운영 API 로 바꾼다 — 아래 이름): 유휴 = 마지막 사용 뒤 — 게스트 `web.guest_idle_hours`, 회원(소셜 계정을 붙인 사용자) `web.member_idle_hours`; 절대 = 만든 뒤 `web.session_max_hours`. 만료 판단은 **쓸 때** 한다(바꾼 값이 곧 적용 · 30초 캐시). 「마지막 사용」은 세션이 인증한 요청이다 — **계획서 링크 열람 · 자동 감시 · 외부 호출은 사용으로 세지 않는다.** 마지막 사용은 `web.session_touch_seconds`(기본 60초)보다 잦게 쓰지 않는다.

**CSRF**(쿠키로 인증된 **쓰기** 요청 `POST·PUT·PATCH·DELETE` 만 — 읽기는 면제). 둘 다 통과해야 한다: ①`Origin` 이 허용 출처(`ACOP_WEB_ALLOWED_ORIGINS` · `ACOP_WEB_ORIGIN`)여야 한다 — 없으면 `Sec-Fetch-Site` 가 `same-origin`/`same-site` 여야 한다 ②헤더 `X-CSRF-Token` 이 그 세션의 토큰과 같아야 한다(`HMAC-SHA256(서버 비밀, "csrf|" + 세션 해시)` — 저장하지 않고 다시 계산, 상수 시간 비교). 토큰은 `session`·`adopt`·`me`·`exchange` 응답에 실린다(웹은 **메모리에만** 둔다). 어긋나면 `403 csrf_failed`. `GET` 으로는 상태를 바꾸지 않는다.
**CORS.** `allow_credentials=true` — 출처는 허용 목록 그대로(와일드카드 불가), 허용 머리말에 `X-CSRF-Token` 을 더한다. 웹은 모든 호출에 `credentials: "include"` 를 붙인다(개발의 `127.0.0.1:3100 ↔ :8042` 는 **출처는 다르지만 같은 사이트**라 쿠키가 간다 — `localhost` 와 `127.0.0.1` 을 섞지 않는다).

- 세션의 종류(`kind`)는 **쓸 때 계산한다**: 소셜 계정이 하나라도 붙어 있으면 `member`, 아니면 `guest` — 게스트가 소셜 계정을 `link` 하면 같은 세션이 다음 요청부터 회원 수명을 받는다(여행도 그대로).
- 소셜 `link` 시작 · `GET /v1/web/auth/links` · `DELETE /v1/web/auth/{provider}` 도 쿠키로 열린다(CSRF 규칙 그대로).
- ★한계: HttpOnly 는 **자격을 읽히지 않게** 할 뿐, 페이지에 악성 스크립트가 있으면 그 스크립트가 사용자 대신 요청을 보내는 것(세션 라이딩)은 막지 못한다. 훔친 쿠키를 다른 기기에서 쓰는 것도 만료·거둠까지는 막지 못한다 — Chrome 의 기기 묶음 세션(DBSC)은 그 위에 나중에 얹는 보강이다(`[미확보]` Safari·Firefox 미지원, 2026-10-04 조사).

### 게스트(로그인 안 한 사용자) · 여행 삭제 · 게스트 정리 `[결정 2026-10-04 사용자]`

`[실측]` 구현 `app/modules/travel_ops/guest_policy.py`(제한) · `trip_delete.py`(삭제) · `guest_cleanup.py`(정리) · `itinerary.py`(감시 · 안내 대상에서 게스트 제외) · 시험 `tests/e2e/test_guest_and_trip_delete.py`(16). 결정 [D-CS-011](../decisions/D-CS-011-browser-session-cookie.md) — **보존 시간 초기값의 공식과 근거도 거기 있다.**
★**게스트 = 웹으로 만든 사용자(`customers.external_id` 가 `web:` 로 시작) 중 소셜 계정이 하나도 안 붙은 사용자.** 소셜 계정을 `link` 하면 그 순간부터 회원이다(여행도 그대로). 에이전트 API 로 만든 고객과 시드는 게스트가 아니다.

| | 게스트 | 회원 |
|---|---|---|
| 여행 | **1개**(`web_guard.guest.max_trips`) — 사용자 행을 잠가 **동시 생성까지** 막는다. 넘으면 `403 guest_trip_limit` + 본문 `login_required: true` · `cap` · `existing` | 제한 없음 |
| 여행 기간 | 시작은 오늘부터 **365일 안**(`403 guest_trip_too_far`), 길이는 **7일 안**(`403 guest_trip_too_long`) | 제한 없음 |
| 감시 · 일정 안내 | **안 한다**(`active_trip_ids` · `due` 에서 뺀다 — 외부 호출 비용) | 한다 |
| 세션 유휴 수명 | `web.guest_idle_hours`(기본 **168시간**) | `web.member_idle_hours`(기본 168시간) |
| 마지막 사용 뒤 데이터 | 아래 「게스트 정리」로 지운다 | 안 지운다 |
| 에이전트 키 | 없다(2단계 — 로그인 사용자만) | 있다(2단계) |

`403 guest_*` 는 모두 본문 `{"error": {"code", "message", "login_required": true, …}}` 이다 — 화면이 「로그인하면 더 만들 수 있어요」를 보인다.

**`POST /v1/web/trips/{trip_id}/delete`** — 쿠키 세션 또는 키(웹 쓰기는 CSRF). 몸통 없음.
```
200 {"trip_id": "...", "status": "deleted"}
404 {"error": {"code": "not_found", "message": "resource not found"}}   ← 남의 여행 · 없는 여행 · 이미 지운 여행(있는지도 말하지 않는다 · 두 번째 호출도 404)
401 unauthenticated · 403 csrf_failed
```
- **즉시 완전 삭제**(숨김 · 유예 없음). **한 트랜잭션**이고 `trips` 행을 잠근다. `trips` 를 지우면 `itinerary_versions` · `itinerary_items` · `pending_changes` 가 CASCADE 로 사라진다.
- **외래키가 없어 이름을 대어 지우는 표**: `trip_chat_turns` · `place_open_checks` · `dining.dn_notice` · `trip_intakes`(그 여행 것만, 자식 `intake_*` 는 CASCADE) · `places.trip_scope`(이 여행 전용 장소 행 — 외부 값이라 다른 고객에게 재사용하면 안 된다) · 바깥함 `trip.notice`(`dedupe_key` 가 `{trip_id}:` 로 시작 — 알림 문장에 일정이 실려 있어 **대기분만이 아니라 전부**). `trip_id` 가 NULL 인 옛 행은 고객 번호만으로 지우지 않는다. 새 표가 여행 번호 칸을 들고 생기면 걸리는 목록 시험이 있다.
- **운영 쪽은 지우지도 가리지도 않는다**: `case_events` 는 append-only. 그 여행을 가리키는 **열린 Case**(`state_json.subject_ref.id`)는 전이표가 허용하는 **정상 전이만으로 `cancelled` 까지 닫는다**(가장 짧은 길 · 이유 `trip_deleted` · 행위자 `trip_delete`) — ★`resolved`/`completed` 를 거치지 않는다(안 한 일을 끝냈다고 기록하게 된다): `running` → `guardrail_escalated` → `escalated` → `cancelled_by_user`. 해결된 Case 는 기록이라 그대로다.
- ★`[2026-10-04 사용자 결정]` **계획서 내려받기** — `GET /plan/{trip_id}?t=…&download=1` 은 같은 페이지를 `Content-Disposition: attachment`(파일 이름 `triPilot-<제목>.html`, 경로 글자 제외)로 준다. 로그인 없음 · 링크가 곧 자격 · 틀린 토큰은 404. 이 HTML 은 외부 파일 없이 혼자 열린다(밖으로 나가는 것은 지도 링크뿐). 게스트 데이터는 보존 시간 뒤 지워지니 **파일로 가져가게 하는 것**이 게스트의 보관 수단이다.
- 계획서 링크는 토큰 행이 없어(HMAC) 여행이 사라지면 조회에서 404 다. ★`[미구현]` **「만료됨」 안내 화면**(삭제된 여행의 유효한 옛 링크에만, 틀린 링크는 404)은 만들지 않았다 — 지금은 404 다. 흔적 한 줄을 남겨야 해서 따로 정한다([open-items](../delivery/open-items.md)).
- ★`[미구현]` ①MCP 삭제 도구(`travel.mcp.write_enabled` 뒤) ②바깥함이 **보내기 직전**에 여행이 아직 있는지 다시 보는 것(삭제와 겹친 알림이 이미 밖으로 나가는 경우는 회수되지 않는다) — 요청서 구현 지침 4 · 7. ③`case_events.payload_json` 에 마스킹 안 된 고객 문장이 없는지 DB 에서 세어 보는 것(지침 8).

**게스트 정리** — 되잡기 작업(`python -m scripts.run_sweepers --only web_guard`)이 한다. 옛 「빈 키 정리」(`idle_key_*`, 2026-09-28 · 여행 0건인 키만 · 기본 꺼짐)를 **이것이 대신한다**(설정 `web.idle_key_days` · `web.idle_key_cleanup_enabled` 는 걷었다).
- 대상: 게스트. 「마지막 사용」 = 사용자 행 생성 · 키의 발급/사용 · 세션의 마지막 사용 중 **가장 늦은 때**(계획서 링크 열람 · 자동 감시 · 외부 호출은 사용이 아니다).
- 지우는 때: 마지막 사용 + `web.guest_idle_hours` 뒤. **일정이 남은 게스트**는 `min(마지막 일정 종료, 마지막 사용 + web_guard.guest.trip_keep_max_days(180일)) + web_guard.guest.trip_grace_days(3일)` 까지 둔다 — 세션은 끝났어도 계획서 링크와 알림이 그때까지 산다. 상한이 「지금」이 아니라 「마지막 사용」 기준이라 날짜를 빌미로 영구히 남지 않는다. 일정 종료가 비면 시작 시각을 종료로 본다.
- 사용자마다 따로 한 트랜잭션: 여행(위 삭제와 **같은 함수**) · 접수 · 세션 · 키 · 사용자 행(프로필은 CASCADE). 사용자 행을 가리키는 외래키 14개 중 13개가 「가리키면 거부」(서버 DB 조회 2026-10-04) — **Case 같은 기록이 가리키면 사용자 행 한 줄만 남긴다**(이메일 · 이름 없는 무작위 `web:` 번호). 결과 `{candidates, held_for_trips, customers_deleted, customers_kept, trips_deleted}`.
- 꺼져 있으면(`web.guest_cleanup_enabled`) `{"skipped": "disabled"}` — 아무것도 안 지운다. **복구 수단이 없어 삭제 전 유예(소프트 삭제)도 없다.**
- **관리 콘솔에서 조절**(운영 API `/admin/limits` — 위): `web.guest_idle_hours` · `web.member_idle_hours` · `web.session_max_hours`(시간, 1~8760) · `web.guest_cleanup_enabled`. 바꾼 값은 30초 안에 적용된다(세션 수명은 쓸 때 계산해 이미 만든 세션에도 곧 적용).

### 에이전트 키 — `/v1/web/agent-keys*` `[결정 2026-10-04 사용자 — D-CS-012]`

`[실측]` 시험 `tests/e2e/test_web_agent_keys.py`(12) · 결정 기록 [D-CS-012](../decisions/D-CS-012-agent-auth-claude-style.md) · 구현 `app/modules/travel_ops/web_agent_keys.py`(저장 · 규칙) · `web_agent_keys_api.py`(HTTP) · 저장 마이그레이션 045 `web_agent_keys`. 개인 AI(MCP · 사용자 API)가 **본인 여행의 작업만** 하는 문이다. 쿠키는 브라우저 전용이라 에이전트는 키를 헤더로 보낸다.
★**만드는 것은 로그인한 사용자(회원)가 브라우저(쿠키 세션)에서만** 한다 — 에이전트 키 · 옛 사용자 키로는 못 만들고(`403 cookie_required`), 게스트는 못 만든다(`403 member_only` + `login_required: true`).

| 경로 | 인증 | 뜻 |
|---|---|---|
| `GET /v1/web/agent-keys` | 쿠키(회원) | `{keys: [{key_id, name, scope, created_at, expires_at, last_used_at, status}]}` — `status` = `active` · `expired` · `revoked`. 키 원문은 없다 |
| `POST /v1/web/agent-keys` | 쿠키(회원) + CSRF | 몸통 `{name(1~60자), scope: "read"\|"write", expires_days?(1~90, 기본 90)}` → `201 {key_id, name, scope, created_at, expires_at, key, notice}`. ★`key`(`acop_a_…`)는 **이 응답에만** 나온다(서버엔 SHA-256 해시만). 활성 키가 `security.web_agent_keys_per_user`(10)개면 `409 agent_key_limit` |
| `DELETE /v1/web/agent-keys/{key_id}` | 쿠키(회원) + CSRF | 폐기 → `200 {key_id, status: "revoked"}`. 남의 키 · 없는 키는 같은 `404 not_found` |

**키를 쓰는 법**: 머리말 `Authorization: Bearer acop_a_…` 또는 `X-User-Key: acop_a_…`(MCP `/mcp/` 도 같다 — URL 에 키를 넣지 않는다). 없는 키 · **만료** · 폐기는 모두 같은 `401 unauthenticated`. 쿠키와 같이 오면 `400 ambiguous_credentials`. 서버용 scope 키(`require_scope`)를 `Bearer` 로 보내도 웹 경로는 안 열린다(`401`).
**권한**: ①`read` 키는 읽기(`GET`)만 — 쓰기 요청은 `403 agent_scope` ②어느 키든 **계정 관리 경로는 못 연다** — `/v1/web/auth/*` · `/v1/web/session*` · `/v1/web/profile*` · `/v1/web/agent-keys*` → `403 agent_forbidden` ③`write` 키의 쓰기 도구(MCP)는 `travel.mcp.write_enabled` 스위치가 켜져 있을 때만 등록된다(기본 꺼짐) ④마지막 소셜 연결을 해제하면 그 사용자의 에이전트 키를 **모두 거둔다**.
- 옛 사용자 키(`acop_u_…`, 만료 없음)는 그대로 둔다(웹이 쿠키로 옮겨 가는 동안) — 에이전트용으로는 새 키를 쓰게 안내한다.
- 2단계 OAuth(`/.well-known/*` · `/oauth/*`)는 [D-CS-012](../decisions/D-CS-012-agent-auth-claude-style.md) 에 설계만 있다 — 에이전트 키와 같은 검증 · 권한 판정으로 합칠 예정.

### 계획 읽기 — `/v1/web/trip-intakes` `[2026-09-27]`

`[실측]` `app/modules/travel_ops/intake/`(`pipeline.py` · `sources.py` · `rules.py` · `llm_spans.py` · `dates.py` · `places.py`) ·
저장 `trip_intakes` · `intake_sources` · `intake_claims`(마이그레이션 028). 설계 `../program/plan/A-COP_고객계획_읽기_설계_2026-09-26.md`.
★**모델은 위치만 가리키고 값은 원문과 조회가 낸다.** 값마다 방법(`rule` · `llm_span` · `lookup` · `customer`)과 근거가 붙는다.

| 경로 | 인증 | 뜻 |
|---|---|---|
| `POST /v1/web/trip-intakes` | 키 | 폼 — `text`(붙여 넣은 일정 · 채팅처럼 쓴 계획) + `files`(사진 · PDF · docx · xlsx, 종류는 **바이트로** 가린다). 곧바로 `202 {intake_id, status: reading}`, 읽기는 뒤에서 돈다(사진 한 장 ~45~60초). ★`[2026-09-30 사용자 결정 — ui 세션 전달]` **글 · 파일이 모두 비어도 거절하지 않는다** — 읽을 것이 없으니 뒤에서 읽지 않고 곧바로 `202 {status: review, stage: review}`(확인 화면 상태)다. 조회하면 `sources: []` · `check.plan.requested: false`(「짜 달라는 요청」 표시를 지어내지 않는다) · `check.ready: false` · 문제 `no_items` — 확인 화면의 「읽은 일정이 없어요 — 대신 짜 드릴까요?」 짜기 칸에서 `/plan` 으로 짜서 등록한다. 사람 확인 · 남용 방어 한도는 그대로(빈 접수도 한 건). ☆전에는 422 `empty_intake` 였다 |
| `GET /v1/web/trip-intakes/{intake_id}` | 키 | 단계 · 원본별 줄 번호 글(`lines[].read` = 읽은 줄) · 항목(`fields` 의 값마다 근거) · `reading`(남은 줄에 모델이 가리킨 결과 — 받은 수 · 버린 인용 · 장애) · `needs_review`. **남의 접수는 404** |
| `POST /v1/web/trip-intakes/{intake_id}/edits` | 키 | 확인 화면에서 고친 값 `{revision, edits:[{source_id, field, value}]}` → **새 판**(앞 판의 값은 남는다). 칸: `items[n].title·date·starts_at·ends_at·kind·place·booking_no·removed` · `trip.title·party_size·first_day`. 장소는 `{"name":…}` 로 받아 **다시 찾고**(못 찾으면 422 `place_not_found`), `{"none": true}` 는 「장소 없음」. 낡은 판은 **409 `stale_revision`** |
| `POST /v1/web/trip-intakes/{intake_id}/confirm` | 키 | 「등록하고 관리 시작」 `{revision, survey?}`. ★`survey`(선택, `TripSurvey` 판 `2026-09-24.v1`)는 등록 몸통의 `constraints.survey` 로 실려 여행에 남는다 — 틀리면 422 `invalid_survey`. 서버가 **다시 조립·판정**한 뒤 `_create_trip` 한 곳으로 등록 — `request_id = intake:{접수}:r{판}` 이라 두 번 눌러도 여행은 하나. 막으면 422 `intake_incomplete`(문제 목록) · 판정기의 422 그대로 |
| `POST /v1/web/trip-intakes/{intake_id}/plan` | 키 | 「일정 짜 줘」 `{revision, start_date, days(1~7), party_size(1~4), keep_read_items?, survey?}` — ★`survey` 는 생성기가 먼저 적용하고(16번 여유 → 하루 곳 수) 여행에 남는다(15번은 감시가 읽는다), 틀리면 422 `invalid_survey` — 원문 그대로를 선호로 일정 생성기(`planner.plan_trip`)가 짜고, **같은 판정**을 지난 초안을 `_create_trip` 으로 등록. `request_id = intake:{접수}:plan:r{판}` — 다시 눌러도 모델을 안 부르고 같은 여행. 못 짜면 422(이유·완화 조건). ★`keep_read_items`(기본 true) — 읽은 일정은 **옮기지도 바꾸지도 않고** 빈 시간만 채운다(`planner.plan_around`: 겹치거나 앞뒤 30분에 걸린 짠 항목 · 같은 때 식사를 빼고, 이동 자리가 모자라면 고정 일정을 밀지 않고 그 앞의 짠 항목을 뺀다. 읽은 장소는 후보에서 뺀다 — ★`[2026-10-01]` 이름이 정확히 같은 것만이 아니라 **같은 곳**(같은 주소 · 30 m 안 · 이름 첫 낱말이 같고 1.5 km 안)이면 다른 이름이어도 뺀다. 고객이 쓴 「경복궁 건청궁」을 고정했는데 생성기가 「경복궁」을 따로 넣던 것을 막는다. 식당은 같은 건물에 다른 가게가 흔해 이 비교에서 뺀다). 읽은 일정이 고른 날짜 밖이면 422 `read_items_outside_days`. false 면 읽은 일정 없이 새로 짠다 |

읽는 순서(원본마다): 규칙 → **남은 줄만** 모델에 보내 원문 조각을 인용하게 함(원문에 글자 그대로 없는 인용은 버린다) →
날짜(적힌 날짜 > 일차 > 상대 날짜, 해가 없으면 다가오는 날 + 확인. 어디에도 없으면 `trip.ask_first_day` — 지어내지 않는다) →
장소(별칭 → 우리 장소 표 → 자모 오타 → 관광공사 서울 → 카카오로 이름 찾고 관광공사 재확인 → 관광공사에 없으면 카카오 값을 그 항목에만
→ 이름이 특정하지 않으면(「한강 카약」·「북한산 둘레길」) **종류가 맞는 후보 중 같은 날 앞뒤 일정에 가장 가까운 곳** — 카카오 근처 거리순 재검색 포함, 확인 필요).
★후보는 원문을 좁혀 찾기가 모두 실패한 뒤에만 쓴다 — 「광장시장 빈대떡」은 광장시장 + 항목 종류 식사(가게를 지어내지 않는다).
확인 화면에서 장소 이름을 고치면 별칭(`place_aliases`, 030)이 쌓여 **그 고객의** 다음 계획의 같은 말은 그 이름으로(`[2026-09-30]` 다른 고객에게는 쓰이지 않는다 — 038. 기본값 별칭만 모두에게) 다시 찾는다.
- 모델·관광공사·카카오 중 없는 것은 그 단계만 건너뛴다. 모델 장애는 `reading.error` 에 이름으로 남는다.
- ★장소 조회가 **막힌 것**(속도 제한 · 시간 초과 · 예산)은 근거의 `blocked` 에 남기고 「없는 곳이라는 뜻이 아니다」라고 적는다.
- 한도: 파일 5개 · 10MB · 글 20,000자. 관광공사는 몰림 30(`travel.rate_burst_by_source`), 카카오는 호출 예산(`travel.kakao_budget`).

- `GET` 응답의 `check` = `{ready, problems, filled, items, title}` — 등록을 막는 문제(`no_title` · `no_date` · `no_place` ·
  `booking_without_time` · `party_size_out_of_range` · `no_items`)와 **규칙으로 채운 칸**(시각이 없으면 원문의 「아침·점심·저녁」,
  아니면 앞 일정 뒤 · 끝이 없으면 활동 90분·식사 60분). 조립은 `app/modules/travel_ops/intake/assemble.py`.
- 등록된 항목의 `detail.provenance` 에 칸마다 방법과 근거가 따라간다. 예약번호는 `detail.booking` —
  **예약 표(`bookings`)는 만들지 않는다**(업체 확인 전 번호를 「확정 예약」으로 적지 않는다). 대신 보호 사유 `booked` 라
  **바꾸기 전에 묻는다**(`pending.protected_reason`).
- 조회로 정한 장소(관광공사·카카오)는 **그 여행 전용 장소 행**으로 등록된다(마이그레이션 029, [migrations.md](../data/migrations.md)).
- 웹 앱의 확인 화면 `frontend/apps/web/src/features/intake-review/` 이 이 경로를 쓴다(`NEXT_PUBLIC_DATA_MODE=live`).
- 「일정 짜 줘」는 모델이 가리키거나, 모델이 없어도 **규칙**(`intake/pipeline.PLAN_ASK` — 일정·코스·계획·동선 + 짜·만들어·추천해·세워·잡아 + 줘)으로 잡는다.
  `check.plan` = `{requested, start_date, days, party_size, preferences}` — **읽은 값에서만** 채우고 모르면 null(화면이 묻는다).
- 시험 `tests/e2e/test_trip_intake_api.py` 15건 · `tests/unit/travel/test_intake_rules.py` 22건 · `test_intake_resolve.py` 22건 · `tests/e2e/test_trip_planner.py` 의 계획 읽기 1건(2026-09-28 실행).

**여행 조회 항목의 종류 표시** `[2026-10-01 사용자 지적]` — `items[].kind_label`(`식사`·`활동`·`이동`·`숙소`·`항공`, 모르는 종류는 `kind` 그대로)와 `items[].meal`(식사만 `아침`·`점심`·`저녁`, 나머지 null). 화면이 「개화」만 보고는 식당인지 활동인지 알 수 없었다. 끼니는 일정 생성기가 적은 아침 표시가 먼저, 없으면 시작 시각(KST)으로 센다 — 10시 전 아침 · 16시 전 점심 · 그 뒤 저녁. 있던 필드는 안 바뀐 추가다.

**여행 조회 항목의 장소 정보** `[2026-09-29 사용자 지적]` — `items[].place_info`(이동 항목은 null):
`{address, phone, category, hours: [{day: "월", weekday: 1, open: "HH:MM", close: "HH:MM", last_order: "HH:MM"|null}] | null,
hours_source: [원장 출처 코드] | null, tags: ["card_payment","michelin","parking","takeout","vegetarian_menu","kids_allowed","halal",…],
michelin: {level, year} | null, source: "dining_ledger" | "tour_api" | "places" | …, source_note: "ⓒ한국관광공사" · "미쉐린 가이드 서울" | null,
hours_text: [운영시간·휴무 원문] | null, hours_conditions: [요일표로 펴지 않은 조건 원문] | null}`(뒤 두 칸은 원장 밖 장소만).
★`[2026-09-29]` **원장 밖 장소(활동 등)** — 주소는 관광공사 목록(`place_catalog`, 식별자 → 같은 이름·500m), 운영시간은 관광공사 원문을 요일별로 옮긴 값
(`hours[]` 에 `closed: true|false` · `last_entry`(입장 마감) — 활동은 `last_order` 가 늘 null), 전화는 관광공사 문의처. 1분 작업(`run_sweepers` 의 `place_facts`)이
진행 중인 여행에 새로 들어온 장소를 한 번 읽어 적는다 — 등록 직후 1~2분은 주소만 보일 수 있다.
★**요식 원장이 먼저**(장소 속성 `dining_place_uid` 또는 원장의 코어 연결), 없으면 코어 장소 속성(주소 정도). 모르는 값은 null — 「없다」로 읽지 않는다.
`tags` 는 원장 속성 코드 그대로다(값이 「yes」인 것). 코드 `app/modules/travel_ops/place_info.py`. 채팅의 주소·운영시간 답도 원장을 먼저 읽는다
(원장에 없는 값만 관광공사) — 답에 「요식 원장」·「관광공사 안내 원문」으로 어디서 온 값인지 적는다.

**지도 조합** `[2026-09-29 사용자 결정]` — 고객 **자기 지도 앱으로 여는 링크**(구글 지도 링크, **API 키 없음** — 공식 문서). 장소 항목 `items[].map_url` = 그 장소(주소를 알면 「이름 주소」, 모르면 좌표) · 이동 항목 `items[].map_url` = 앞 장소 → 다음 장소 **대중교통 길찾기**. `map.days[] = {date, stops[{number, item_id, name, lat, lon, map_url}], legs[{from_item_id, to_item_id, from, to, url}]}` — `stops[].number` 는 화면의 무료 지도가 찍는 번호. ☆처음엔 하루 경로 링크(들를 곳 여러 개)와 구글 퍼가기 경로 지도도 실었으나 **한국에서는 구글이 자동차·도보 길찾기를 주지 않고 대중교통은 들를 곳을 받지 않아** 둘 다 경로를 못 그렸다(ui 세션 실측) — 뺐다. 코드 `trip_api.map_view`.

**구글 지도 불러오기 허락** `[2026-09-29 사용자 지시]` — `POST /v1/web/map-load`(사용자 키). 화면이 구글 지도를 부르기 **전에** 한 번 묻는다. 답 `{provider: "google", allowed, meter: "google_maps_dynamic_maps", used: {day, month}, cap: {day, month}, fallback: null | "free_map"}`. `allowed: false` 면 구글을 부르지 않고 무료 지도로 보인다. 한도는 다른 구글 요금 단위와 같은 규칙(하루 = 무료 월 10,000 ÷ 32 = 312, 월 = 9,688)이고 DB(`external_call_budget`)에서 모든 프로세스가 같이 센다. ☆전에는 브라우저가 구글을 직접 불러 한도 장치 밖이었다. 코드 `trip_api.web_map_load`.

**활동 「다른 데로 바꿔」의 후보** `[2026-09-29 사용자 요구 — ui 세션 전달]` — 활동이면 대체 후보를 **관광공사 목록**(`place_catalog`, 일정 짜기와 같은 원천)에서 원래 장소 5km 안 가까운 10곳까지 넓힌다. ★`[2026-09-29 사용자 지시]` **요청 자리에서 관광공사를 부르지 않는다** — 「장소 갱신은 새벽 3시에 한 번, 요청은 DB 만」. 운영시간은 **새벽 작업**(`scripts.run_sweepers --only catalog_hours`, 03:00~08:00 · 한 번에 10곳 · 하룻밤 600곳 · 처음 보는 곳과 목록 수정 시각이 바뀐 곳만 — 마이그레이션 036 `catalog_hours`)이 읽어 둔 값과 다른 여행에서 이미 읽은 장소 행(같은 관광공사 id, 14일 안)만 쓴다. 운영시간을 모르는 곳은 후보가 아니다. 같은 여행·같은 자리는 6시간 동안 다시 넓히지 않는다. ☆앞 판은 요청 자리에서 관광공사를 최대 10번 불렀다(첫 요청 33초 → 뒤에서 읽기 0.5초였으나 한도·모델 서버 다툼) — 없앴다. ★**같은 곳**(같은 주소 · 30m 안 · 이름 첫 낱말 같고 1.5km 안 — `same_site`)은 후보끼리도 하나만(바뀐 곳·다른 안에 같은 건물 둘이 나오지 않는다), 일정의 다른 활동과 같은 곳도 후보가 아니다. 일정 짜기도 같은 곳은 순위 앞선 하나만 넣는다(`planner.distinct_sites` — 경복궁·건청궁). 운영시간을 읽은 곳만 그 여행 전용 장소 행으로 적는다. ★시연 대본 장소(`attributes.scenario_seed` — 「명동 대형마트(시나리오 지점)」 등)는 실서비스 테넌트에서 **대본 여행**(처음 등록한 판이 시연 장소를 쓴 여행 · 일정 짜기가 넣은 항목은 안 침)과 그 장소를 이미 일정에 넣은 여행에만 보인다 — 다른 고객의 바꾸기·일정 짜기·감시 후보에 안 나온다. 그 시각에 되는 곳이 없으면 막다른 답 대신 **안 셋까지**를 「선택이 필요해요」로 묻는다(보류 제안 이유 `relaxed`) — ①시각 늦추기 ②다음 일정 근처 ③5km 로 넓히기. 문구 「3km 안에서 10:10에 갈 수 있는 활동이 없어요(살펴본 곳: A — 그 시각 영업하지 않는다 · B — …). 대신 이런 곳이 있어요 — 1) … 2) … 3) …」 — 살펴본 곳이 셋 이하면 곳마다 이유를 적는다. 코드 `catalog_pool.py` · `catalog_hours.py` · `trip_desk._widen_activities` · `itinerary_changes.relaxed_options` · `itinerary.SCENARIO_SEED`.

**고객 연락처(복구 이메일 · 디스코드 웹훅)** `[2026-10-01 사용자 지시 — ui 세션 전달]` — 사용자 지시: 「리커버리 이메일 받는 곳에서 나중에 디스코드 웹훅 URL 도 받게 될 건데, 그게 추가되면 받을 수 있게 서버 구현해 두라」. **1단계 — 받아서 검증 · 저장 · 마스킹 조회 · 시험 발송까지.** 바깥함 일꾼이 고객 웹훅으로 계획 변경을 보내는 연결(2단계)은 사용자 확인 뒤에 한다. 세 경로(모두 `X-User-Key` — 키 → 고객이라 **남의 값은 안 보인다**, 키 없음 401):
- `GET /v1/web/profile` → `{recovery_email: str|null, discord_webhook: {set: bool, masked: "https://discord.com/api/webhooks/<번호 앞 4자리>…/••••"|null, status: "untested"|"ok"|"invalid"|null, checked_at: ISO|null}, updated_at: ISO|null}`. `status` 는 웹훅이 있을 때만(`untested` 저장만 함 · `ok` 시험 발송 성공 · `invalid` 웹훅이 없어졌거나 거부 — 401/404). **원문 URL · 토큰은 어느 응답에도 없다.**
- `PUT /v1/web/profile` — **부분 갱신.** 본문 `{recovery_email?: str|null, discord_webhook_url?: str|null}`. 칸이 없으면 안 건드리고, `null` 이나 공백만 있으면 지운다(웹훅은 함께 암호화한 값 · 마스킹 · 상태도 지움). 응답은 `GET` 과 같은 모양. **모르는 칸 · 틀린 값은 422 이고 하나라도 틀리면 전부 거절**(일부만 저장되지 않는다). 오류는 고정 문구 + 코드 `invalid_email` · `invalid_webhook` · `unknown_field`(칸 **이름**만 알림) — **받은 값을 되돌려 싣지 않는다.** 웹훅을 새로 저장하면 상태는 `untested` 로 돌아간다.
- `POST /v1/web/profile/discord/test` — 저장된 웹훅으로 시험 메시지 한 줄(`@` 호출 없음). **고객이 누를 때만.** → `{result: "ok"|"invalid"|"rate_limited"|"failed", profile: {…}}`. `ok`(2xx) · `invalid`(401/403/404/410 — 상태 저장) · `rate_limited`(디스코드 429) · `failed`(리다이렉트 · 5xx · 연결 실패 · 시간 초과). 웹훅이 없으면 409 `no_webhook`, 저장값을 못 풀면 409 `unreadable`(다시 입력), **마지막 시도에서 20초 안이면 429 `too_soon` + `Retry-After`**(분당 최대 3회 — DB 시각으로 세서 프로세스가 여럿이어도 맞다, 설정 `travel.profile.test_interval_seconds`).
★**웹훅 URL 은 비밀값이자 서버가 나중에 POST 하는 바깥 호출 통로(SSRF)라 이렇게 다룬다.** ①**받을 때** — `https://` + 호스트가 디스코드 공식 도메인(`discord.com` · `discordapp.com` · `canary.`/`ptb.` 하위)일 때만 + 경로가 `/api/webhooks/<숫자>/<토큰>`. 다른 호스트 · http · IP 주소 · 사용자정보(`@`) · 포트 · 쿼리 · 조각 · 점이 붙은 호스트 · 퍼센트 인코딩 · 공백 · 전각 글자는 422. ②**저장은 암호화**(Fernet — 키는 서버 `secret_key` 에서 파생, 값에 판 이름 `v1:`)만, 원문은 DB 어디에도 없다. `secret_key` 를 바꾸면 저장값을 못 풀어 고객이 다시 넣어야 한다. ③**응답은 마스킹만.** ④**발송 때 같은 검사를 한 번 더** 하고 **리다이렉트는 따라가지 않는다.** ⑤**로그에 원문을 남기지 않는다** — `httpx` 가 요청 주소를 INFO 로 찍는 기록은 웹훅 경로가 있으면 버린다. 한계: 호스트 **이름**만 검사한다 — DNS 재결합(허용 이름이 다른 주소로 풀리는 공격)까지는 막지 않는다(허용 목록이 디스코드 공식 도메인뿐이라 위험은 작고, 배포 때 바깥 호출을 허용 목록 프록시로 보내면 닫힌다).
이메일은 형식만 본다(인증 메일은 이번에 안 보낸다) · 닉네임은 이번 범위가 아니다. **이메일로 키를 되찾는 흐름은 서버에 아직 없다**(키 재발급 `rotate` 는 기존 키가 있어야 한다) — 웹은 「저장만 되고 복구 메일은 준비 중」으로 적는다. CORS: 화면(다른 출처)이 `PUT` 을 보내도록 허용 메서드에 `PUT` 을 더했다. 저장 표 `customer_profiles`(마이그레이션 039). 코드 `customer_profile.py` · `trip_api.web_profile*`.

**현재 위치로 묻기** `[2026-09-30 사용자 지시 — ui 세션 전달]` — 사용자 지시: 「위치정보가 필요하면 브라우저 Geolocation API 로 얻게」. `POST /v1/web/trips/{id}/messages` · `POST /v1/trips/{id}/messages` 본문에 선택 칸 `location: {lat, lng, accuracy_m?, at?}`(`lat` −90~90 · `lng` −180~180 · `accuracy_m` 0 이상). 없으면 지금과 같다. **위치가 필요한 질문인지는 판단 단위(모델)가 정한다**(낱말 추측 없음) — 사실 종류 `route_here`(현재 위치 → 도착지 가는 길 · 시간) · `nearby_dining`(근처 식당) · `nearby_activity`(근처 볼거리). 출발지도 일정의 곳 이름이면 기존 `move` 다. ★위치가 필요한데 `location` 이 없으면 **일정을 바꾸지 않고** `status: answered` · `needs_location: true` · `answer` 한 문장(「…현재 위치를 알려 주시면 …」) — 웹은 「내 위치 알려 주고 다시 묻기」를 띄우고 **새 `request_id`** 로 같은 문장 + `location` 을 다시 보낸다(첫 요청이 일정을 안 바꿨으니 두 번 바뀌지 않는다). 위치가 오면: 가는 길 = 이동 계산기(시간표)로 「지금 출발하면」 시간 · 못 쓰면 직선 어림값 `[추정]`, 근처 식당 · 볼거리 = 「다른 데로 바꿔」와 같은 후보 계산(그 시각에 여는 곳만, 요식 원장 먼저) 상위 3곳 + 도보 분. 서울 밖 좌표는 「서울 밖으로 보여서 …」 · 정확도 ±2km 넘으면 쓰지 않고 이유를 한 문장 · ±500m 넘으면 「조금 다를 수 있어요」 · 10분 넘게 낡은 위치는 알린다. ★**개인정보** — 원 좌표는 그 요청을 처리하는 데만 쓰고 로그 · DB · 알림 · Case · 대화 기록 · 답 문장 · 메모리 캐시 어디에도 남기지 않는다(답에는 거리 · 분 · 곳 이름만) — 시험이 응답 · Case · 대화 기록 · 바깥함 · 여행 전용 장소 · 로그를 훑어 좌표 문자열이 없음을 검사한다. 잘못된 값의 422 도 다른 좌표 값을 되돌려 주지 않는다. 코드 `trip_here.py` · `itinerary_changes.plan_nearby` · `trip_messages._answer_here`. 재생 시험 `cases_fact.jsonl` 42문장 — 새 질문 8/8(단 2문장은 지시문의 예시와 같은 문장이라 안 본 문장으로는 6/8).

**변경 초인종** `[2026-09-30 사용자 승인 — ui 세션 전달]` — `GET /v1/web/trips/{trip_id}/events`(사용자 키 `X-User-Key`, `text/event-stream`, `Cache-Control: no-cache` · `X-Accel-Buffering: no`). 서버는 **내용이 아니라 신호**만 보낸다. `event: ready` `{trip_id, version}`(연결 직후 한 번) → 바뀔 때마다 `event: trip.changed` `{trip_id, kinds, version}`(`kinds` = `itinerary` · `notice` · `proposal` 중 웹이 다시 읽을 것의 **힌트**) → 조용하면 약 20초마다 `: ping` 주석. 사용자 키 · 알림 본문 · 장소 내용은 싣지 않는다 — 웹은 받으면 지금 있는 조회(여행 본문 · `/notices` · `/proposals`)로 다시 읽는다. 신호가 나가는 변화: 새 판(감시 자동 변경 · 되돌리기 · 고르기 · 채팅) · 새 알림 · 제안 생성 · 만료 · 선택(알림이 안 생기는 변화도 제안 상태 지문으로 잡는다). 발행: 연결마다 2초 간격으로 DB 의 **커밋된 값**(여행 판 · 알림 수와 마지막 시각 · 제안 상태 지문)을 읽어 달라졌을 때만 보낸다 — 재시작 · 여러 일꾼에서도 맞다. **신호가 실패해도 일정 변경은 실패하지 않는다**(읽기만 하고, 변경 코드는 이 모듈을 import 하지 않는다 — 시험이 검사). 읽기가 연속 5번 실패하면 스트림을 조용히 닫는다. 놓친 신호를 되풀이하지 않는다 — 웹이 재연결하거나 화면이 돌아오면 전부 다시 읽는다. 서버는 누가 받았는지 기억하지 않는다(연결 수 상한만 프로세스 안에서 센다). 한 연결은 15분 뒤 서버가 닫는다(웹이 다시 붙는다). 남의 여행 · 없는 여행 **404**(다른 조회와 같다) · 키 없음 **401** · 사용자당 열린 연결 4개 초과 **429** `too_many_streams`(`Retry-After: 5`). 설정 `travel.trip_events.*`(guardrails). CORS: `X-User-Key` 를 실은 GET 이 통과한다(기존 설정 그대로). ★알림 조회의 앞부분 검색을 받치는 인덱스를 더했다(마이그레이션 037 — 바깥함 전체 훑기 방지). 코드 `trip_events.py` · `trip_api.web_trip_events`.

**웹 실시간 진행 (SSE)** `[2026-10-02 사용자 지시]` — 서버·모델이 멈추면 사용자가 자기 요청의 상태를 몰랐다(채팅 · 일정 짜기는 끝날 때까지 아무것도 안 보이는 호출이었다). 그래서 **오래 걸리는 웹 일은 SSE 로** 답한다. ★새 경로를 늘리지 않았다 — `POST /v1/web/trips/{id}/messages`(채팅) · `POST /v1/web/trip-intakes/{id}/plan`(일정 짜기)에 **`Accept: text/event-stream`** 을 붙이면 스트림, 안 붙이면 전과 같은 JSON 한 번이다(에이전트 입구 `/v1/trips/*` 는 안 바뀐다). 접수 읽기는 새 경로 `GET /v1/web/trip-intakes/{id}/events`. 사용자 키 `X-User-Key` · `text/event-stream` · `Cache-Control: no-cache` · `X-Accel-Buffering: no`.

| 이벤트 | 몸통 | 뜻 |
|---|---|---|
| `accepted` | `{op, at}` (접수 읽기는 `state` 도) | 받았다 — **첫 바이트**. 이게 안 오면 서버·연결 문제다 |
| `stage` | `{stage, label, waiting_on, elapsed}` | 서버가 **실제로 그 단계에 들어갔을 때만**. 지어낸 진행률은 없다. 채팅 `reading`·`understanding`·`looking_up`·`classifying`·`extracting`·`applying`, 일정 짜기 `planning`·`checking`·`registering`. 모르는 이름은 이름 그대로 보인다 |
| `beat` | `{elapsed, stage, label, waiting_on, stage_elapsed, slow, server_time}` | **3초마다**. 일꾼이 모델 호출에 막혀 있어도 이벤트 루프가 낸다. `slow=true` = 모델·장소 조회를 기다리는 단계가 8초를 넘음(「모델이 느려요」) |
| `result` | 기존 JSON 응답과 **같은 본문** (접수 읽기는 `{state}`) | 끝 |
| `error` | `{code, message, retryable, status?, retry_after_seconds?, …}` | 실패 · 시간 초과(`timeout` — 채팅 90초 · 일정 짜기 240초 · 접수 읽기 600초) · 읽던 일꾼이 죽음(`stalled`). 일정 짜기 거절의 이유·완화 조건은 몸통에 그대로 |

★**웹이 할 일(서버는 재료만 준다).** ①`beat` 가 오는데 `slow=true` → 「모델 응답이 느려요 (12초째)」 — 서버는 살아 있다. ②`beat` 를 **2번(약 6초) 못 받으면** 서버·연결이 죽은 것 → 「연결이 끊겼어요 — 다시 연결 중」(워치독은 웹 몫). ③`error{retryable:true}` → 다시 시도는 **같은 request_id** 로 하면 두 번 처리되지 않는다(채팅은 `status: duplicate` 로 돌아오고, 앞 요청의 답은 `GET /chat` 대화 기록에 있다. 일정 짜기는 이미 등록된 여행을 곧바로 `accepted` → `result` 로 돌려준다).
★**규칙.** 스트림이 열리기 **전**의 거절(남의 것 404 · 판이 낡음 409 · 날짜 밖 422 · 남용 방어 429 · 열린 연결 상한 429 `too_many_streams`)은 SSE 여도 **보통의 HTTP 오류(JSON `{error:{…}}`)** 다 — 응답 `Content-Type` 으로 가르면 된다. 연결이 끊겨도 서버의 일은 끝까지 돈다(처리 중인 요청을 버리지 않는다) · 응답 뒤로 미룬 일(분류 기록)은 정확히 한 번. 사용자당 열린 실시간 작업 3개(`travel.op_stream.max_per_user`). 값은 `config/guardrails.yaml` `travel.op_stream.*`, 코드 `app/modules/travel_ops/op_stream.py`, 시험 `tests/e2e/test_op_stream.py`.
**접수 읽기 진행** `GET /v1/web/trip-intakes/{intake_id}/events` — `accepted{state}` → 단계가 바뀔 때마다 `stage{state}` · 조용하면 `beat` → `review`·`confirmed`·`fatal` 이면 `result{state}`. `state` = `{status, stage, stage_label, revision, fatal_code, quiet_seconds}` — 읽은 값은 싣지 않는다(웹이 `GET /v1/web/trip-intakes/{id}` 로 읽는다). 갱신이 180초 넘게 멈추면(뒤에서 읽던 일꾼이 서버 재시작으로 죽음) `error{code: stalled, retryable}` — 영원히 「읽는 중」으로 두지 않는다. 남의 접수 · 없는 접수는 404.

**확인 화면 검사 · 대체 후보 · 장소 검색 · 사진 · 잠금 · 전체 자동 추천 · 재검증 · 내용 이벤트** `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업 `team_branch/sw/2026-10-02_계획확인_스트리밍_대표목업.html` + 멘토링 1001]` — 목업이 「협의 필요」로 적은 것을 서버가 채웠다. 읽기 파이프라인은 그대로이고(`intake/pipeline.py`), 읽은 값에서 **검사를 계산해 한 판(revision)마다 한 번 저장**한다(`intake_reviews`, 마이그레이션 040 — 정본은 `intake_claims`, 지워도 다시 계산한다). 새 코드: `intake/review.py`(검사) · `hours.py`(운영시간 사실) · `moves.py`(이동) · `candidates.py`(후보 · 검색 · 사진) · `autofix.py`(전체 자동 추천) · `stream.py`(내용 이벤트). 시험 `tests/e2e/test_intake_review.py` · `tests/unit/travel/test_intake_review_units.py`.

| 목업이 필요로 한 것 | 서버 |
|---|---|
| 「장소·운영시간 확인」 단계 | 접수 `stage` 에 `checking`(「장소·운영시간 확인」) 추가 — `received → transcribing → reading → checking → review` |
| 장소별 검사 줄 · 장소 사이 이동 · 확인 필요 개수 | `GET /v1/web/trip-intakes/{id}` 응답의 **`review`** (아래) |
| 이름이 모호한 장소(올리브영) | 읽을 때 앞뒤 일정에 가까운 한 곳을 **먼저 채우고**(`place_state: picked_nearest`, 확인 필요) 다른 지점은 후보로 — 빈칸을 던지지 않는다 |
| 대체 후보 1~3순위 · 후보별 판정 | `GET …/candidates` |
| 장소 검색 · 사진 | `GET …/place-search` · `GET /v1/web/places/photos` |
| 장소 · 시각 바꾸기 · 삭제 · 삭제 되돌리기 · 잠금 | `POST …/edits` 의 칸 확장 (아래) |
| 전체 자동 추천 · 재검증 | `POST …/autofix` · `POST …/revalidate` |
| 진행 이벤트 | `GET …/events` 에 내용 이벤트 `line` · `item` · `check` · `move` · `progress` · `done` |

**`review`**(접수 상태가 `review` · `confirmed` 일 때) = `{revision, built_at, engine: timetable|estimate|mixed|null, items[], moves[], needs: {items, moves, total}, ready}`. 계산이 실패해도 읽은 값은 그대로 가고 `review: null` + `review_error: "review_failed"` 다(조용히 비우지 않는다).
- `items[]` = `{id: "<원본 위치>-<번호>", source_id, index, title, kind, day, date, starts_at, ends_at (HH:MM), locked, edited, status, can_lock, place_state, place: {name, latitude, longitude, source, kind, category}|null, candidates_hint, booked, parts, rows[]}`. **`id` 는 이벤트 · 이동 · 후보가 서로를 가리키는 키**이고, 고칠 때는 `source_id` + `items[index].칸` 을 쓴다. 날짜 · 시각 순.
  - `status` — `keep` 유지 · `adjusted` 조정(규칙이 시각을 채웠거나 고객이 고침) · `review` 확인 필요(고쳐야 하는 줄이 있거나 · 장소가 임시 선택이거나 · 운영시간 밖). `can_lock` — 장소가 정해지고 확인 필요가 아닐 때만 참.
  - `place: {name, latitude, longitude, source, kind, content_id, content_type_id}` — `content_id` · `content_type_id` 는 관광공사 번호(있을 때만, 후보 · 자동 추천이 운영시간 표를 찾는 열쇠). 서버 안의 장소 행 번호(`place_id`)와 이동 재사용 키(`sig`)는 응답에 싣지 않는다.
  - `place_state` — `found` 찾음 · `picked_nearest` 이름이 여러 곳이라 가까운 곳을 임시로 고름(`candidates_hint` = 그때 본 후보 수) · `customer` 고객이 고름 · `none` 고객이 「장소 없음」 · `unresolved` 못 찾음(`place: null`) · **`needs_choice`** `[2026-10-03]` 이름 없이 **종류 + 지역만** 적은 줄(「성수 식당」) — `place: null`, 후보에서 고른다 · **`needs_name`** 같은 줄인데 **예약이 있다고** 적혀 있다 — 후보를 권하지 않고 예약한 곳의 이름을 묻는다(아래 「이름 없는 줄」).
  - `rows[]` = `{row, result, text}` — `row`: `place` 장소 · `time` 시간(채웠거나 겹칠 때만 나온다) · `hours` 운영시간 · `closed` 휴무일 · **`booking` 예약**(예약 말이 있거나 이름 없는 식사 줄일 때만 — `ok` 예약 있음(자동으로 안 바꾼다) · `ok` 예약 없이 간다 · `warn` 예약 있다는데 장소 모름 · `unknown` 식사인데 예약 여부 모름). `result`: `ok` 통과 · `filled` 규칙이 채움 · `warn` 주의 · `bad` 고쳐야 함 · `unknown` 아직 모름. **모르는 것은 `unknown` 이다 — 「열려 있다」를 지어내지 않는다.** `text` 는 화면에 그대로 보일 한 줄.
- `moves[]` = 같은 날 앞뒤 장소 사이 `{from, to (items[].id), day, date, status: keep|review|waiting, mode: walk|subway|bus|transit|estimate|null, mode_label, minutes, km, depart, arrive, slack_min, basis: timetable|estimate|null, summary, fare_krw?, rows[{row: route|mode|arrival, result, text}]}`. `slack_min` < 0 이면 다음 일정에 **늦게 닿는다**(`status: review`). `waiting` = 한쪽 장소가 정해지지 않아 아직 못 쟀다(확인 필요 개수에 안 센다 — 장소를 못 찾은 일정은 그 줄 자체가 `bad` 로 세고, 고객이 「장소 없음」으로 둔 일정의 구간은 계속 `waiting` 이며 **등록을 막지 않는다**(자유 시간)). **`basis: estimate` 는 이동 계산기가 꺼졌거나 그 구간을 못 채워 직선거리로 어림한 값**이다 — `summary` 에 `[추정]`, 이유는 `rows[0].text`. `timetable` 은 이동 계산기(시간표 판정) 값이고 출발 · 도착은 계산기가 낸 시각이다.
- `needs.items` = `status: review` 항목 수, `needs.moves` = `status: review` 이동 수. **`ready` = 읽은 값 문제가 없고 `needs.total == 0`** — 화면의 「여행 등록」이 켜진다. 등록 판정(`confirm`)은 그대로이고 막지 않는다(고객이 확인 필요를 남기고 등록할 수 있다).
- ★판정은 새로 만들지 않았다 — 운영시간 · 휴무 · 겹침은 **등록 판정기**(`itinerary_checks.check_itinerary`)의 위반(`closed_day` · `before_opening` · `after_closing` · `after_last_entry` · `break_time` · `overlap`)을 줄로 옮긴 것이다. 운영시간 사실은 **DB 에 이미 읽어 둔 값**만 쓴다(바깥 호출 없음): 장소 행 속성 → 관광공사 운영시간 표(`catalog_hours`, 새벽 작업) → 다른 여행에서 읽은 같은 관광공사 id(14일) → 요식 원장(`dining_state`, 식당만). 카카오로만 찾은 곳은 운영시간이 없다(`unknown`).

**편집 칸 확장** `POST …/edits` (`{revision, edits:[{source_id, field, value}]}`, 새 판 · 낡은 판 409):
- `items[n].locked`: `true` 고정 · `false` 풀기. 고정은 **장소가 정해지고 확인 필요가 아닌 일정만**(아니면 422 `lock_needs_confirmed_item`). 고정한 일정에 다른 칸(`place` · 시각 · `removed` …)을 고치면 **409 `item_locked`** — 같은 요청에 잠금 풀기가 있으면 함께 된다. 반대로 **고정하는 요청에 같은 일정의 다른 고치기를 섞으면 422 `lock_with_changes`**(고정은 따로 보낸다). 이 접수에 없는 일정 번호를 고치면 **422 `unknown_item`**(일정은 새로 만들어지지 않는다). 고정한 일정은 등록되면 `detail.customer_pinned` 가 되어 **감시 루프가 다시 자동으로 바꾸지 않는다**(`pending.protected_reason`).
- `items[n].removed`: `true` 빼기 · **`false` 되돌리기**(전에는 true 만 받았다).
- `items[n].place` 는 세 모양: `{"name": …}`(서버가 다시 찾는다 — 못 찾으면 422 `place_not_found`) · `{"none": true}`(장소 없음) · **`{name, latitude, longitude, source, kind?, content_id?}`**(후보 · 검색 결과에서 **고객이 고른 것**을 그대로 받는다. 서버는 다시 찾지 않고 모양만 본다: 이름 1~80자 · 좌표는 숫자이고 **서울 범위 안**(위도 37.4~37.72 · 경도 126.7~127.3, 아니면 422 `place_out_of_seoul`) · `source` ∈ `customer_pick|kakao|tour_api|places|search|map`(저장은 늘 `customer_pick`, 보낸 값은 `origin`) · `content_id` 는 숫자이고 서버의 관광공사 목록과 대조한다 — 그 번호의 장소가 보낸 좌표 500m 안이 아니면 번호만 뗀다 · `place_id` 는 받지 않는다(남의 장소 행을 가리킬 수 있다)). 이 값은 등록되면 **그 여행 전용 장소 행**(`attributes.source = customer_pick`)이고 공용 장소 표에 섞이지 않는다. 별칭(`place_aliases`)에는 쌓지 않는다.

**`GET …/candidates?source_id=&index=[&revision=]`** — 이 일정의 **다른 안 셋**(후보 A·B·C). 같은 날 앞뒤 일정에 가까운 순, 맞는 곳(`fits`)이 먼저. 이름이 모호한 일정은 같은 이름의 다른 지점(카카오 키워드 검색, 앞뒤 일정 가운데에서 거리순), 아니면 같은 종류(활동 = 관광공사 목록 DB · 같은 분류 우선 · 3km, 식사 = 요식 원장 DB · 2km). 응답 `{revision, item, current, reference: {before, after}, candidates: [{rank, place: {name, latitude, longitude, source, kind, address, category, content_id, content_type_id, ref}, distance_m, reference, rows[], fits, status: ok|warn|bad, slack: {before, after}, estimated}], notes}`. `estimated: true` = 앞뒤 이동 중 하나가 계산기 대신 직선 어림값(계산기가 꺼졌거나 그 구간을 못 채웠거나 시간 상한이 닿음). 같은 적합성 안에서는 시간표로 잰 곳이 어림으로 잰 곳보다 앞이다. 어림이 섞였는지(`engine_budget_exhausted`) · 같은 분류의 대체가 없는지(`no_same_kind`) · 같은 이름의 다른 지점이 없는지(`no_other_branches`) · 카카오를 못 불렀는지(`kakao:<이유>`)는 `notes` 로 말한다. 최종 셋은 상위 5곳을 이동 계산기로 잰 뒤 전체 판정 순서로 고른다. 후보마다 **그 일정의 날짜 · 시각**으로 운영시간 · 휴무 · 앞뒤에 닿는 시간을 검사한 줄이 붙는다. `place` 객체를 그대로 `edits` 의 `items[n].place` 에 보내면 된다. 읽기 전용 — 아무것도 저장하지 않는다(카카오 값은 약관상 저장하지 않는다). `notes` 에 `kakao:budget_exhausted` 같은 이유가 있으면 카카오를 못 불렀다는 뜻이다(후보가 비어도 「없다」가 아니다).
**`GET …/place-search?q=(2자 이상)&source_id=&index=[&revision=]`** — 수정 화면의 장소 검색. 관광공사 목록 · 요식 원장(DB)과 카카오를 함께 찾아 이름이 검색어로 시작하는 곳 먼저, 앞뒤 일정에서 가까운 순으로 최대 8곳, 각각 같은 검사 줄을 붙인다. 응답 `{revision, item, query, results[], notes}`(`results[]` 는 `candidates[]` 와 같은 모양).
**이름 없는 줄(종류 + 지역만)** `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]` — 「성수 예약 식당 · 예약 있음」 · 「서울역 인근 저녁 식당」 · 「이태원 소품숍」 · 「호텔 조식」처럼 **가게 이름이 없는 줄**.
  ☆전에는 이런 줄도 가게 이름으로 찾았고(없는 가게를 글자를 줄여 가며) 종류를 활동으로 읽었고 후보를 앞뒤 일정의 한가운데에서 찾았다 — 성수 식당 자리에 동대문 활동이 권해졌고 예약한 식당을 바꾸자고 했다(실서버 실측).
  - **읽는 법**(`intake/line_parts.py`): 줄을 띄어쓰기로 나눠 조각마다 **말 표**(`config/place_terms.yaml` — 종류 · 끼니 · 근처 · 예약 말 · 군더더기)와 **지명 사전**(`intake/areas.py` — 요식 원장의 허브 · 관광공사 목록 주소의 동 · 구에서 DB 로 만든 지역별 중앙값 좌표 + 반경, 한 시간 기억)의 말로 **전부 설명되면** 일반 말이다. 남는 조각(= 고유 이름)이 있으면 이름 있는 줄(지금처럼 이름으로 찾는다). 종류 말이나 끼니 말이 있고 남는 조각이 없으면 이름 없는 줄 — **가게 이름으로 찾지 않는다**. 끼니 말이 종류 말을 이긴다 — ★`[2026-10-04 사용자 지적 「그거 호텔인데 왜 식당이야?」]` **단 숙소 말 + 끼니 말(「호텔 조식」)은 예외**: 일정 `kind` 는 식사(`dining`)지만 **장소는 숙소**다 — `parts.label` 은 「숙소」, `parts.lodging_meal: true`, `parts.content_type` 은 숙박 분류(`32`). 화면 문장은 「숙소에서 하는 식사예요 — 숙소의 이름이 적혀 있지 않아요 · 숙소 이름을 알려 주세요(식당으로 바꾸지 않아요)」이고, 후보 · 장소 검색 · 전체 자동 추천은 **식당 목록과 식당 지도 검색을 쓰지 않는다**(결과 `kind` 는 `activity`, 숙박 후보가 없으면 빈 목록 — 호텔 줄을 식당으로 바꾸지 않는다). 앞 판은 식당으로 읽었다. 새 말은 **표에 한 줄을 더하는 것만으로** 같은 길을 탄다(코드 수정 없음).
  - **항목 새 칸**: `booked` = `true`(예약 있음 · 예약번호) · `false`(예약 없음) · `null`(말 없음) · `parts` = 이름 없는 줄일 때만 `{label: "식당"|"쇼핑"|…, kind, content_type, meal, near, area: {name, kind: hub|dong|district, latitude, longitude, radius_m}|null}`(그 밖은 `null`). 일정 `kind` 는 식당 · 끼니 말이면 `dining`.
  - **후보 · 검색의 약속**(시험으로 막는다): ①결과의 `kind` 는 일정의 `kind` 와 **같다** — 맞는 것이 없으면 다른 종류로 채우지 않고 빈 목록 + `notes: ["no_same_kind"]` ②`needs_choice` 후보의 중심은 **줄의 지역**(`reference.area` · 각 후보의 `reference` 도 그 지역 이름 · 반경은 `area.radius_m`) — 지역이 없으면 앞뒤 일정의 한가운데 ③`needs_name` 은 `candidates: []` + `notes: ["booked_needs_name"]`(검색 · 직접 입력은 열려 있다) ④앞뒤도 지역도 없어 중심이 없으면 `no_reference_point` · 지역 둘레에 같은 종류가 하나도 없으면 `no_candidates_in_area`. 카카오가 음식점 · 카페가 아닌 곳을 식사로 태그하던 것을 고쳤다(식당 자리 검색에 약국 · 공원이 섞이던 원인).
  - **전체 자동 추천**: 예약했다고 적힌 일정은 **장소도 시각도 바꾸지 않고** `kept: [{id, title, reason: "booked"}]`. `needs_choice` 는 같은 종류 · 지역 안의 후보로 채운다.
  - **`category`** `[2026-10-03]` — 후보 · 검색 결과 · 현재 장소에 종류 이름을 채운다: 관광공사 목록은 `content_type_id` → 표의 `content_types`(관광지 · 문화시설 · 쇼핑 · 음식점 …), 요식 원장은 「음식점 > 한식」(요리 갈래를 모르면 「음식점」) + `address`(원장 도로명 주소), 카카오는 원래 값. 고객이 고른 값(`edits` 의 `place`)은 보낸 `category`(60자까지)를 그대로 들고 있다.
  - **고른 곳 문장**: `직접 고른 곳이에요 · 관광공사에서 찾았어요`(출처는 `origin` — 관광공사 · 카카오 지도 · 우리 장소 목록, 모르면 뒷말 없음). 전에는 「직접 고른 곳이에요 · 직접 고른 곳」으로 겹쳤다.
  - 알려진 한계: 이름이 통째로 일반 말로만 된 가게(「성수커피」 = 성수 + 커피)는 이름 없는 줄로 읽힌다 — 고객이 후보 · 검색에서 직접 고른다(고른 값은 언제나 이긴다). 사전에 없는 지역 말은 이름 조각으로 남아 지금처럼 이름으로 찾는다.

**`GET /v1/web/places/photos?ref=tour:<관광공사 번호>`** — 그 장소에 **등록된 사진** 주소 `{ref, photos: [{url, thumb, name}], source_note: "ⓒ한국관광공사"|null, reason}`. ★**사진은 저장하지 않는다**(사진 · 소개글은 저장 금지 — 루트 사실표): 부를 때마다 관광공사(`detailImage2`)에서 주소만 받아 그대로 넘기고 출처 표시를 붙인다. 관광공사가 아닌 `ref`(카카오 · 요식 원장)는 `photos: []` + `reason: no_photo_source` — 지어내지 않는다. 같은 장소를 되풀이해 불러도 관광공사 호출이 되풀이되지 않는다 — 어댑터가 응답을 **프로세스 메모리에만** `travel.tour_api_cache_seconds`(6시간) 동안 들고 있고(저장하지 않는다) 호출은 관광공사 몰림 제한(`rate_burst`)을 지난다.
검색어는 공백을 뺀 두 글자 이상이어야 한다(아니면 422 `query_too_short`). 이 읽기들과 `autofix` 는 웹 남용 방어의 새 세는 작업 **`place_search`**(키당 하루 60 · 주소당 200 · 서비스 전체 500 — 기본은 세기만 하고 제한은 `web.limits_enabled` 가 켜져야 막는다)로 센다. 남의 접수 404 · 낡은 `revision` 409 `stale_revision` · 아직 확인 화면이 아니면 409 `intake_not_editable` · 없는 일정 404 `item_not_found`.

**`POST …/autofix {revision}`** — **전체 자동 추천**. 확인 필요 장소 + 앞 일정에서 늦게 닿는 일정을, 고정한 일정은 두고, 일차별 시각 순으로 하나씩 맞춘다(앞 일정이 바뀌면 그 값이 다음 기준이다): 장소가 문제면 후보를 차례로(이름 모호함뿐이면 지금 곳이 먼저) **운영시간 · 휴무를 통과하는 첫 곳** → 그 곳에서 시작 = 앞 일정이 끝난 뒤 이동해 닿는 시각(5분 올림), 끝 = 다음 일정에 닿도록 줄임(5분 내림), 머무는 시간이 30분 미만이면 못 맞춘 것. 맞으면 `edits` 와 같은 길로 **새 판 하나**(`applied: true`, 자동 추천이 낸 값은 근거에 `via: autofix`), 맞는 안이 없으면 **판을 만들지 않고** 이유를 말한다. 응답 `{applied, revision, changed: [{id, source_id, index, title, from: {place, starts_at, ends_at}, to: {…}, reason: place|time|place_and_time}], kept: [{id, title, reason: locked|no_time|no_candidates|no_fitting_place|no_fitting_time|nothing_to_change}], view}` — `view` 는 `GET …/{id}` 와 같은 모양(새 검사 포함). 되돌리기는 `from` 값으로 다시 `edits`(고객이 고른 것과 같은 길).
**`POST …/autofix {revision, dry_run: true}`** `[2026-10-03 ui 세션 요청서 3번]` — **미리 보기**: **저장하지 않고** 바뀔 모습만 돌려준다. 같은 길(`edit`)로 새 판을 만들어 `view` 를 읽은 뒤 저장 구간을 되돌리므로(세이브포인트 롤백) 미리 보기의 검사가 **실제로 적용한 결과와 같다**. 응답 = `{applied: false, dry_run: true, revision(현재 판), changed, kept, view}` — `view.preview: true` 이고 `view.revision` 은 **적용하면 생길 판 번호**다. 바꿀 것이 없으면 `view` 는 현재 모습(`preview` 없음). `dry_run` 을 안 보내면 전과 같이 적용한다(응답에 `dry_run: false`). `revalidate` 는 `dry_run` 을 받지 않는다(모르는 칸 422).

**`POST …/revalidate {revision}`** — **재검증**. **새 판을 만들지 않고**(고객이 고친 값은 그대로) 같은 판의 검사(운영시간 · 휴무 · 이동)를 처음부터 다시 계산해 그 판의 저장된 검사를 **새 값으로 바꾼다**(운영시간 표가 새벽에 바뀌었거나 계산기 답이 달라졌을 수 있다 — 조회는 판마다 한 번 계산한 값을 주므로 재검증 뒤의 조회도 새 값이다). 이동은 앞 판의 값을 재사용하지 않고 다시 잰다. 응답 = `GET …/{id}` 와 같은 모양, `review.ready` 가 참이면 「여행 등록」.

**내용 이벤트** `GET …/events` — 기존 `accepted` · `stage` · `beat` · `result` · `error` 사이에 흐른다. ★**이벤트는 상태의 복사본(덮어쓰는 값)이다**: 같은 키가 다시 와도 나중 것으로 덮으면 되고, 다시 연결하면 지금까지의 상태가 처음부터 다시 온다(서버는 누가 어디까지 받았는지 기억하지 않는다). 정본은 `GET …/{id}` 다. 서버는 **순서만** 맞춘다(줄 → 일정 → 검사 줄 → 이동 → done) — 보이는 속도는 웹이 정한다(받은 이벤트를 차례 줄에 쌓아 최소 표시 시간을 두고 그린다). 값은 읽는 **동안** 적히므로(전에는 끝에 한꺼번에) 이벤트도 그때그때 나간다: 규칙으로 읽은 줄 → 모델이 가리킨 줄 → 날짜 → 이름이 특정된 장소가 하나씩 → 모호한 장소(앞뒤가 다 찾아진 뒤) → `checking` 단계 → 검사.

| 이벤트 | 몸통 | 키 |
|---|---|---|
| `line` | `{source_id, no, text, read: true, found: {id, index, day, date, starts_at, title}\|null}` — 읽힌 줄만(안 읽힌 줄은 `GET` 의 `lines[].read=false`) | `source_id` + `no` |
| `item` | `{id, source_id, index, title, kind, day, date, starts_at, ends_at, locked, status, can_lock, place_state, place, candidates_hint}` — 시각 → 장소가 채워질 때마다 같은 `id` 로 다시(`place_state: searching` = 아직 찾는 중, `status` 는 검사 전엔 null) | `id` |
| `check` | `{item, row, result, text}` | `item` + `row` |
| `move` | `moves[]` 한 건 | `from` + `to` |
| `progress` `[2026-10-03]` | `{phase: places\|hours\|moves, done, total, current: {id, title}}` — 「3/14 · 광장시장 운영시간 확인 중」. `places` 는 **읽는 동안** 장소 찾기가 일정마다(찾든 못 찾든 그 일정의 장소 값이 정해지면 센다 — 이름이 특정된 것은 찾는 즉시, 모호한 것은 앞뒤가 다 찾아진 뒤), `hours` 는 검사의 운영시간 확인이 일정마다, `moves` 는 이동이 구간마다(`current.title` = 「A → B」). `done` 은 1씩 늘어 `total` 에서 끝난다. 접수에 원본이 여럿이면 `places` 는 원본마다 센다 | `phase` |
| `done` | `{stage: review, revision, needs, ready}` — 검사가 끝났다, 곧 `result`. 검사할 것이 없는 접수(빈 접수)는 `done` 없이 곧바로 `result` | — |

**검사 진행을 끝에서 한꺼번에 내지 않는다** `[2026-10-03 ui 세션 요청서 2번]` — 검사(`review.build`)는 한 트랜잭션 안에서 돌고 끝나 커밋돼야 DB 에 보이므로, 전에는 검사 줄 56개 · 이동 12개가 끝난 4.9초에 한꺼번에 나갔다(이동 계산이 대부분의 시간인데 화면은 아무것도 몰랐다). 이제 계산이 **끝나는 대로**: ①일정마다 `item` · `check` 를 이동 계산 **전에**(`status` 는 이때 정해진 값이고, 겹침 확인 필요는 끝에서 바뀔 수 있어 최종 값이 같은 키로 덮는다) ②이동은 구간마다 `move` + `progress{moves}` ③운영시간은 일정마다 `progress{hours}`. ★이 중간 진행은 **프로세스 안 보관소**(`intake/progress.py`)를 거친다 — DB 에 쓰지 않고(접수 하나에 150개 안팎), 읽는 일꾼(스레드)과 SSE 연결이 **같은 프로세스**일 때만 보인다(배포는 한 프로세스). 여러 프로세스(`--workers N`)에서 다른 프로세스의 연결은 전처럼 끝에서 받는다 — 깨지지 않고 **중간 진행만 안 보인다**. 접수 하나당 600개 상한(앞에서부터 버림) · 15분 지나면 버림 · 읽기가 끝나면 비운다(최종 값은 DB 에서 읽힌다). 서버는 DB 의 덜 채운 값(`status: null`)으로 이미 검사 줄까지 낸 일정을 **되돌리지 않는다**.

내용 이벤트를 만드는 데 실패해도 단계 이벤트(`accepted` · `stage` · `result`)는 끝까지 나간다(실패는 로그에 남는다).

**함께 고친 것**: ①「10시 경복궁 관람 1시간 반」의 「1시간」을 시각 「1시」로 읽어 가짜 항목(「간 반」 01:00)이 생기던 결함 — 이제 「시간」은 시각이 아니고 **소요 시간(1시간 반 · 2시간 · 40분)이 끝 시각**이 된다(원문 조각이 근거) ②카카오 결과에서 지점 접미어를 뗀 이름이 같은 곳이 여럿이면(「올리브영 ○○점」들) **첫 결과를 고르지 않고** 후보로 넘겨 앞뒤 일정에 가까운 곳을 고른다(전에는 관련도 첫 결과를 확인 표시도 없이 썼다 — 2026-10-01 「강남 올리브영 → 명동 다이소」). 고객이 지점까지 적으면(「올리브영 광화문점」) 그 지점이 먼저다 ③`GET` 의 `review` · 접수 `stage: checking` · 값을 읽는 동안 바로 적기 · `fatal` 이면 읽다 만 값을 치움. ★목업과 다른 점: 목업은 올리브영을 「지점 미정 · 위치 미정」으로 두었지만 **서버는 가까운 한 곳을 임시로 채우고**(프로젝트 결정 15 · 사용자 요구 「빈칸 금지」) `place_state: picked_nearest` + 확인 필요로 알린다 — 화면은 임시 선택임을 보이고 후보로 바꾸게 하면 된다.

**바꾼 뒤에도 다른 안 셋** `[2026-09-29 사용자 제안 — ui 세션 전달]` — 「다른 데로 바꿔 줘」로 바꾼 뒤(`status: adjusted`), 조건을 다 통과한 나머지 → 모자라면 조건을 푼 안(시각 늦추기 · 다음 일정 근처 · 5km — `note`)을 셋까지 모아 **바꾼 항목에 보류 제안**(`reason: other_options`)을 연다(응답 `proposal_id` · `options`). 고르면 그 안으로, 답이 없으면 지금 것. 원래 곳은 넣지 않는다(되돌리기 몫). 답 문장에 「다른 안: 1) … · 2) … — 다른 곳이 좋으면 고르세요」. 바꾼 뒤에도 `trip_outcome` 에 `seen`(떨어진 곳 + 통과한 곳 — 통과는 셋까지만 셈) · `rejected` · `radius_m` 를 남긴다. 식사 · 활동 같은 방식. 마이그레이션 035.

**웹 답 문장의 선택 목록** `[2026-09-29 ui 세션 요청]` — 웹 입구(`/v1/web/…/messages`)의 `answer` 에서는 「혹시 이런 뜻이었나요?」·「다음 중 하나인가요?」 번호 목록 문단을 뺀다(`choices` 버튼으로만). 에이전트 입구와 대화 기록(`GET …/chat`)은 글만 읽으니 문장에 목록을 둔다.

**사실 답 — 먼저 답하고 「혹시 이런 뜻이었나요?」** `[2026-09-29 사용자 지시 · ui 세션 결함 보고]` — 사실 질문(answer_fact)은 되묻지 않는다. 모델이 되묻기를 골랐어도 해석 후보가 **모두 사실 질문**이면 첫 후보로 답한다(`decision_unit.fact_first`). 답에는 `choices: [{label, message}]` + `choices_title: "혹시 이런 뜻이었나요?"` 가 붙는다(모델의 다른 해석 먼저, 모자라면 같은 일정의 가까운 질문 — `NEAR_FACTS`, 셋까지). `status` 는 `answered` 다(되묻기의 `clarify` 와 다르다) — 버튼 `message` 를 그대로 보내면 된다. 답 문장 끝에도 번호 목록이 붙는다(버튼 없는 에이전트용). 바꾸기·되돌리기는 지금처럼 되묻는다(잘못 짚으면 일정이 바뀐다). ★질문 종류는 **물은 것 하나**(가장 좁은 칸) — 「어디 있어·어딨어·위치」→ address, `detail` 은 무엇을 묻는지 특정하지 않을 때만. address 답은 주소 한 줄 + 지도 앱 링크(구글 지도 검색 링크 — API 호출이 아니다). detail 답은 핵심(무엇 · 어디 · 지도 · 그날 영업 · 다음 일정)만 `answer` 에, 나머지(주소 출처 · 운영시간 원문 · 가격 · 결제 · 예약 · 오는 길 · 장소 정보)는 **`more`**(화면의 「더 보기」)에 싣는다. 재생 시험: 질문 종류 묶음 `eval/decision_unit/cases_fact.jsonl` 34문장(「○○ 알려줘」 → detail 7문장 추가) — 지시문 고치기 전 24/27, 뒤 33/34. 네 묶음 합 159/164(97%) · 질문 종류 79/80 · 엉뚱한 대상 변경 0 (각 1회). ★남은 것: 앞 대화에 바꾸기가 있을 때 「경복궁 알려줘」가 address 로 간다. 문구를 더 세게 고치면 34/34 가 됐지만 되돌린 뒤의 맨 「바꿔」를 되돌리기로 읽는 착오가 다시 생겨(일정이 바뀌는 쪽) 약한 문구를 택했다 — 잘못 짚은 사실 답은 버튼 한 번으로 고친다.

**채팅 결정 단위** `[2026-09-29 사용자 지시 · Codex 3회 합의]` — `POST /v1/web/trips/{id}/messages` · `/v1/trips/{id}/messages` 는 이제 **여행 상태(일정 · 변경 이력 · 서버에 저장한 최근 대화 · 화면 선택)를 보며 모델 한 번**으로 할 일과 대상을 고른다(옛 분류기 · 추출기 · 낱말 규칙 대신). 응답에 `decision = {action, item, item_id, change, fact, minutes, choices, seconds}` · `reason = "decision_<action>"`. action: apply_change · propose_alternatives(바꾸지 않고 후보를 「선택이 필요해요」로 — 보류 제안 이유 `requested_options`) · rollback · redo · answer_fact · ask_policy · report_delay · report_closed · clarify · other. ★이해하지 못하면 `status: "clarify"` + `choices: [{label, message}]`(「다음 중 하나인가요?」 — `message` 를 그대로 보내면 한 번에 알아듣는 문장, 버튼용) — 사용자 제안. 「1번」으로 답해도 앞 대화로 풀린다. 뒤에 다른 변경이 있는 옛 변경을 되돌리면 한 번 묻고(`ask_rollback`), 「네」면 되돌린다. 모델 실패 · 목록 밖 id 는 **바꾸지 않고** `escalated`(`reason: decision_failed`) — 옛 경로로 넘기지 않는다. 켜기/끄기: 운영 설정 `chat.decision_mode`(off · shadow · on, 기본 on — `PATCH /admin/limits`, 30초 안 반영). 대화 기록 `GET /v1/web/trips/{id}/chat?limit=40`(사용자 키) · `GET /v1/trips/{id}/chat`(trip:read) → `{turns: [{role: customer|assistant, text, case_id, at}]}` — 고객 문장은 가린 값. 코드 `decision_unit.py` · `trip_messages._run_decision` · `chat_log.py`(034). 재생 시험 `eval/decision_unit/`.

**근거 표시 · 개발 모드** `[2026-09-29 사용자 지시]` — 고객 문장(`answer`)에는 **늘** 내부 근거 id(t_doc_… · #c… · 예약 조건 scope)를 싣지 않는다 (사실 답의 「출처 요식 원장 · 미쉐린 가이드 서울」 같은 출처 **이름**과 ⓒ한국관광공사 표시는 고객용이라 남는다). 근거는 Case 기록(`state_json.basis` · `trip_outcome.basis`)에 늘 남는다. 웹 메시지 응답의 `basis`(원래 모양) · `basis_sources: [{source}]` · `decision` 은 운영 설정 `web.dev_mode`(off · on, 기본 off)가 on 일 때만 실린다.

**채팅 「다른 데로 바꿔 줘」** `[2026-09-29 사용자 지적]` — 몸통에 선택 칸 **`item_id`**(화면에서 고른 일정). 어느 항목인가:
★**문장이 분명히 말하면 문장이 먼저**(`[2026-09-29 ui 세션 지적]`) — 문장의 번호(「2번」 = 식사·활동을 시각 순으로 센 차례) → 이름 → 끼니(「점심」 — 그 시간대 식사) → `item_id` → 들고 있던 「다른 안」이 있는 항목 → 다음 일정. 예: 경복궁을 눌러 둔 채 「점심 식당 바꿔 줘」면 점심이 바뀐다.
그 항목에 들고 있던 안이 있으면 그것으로(`swap_alternate`), **없으면 그 자리에서 찾는다**(`plan_fresh_alternate` — 식사는 요식 원장 후보 먼저 ·
같은 시각 · 동선 · 동행 조건, 활동은 그 시각 영업하는 근처). 바꾸면 `adjusted`, 나머지 후보는 「다른 안」(`other_options`)으로 남는다.
`no_alternate` 는 후보를 **실제로 다 뒤져도** 없을 때만(`reason` · `rejected`).
★`[2026-09-29 사용자 지적]` 같은 조건으로 0곳이면 반경을 넓히고(식사 700m→1.5km→3km · 활동 1.5km→3km), 그래도 0곳이면 **조건을 풀어** 되는 안을 계산한다 — ①시각을 30·60·90·120분 늦추기(다음 일정과 안 겹치게) ②다음 일정 근처 같은 시각. 있으면 **바로 바꾸지 않고 묻는다** — `status: "asked"`, 「선택이 필요해요」 제안(보류 제안 이유 `relaxed`, 알림 `proposal_request` 의 `options[].note` = 「09:00으로 늦추면」 · 「다음 일정(경복궁) 근처」). 고르면 `…/proposals/{id}/choose` 로 그 시각 · 그 장소가 적용된다. 정말 어떤 조건을 풀어도 없을 때만 `no_alternate` + 이유(「(그 안에 후보 장소가 하나도 없어요)」 · 「(살펴본 N곳 중 M곳은 「이유」)」, 기록 `trip_outcome.seen`). 종류 넓히기(아침 카페 등)는 아직 없다.

★`[2026-10-03 사용자 지적 · multi-agent flow 세션 전달]` **감시도 같은 조건 풀기를 한다.** 전에는 이 계산(`relaxed_options`)을 고객이 「다른 곳으로」를 요청한 길만 불렀고, 감시가 바꿀 곳을 못 찾으면(`itinerary_unresolved` — 같은 조건 0곳) 또는 찾은 안이 **일정 전체 재판정에 다 걸리면**(`itinerary_recheck_failed`)
곧바로 「일정은 그대로 두었어요 + 원인」 알림으로 끝났다. 이제 같은 계산으로 **비슷한 안을 묻는다** — 보류 제안(이유 `relaxed`, 알림 `proposal_request` · 안전 사건이면 `safety_alert`)에 안 1·2·3 + 무엇을 풀었는지(`note`):
「{항목} — {원인}. 같은 조건으로는 대신 갈 곳을 찾지 못했어요(또는 「바꿀 곳을 찾았지만 일정 전체와 맞지 않았어요」). 그래서 **일정은 그대로 두었어요.** 조건을 조금 풀면 이런 곳이 있어요 — 1) 16:00으로 늦추면 ○○ · 2) 다음 일정(△△) 근처 □□. 고르시면 바꿀게요. 답이 없으면 지금 일정을 그대로 둡니다.」
①**자동 적용하지 않는다**(판 번호 그대로 — 고르면 `…/proposals/{id}/choose` 로 바뀐다, 답이 없으면 그대로) ②묻는 안은 **고르면 그대로 적용될 안만** — `plan_swap` 으로 미리 해 보고, 같은 원인을 **다시 점검**해(활동 · 식사 모두) 통과한 곳만, **일정 전체 재판정**(바꾼 뒤 새로 생기는 구조 위반 없음)과 **밀도 판단**(하루가 원하신 여유보다 빡빡해지지 않음)을 통과한 안만 싣는다 — 못 쓸 안은 순위에서 빠지고 순위는 다시 매긴다
③날씨 원인이면 활동은 **실내만**(시각 · 거리를 푸는 것이지 안전 조건을 푸는 것이 아니다) ④한 곳도 없으면 지금처럼 「일정은 그대로 두었어요」 ⑤같은 항목 · 같은 판에는 제안 하나(`pending_changes` UNIQUE) — 알림도 한 번 ⑥묶음 Case 는 못 푼 항목마다 묻고, 묻는 항목은 묶음의 「그대로 두었어요」 줄에서 빠진다
⑦스위치 `travel.watch.relaxed_enabled`(기본 켜짐 — 끄면 전과 같다). 구현 `app/modules/travel_ops/watch_relaxed.py`(감시 Case `trip_watch_cases` · 시나리오 감시 `trip_watch`/`pending.apply_or_ask`(점검기를 받은 자리만)가 부른다) · 시험 `tests/e2e/test_watch_relaxed.py`.
`[미확보]` 식당의 **요리 분류를 넓히는** 안(아침엔 카페 · 베이커리)은 아직 없다 — 요식 원장 분류와 끼니를 엮는 자료가 정리되면 더한다. 활동은 후보를 분류로 거르지 않으므로(순위에만 쓴다) 따로 넓힐 단계가 없다. 새벽 확인(`dawn_check`)과 「바꿔 줘」 동의 뒤의 못 찾음(`pending._consented`)은 아직 이 길을 타지 않는다.

**여행 조회 항목에 더한 칸** `[2026-09-27]` — `lat`·`lon`(그 고객 자신의 여행 장소 좌표, 웹 지도 핀) · `booked`(예약 표 연결 또는
`detail.booking`). **웹 메시지 응답**에는 「바꾸지 않아도 되는 결과」(`no_meal` · `still_fits` · `no_alternate` · `clear` · `gone`)일 때
대화 경로와 **같은 문장표**(`itinerary_team.ANSWERS`)의 `answer` 가 실린다 — 웹이 문장을 지어내지 않게.

### 지도 경로선 — `/v1/web/trips/{trip_id}/route-shapes` · `/v1/web/trip-intakes/{intake_id}/route-shapes` `[2026-10-04]`

이동 하나마다 지도에 그릴 GeoJSON `LineString` 을 우리 도로 그래프(OSM)로 계산해 내린다 — 외부 길찾기 API 를 부르지 않는다. 읽기 전용, 사용자 키/쿠키, **본인 것만**(남의 것은 404).

| | 등록된 여행 | 접수 확인 화면(등록 전) |
|---|---|---|
| 경로 | `GET /v1/web/trips/{trip_id}/route-shapes` | `GET /v1/web/trip-intakes/{intake_id}/route-shapes` |
| 응답 | `{trip_id, shapes[], attribution}` | `{intake_id, revision, shapes[], attribution}` |
| 원천 | 여행 항목의 `route_def` | **저장된 확인 검사**(`items[]` · `moves[]`) — 없으면 이동을 다시 계산하지 않고 `shapes: []` |
| `shapes[]` | `{item_id, from_item_id, to_item_id, from, to, mode, line, source, grade, distance_m, note}` | 같은 모양, **`item_id` 없음**. `from_item_id`·`to_item_id` 는 확인 화면 `review.items[].id`(「0-3」) |

- `mode`: walk · bike · taxi · subway · bus · mixed · unknown. `source`: `local_road_graph`(도로 그래프) · `stations`(탄 역 좌표 순서 + 양 끝 걸음) · `straight_line`(직선 — 이유는 `note`). `grade`: 추정 · 근거없음(확정은 없다).
- 좌표 없는 장소가 낀 이동은 건너뛴다. 접수용은 저장된 검사에 탄 역 정보(`uses`)가 없는 **옛 검사**의 지하철·대중교통을 직선 + `note` 로 내린다 — **새로 접수한** 검사부터 역 좌표를 따라 그린다(고쳐도 바뀌지 않은 이동은 저장된 값을 다시 쓰므로 옛 검사는 그대로 직선).
- `attribution`(「지도 데이터 © OpenStreetMap contributors (ODbL)」)은 선을 그릴 때 화면이 보여야 한다.

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

운영 화면은 `/ui/delegations` 다 — ★`[2026-09-29]` **운영 앱**(별도 프로세스, [D-CS-008](../decisions/D-CS-008-ops-console-separate-app.md))이 이 경로를 **실제 HTTP** 로 불러(`ACOP_OPS_API_BASE_URL` · 키 `ACOP_OPS_API_KEYS`) 서버에서 그린다. 전에는 같은 프로세스 안에서 불렀다.

시험: [`tests/integration/api/test_delegation_api.py`](../../tests/integration/api/test_delegation_api.py)(12) ·
[`tests/integration/api/test_ui_delegation_screen.py`](../../tests/integration/api/test_ui_delegation_screen.py)(8).

## 관계

- [rest-api.md](rest-api.md) — 경계와 원칙
- [auth-boundary.md](auth-boundary.md) — scope
- [../actions/idempotency.md](../actions/idempotency.md) — 멱등 키

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
  거절 상세는 `error.detail` 아래에 있다. ★거절되면 **아무것도 바뀌지 않는다**(한 트랜잭션).
- 답이 없으면 그 일정이 끝날 때 `expired` — **원래 일정대로 간다.**

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
| `POST /v1/web/warmup` | 키 | ★`[2026-09-29]` **모델 예열** — 화면이 여행·채팅 칸을 열 때 부른다(식은 모델의 첫 채팅이 34초 걸렸다). 몸통 없음. 응답 `{status: "warm" \| "warming" \| "unavailable", model, last_attempt: null \| {ok, seconds, at, reason?}, deduped?}` — 이미 올라가 있으면 `warm`(아무것도 안 함), 1분(`web_guard.warmup.dedupe_seconds`) 안 되풀이는 `warming` + `deduped: true`(다시 안 부름), 그 밖엔 응답 뒤 한 토큰 생성으로 깨우고 `warming`. **`last_attempt.ok=false` 면 모델 서버가 못 올린 것**(`reason` 에 서버가 준 이유 — 예: GPU 메모리 부족). 실제로 부를 때만 남용 방어 `warmup` 으로 센다(한도가 켜져 있으면 429/503) |
| `GET /v1/web/trips/{trip_id}/notices` | 키 | 나간 알림 전부. `type` = `guidance`(하루 시작·다음 일정·이동) · `proposal_request` · `safety_alert` · `change_notice` |

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

### 남용 방어 — 횟수 제한 · 사람 확인 · 빈 키 정리 `[2026-09-28]`

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

**빈 키 정리 — ★기본 꺼짐.** `[사용자 결정 2026-09-29]` 키는 그 사용자를 알아보는 유일한 수단이라 지우지 않는다 — 켤지·다른 방식으로 할지는 다시 정한다(`web.idle_key_cleanup_enabled`, 켜기 전까지 아무 키도 안 지운다). 켜면: 발급 뒤 `web_guard.idle_key_days`(기본 7일)가 지나도록 **여행이 0건**이고 진행 중인 계획 읽기도 없는 사용자 키를
되잡기 작업(`python -m scripts.run_sweepers --only web_guard`)이 지운다 — 그 사용자를 가리키는 다른 행이 없으면 사용자 행도 지운다.
지운 수 · 남긴 수를 센다. 같은 단계가 48시간 지난 주소 줄과 35일 지난 사용량 줄도 지운다.

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
  `web.session.per_ip_hour` · `web.idle_key_days` · `web.idle_key_cleanup_enabled`. 기본값·범위는 가드레일, 바꾼 값은 `runtime_limits`.
- 바꾼 값은 각 프로세스가 최대 30초 캐시해 늦게 반영된다(`applies_within_seconds`). 감사 줄(`runtime_limit_events`)은 고치지도 지우지도 못한다(트리거).
- 시험 `tests/e2e/test_web_api.py` 10건.

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
| `POST /v1/web/trip-intakes/{intake_id}/plan` | 키 | 「일정 짜 줘」 `{revision, start_date, days(1~7), party_size(1~4), keep_read_items?, survey?}` — ★`survey` 는 생성기가 먼저 적용하고(16번 여유 → 하루 곳 수) 여행에 남는다(15번은 감시가 읽는다), 틀리면 422 `invalid_survey` — 원문 그대로를 선호로 일정 생성기(`planner.plan_trip`)가 짜고, **같은 판정**을 지난 초안을 `_create_trip` 으로 등록. `request_id = intake:{접수}:plan:r{판}` — 다시 눌러도 모델을 안 부르고 같은 여행. 못 짜면 422(이유·완화 조건). ★`keep_read_items`(기본 true) — 읽은 일정은 **옮기지도 바꾸지도 않고** 빈 시간만 채운다(`planner.plan_around`: 겹치거나 앞뒤 30분에 걸린 짠 항목 · 같은 때 식사를 빼고, 이동 자리가 모자라면 고정 일정을 밀지 않고 그 앞의 짠 항목을 뺀다. 읽은 장소는 후보에서 뺀다). 읽은 일정이 고른 날짜 밖이면 422 `read_items_outside_days`. false 면 읽은 일정 없이 새로 짠다 |

읽는 순서(원본마다): 규칙 → **남은 줄만** 모델에 보내 원문 조각을 인용하게 함(원문에 글자 그대로 없는 인용은 버린다) →
날짜(적힌 날짜 > 일차 > 상대 날짜, 해가 없으면 다가오는 날 + 확인. 어디에도 없으면 `trip.ask_first_day` — 지어내지 않는다) →
장소(별칭 → 우리 장소 표 → 자모 오타 → 관광공사 서울 → 카카오로 이름 찾고 관광공사 재확인 → 관광공사에 없으면 카카오 값을 그 항목에만
→ 이름이 특정하지 않으면(「한강 카약」·「북한산 둘레길」) **종류가 맞는 후보 중 같은 날 앞뒤 일정에 가장 가까운 곳** — 카카오 근처 거리순 재검색 포함, 확인 필요).
★후보는 원문을 좁혀 찾기가 모두 실패한 뒤에만 쓴다 — 「광장시장 빈대떡」은 광장시장 + 항목 종류 식사(가게를 지어내지 않는다).
확인 화면에서 장소 이름을 고치면 별칭(`place_aliases`, 030)이 쌓여 다음 계획의 같은 말은 그 이름으로 다시 찾는다.
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

**여행 조회 항목에 더한 칸** `[2026-09-27]` — `lat`·`lon`(그 고객 자신의 여행 장소 좌표, 웹 지도 핀) · `booked`(예약 표 연결 또는
`detail.booking`). **웹 메시지 응답**에는 「바꾸지 않아도 되는 결과」(`no_meal` · `still_fits` · `no_alternate` · `clear` · `gone`)일 때
대화 경로와 **같은 문장표**(`itinerary_team.ANSWERS`)의 `answer` 가 실린다 — 웹이 문장을 지어내지 않게.

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

---
type: contract
title: 여행·제안 API
description: 호출 주체와 책임별 REST 요청·응답 계약
status: draft
domain: travel
---

# 여행·제안 API

고객 여행 채팅의 선택지 대상과 새로고침 복원은 [후속 질문 계약](../trip-chat-context.md)을 따릅니다. 2026-10-12 로컬 수정·검증 범위이며 운영 반영은 별도입니다.

## 여행 API — `/v1/trips/*` · `/plan/{trip_id}`

`[실측 2026-09-14]` `app/domains/travel_ops/entry/trip_api.py`. 라우터는 도메인 폴더에 있고
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

`[실측 2026-09-22]` `app/domains/travel_ops/components/planning/planner.py` · 라우트는 `trip_api.py`.
시험 [`tests/e2e/test_trip_planner.py`](../../../tests/e2e/test_trip_planner.py)(19) ·
[`tests/unit/travel/test_planner.py`](../../../tests/unit/travel/test_planner.py)(13).

★★**이 경로는 v11 §4-A 를 뒤집는다.** 기준선은 「계획 생성은 우리 일이 아니다 — 외부
에이전트가 만든 일정을 받아 검증한다」였다. 사용자 지시로 생성기를 우리가 만들었고, 계획서는
읽기 전용이라 고치지 않았다. 무엇을 왜 뒤집었고 이 생성기가 **못 하는 것**이 무엇인지는
[리포트](../../records/reports/2026-09-22_2205_일정생성기_v11-4A를_뒤집는다.md)에 있다.

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

`[실측]` `app/domains/travel_ops/components/booking/change_link.py` · 라우트는 `trip_api.py`. v11 §4-C · §12 DoD-16·17.

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

시험: [`tests/e2e/test_booking_change_link.py`](../../../tests/e2e/test_booking_change_link.py)(4) — 세 값이 보이는가 · 틀린 토큰은 404 · **차액을 모를 때 지어내지 않는가** · 실제 공급자 원장이 안 바뀌는가.

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

`[정정 2026-10-05]` 고객 **자유 문장** → Case 생성 · 전이 경로는 `trip_messages.handle_trip_message` 에 구현돼 있고 `/v1/trips/{trip_id}/messages` 와 웹 상담(`/v1/web/trips/{trip_id}/messages`)이 부른다 — 이 줄은 앞 판의 `[미구현]` 이었다(팀 저장소 develop 의 정정을 읽고 우리 코드로 확인해 가져왔다).
`[미구현]` 고객 웹이 고른 언어를 접수 · 생성에 전달하는 계약은 없다(`trip_api.py` 의 요청 몸통에 언어 입력 필드가 없다 — grep). 계획서의 고객 언어 생성(결정 14)은 지금 한국어 원문이다.

### `constraints.survey` — 여행 시작 설문 `[2026-09-24]`

결정 [D-020](../../../../wiki/decisions/D-020-trip-survey-and-ask-first.md) · 구현 `app/domains/travel_ops/components/planning/survey.py`.
`POST /v1/trips`(과 `/v1/trips/plan` 의 등록)이 받는다. **없어도 된다** — 없으면 지금까지와 똑같이 동작한다.

| 칸 | 모양 | 판정에 |
|---|---|---|
| `version` | `"2026-09-24.v1"` (필수) | — |
| `on_disruption` | `replace`(기본) · `ask_first` | ★**쓴다** — 15번. 보류 제안 조회 · 선택 API 가 구현돼 있다(아래 「보류 제안」 절) |
| `pace` | `relaxed` · `moderate` · `packed` | ★**쓴다** — 16번 → 밀도 목표 0.40 · 0.55 · 0.70 |
| `theme` · `party` · `preferred_mobility[]` · `domestic` · `priority[]`(`food`·`activity`·`mobility`) · `priority_details{영역: [..]}` · `indoor_outdoor{dining·activity: indoor·outdoor·any}` · `theme_details[]` | 문자열·목록 | 필드별 소비 경로는 아래 설명을 따른다 — 세부 값은 담당 팀이 정한다. 저장됐다는 이유로 모든 선호가 계획에 반영됐다고 표시하지 않는다 |

- `[실측 2026-09-29]` 이동 계산기 연결이 `priority_details.mobility` 와 `preferred_mobility` 를 수단 집합으로 바꾼다([wiring.py](../../../app/domains/travel_ops/instances/mobility/wiring.py) `modes_from_survey` — 화면은 `priority_details.mobility` 로 보내고 둘 다 읽는다). 도보는 늘 포함하며 변환 가능한 값이 없으면 계산기 기본 수단(지하철 · 버스 · 도보)을 쓴다. 선호 순위를 그대로 최적화한다는 뜻은 아니다.
- `[실측 2026-09-29]` `domestic` 이 주어지면 [이동 계획기](../../../app/domains/travel_ops/instances/mobility/engine/plan.py)의 동행 조건 `foreign`(= `not domestic`)에 대응한다.
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
(`app/domains/travel_ops/ports/data_sources/utic.py:177`). 짧게 줄이면(`도로:대로`) 무관한 사건까지 걸린다.
택시 구간도 같다.

**도보** — `도보:` 는 쓰지 않는다. 걷는 길을 막는 것은 집회·행사 통제이고, 그것은 도로 통제 정보로 들어온다.
큰길을 지나지 않는 짧은 도보는 `uses: []`.

`[실측 2026-09-23]` **지금 실제로 감시되는 것**

| 대상 | 상태 |
|---|---|
| `도로:` | UTIC 돌발정보(1차) + **ITS 돌발정보(2차)** 를 함께 물어 합친다 `[2026-10-05]` — 한쪽만 못 읽으면 읽은 쪽으로 답하고(`degraded` 에 남김), **둘 다 못 읽을 때만** 치명. ITS 월 호출 한도가 소진되면 2차가 못 읽는다(실측 2026-10-05) |
| 지하철 `N호선:역`(1~8호선) | `[2026-10-04]` **서울교통공사 지하철알림정보(15144070)로 무정차 통과를 감시한다**(`domains/travel_ops/ports/data_sources/subway_notice.py`). 그 호선·그 역을 말하는 **가장 최근 알림**의 제목이 「무정차」이고 종료어(종료·해제·재개·정상·복구·완료·해소)가 없으면 `skip_station`. 발생 3시간 뒤엔 진행 중으로 안 본다(끝 알림이 안 오는 경우). **한계**: 제목이 자유 텍스트라 역을 못 읽는 알림이 있다(과거 무정차 138건 중 42건 · 나열형은 마지막 역만) — 그래서 이 소스의 「사건 없음」은 「알림에서 못 찾음」이다(증거 등급 추정). 못 읽으면 `None`(치명 · 결정 15) |
| 버스 · 9호선 · 코레일/공항철도 등 서울교통공사 밖 노선 | **우리 코드에 연결된 실시간 소스가 없다.** 감시는 이 대상을 「사건 없음」이 아니라 **확인 못 한 대상**(`unsupported`)으로 센다. 후보: TOPIS 공지(버스 우회) `[미연결]` |

`[반영 2026-09-23]` 이 계약을 코드가 지킨다.
- ★**등록이 형식을 검사한다** — `POST /v1/trips`·`POST /v1/trips/plan`(`register:true`) 둘 다 같은 본문을 지난다.
  틀리면 **`422 invalid_route_uses`** 이고 `problems[]` 에 **틀린 값 전부**를 `route`·`option`·`value`·`reason`
  으로 싣는다(첫 하나에서 멈추지 않는다). **경고가 아니라 거절**로 정했다 — 받아 두고 경고하면 보낸 쪽이 모르고,
  모르는 채로 그 구간의 사건을 놓친다. 구현 `app/domains/travel_ops/components/itinerary/route_uses.py` ·
  시험 `tests/e2e/test_route_uses_contract.py`. 검사를 붙이기 **전에** 틀린 표기 셋(`잠실역`·`02호선:잠실`·
  `버스:성수동`)이 전부 **201 로 받아들여지는 것**을 먼저 봤다.
  ★**모양만 본다** — 그 역이 그 노선에 있는지, 그 번호의 버스가 실제로 있는지는 안 본다(우리 쪽에 노선 자료가 없다).
- 확정 시나리오를 맞췄다 — `버스:성수동` 두 곳 → `버스:2016`·`버스:2224`(+ `도로:아차산로`), `bus_sejong` 에
  `버스:7022`, 환승역 두 노선 각각(`을지로3가`·`충무로`), `도보:서울역` → `[]`. 번호·도로의 근거는
  [2026-09-23_경로_uses_표기_검사.md](../../records/evidence/2026-09-23_경로_uses_표기_검사.md).
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

`[실측]` `app/domains/travel_ops/entry/trip_api.py` · 저장 `pending_changes`(마이그레이션 024) · 결정 [D-020](../../../../wiki/decisions/D-020-trip-survey-and-ask-first.md).
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

**예보 주의와 변경 버튼** `[2026-10-09 사용자 지시]` — 감시 대상 활동의 강수확률·풍속이 설정한 주의 기준에 도달하면, 예보는 `advisories`로 유지하고 `proposal_request` 알림과 `reason: forecast_advisory` 제안을 함께 만든다. 확정 사건이나 조회 실패로 바꾸지 않는다. 알림은 관측한 예보 값과 원래 일정이 유지된다는 안내를 담는다. 앱은 같은 카드에 **「예보에 맞게 일정 변경」** 버튼을 보인다. 버튼은 기존 선택 API에 `{"key":"change"}`를 보내고, 그때 대체안을 계산해 같은 제안에 채운다(`forecast_advisory_options`, 응답 `status: options`). 후보를 선택한 뒤에만 일정을 변경한다. 유지·무응답·후보 없음이면 원래 일정이 유지된다. 자동 변경을 선택한 고객도 예보 주의만으로 자동 변경하지 않는다.

- 같은 여행·항목·기준 버전의 예보 제안은 한 번만 만든다. 이미 유지·만료한 제안도 반복해서 열지 않는다. 예보와 확정 사건 제안은 중복 방지 범위를 분리한다(DB 변경 059). 확정 사건이 생기면 열린 예보 제안은 `superseded`로 닫고 기존 사건 처리로 진행한다. 닫힌 예보 제안이 확정 사건·안전 알림을 막지 않는다.
- 고객 외부 알림이 꺼져 있거나 연결하지 않았으면 앱 알림으로 제공한다. 연결·발송 조건을 충족하면 기존 고객 채널로 같은 안내와 여행 링크를 보낸다. 메신저 안에서 일정 변경을 수행하지 않으며 앱에서 버튼을 누른다. 개발용 디스코드는 운영 리포트 용도다.
- 로컬 구현·검증 결과: [예보 주의 알림과 변경 버튼](../../records/reports/2026-10-09_2113_예보주의_알림과변경버튼.md). x600 서버의 cs 프로젝트 서버에는 아직 배포하지 않았다.


## 관계

- [REST 안내](index.md) — 계약 지도

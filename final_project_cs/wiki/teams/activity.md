---
type: plan
title: Activity Team
description: 여행지에서 하는 활동 전반(관람·체험·레저) — 정보를 제공하고 일정에서 성립하는지 판정한다. 깨지면 대체 후보를 낸다. MVP 셋(Activity·Dining·Mobility) 중 하나
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
domain: travel
---

# Activity Team

`[실측 2026-09-10]` **코드가 붙었다** — `app/modules/travel_ops/activity.py` **274줄**, capability 셋(`activity.check_cancelable`·`check_feasible`·`propose_change`), `knowledge_scope` 넷(`activity`·`cancellation`·`refund`·`weather`). 이 문서의 명세와 코드가 어긋나면 **코드를 고친다**(명세가 정본이다). `[정정 2026-09-10]` **「지금 어떻게 돼 있나」의 정본은 코드다** — 명세는 「무엇을 만들려 하나」의 정본이다. 어긋나면 어느 쪽이 틀렸는지부터 가린다. 이 문서도 manifest 절(`accepted_case_types`·`allowed_tools`)을 코드에 맞춰 고쳤다.

근거는 계획서 v11 §5. 여행 도메인 판올림(2026-09-08)으로 생긴 Team이다.

## 왜 이것이 첫째인가

`[실측]` v11 §5. 이유가 둘이다.

| | |
|---|---|
| 판정 규칙을 바로 쓸 수 있다 | **취소·변경 규정이 문서로 존재한다.** 우천 취소 규정 틀을 그대로 판정에 넣을 수 있다 |
| 실패 비용이 크다 | 예약금이 걸려 있다. 틀리면 돈이 날아간다 |

`[실측]` 뼈대는 쇼핑몰 `return_refund` 에서 가져온다 — 취소 기한·위약금율 판정이 구조가 같다.

## 무엇이 이 Team 의 상품인가

★**액티비티는 「여행지에서 하는 활동」 그 자체다.** `[사용자 확정 2026-09-09]`
레저만이 아니다 — **경복궁을 보러 가는 것도 액티비티**다.

| | |
|---|---|
| **다루는 것** | 일정의 **「무엇을 한다」 칸 전부** — 관람 · 체험 · 레저 · 공연 |
| **하는 일** | ① 그 활동의 **정보를 제공한다** ② 일정에서 그 활동이 **성립하는지 판정한다** |
| **예약은 조건이 아니다** | 경복궁은 예약 없이 간다. 그래도 **휴관일·운영시간·날씨**가 걸리므로 판정 대상이다 |

### 범위 — 관광 분류체계로 못박는다

`[팀원 제공 2026-09-10]` 말로 "활동 전반" 이라고만 두면 또 좁혀 읽는다. **외부 분류표에 걸어 둔다.**

★`[정정 2026-09-20]` 아래 A01~A04 표는 한국관광공사 관광정보 API의 **구(舊)분류체계**다. 관광공사가 2023년 개편한 **신분류체계**(대분류 10종)가 지금 근거이고, [팀 스프레드시트](https://docs.google.com/spreadsheets/d/1lCXbot4Ro0BUSnNHp7tVqn5ZXwW0A_xg/edit?gid=1765698897#gid=1765698897)의 `신분류체계정보 관광타입정보 연계 정의서`에서 가져왔다. 구분류 표는 매핑 대조용으로 아래에 남긴다.

| 기준 | Activity 가 맡는 대분류 (구분류, 참고용) |
|---|---|
| **한국관광공사 관광정보 API**<br>(`data.go.kr` 15101578) | **A01 자연** · **A02 인문**(문화/예술/역사) · **A03 레포츠** · **A04 쇼핑** |

### ★ [2026-09-20] 신분류체계 — 지금 근거

`[사용자 제공 2026-09-20]` 신분류체계 대분류 10종 중 Activity 가 맡는 것과 맡지 않는 것.

| 대분류코드 | 대분류명 | Activity 담당 | 왜 |
|---|---|---|---|
| NA | 자연관광 | **담당** | 구분류 A01 자연과 동일 — 산·하천·해양·생태·자연공원 |
| HS | 역사관광 | **담당** | 역사유적지·유물·종교성지·안보관광지. **경복궁이 여기 들어온다**(HS01 역사유적지 · 고궁) |
| VE | 문화관광 | **담당** | 랜드마크·테마공원·도시공원·공연시설·전시시설(박물관·미술관 포함). 구분류 A02 인문의 상당수가 여기로 재편됐다 |
| LS | 레저스포츠 | **담당** | 구분류 A03 레포츠와 동일 — 골프·스키·수상레저·항공레저 |
| EX | 체험관광 | **담당** | 구분류에 없던 축이다. 전통체험·공예체험·농산어촌체험·템플스테이·웰니스관광·산업관광이 여기 명시적으로 잡힌다 |
| SH | 쇼핑 | **담당** | 구분류 A04 쇼핑과 동일. ★**대형마트(SH03)가 정식 소분류로 있다** — 아래 「걸리는 것」의 "쇼핑 제외 목록에 대형마트가 있다" 미확보는 이걸로 닫힌다. 신분류체계에서 대형마트는 처음부터 쇼핑 정식 항목이라 제외 목록 자체가 잘못 짜인 것이었다 |

★**`accepted_case_types`·`knowledge_scope`는 아직 구분류 축으로 남아 있다**(아래 manifest 절 참고). 신분류체계로 갈아탈지, 두 축을 병기할지는 정해지지 않았다.

**Google Places API** `place types` 기준(참고용, 아직 유지):

| 갈래 | 유형 |
|---|---|
| 자연 | `beach` · `island` · `lake` · `mountain_peak` · `nature_preserve` · `river` · `scenic_spot` · `woods` |
| 인문·문화 | `historical_place` · `historical_landmark` · `castle` · `monument` · `cultural_landmark` · `tourist_attraction` · `museum` · `art_museum` · `history_museum` · `art_gallery` |
| 쇼핑 | `shopping_mall` · `department_store` · `market` · `flea_market` · `farmers_market` · `gift_shop` · `clothing_store` · `womens_clothing_store` · `jewelry_store` · `shoe_store` · `cosmetics_store` · `toy_store` · `tea_store` · `book_store` · `electronics_store` · `sporting_goods_store` · `sportswear_store` · `liquor_store` |

★`[미확보]` **이 분류는 확정이 아니다.** 쇼핑에서 제외한 **생활밀착형·저관광연관 21종**에
시나리오에 넣은 **대형마트**가 포함돼 있다. **제외 목록을 다시 봐야 한다** — 제외 기준이
"생활밀착"인데 관광객에게는 대형마트가 관광 목적지인 경우가 있다.

| 활동 | 걸리는 감시 소스 | 예약 |
|---|---|---|
| 골프(티타임) | 기상 · 예약 확인 | 필요 |
| 한강 수상 · 겨울 스키·눈썰매 | 기상 · 운영 공지 | 필요 |
| **경복궁 · 박물관 관람** | **운영 공지(휴관일)** · 기상(야외 동선) | **없어도 된다** |
| 공연·뮤지컬 | 취소 공지 | 필요 |
| 쿠킹 클래스 | 운영 공지 | 필요 |
| 테마파크 | 운영 공지 · 기상 | 날짜권 |

★**감시 소스가 활동마다 다른 것은 팀을 쪼갤 이유가 아니다.** 항목마다 **해당하는
소스만** 본다 — 실내 공연에 기상을 걸지 않고, 무료 관람에 위약금을 걸지 않는다.
Team 이 셋을 다 알고 있고 **항목이 어느 것에 걸리는지를 판정**한다.

### 활동의 범위 — 확정

`[사용자 확정 2026-09-09]` Activity는 **활동 그 자체**다. 레저로 좁히지 않는다. 경복궁 관람도 포함된다.

`[결정 2026-09-10]` v11 §5-D — Activity가 판정하고 새 업무 규칙을 만들지 않는다. 판정 입력은 「예약」이 아니라 「일정 항목」이다.

`[실측 2026-09-10]` 코드는 아직 이 결정을 따라가지 못했다 — 예약이 없으면 「모름」으로 끝난다(`activity.py:66,76,78`).

## 셋을 갖는다

모든 여행 Team이 같은 셋을 갖는다(v11 §5). Activity의 값은 이렇다.

### ① 검증 규칙 — 코드가 판정한다

| 무엇 | 판정 |
|---|---|
| 예약 시간 | 앞뒤 일정과 겹치는가. 이동 시간을 빼고도 남는가 |
| 운영일 | 그날 문을 여는가. 휴무·시즌 종료인가 |
| 인원 | 예약 인원과 일행 수가 맞는가. 최소 인원 미달인가 |
| 날씨 조건 | 우천·강풍 취소 조건에 걸리는가 |
| 취소/환급 규정 | 지금 취소하면 얼마가 돌아오는가. 무료 취소 구간이 언제 끝나는가 |

**LLM을 부르지 않는다.** v11 §4-D — 계산으로 판정 가능한 것은 코드가 한다.

`[실측 2026-09-20]` **입력 JSON의 필수값이 빠졌을 때 동작이 정식 테스트로 고정됐다** — `tests/unit/travel/test_activity_input_validation.py`(8건).

| 없는 값 | 결과 |
|---|---|
| `booking`(일정) 자체 | escalate, `unknown_예약 내역` |
| `starts_at`(시각) 누락·타입 오류 | escalate, `unknown_예약 시각` |
| `policy`(규정) | escalate, `unknown_취소·환급 규정` |
| `place`(장소) — `None` | **escalate 안 함.** `feasible: True` 유지, `place_confirmed: False`로만 표시하고 계속 진행 |
| `party_size`·`capacity` | 정원 초과 검사만 건너뛰고 계속 진행 |

★**경계 케이스 하나를 있는 그대로 고정해 뒀다** — `place`가 `None`이 아니라 **빈 dict `{}`**면 `place_confirmed: True`로 찍힌다(`place is not None`만 보는 코드라서). 필드가 하나도 없어도 "확인됨"으로 잡히는 셈이다. 옳고 그름을 판정하지 않고 **지금 이렇게 동작한다**는 사실만 테스트로 남겼다 — 스키마를 더 엄격히 검사할지는 별도 결정이다.

### `weather_sensitive` — DB가 모르면 장소명으로 추정한다

★★★`[구현 2026-09-20]` **실 데이터에서 이 컬럼은 영원히 `NULL`이다.** TourAPI가 실내/실외 필드를 안 주고(어떤 응답에도 그런 필드가 없다), `places`에 실제로 값을 쓰는 프로덕션 경로 자체가 없다(`scripts/seed_travel.py` 말고는 `INSERT INTO places`가 저장소 어디에도 없다 — 2026-09-20 실측). 사용자가 이걸 확인하고 "title 기준으로 실내·실외 판별 알고리즘을 새로 작성"하라고 결정했다.

`ActivityTeam._weather_sensitive_from_title(name)` — DB 값이 `None`일 때만 불린다. DB에 이미 값이 있으면(`True`/`False`) 이름은 아예 안 본다.

| 갈래 | 키워드 |
|---|---|
| 실외(`True`) | "옥상"·"광장"·"공원"·"거리"·"운동장" |
| 실내(`False`) | "층"(정규식 `\d+층`/`\d+F`/`B\d+`)·"홀"·"실내"·"전시실" |
| 모름(`None`) | 단서 없음, 또는 양쪽 다 걸림(예: "○○공원 전시홀") — **억지로 고르지 않는다** |

★**추정했다는 사실을 숨기지 않는다.** DB 확정값이 아니라 이름으로 추정해서 기상을 조회했으면 근거(`activity.weather_sensitive_from_title`)와 경고("실내·실외를 장소명으로 추정해 날씨를 조회했다 — DB에 확인된 값이 아니다")를 반드시 남기고, `decisions.weather.weather_sensitive_guessed_from_title`에 `true`를 찍는다.

`[실측 2026-09-20]` **정식 테스트** — `tests/unit/travel/test_activity_weather_sensitive_guess.py`(17건): 사용자가 준 키워드 예시 전부(parametrize), 상충 케이스, DB 확정값이 있으면 이름을 안 보는지, DB가 모를 때만 추정하고 그 사실을 공개하는지, 단서가 없으면(`경복궁`) DB가 몰라도 억지로 기상을 안 부르는지.

### ② 감시 소스

| 소스 | 무엇을 본다 | 상태 |
|---|---|---|
| 운영 공지 | 휴무·시간 변경·시즌 종료 | **닫힘 — `[확정 2026-09-20]`** `Activity_모듈_스펙.md`가 출처를 **TourAPI**(운영 여부)·**재난문자API**(재난상황)로 확정했다. 소스·조회 시점·재검토 주기까지 정해졌다 → [TourAPI·재난문자API 연동](#tourapi--재난문자api-연동-확정) |
| 기상청 초단기예보 | 우천·강풍 | `[정정 2026-09-20]` `Activity_모듈_스펙.md`가 **날씨 조회를 현재 구현 범위에서 뺐다.** 9절(추후 확장)로 이동 — 지금 `check_feasible` 판정 순서엔 없다. `knowledge_scope`의 `weather`는 아직 이 정정을 안 반영했다(manifest 절 참고) |
| 예약 확인 | 예약이 아직 유효한가 | Mock 허용 |

★**②가 이 Team의 가장 큰 미확보였다.** 판정 규칙은 규정 문서로 만들 수 있지만, "오늘 그 업체가 쉰다"를 아는 경로가 없으면 감시가 성립하지 않았다 — TourAPI·재난문자API 확정으로 경로 자체는 생겼다. 남은 건 세부 사양(§ 아래 미정 항목들)이다.


### ★ [2026-09-10] 감시 소스는 넓은 것부터 좁은 것으로

`[결정 2026-09-10]` v11 §7-C — **업체를 먼저 뚫지 않는다.** 어느 장소에나 통하는 공개 소스에서 시작해 덮이는 범위를 넓혀 간다.

| 단계 | 무엇을 본다 | 덮는 범위 | 상태 |
|---|---|---|---|
| **1** | **공개 API** — 기상 · 관광정보(운영시간·휴무) · 장소 · 이동 | 서울의 거의 모든 항목 | **이미 쓴다** |
| **2** | **공개 사이트·공지** — 개별 시설의 휴관·운영 변경 | 표본을 뽑아 늘린다 | 도시가 정해져 **시작할 수 있다** |
| **3** | **업체 정보** — 공급자가 주는 변경 | 협약한 곳만 | **MVP 밖** |

★**1단계만으로 루프가 증명된다.** 대표 시연이 기상 하나로 돈다 — **2단계가 없다고 시연이 막히지 않는다.** 다만 "실제 운영 변경을 잡는다"는 주장은 2단계까지 가야 선다.

★**커버리지를 세어서 말한다.** "공지를 수집한다"가 아니라 **서울 표본 N곳 중 몇 곳이 어느 단계로 덮이나**를 적는다. **분모를 안 밝히면 커버리지가 아니다.**

★**못 덮는 것은 Mock 으로 증명하고 그렇게 표시한다.** Mock 이벤트로 돈 루프를 "실제 운영 변경을 감지했다"로 말하지 않는다.

`[미확보]` 2단계의 대상 목록과 수집 방식은 표본 조사 결과로 정한다.

### ③ 재계획 후보

| 후보 | 언제 |
|---|---|
| 같은 시간대 대체 | 같은 종류의 다른 액티비티가 그 시간에 가능할 때 |
| 날짜 이동 | 같은 액티비티를 다른 날로 옮길 수 있을 때 |
| 환급 안내 | 대체가 없고 취소가 유리할 때 |

**후보 생성은 LLM이 하고, 생성한 후보는 ①을 다시 통과해야 통지된다**(v11 §5). 판정을 건너뛴 대안은 나가지 않는다.

`[실측 2026-09-10 작업 트리]` **LLM 후보 생성은 아직 없다.** `_propose_change()`(`activity.py:232`)는 대안을 만들지 않는다 — 받은 예약에 `activity.change` 제안 하나(`booking_id`·`reason`)를 만들어 승인 대기에 올린다. 그래서 무예약 활동은 이 경로로도 제안을 못 만든다(아래 대조 표 절과 같은 문제).

★`[실측 2026-09-20]` `Activity_모듈_스펙.md` §3-3 — 더 근본적인 문제가 하나 더 있다. **분류 경로가 `activity.propose_change`에 아예 도달하지 못한다.** 분류된 intent(`itinerary_submit` 등)가 이 Team의 capability 네임스페이스와 매칭되지 않아서, 지금 분류 경로는 항상 기본 capability(`activity.check_feasible`)만 고른다(`registry.py:115~119`). LLM 후보 생성이 없는 것과는 별개로, **애초에 변경 제안 경로 자체가 선택되지 않는다.** `[정정 2026-09-20]` **`itinerary_submit` 쪽은 아래 절에서 닫혔다** — `propose_change`(기존 예약 변경)와는 다른 별도 capability(`submit_itinerary`, 신규 일정)로 받기로 했다. `propose_change` 자체의 라우팅 미도달은 아직 안 고쳤다.

## 일정 제출 — 예약 없이 시작하는 capability

★★★`[구현 2026-09-20]` **`itinerary_submit`이 100% escalate 되던 문제를 고쳤다.** 사용자가 "뭐부터 해야 돼?"로 순서를 물어서 설계→구현까지 이어졌다.

### 실측 — 고치기 전엔 무슨 일이 있었나

고객이 "화요일에 경복궁 갈 거야"라고 하면: 분류기가 `intent="itinerary_submit"`·`issue_code="activity_*"`를 뽑고 → `issue_code` 접두로 ActivityTeam까지는 라우팅되는데 → `capability_for()`가 `intent`를 이름으로 못 맞춰서(`activity.*` 네임스페이스와 `itinerary_submit`이 안 겹침) 항상 `default_capability="activity.check_feasible"`을 고르고 → `check_feasible`이 `read.booking`부터 불러 **당연히 없는 예약**을 찾다가 → `unknown_예약 내역`으로 **무조건 escalate**됐다. `wiki/teams/Activity_모듈_스펙.md`(삭제됨, 2026-09-20)가 처음 지적한 문제의 실제 재현 경로다.

### 결정 — Phase 1 범위로 좁힌다

`[결정 2026-09-20]` 이 시스템 전체(`activity.change` 포함 **모든** action type)가 "승인해도 실제로 실행하는 코드가 없다"는 걸 확인했다 — `scripts/run_outbox_worker.py`의 `publish()`가 `"Transport is intentionally an injected boundary in Phase 1"`이라고 명시한 no-op 스텁이다. `/v1/cases/{id}/actions/{id}/approve`도 Case 상태만 `approved`로 바꿀 뿐, `action_type`별 실행기는 어디에도 없다. **그래서 일정 제출도 같은 성숙도에 맞춘다 — `ActionProposal`까지만 만들고, 실제 `activities`/`places` INSERT는 만들지 않는다.** 더 넓게(이 흐름만 실제로 쓰게) 갈지는 사용자가 명시적으로 거절했다 — Activity 하나의 문제가 아니라 시스템 전체의 실행 계층이 필요한 일이라서다.

### 구현

- **manifest**: `capabilities`에 `activity.submit_itinerary` 추가. `allowed_tools`에 `read.place_search` 추가
- **라우팅**: `ActivityTeam.select_capability(intent, input_text)` 신설(`registry.py:105~114`의 기존 훅 — `mobility.py`가 선례) — `intent == "itinerary_submit"`이면 이 capability를 고른다. **코어(`registry.py`)는 한 줄도 안 고쳤다**
- **`execute()` 분기**: 이 capability만 `read.booking`을 부르기 **전에** 갈린다(`activity.py` `execute()` 상단) — 나머지 셋은 예약이 있다고 전제하는 공통 경로를 그대로 탄다
- **`read.place_search`(신규 도구, `read_tools.py`)**: `place()`(이미 아는 `place_id`로 우리 DB 조회)와 다르다 — **아직 모르는** 장소를 이름으로 TourAPI에서 찾는다. `tour_api.py.find()`를 그대로 감싼다. 정확일치 1건이 아니면(동명이인 등) 확정하지 않고 `None`(013이 겪은 문제 재발 방지)
- **`_submit_itinerary()`**: `current_state`에서 `requested_place_name`·`requested_activity_time`을 읽는다(고객 문장을 이 Team이 직접 파싱하지 않는다 — 그건 분류·추출 계층의 몫). 장소를 찾으면 `activity.submit`(`risk="low"`, `activity.change`의 기본값 `high`보다 낮다 — 고객 자기 입력이라 위험도가 낮다는 판단) 제안을 만들어 `WAIT_FOR_APPROVAL`. 못 찾으면(애매함 포함) **사람에게 escalate하지 않고** `WAIT_FOR_INPUT`으로 고객에게 되묻는다 — 계약에 선언만 되고 아무도 안 쓰던 `required_input_schema`의 **첫 실사용 사례**

★**회귀로 걸린 것 하나**: 장소를 못 찾으면 `read.place_search`가 `None`을 줘서 `_evidence()`가 근거를 안 쌓는데, `WAIT_FOR_INPUT`은 `answer`가 있으면 근거가 최소 1건 있어야 한다(계약 검증). 고객이 실제로 제출한 값(`requested_place_name`·`requested_activity_time`) 자체를 `case.current_state` 근거로 남겨서 해결 — "검색이 실패했다고 근거까지 사라지면 안 된다."

`[실측 2026-09-20]` **정식 테스트** — `tests/unit/travel/test_activity_submit_itinerary.py`(11건): 라우팅 훅 3건, `read.booking` 미호출 회귀 가드 1건, 필수값 누락 3건, 정상 제안 2건, 장소 미매칭 2건(위 근거 회귀 가드 포함).

## TourAPI · 재난문자API 연동 (확정)

`[확정 2026-09-20]` `Activity_모듈_스펙.md` — `check_feasible` 판정 순서에 신규 조회 둘이 들어간다. 날씨 조회는 여기 없다(위 ②감시 소스 표 참고 — 현재 구현 범위 아님, 9절로 이동).

### 판정 순서

1. **정원 확인** — 정원 초과 시 즉시 `feasible: False`로 RESPOND (`activity.py:107`, `131~136`)
2. **장소 확인(TourAPI 조회)** — 운영시간·휴무 **원문** 확인. `[구현 2026-09-20]` 아래 참고
3. **재난문자API 조회** — 재난상황 없는지 감지. **세부 사양 미정**

> `[미확보]` 이 순서(정원→TourAPI→재난문자)가 판정 로직상 타당한지는 세부 설계 시 재검토가 필요하다고 스펙 문서 자체가 표시하고 있다.

★★`[정정 2026-09-20, 재정정]` 앞서 이 절은 "TourAPI 클라이언트가 `scripts/seed_travel.py`와 테스트에서만 쓰인다"고 적었다 — **이것도 부정확했다.** `app/infrastructure/travel/base.py`의 `build_travel_sources()`가 이미 `sources.place = TourApiPlace(...)`로 조립하고 있었고, `composition.py:160~163`이 그걸 `ReadToolbox(travel=...)`에 실제로 주입한다. **빠진 건 클라이언트도 배선 진입점도 아니라, `ReadToolbox.place()`(=`read.place` 도구)가 그 `self.travel.place`를 안 쓰고 있었다는 것 하나였다.**

**`[구현 2026-09-20]` 그 한 곳을 이었다.** `app/tools/read_tools.py`의 `place()`가 이제 `places.source_content_id`/`source_content_type_id`(013으로 해소된 신원)가 있으면 `self.travel.place.operating(content_id, content_type_id)`를 불러 `place["operating"]`에 담는다(`_fill_operating()`). `activity.py`의 `_check_feasible()`이 이 값을 근거(`read.place.operating`)와 안내 문구(`_operating_note()`)로 쓴다. `tour_api.py`의 `operating()`이 애초에 `usetime_text`·`restdate_text`를 자연어 원문으로만 주고 `answers_open_at_slot: False`로 명시한다(파싱하면 "화요일 휴무, 단 공휴일과 겹치면 개방" 같은 예외 조건에서 하나 틀려도 고객이 문 닫힌 곳 앞에 선다). `read.weather`가 강수확률·풍속을 판정에 안 쓰는 것과 같은 원칙이다.

새 도구 이름을 안 만들었다 — `allowed_tools`(`read.place`)·budget 변경이 필요 없다.

라이브 DB에 `place()`의 새 SQL을 직접 실행해 스키마와 맞음을 확인했고, 가짜 TourAPI 소스로 `_fill_operating()`·`_operating_note()` 경로를 확인했다. 기존 테스트 304개는 그대로 통과(무관한 사전 실패 3건은 이 DB에 prompt 미등록 때문).

### 휴무 요일 대조 — 유일한 예외

★★`[결정 2026-09-20]` **위 "`feasible`을 이 값으로 바꾸지 않는다"에 예외가 하나 생겼다.** 처음엔 원문 전체를 절대 파싱하지 않기로 했었다(그래서 회귀 가드 테스트까지 만들었다). 그런데 사용자가 "화요일에 요청하면 false가 나와야 한다"는 구체적 기대를 냈고, 그건 정확히 그 원칙과 부딪혔다 — 다시 확인했더니 **"요일 하나만 좁게 비교하고, 예외 조건은 절대 반영하지 않으며, 반영 안 했다는 사실을 안내문에 반드시 남긴다"** 는 조건으로 좁혀서 만들기로 정했다("전체 파싱" 대신 "요일 하나"를 선택 — 세 방향 중 가장 좁은 것).

`_weekday_closure_match(restdate_text, at)`(`activity.py`)가 하는 일 전부:

```
weekday_name = <요청 시각의 요일>
return weekday_name in restdate_text and "휴무" in restdate_text
```

| 결과 | 의미 | `decisions["feasible"]` |
|---|---|---|
| `True` | 요청 요일이 정기휴무 요일과 같은 문구가 원문에 있다 | `False`로 바뀜 + 캐비앗 문구 필수 |
| `False` | `restdate_text`는 있지만 요일이 안 맞는다 | 안 바뀜(`True`) |
| `None` | `restdate_text` 자체가 없다(모름) | 안 바뀜(`True`) |

`True`일 때 answer에 **반드시** 붙는 캐비앗: *"단, 이 판단은 요일만 비교한 것이고 공휴일과 겹치는 경우 같은 예외 조건은 반영하지 않았습니다 — 정확한 개방 여부는 원문을 직접 확인하세요."* 이 문장이 빠지면 "요일만 본 근사 판정"이 "확정 판정"처럼 보인다 — 그래서 테스트(`test_a_real_place_on_its_closure_weekday_is_marked_infeasible_with_caveat`)가 이 문구 존재를 강제한다.

★**`usetime_text`는 여전히 절대 안 본다.** 오직 `restdate_text` 대 요일 하나뿐이다. 강수확률·풍속(날씨)도 여전히 안 본다 — 이 예외는 "휴무 요일 대조" 하나로 한정된다.

`[실측 2026-09-20]` **정식 테스트 파일** — `tests/unit/travel/test_activity_tour_operating.py`(6건, `test_activity_weather.py`와 같은 패턴). `FakeTools`로 `read.place` 응답에 `operating` 서브딕트를 직접 넣어 API 키·DB·네트워크 없이 검증한다. `DEFAULT_STARTS_AT`을 고정 시각(2026-10-03, 실측 토요일)으로 박아 뒀다 — 상대 시각(`in_hours`)을 쓰면 테스트 실행일이 우연히 화요일일 때 무관한 테스트가 이유 없이 깨지는 flaky 버그가 생기기 때문이다.

| 테스트 | 확인하는 것 |
|---|---|
| `test_free_text_closure_without_a_weekday_pattern_does_not_flip_feasibility` | "매주 &lt;요일&gt; 휴무" 패턴이 아닌 휴무 문구는 여전히 무시된다(회귀 가드) |
| `test_a_real_place_on_a_non_closure_weekday_stays_feasible` | 경복궁·토요일 — 요일 안 맞음, `feasible: True` |
| `test_a_real_place_on_its_closure_weekday_is_marked_infeasible_with_caveat` | 경복궁·화요일 — `feasible: False`, 캐비앗 문구·경고 필수 |

★`[정정 2026-09-20]` **재난문자API 클라이언트는 여전히 없지만("코드 0줄"), 배선과 판정 함수는 생겼다.** 아래 절 참고 — 클라이언트 부재와 "check_feasible이 재난문자를 볼 줄 안다"는 별개다(TourAPI가 처음 그랬던 것과 같은 구도).

참고로 `activity.check_cancelable`(취소 가능 여부)은 **위약금율이 확인되지 않으면 금액을 생성하지 않는다**(`activity.py:94`) — 근거 없는 숫자를 만들지 않는다는 이 Team의 원칙(아래 「이 Team이 하지 않는 것」)과 일치하는, 이미 지켜지고 있는 동작이다.

### 재난문자 등급 대조 — `check_feasible` 배선

★★`[구현 2026-09-20]` 휴무 요일 대조와 같은 날, **두 번째 예외**가 생겼다. `app/tools/read_tools.py`에 `disaster()` 도구를 신설했다(`weather()`와 같은 패턴 — 좌표·시각을 받아 `self.travel.disaster.near(...)`에 위임). `allowed_tools`에 `"read.disaster"`, `knowledge_scope`에 `"disaster"`를 추가했다(manifest 절 참고). `app/infrastructure/travel/base.py`의 `TravelSources`에 `disaster` 슬롯도 추가했다.

### 실제 클라이언트 — `disaster_msg.py` (실 키 미검증)

★★★`[구현 2026-09-20, 같은 날 이어서]` **클라이언트 자체도 생겼다** — `app/infrastructure/travel/disaster_msg.py`(`DisasterMsgSource`). 하지만 `tour_api.py`(313줄, "실측 2026-09-10, 실 키로")와 격이 다르다 — **API 키를 발급받지 못해 실제 호출을 한 번도 못 해 봤다.** 웹 조사로 확인한 것과 추정한 것을 코드 상단 docstring에 명시적으로 나눠 뒀다.

| | 확인됨 | 추정(미검증) |
|---|---|---|
| 근거 | 웹 검색 — 자매 API(대피소 DSSP-IF-00195)의 실제 코드 예제, 데이터셋 설명 페이지 | 자매 API 관례를 방어적으로 가정 |
| 기본 URL | `https://www.safetydata.go.kr/V2/api/DSSP-IF-00247` | — |
| 공통 파라미터 | `serviceKey`·`returnType=json`·`pageNo`·`numOfRows`·`rgnNm`(지역 필터) | 날짜 범위 필터 파라미터 이름 |
| 응답 모양 | 최상위 `body` 키 아래 **배열** | 오류 봉투(`header.resultCode`) 모양 |
| 필드명 | `SN`·`CRT_DT`·`MSG_CN`·`RCPTN_RGN_NM`·`DST_SE_NM`·`EMRG_STEP_NM`(013·016 설계와 일치) | `CRT_DT` 정확한 포맷(14자리로 가정) |

★**날짜 필터를 서버에 맡기지 않는다.** 서버 쪽 파라미터 이름을 확신 못 해서, `recent()`가 넓게 받은 뒤 **클라이언트 쪽에서 `CRT_DT`로 최근 것만 자른다**(`_recent_only`). 시각을 못 읽으면 걸러내지 않고 포함시킨다 — "모른다"를 "오래됐다"로 단정하지 않는다.

★★**`near(lat, lng, at)`가 위도·경도를 실제로 안 쓴다.** 이 API는 좌표가 아니라 지역명(`rgnNm`)으로 거른다 — `places`엔 지역명이 없어서 지금은 **전국**을 그대로 받는다. `_disaster_blocks()`가 "지역·주제 관련성을 확인하지 않는다"고 경고하는 게 판단이 아니라 **이 API의 실제 구조적 한계**라는 뜻이다 — 역지오코딩이 생기기 전까지는 못 좁힌다.

키 설정: `ACOP_DISASTER_API_KEY`(`.env.apikeys.example`). `[미확보]` 공통 키(`ACOP_DATA_GO_KR_KEY`)로 되는지, safetydata.go.kr 가입이 별도로 필요한지 확인 안 됐다. `build_travel_sources()`가 키 없으면 `unavailable["disaster"]`에 이유를 남기고, 있으면 `DisasterMsgSource`를 조립한다.

가짜 HTTP 전송으로 검증한 것(실제 네트워크 없이): 정상 응답 파싱·오류 봉투 감지(`resultCode≠00`)·오래된 메시지 필터링·`region_name`→`rgnNm` 전달 — 전부 확인. **실 키로 첫 호출을 해본 뒤에야 위 "추정" 칸이 "확인"으로 넘어간다.**

`activity.py`의 `_disaster_blocks(messages)`가 판정 함수다.

```
EMRG_STEP_NM in {"위급재난"}  →  True (막는다)
그 외(긴급재난·안전안내)      →  False (근거로만 전한다)
```

★**"몇 단계부터 막을지"가 오래 미확보였는데, 가장 보수적인 쪽(최고 등급 하나)으로 좁혀서 닫았다.** 휴무 요일 대조와 같은 이유 — `MSG_CN`(메시지 본문)은 자연어라 통으로 해석하지 않는다. **더 중요한 한계 하나**: 이 함수는 **지역·주제 관련성을 전혀 확인하지 않는다.** "위급재난" 문자가 인근에 있다는 사실 하나만으로 막고, "미세먼지 위급재난"이 야외 활동과 실제로 관련 있는지, "서울 전역"이 아니라 다른 구(區) 얘기인지는 안 본다. 그래서 막힐 때는 캐비앗 문구("지역·주제가 이 활동과 실제로 관련 있는지는 확인하지 않았습니다")를 answer에 **반드시** 붙인다.

날씨(`weather_sensitive`에만 걸림)와 달리 **재난문자는 실내외를 안 가리고 항상 조회한다** — 재난은 장소 종류와 무관하다.

`[실측 2026-09-20]` **정식 테스트** — `tests/unit/travel/test_activity_disaster.py`(5건). `FakeTools`로 `read.disaster` 응답을 직접 넣어 API 키·DB·네트워크·실제 클라이언트 없이 검증한다.

| 테스트 | 확인하는 것 |
|---|---|
| `test_critical_disaster_blocks_feasibility_with_caveat` | "위급재난" 1건 → `feasible: False` + 캐비앗·경고 필수 |
| `test_lower_grade_messages_are_surfaced_but_do_not_block` | "긴급재난"·"안전안내" → 근거로만 전함, `feasible` 안 바뀜 |
| `test_no_disaster_messages_says_none_confirmed` | 목록이 빈 배열이면 "없다"고 정직하게 답함(모름과 구분) |
| `test_no_disaster_source_does_not_claim_it_was_checked` | 소스가 `None`(지금 실제 상태)이면 아무 말도 안 만듦 |
| `test_disaster_tool_is_not_even_declared_in_the_fake_when_omitted` | 옛 테스트가 `read.disaster` 키를 안 줘도 안 죽음(하위 호환) |

### 현재 장소 변경 감지 가능한 목록 (확장 예정)

`[확정 2026-09-20]` `Activity_모듈_스펙.md` §3-4.

| 번호 | 감지 항목 | 담당 API |
|---|---|---|
| 1 | 운영하는지 | TourAPI |
| 2 | 재난상황 없는지 | 재난문자API |

### 하루 기준 감지 시점

| API | 감지 시점 | 방식 |
|---|---|---|
| TourAPI | ① 전날(D-1) 24시간 전 1회 | 전체 일정 일괄 체크 |
| TourAPI | ② 당일 활동 시작 시각 기준 | 활동마다 독립적으로 체크 |
| 재난문자API | 5분 간격 | 폴링 |

### 검토 주기 원칙

- **가까운 일정만 재검토한다.** 하루 전체를 상시 재검토 대상으로 두지 않고, 활동 시작 시각이 임박한 것만 좁혀서 확인한다.
- **재난상황 감지는 활동 시작 3시간 전부터 5분 간격으로 좁혀서 재검토한다.** 3시간보다 먼 활동은 이 주기의 대상이 아니다.

★위 둘은 층이 다르다 — "하루 기준 감지 시점"의 재난문자API 5분 간격은 **기본 폴링 주기**이고, "검토 주기 원칙"의 3시간은 **그 폴링을 언제부터 활동에 적용하는지**를 좁힌다. `due_activities()`(`watch.py`)가 이 3시간 필터를 쿼리에 직접 반영해 구현했다.

**확정**: 재난문자 API는 이벤트 푸시(웹훅)를 지원하지 않는다. 5분 폴링이 유일한 방식이고, 웹훅 대체는 더 이상 검토 대상이 아니다.

### 사용 필드 · DB 연계

| API | 사용 필드 (확정) | 대응 테이블 | 실패/누락 처리 |
|---|---|---|---|
| TourAPI | `contentid`·`contenttypeid`·`title`·`addr1`·`mapx`·`mapy`·`lclsSystm1`·`lclsSystm2`·`lclsSystm3` (9개) — 카탈로그(`tour`)용. **판정 경로**는 `operating()`의 `usetime_text`·`restdate_text` 원문을 쓴다(`[구현 2026-09-20]`, `places` 테이블에서 신원 해소) | `tour` / `places` | 운영 정보 없으면 `read.place`가 `place["operating"]`을 안 채운다(013과 같은 "모름" 패턴). 「알려진 결함」①(장소 정보 자체가 없을 때 경고 후 성립)과는 별개 |
| 재난문자API | `[미확보]` 조사 자료(`SN`·`CRT_DT`·`MSG_CN`·`RCPTN_RGN_NM`·`DST_SE_NM`·`EMRG_STEP_NM`) 중 판정 조건으로 쓸 필드 미확정 | `disaster`(원본 저장) + `watch_observations`(활동별 관련성, `[결정 2026-09-20]` 아래 「재난문자 관련성」절) | `[미확보]` 판정 기준(긴급단계 몇 단계부터 `feasible: False`인지)도 함께 미정 |

★**신규 조회 실패 처리에서 기존 결함 패턴을 반복하지 않는다.** 아래 「알려진 결함」①·③이 "정보 부재를 성립으로 넘기는" 패턴이다 — TourAPI·재난문자API 설계 시 같은 패턴을 또 넣지 않도록 주의가 필요하다(스펙 문서 자체의 경고).

`[미확보]` 신규 조회 결과(TourAPI·재난문자API)가 Case 상태에 저장되는지도 안 정해졌다 — Controller가 실제로 저장하는 `TeamResult` 필드는 `answer`·`evidence`뿐이고 `warnings`·`decisions`·`confidence`는 저장되지 않는다(`controller.py:353~354`). 신규 조회 결과도 이 제약을 그대로 따를지 별도 저장 경로가 필요한지 확인이 필요하다.

`[미확보]` 재난문자 캐시를 파일럿 도시 단위로 공유해 중복 호출을 줄일지도 안 정해졌다.

## 알려진 결함 — 코드 실측

`[실측 2026-09-20]` `Activity_모듈_스펙.md` §2·§7·§9-2가 정리한, 기존 코드(`activity.py`) 기준 결함이다. 이 문서(activity.md)에 처음 옮긴다.

| 번호 | 결함 | 근거 |
|---|---|---|
| 1 | 장소 정보가 없어도 경고와 함께 성립으로 답한다 | `activity.py:159~164` |
| 2 | 시작 시각이 지난 예약도 성립으로 답한다 | `activity.py:81~83`, `162` |
| 3 | 취소·순연 규정·시각이 없으면 "모름"으로만 끝나고 판정하지 않는다 | `activity.py:78~83` |
| 4 | 주석의 "대안 생성만 LLM"이 실행 코드에 없다(문서-코드 불일치) | `activity.py:8~9`, `232~244` |
| 5 (참고, 날씨 — 현재 구현 범위 아님) | 예보 객체의 강수확률·풍속 값이 모두 비어도 `feasible: True` | `activity.py:208~211`, `160~180` |
| 6 | `read.booking`이 `case_id`를 무시하고 고객 예약 중 `starts_at`이 가장 이른 1건을 반환한다 — 종류·과거·취소 여부를 걸러내지 않는다 | `activity.py:66`, `read_tools.py:143~162` |

## 재계획이 다른 Team의 일정을 건드린다

날짜를 옮기면 그날의 식사·이동이 전부 흔들린다. 그런데 **Team은 다른 Team을 직접 호출하지 않는다**(승계 경계). 그래서 이렇게 된다.

```
Activity: "10/03 15시 → 10/04 10시" 후보를 낸다
   ↓ 후보는 제안이지 확정이 아니다
코어 검증 층: 전체 일정 정합성을 다시 본다 (시간 충돌·예산·이동 여유)
   ↓ 통과
통지
```

★**전체 일정 정합성은 Team이 아니라 코어 검증 층이 본다**(v11 §5). Activity는 자기 객체만 판정하고, 그 후보가 여행 전체에서 성립하는지는 코어가 판정한다. 이 경계를 흐리면 Team마다 전체 일정을 알아야 하고 Team 교체가 불가능해진다.

## manifest — 실제 구현

`[실측 2026-09-10 작업 트리]` `app/modules/travel_ops/activity.py`. **한때 이 절은 「제안이다. 코드에 없다」였다.**

```python
capabilities          = ["activity.check_cancelable",   # 지금 취소할 수 있나 · 위약금은 얼마인가
                         "activity.check_feasible",     # 이 시각에 이 활동이 성립하나
                         "activity.propose_change",     # 대안을 제안한다 (승인 대기)
                         "activity.submit_itinerary"]   # ★[2026-09-20] 신규 일정 제출 (승인 대기)
accepted_case_types   = ["activity"]                    # ★객체 종류다. 요청 종류가 아니다
required_context      = ["case_state", "policy", "db_facts", "history"]
allowed_tools         = ["read.booking", "read.policy", "read.place", "read.weather",
                         "read.disaster", "read.place_search"]  # ★[2026-09-20] read.place_search 추가
knowledge_scope       = ["activity", "cancellation", "refund", "weather", "disaster"]
max_steps             = 6
default_capability    = "activity.check_feasible"
```

★`[구현 2026-09-20]` `select_capability(intent, input_text)`도 추가됐다(`registry.py`의 기존 훅) — `intent="itinerary_submit"`이면 `activity.submit_itinerary`를 고른다. 이 manifest 테이블 자체는 안 바뀌지만 실제로 **어느 capability가 선택되는지**는 이 훅이 먼저 결정한다 → [일정 제출 절](#일정-제출--예약-없이-시작하는-capability)

★`[실측 2026-09-20]` `allowed_tools`·`knowledge_scope`에 `read.disaster`/`disaster`를 추가했다 — 아래 「걸리는 것」에 있던 "manifest가 신규 연동과 어긋난다"는 미확보 중 재난문자 쪽은 이걸로 닫혔다. `weather` scope 처리(날씨 조회가 판정 범위 밖으로 빠진 것과 manifest가 안 맞는 문제)는 아직 안 건드렸다.

★**`accepted_case_types` 가 「객체 종류」다.** 이 문서는 한때 `itinerary_submitted`·`incident_reported` 같은 **요청 종류**를 적어 뒀다. **축이 틀렸다.** v11 §5-B — 라우팅은 두 축이고 Team 을 고르는 것은 `case_type`(객체 종류, `issue_code` 접두에서 뽑는다)이다. 요청 종류는 `intent` 쪽이다.

★**요청 종류 다섯만으로는 여섯 팀 어디에도 안 간다** — 2026-09-09 실행으로 확인됐고 그래서 v11 이 축을 둘로 갈랐다.

`[정정 2026-09-10]` 「`allowed_tools` 이름을 안 정했다」는 낡았다 — 바로 위 manifest 에 넷(`read.booking`·`read.policy`·`read.place`·`read.weather`)이 붙어 있다. 그 전 서술 — `allowed_tools` 이름을 안 정했다. v11 §5-A가 정한 Action은 **장소·운영 조회 / 이동 시간 조회 / 기상 조회 세 개**이고 이름은 구현 때 붙인다. `accepted_case_types` 는 v11 §5-A의 새 분류 라벨(일정 제출 / 사건 신고 / 확인 요청 / 조정 거부 / 그 외)에서 왔다.

★`[미확보 2026-09-20]` TourAPI·재난문자API 연동이 확정되면서 `allowed_tools`·`knowledge_scope`가 이 manifest와 어긋나게 됐다. `read.place`가 TourAPI 조회를 대신하는지, 재난문자API용 새 도구(예: `read.disaster`)가 필요한지 안 정해졌다. `knowledge_scope`의 `weather`도 위 ②감시 소스 정정(날씨 조회는 현재 구현 범위 아님)과 어긋난다. **manifest를 코드보다 먼저 고친다**(RULE.md §3.5, Contract-first) — 지금은 어긋남만 적는다.

## 데이터 저장 — Activity 전용 스키마

`[실측 2026-09-20]` `데이터베이스_저장소_설계_v2.md`의 제안이 **마이그레이션으로 반영됐다** — `app/infrastructure/db/migrations/014_activity_tour_disaster.sql`. `activities`·`tour`·`disaster` 테이블이 이제 실제로 존재한다(재실행 안전 확인, `\d activities`·`\d tour`·`\d disaster`로 대조 완료).

★`[정정 2026-09-20]` 설계 원본에 없던 `tenant_id`를 세 테이블 모두에 추가했다 — 이 저장소의 도메인 테이블은 전부 tenant 격리를 쓰고(001_schema.sql, RULE.md §1), tenant_id가 없으면 격리 테스트를 통과하지 못한다. FK는 걸지 않았다(`places`·`place_catalog`와 같은 패턴).

대신 장소·감시 계열로 `places`·`place_catalog`·`watch_observations`·`watch_changes`가 이미 있다(`010_domain_travel.sql`~`013_places_source_identity.sql`) — 이 테이블들은 그대로 두고 건드리지 않았다.

### `activities` ↔ `places` 관계 — 결정

`[결정 2026-09-20]` `015_activities_place_link.sql`. **`activities.place_id`(nullable FK → `places.place_id`)가 canonical 링크다.** `activities.tour_api_content_id`는 뺐다.

**왜.** `places`(013)가 이미 TourAPI 신원 해소 결과를 들고 있다(`source_name`·`source_content_id`·`source_content_type_id`) — 013의 요지가 "해소는 한 번만 하면 된다, 그 다음부터는 id로 본다"였다. `activities`에 `tour_api_content_id`로 또 다른 TourAPI 식별자 칸을 두면 같은 신원을 두 곳에서 따로 해소하게 되고, 둘이 어긋날 수 있다 — 013이 막으려던 문제를 그대로 재현한다.

**역할을 가른다.** `activities` = 「언제·무엇을」(일정 사실). `places` = 「어디·그곳이 지금 어떤 상태인가」(장소 사실 — `weather_sensitive`·`hours_confirmed_at`·`open_at_slot` 등 판정에 쓰는 값이 이미 거기 있다). 장소 사실을 중복해 두지 않고 `place_id`로 참조한다.

`place_id`는 **NULL 허용**이다 — 무예약 활동은 아직 `places` 행으로 해소되지 않았을 수 있다(v11 §5-D). NULL = 「아직 해소 안 됨」이지 「장소가 없다」가 아니다.

### 재난문자 관련성 — `watch_observations`로 결정

`[결정 2026-09-20]` `016_activities_disaster_to_watch.sql`. `activities.disaster_api_content_id`는 뺐다. **재난문자 관련성은 정적 FK가 아니라 `watch_observations`의 관측으로 다룬다** — `target_kind='activity'` · `target_id=activities.id` · `source='disaster_api'`.

**왜.** TourAPI 신원(`place_id`)은 한 번 해소하면 안 바뀌는 값이지만, 재난문자 관련성은 **활동 시작 3시간 전부터 5분 간격으로 다시 보는 값**이다(위 「조회 시점·재검토 주기」). 발령→격상→해제처럼 여러 번 바뀔 수 있는데 정적 칸 하나로 덮어쓰면 이전에 뭘 봤는지가 사라진다. `watch_observations`(012)가 이미 이 모양(주기적 관측 append + `fingerprint`로 실질 변화만 `watch_changes`에 기록)이고, TourAPI·장소 감시가 `target_kind='place'`로 같은 인프라를 쓴다 — 감시 방식을 두 개로 쪼개지 않는다. `target_kind`를 `place`가 아니라 `activity`로 둔 이유는 재난 관련성이 장소가 아니라 **이 활동의 예정 시각(3시간 이내)**에 달려 있어서다.

FK는 걸지 않는다 — `payload`(jsonb)에 원본을 담고, 필요하면 그 안의 `SN`으로 `disaster` 테이블을 대조한다(TourAPI 관측이 `place_catalog`에 FK 안 거는 것과 같은 패턴).

★`[실측 2026-09-20]` **`due_activities()`·`tick_activities()`가 생겼다** — `app/modules/travel_ops/watch.py`. `due_places()`와 같은 구조(가장 오래전에 본 것부터, NULLS FIRST)이되, 재검토 주기 결정(3시간 이내)과 `place_id` 해소 여부를 쿼리에 직접 반영했다. `tick_activities()`는 `self.sources.disaster`에 duck-typed로 의존한다 — `source.name`·`source.near(lat, lng, *, within=activity_time)` 인터페이스만 정했고, **실제 재난문자API 클라이언트는 여전히 없다**(코드 0줄, 위 「알려진 결함」 참고). 라이브 DB에 대고 SQL 실행을 확인했다(빈 테이블에서 정상적으로 빈 결과).

`[미확보]` `affected_bookings`를 채우는 일은 안 했다 — 무예약 활동은 예약이 없고, 예약이 있는 경우 장소·시각으로 역추적하는 방법이 정해지지 않았다.

| 항목 | 값 |
|---|---|
| 저장소 | Supabase Postgres 하나로 여행 코어·액티비티 모듈을 함께 관리. 문서/KV 저장소는 현재 범위 밖 |
| 정규화 | 3NF 기준, 조회 성능이 중요한 일부만 의도적으로 반정규화 |
| ERD | `[미확보]` 내용 확정 때까지 비워둠(`데이터베이스_저장소_설계_v2.md` 3절) |

### 실제 `places` 테이블 — Activity 전용이 아니다

`[실측 2026-09-20]` **`places`는 Activity·Dining이 공유하는 장소 테이블이다.** `010_domain_travel.sql`의 `kind` 컬럼 주석이 이미 이렇게 적고 있다.

```sql
kind text NOT NULL,  -- activity / dining / lodging / flight
```

코드로도 확인된다.

| Team | `places` 사용 | 근거 |
|---|---|---|
| Activity | 사용 | `activity.py:138` — `read.place`를 `booking.place_id`로 호출 |
| Dining | 사용 | `dining.py:52~53` — 같은 패턴(`place_id`로 `read.place` 호출) |
| Mobility | **미사용** | `read.route`·`read.transit`만 쓴다(`mobility.py:25,51,57`) — "장소 하나"가 아니라 "구간 이동"을 판정해서 구조적으로 다르다 |

`watch.py:120`의 감시 루프도 `target_kind = 'place'`로 테이블 전체를 대상으로 돌지 특정 Team에 묶여 있지 않다 — Activity가 감시를 세팅해도 같은 장소가 Dining 예약에도 걸려 있으면 같이 덮인다.

**이 절의 `activities`/`tour`/`disaster` 제안 스키마와 실제 `places`를 섞어 읽지 않는다.** `places`는 이미 있고 쓰이고 있으며 Activity 전용이 아니다. 아래 제안 스키마는 **Activity 전용**이다 — 다음 절 참고.

### 제안 테이블 — Activity 전용

`[결정 2026-09-20]` **아래 `activities`·`tour`·`disaster` 세 테이블은 Activity Team 전용이다.** 위의 실제 `places`(Activity·Dining 공유)와는 별도 축이다 — 공유 여부를 다시 묻지 않는다. Dining·Mobility가 같은 데이터를 필요로 하면 별도 테이블을 새로 파거나 이 스키마를 확장하기로 그때 다시 정한다. 지금은 Activity가 유일한 소비자다.

★`[실측 2026-09-20]` 아래는 **최초 제안 당시** 모양이다. 015·016에서 `tour_api_content_id`·`disaster_api_content_id`를 뺐다 — 지금 실제 구조는 [`activities` ↔ `places` 관계 — 결정](#activities--places-관계--결정)과 [재난문자 관련성 — `watch_observations`로 결정](#재난문자-관련성--watch_observations로-결정) 두 절이 정본이다. 요약하면:

```
places (1) ──< activities        # place_id FK (015, nullable)
tour, disaster                   # activities 에서 FK로 안 묶인다. 원본 대조용 독립 테이블
watch_observations               # target_kind='activity' 로 재난문자 관련성을 관측(016)
```

| 테이블 | 역할 | 주요 컬럼(현재) | 소유 |
|---|---|---|---|
| `activities` | 고객이 입력한 일정 | `id`(uuid, PK) · `name` · `lat`/`lng` · `activity_time`(timestamptz) · `address`(nullable) · `place_id`(FK→places, nullable) | **Activity 전용** |
| `tour` | TourAPI 원본 저장(카탈로그) | `contentid`(text, PK) · `contenttypeid` · `title` · `addr1` · `mapx`/`mapy` · `lclsSystm1`/`2`/`3`(대/중/소분류 — [신분류체계](#-2026-09-20-신분류체계--지금-근거) 코드와 대응) | **Activity 전용** |
| `disaster` | 재난문자API 원본 저장 | `SN`(text, PK) · `CRT_DT` · `MSG_CN` · `RCPTN_RGN_NM` · `DST_SE_NM`(재해구분명, 34종) · `EMRG_STEP_NM`(긴급재난·안전안내·위급재난) | **Activity 전용** |

★**`tour.lclsSystm1/2/3`이 위 신분류체계 대분류·중분류·소분류와 같은 축이다.** 같은 스프레드시트에서 나왔다 — 이 절과 「범위」절의 분류표가 서로 다른 것을 가리키지 않는다.

★**판정 경로의 TourAPI 조회는 `tour`가 아니라 `places`를 거친다.** `[구현 2026-09-20]` `read.place`가 `places.source_content_id`(013)로 TourAPI `operating()`을 직접 부른다 → [배선 절](#판정-순서). `tour` 테이블은 카탈로그 동기화(`scripts/seed_travel.py`)용 원본 사본이지 판정 경로가 실시간으로 읽는 자리가 아니다.

## `business_subject` — 도메인이 바뀌어도 안 바꾸는 칸

`[정정 2026-09-10]` Team의 3단 폴백 값은 최종 멱등 키에 쓰이지 않고 Core가 `business_subject=str(case["case_id"])`로 다시 계산한다. `booking_id` 유무와 무관하게 같은 Case·같은 종류의 제안이 서로 다른 객체를 바꾸면 충돌할 수 있으므로 결함의 수정 위치는 Core다. 근거: `app/application/controller.py:371-374`(2026-09-10 실측). Team은 대상 id를 제안하고 서버는 예약이 있으면 `booking_id`, 없으면 `item_id`를 인자에서 꺼내 실재·소유를 확인한 뒤 최종 키에 쓰며, 대상을 특정하지 못하면 폴백하지 않고 거부해야 한다(v11 §4-E 미구현). 아래는 당시 Team 코드 관찰과 판단의 기록이다.

`[실측 2026-09-09]` `A-COP_여행Team모듈_구성안.md`. 도메인 객체 id 는 코어에 없다 — `customer_cases` 컬럼에도 `app/core/`·`app/application/` 코드에도 `order_id`·`booking_id` 가 **0회**다. 도메인 객체는 `idempotency_key(tenant_id, request_id, action_type, business_subject)` 의 `business_subject` **문자열 한 칸**으로 들어간다.

★**칸 이름을 `booking_id` 로 바꾸면 다음 도메인에서 또 바꿔야 한다.** 이름은 이미 중립이고 맞다. 정해야 하는 것은 규칙이다.

> **`business_subject` 에는 그 Action 이 바꾸는 대상 객체의 id 를 넣는다. 대상이 특정되지 않으면 실행하지 않고 escalate 한다.**

**`case_id` 폴백을 두지 않는다.** 폴백이 있으면 특정 실패가 조용히 넘어간다. 그리고 여행에서 실제로 터진다 — `request_id` 는 Case 당 하나라서, **한 Case 안에서 같은 종류의 작업을 두 객체에 하면 키가 같아진다.**

```
subject = case_id   →  같은 키    ← 둘째가 조용히 중복 처리되거나 막힌다
subject = 객체 id    →  다른 키
```

`[실측]` 쇼핑몰에서는 Case 하나가 대개 주문 하나라 잘 안 드러났다. 여행은 Trip 하나에 예약이 여럿이고 **"비가 온다" 는 사건 하나가 여러 예약을 동시에 바꾼다.**

### ★ [2026-09-09] 코드가 이 규칙을 안 지킨다

`[실측]` `app/modules/travel_ops/_base.py:169` — 여행 Team 공용 기반이 **3단 폴백**을 쓴다. `[정정 2026-09-10]` 위 「business_subject」 절의 정정 참조 — Team 코드 관찰이며 최종 키 결함 자리는 Core다.

```python
subject = str(arguments.get("booking_id") or arguments.get("trip_id") or task.case_id)
```

`[정정 2026-09-10]` 위 「business_subject」 절의 정정 참조 — 최종 키 결함 자리는 공용 기반의 상속이 아니라 Core다.

`[정정 2026-09-10]` 위 「business_subject」 절의 정정 참조 — 충돌은 `booking_id` 누락에 한정되지 않는다.

| 지금 | 문서가 정한 것 |
|---|---|
| Core의 최종 키 대상 고정 | `[정정 2026-09-10]` 위 「business_subject」 정정 참조 — 예약 없으면 `item_id`. |

`[실측]` 보낼 자리는 이미 있다 — 같은 파일의 `_unknown()` 이 "값이 없는 게 아니라 모르는 상태"를 escalate 로 보낸다.

`[정정 2026-09-10]` 이는 현재 코드의 관찰이며, 필요한 값을 모를 때의 현행 사양은 대체 소스로 값을 내고 대체까지 실패하면 서버를 끄되 근거 없는 문장은 만들지 않는 것이다(v11 §0-4 결정 15).

**코드 수정은 담당 세션 몫이다.** 이 문서는 어긋남만 적는다.

### ★ [2026-09-10] 계획서가 이 규칙을 받았다 — v11 §4-E

`[결정 2026-09-10]` **`[미확보]` 가 닫혔다.** 어제까지 "규칙을 계획서 §6 에 넣는 일이 남았다"고 적혀 있었다. v11 이 **§4-E 를 신설해** 정했다.

> **실행 요청의 멱등 키에 들어가는 「대상」은 서버가 정한다** — 인자에서 꺼내 **실재하는지·이 여행의 것인지 확인한 뒤** 키에 넣는다.

| 작업 종류 접두 | 꺼낼 인자 | 무엇인가 |
|---|---|---|
| `activity.*` | **예약이 있으면 `booking_id`, 없으면 `item_id`** | 예약 한 건 또는 일정 항목 하나 |

★**무예약 활동이 이 표를 고쳤다.** `[정정 2026-09-10]` 처음에는 `booking_id` 하나였는데 그러면 **무예약 활동의 변경 제안이 대상 없음으로 거부된다** — 경복궁 휴관을 알아채고도 일정을 못 고친다(v11 §5-D). **일정 항목에는 언제나 id 가 있으므로 「대상을 특정 못 하면 거부한다」는 원칙은 그대로 지켜진다.**

★**Team 이 준 값을 그대로 쓰지 않는다.** 코드 주석이 이미 그렇게 경계한다 — `controller.py:371` 의 *"The Team value is advisory. The server owns the final key at the write boundary."*

★**왜 Case 를 쪼개는 쪽을 택하지 않았나.** 다른 안은 "한 Case 에 같은 종류 작업은 하나"를 사양으로 못박는 것이었다. **비가 오면 액티비티·식당·이동이 한꺼번에 흔들린다** — Case 를 쪼개면 한 사건을 여러 Case 로 나눠 고객에게 따로 통지하게 되고, **DoD-8(거부하면 되돌린다)에서 어디까지 되돌릴지가 애매해진다.**

`[실측 2026-09-10]` **v11 §12 가 이것을 DoD-24 로 올렸다** — 「한 Case 에서 대상 객체가 다른 제안 둘이 각각 저장된다」. 문서 규칙이 아니라 검사 항목이 됐다.

`[미확보]` 위 규칙표를 코드에 둘지 `config/` 에 둘지는 안 정했다. **어휘는 설정으로 빼기로 했지만(v11 §5-B) 이건 계약에 더 가깝다.**

## ★ 두 번 다시 이렇게 부르지 않는다

`[실측]` 실제로 두 번 잘못 불렸다. 둘 다 **정의를 다른 데서 거꾸로 유도한** 것이다.

| 잘못 부른 것 | 왜 그렇게 됐나 | 맞는 것 |
|---|---|---|
| **결제·환불 팀** | 뼈대를 `return_refund`·`procurement_order_payment` 에서 베껴서 도해에 그렇게 그렸다(2026-09-09) | **뼈대 출처는 판정 구조를 어디서 베꼈나일 뿐 팀의 정체가 아니다.** `Activity(return_refund)` 처럼 붙여 부르지 않는다 |
| **레저 전용 팀** | 판정 규칙에 「날씨 조건」이 있으니 날씨 걸리는 것만 넣자고 좁혔다 | **규칙은 팀이 무엇을 보는지이지 팀이 무엇인지가 아니다.** 좁히면 경복궁·박물관·쇼핑이 갈 곳이 없다 |
| (같은 뿌리) **예약 있는 것만** | 취소·위약금 판정이 눈에 띄어서 | **예약은 조건이 아니다.** 경복궁은 예약 없이 가도 휴관일·운영시간이 걸린다 |

★**감시 소스가 항목마다 다른 것은 팀을 쪼갤 이유가 아니다.** 팀은 하나이고 셋을 다
알되 **이 항목이 어디에 걸리는지를 판정**한다. 그게 이 Team 의 일이다.

## 이 Team이 하지 않는 것

승계 경계 그대로다(v11 §6, [team-boundary.md](team-boundary.md)).

| 하지 않는다 | 왜 |
|---|---|
| 업체 예약을 직접 바꾸지 않는다 | side effect는 코어 Action 층이 한다. `ActionProposal` 로 돌려준다 |
| 다른 Team을 부르지 않는다 | 의존 그래프가 생기면 교체가 불가능해진다 |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |
| 전체 일정 정합성을 판정하지 않는다 | 코어 검증 층의 일이다 |
| 근거 없이 답하지 않는다 | 모든 핵심 주장에 `Evidence` 를 붙인다 |

## 걸리는 것

| 항목 | 상태 |
|---|---|
| ~~운영 변경 정보 출처~~ | **닫힘 — `[확정 2026-09-20]`** TourAPI·재난문자API로 확정 → [TourAPI·재난문자API 연동](#tourapi--재난문자api-연동-확정) |
| 취소·환급 규정의 원문 | `[미확보]` 업체마다 다르다. 표본을 몇 개까지 모을지 안 정했다. **골프장 우천 위약금 규정이 가장 문서화가 잘 돼 있어 여기서 시작한다** |
| ~~Activity 정의 (레저로 좁히나)~~ | **닫힘 — 좁히지 않는다.** `[사용자 확정 2026-09-09 · 팀원 분류체계 2026-09-10]` 활동 그 자체(관광공사 A01 자연·A02 인문·A03 레포츠·A04 쇼핑). 수요 비교는 **필요 없다** — 둘 다 액티비티다 |
| ~~쇼핑 분류의 제외 목록~~ | **닫힘 — `[정정 2026-09-20]`** 신분류체계(SH 쇼핑)에 **대형마트(SH03)가 정식 소분류로 있다.** 21종 제외 목록 자체가 구분류 임시안이었고, 지금은 신분류체계 대분류·중분류·소분류 표를 그대로 쓴다 → [범위 절](#범위--관광-분류체계로-못박는다) |
| 기상 조건 임계값 | `[미확보]` "우천이면 취소"의 판정선(강수량·풍속)을 규정에서 읽을 수 있는지 확인 필요. `[정정 2026-09-20]` 날씨 조회 자체가 지금 구현 범위 밖이라(②감시 소스 참고) 이 항목은 확장 시점까지 미룬다 |
| 골든셋 | `[실측]` 지금 골든셋 72건은 쇼핑몰이다. 이 Team의 시나리오는 0건 → v11 §8 |
| TourAPI·재난문자API 실패/누락 처리 | `[미확보 2026-09-20]` 정보 부재를 어떻게 처리할지 — 기존 결함(위 「알려진 결함」①·③, 정보 부재를 성립으로 넘기는 패턴)과 같은 실수를 반복하면 안 된다 |
| TourAPI·재난문자API 사용 필드·판정 기준 | `[미확보 2026-09-20]` 재난문자API는 어느 필드로 판정할지, 긴급단계 몇 단계부터 불가로 볼지 미정 |
| 신규 조회 결과의 Case 상태 저장 | `[미확보 2026-09-20]` Controller가 저장하는 `TeamResult` 필드는 `answer`·`evidence`뿐(`controller.py:353~354`) — TourAPI·재난문자API 조회 결과가 여기 실리는지 별도 경로가 필요한지 미정 |
| ~~제안 DB 스키마 vs 실제 마이그레이션~~ | **닫힘 — `[실측 2026-09-20]`** `014_activity_tour_disaster.sql`로 반영, 재실행 안전 확인 → [데이터 저장 — Activity 전용 스키마](#데이터-저장--activity-전용-스키마) |
| ~~`activities`↔`places` 관계~~ | **닫힘 — `[결정 2026-09-20]`** `activities.place_id`(nullable FK)가 canonical 링크. `015_activities_place_link.sql` → [관계 절](#activities--places-관계--결정) |
| ~~`activities.disaster_api_content_id`를 정적 FK로 둘지 관측으로 다룰지~~ | **닫힘 — `[결정 2026-09-20]`** `watch_observations`(`target_kind='activity'`)로. `016_activities_disaster_to_watch.sql` → [재난문자 관련성 절](#재난문자-관련성--watch_observations로-결정) |
| ~~`due_activities()`(watch.py 감시 루프 배선)~~ | **닫힘 — `[실측 2026-09-20]`** `due_activities()`·`tick_activities()` 구현됨 → [재난문자 관련성 절](#재난문자-관련성--watch_observations로-결정) |
| ~~재난문자API 실제 클라이언트~~ | **부분 닫힘 — `[구현 2026-09-20]`** `app/infrastructure/travel/disaster_msg.py` 작성·조립 완료. **단 실 키로 검증 안 됨**(키 발급 못 받음) → [재난문자 등급 대조 절](#재난문자-등급-대조--check_feasible-배선) |
| ~~재난문자 키가 공통 키(`data_go_kr_key`)로 되는지~~ | **닫힘 — `[확인 2026-09-21]`** data.go.kr 공통 키와 **별개다.** safetydata.go.kr 에 별도 가입·신청해서 발급받아야 한다. `ACOP_DISASTER_API_KEY` 설정 완료 |
| 재난문자 날짜·오류 봉투 파라미터/모양 추정치 | `[부분 닫힘 2026-09-21]` 실 키로 live 테스트 5/5 통과, 응답 구조·필드명·CRT_DT 포맷 확인 완료. **오류 봉투 모양**과 **서버 날짜 필터 파라미터**는 아직 미검증 — 정상 응답만 봤고 오류 케이스는 못 봤다 |
| 재난문자 "위급재난" 판정의 지역·주제 관련성 미확인 | `[미확보 2026-09-20]` `_disaster_blocks`가 등급만 보고 지역·재해구분은 안 본다 — 오탐(무관한 위급재난으로 막힘) 가능성이 남아 있다 |
| ~~TourAPI 클라이언트를 `check_feasible`에 배선~~ | **닫힘 — `[구현 2026-09-20]`** `read_tools.place()`가 `source_content_id`로 `operating()`을 불러 `place["operating"]`에 원문을 싣는다. `activity.py`는 원칙적으로 근거·안내 문구로만 쓰되, **휴무 요일 대조 하나만 예외**로 `feasible`을 바꾼다 → [휴무 요일 대조 절](#휴무-요일-대조--유일한-예외) |
| `tick_activities()`의 `affected_bookings` | `[미확보 2026-09-20]` 항상 빈 리스트다 — 예약과의 역추적 방법 미정 |
| `allowed_tools`·`knowledge_scope`와 신규 연동의 어긋남 | `[미확보 2026-09-20]` manifest 절 참고 — TourAPI·재난문자API용 도구 이름, `weather` scope 처리 미정 |
| ~~`itinerary_submit`이 100% escalate 되던 문제~~ | **닫힘 — `[구현 2026-09-20]`** `activity.submit_itinerary` + `select_capability` 훅 → [일정 제출 절](#일정-제출--예약-없이-시작하는-capability) |
| ~~Phase 2 — 승인된 `activity.submit` 제안을 실제로 `activities`/`places`에 반영하는 실행기~~ | **비전으로 등록 — `[결정 2026-09-20]`** 사용자가 "나중에 별도로 설계하자"고 명시적으로 미뤘다. Activity 하나의 범위를 넘는 시스템 전체(action_type dispatcher) 설계라 `wiki/records/vision/TODO_VISION.md`에 등록(RULE.md §4.4) |
| ~~`activity.propose_change`의 라우팅 미도달~~ | **닫힘 — `[구현 2026-09-21]`** `select_capability`에 `intent="adjust_reject"` → `activity.propose_change` 분기 추가. 테스트 2건(`test_activity_submit_itinerary.py`) |
| ~~`weather_sensitive`가 실 데이터에서 검증 불가~~ | **완화 — `[구현 2026-09-20]`** `_weather_sensitive_from_title()`로 이름 단서 추정(추정 사실은 항상 공개). **완전히 닫힌 건 아니다** — 키워드에 안 걸리는 장소(예: "경복궁")는 여전히 `None`이고, 근본 원인(프로덕션에 `places` 쓰기 경로 자체가 없음)은 그대로다 → [`weather_sensitive` 절](#weather_sensitive--db가-모르면-장소명으로-추정한다) |

## 세션 리포트 (2026-09-20)

`[실측]` RULE.md §2 — 결론 한 줄 + 리포트 링크. 상세 근거·검증 로그는 각 리포트에 있다.

| 시각 | 결론 한 줄 | 리포트 |
|---|---|---|
| 14:58 | 관광공사 구분류(A01~A04)를 신분류체계(대분류 10종)로 갱신, 대형마트 쇼핑 제외 미확보를 닫음 | [2026-09-20_1458](../records/reports/2026-09-20_1458_Activity_신분류체계_대분류_갱신_리포트.md) |
| 15:11 | `Activity_모듈_스펙.md`·`데이터베이스_저장소_설계_v2.md`를 처음 반영 — TourAPI·재난문자API 연동, 제안 스키마 | [2026-09-20_1511](../records/reports/2026-09-20_1511_Activity_TourAPI_재난문자API_DB연계_반영_리포트.md) |
| 15:53 | TourAPI 클라이언트가 이미 있었다는 정정(이전 리포트의 오류를 바로잡음) | [2026-09-20_1553](../records/reports/2026-09-20_1553_Activity_TourAPI클라이언트_places공유_정정_리포트.md) |
| 15:57 | `activities`·`tour`·`disaster`를 Activity 전용으로 결정(공유 여부 재논의 안 함) | [2026-09-20_1557](../records/reports/2026-09-20_1557_Activity_제안스키마_전용테이블_결정_리포트.md) |
| 16:00 | 마이그레이션 014 작성·적용 — `activities`·`tour`·`disaster` 실제 생성 | [2026-09-20_1600](../records/reports/2026-09-20_1600_Activity_014마이그레이션_작성_적용_리포트.md) |
| 16:26 | `activities.place_id`(FK→places)를 canonical 링크로 결정, `tour_api_content_id` 제거(015) | [2026-09-20_1626](../records/reports/2026-09-20_1626_Activity_activities_places_관계_결정_리포트.md) |
| 16:47 | 재난문자 관련성을 정적 FK 대신 `watch_observations`로 이관 결정(016) | [2026-09-20_1647](../records/reports/2026-09-20_1647_Activity_재난문자_watch_observations_이관_결정_리포트.md) |
| 16:53 | `due_activities()`·`tick_activities()` 구현 — 감시 루프 배선 | [2026-09-20_1653](../records/reports/2026-09-20_1653_Activity_due_activities_tick_activities_구현_리포트.md) |
| 16:57 | 감시 시점·주기 문서 구조를 원본 스펙과 맞게 복원 | [2026-09-20_1657](../records/reports/2026-09-20_1657_Activity_감시_시점_주기_구조_복원_리포트.md) |
| 17:18 | TourAPI 클라이언트를 `check_feasible`에 실제로 배선(`read.place.operating`) | [2026-09-20_1718](../records/reports/2026-09-20_1718_Activity_TourAPI_check_feasible_배선_리포트.md) |
| 17:37 | TourAPI operating 배선의 정식 단위 테스트 4건 추가 | [2026-09-20_1737](../records/reports/2026-09-20_1737_Activity_TourAPI_operating_테스트_리포트.md) |
| 18:12 | 장소·일정 JSON 필수값 검증 테스트 8건 추가, 빈 place dict 경계 케이스 발견 | [2026-09-20_1812](../records/reports/2026-09-20_1812_Activity_입력JSON_필수값_검증_테스트_리포트.md) |
| 18:24 | 경복궁 실사용값으로 TourAPI 대조 테스트 완성(자동 판정 금지 원칙 유지) | [2026-09-20_1824](../records/reports/2026-09-20_1824_Activity_경복궁_실사용값_테스트_리포트.md) |
| 19:18 | 휴무 요일 대조를 유일한 예외로 구현 — `feasible`이 바뀌는 첫 사례, 캐비앗 문구 필수 | [2026-09-20_1918](../records/reports/2026-09-20_1918_Activity_휴무요일대조_예외_구현_리포트.md) |
| 20:53 | 재난문자 가데이터 배선(`read.disaster`)과 등급 판정 함수(`_disaster_blocks`) 구현 — "위급재난"만 막음 | [2026-09-20_2053](../records/reports/2026-09-20_2053_Activity_재난문자_check_feasible_배선_리포트.md) |
| 21:17 | 재난문자API 실제 클라이언트(`disaster_msg.py`) 작성 — 웹 조사로 근거 확보, 실 키 미검증 명시 | [2026-09-20_2117](../records/reports/2026-09-20_2117_Activity_재난문자_실제클라이언트_작성_리포트.md) |
| 22:00 | 일정 제출(`itinerary_submit`) capability 구현 — 100% escalate 되던 라우팅 버그 수정, Phase 1 범위로 확정 | [2026-09-20_2200](../records/reports/2026-09-20_2200_Activity_일정제출_capability_구현_리포트.md) |
| 22:57 | `weather_sensitive`를 장소명 키워드로 추정하는 로직 구현 — DB가 모를 때만, 추정 사실은 항상 공개 | [2026-09-20_2257](../records/reports/2026-09-20_2257_Activity_weather_sensitive_title_추정_구현_리포트.md) |

## 관계

- [index.md](index.md) — Team 목록과 경계
- [team-contract/index.md](team-contract/index.md) — `TeamTask`·`TeamResult` 계약. **도메인이 바뀌어도 그대로다**
- [team-boundary.md](team-boundary.md) — 하면 안 되는 것 셋
- [booking-handoff.md](booking-handoff.md) — 업체 예약을 바꿔야 할 때 넘기는 곳
- [../domain-swap.md](../domain-swap.md) — 도메인을 갈아 끼울 때 무엇을 바꾸나
- [../../../wiki/product/scope.md](../../../wiki/product/scope.md) — 여행 MVP 범위
- [../data/migrations.md](../data/migrations.md) — 실제 마이그레이션. 제안 스키마와 대조할 때

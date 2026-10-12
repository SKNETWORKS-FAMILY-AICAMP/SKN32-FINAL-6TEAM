# 서버 현황 표(v2_data.py) 적대적 검토 — claude 검토자

검토 범위: 코드만 읽었다(서버 기동·DB 조회 없음). 경로 약칭은 표와 같다(TO/ · INF/ · E/ · G:). 마이그레이션은 `app/infrastructure/db/migrations/` 를 MIG/ 로 줄인다.
모양: `ID | 칸 | 유지/정정/불확실 | 정정 내용(칸 값 + 새 설명) | 근거 파일:줄`

## 1. 갈린 판정 7개

M9 | w | 정정 N→P | P|일정 항목의 경로 정의(route_def)에 택시 선택지가 eta_min 과 함께 실려 있을 때만(시나리오 JSON처럼), 계획 경로에 사건이 걸리면 그 택시 선택지를 대체 후보로 보고 **보낸 소요 그대로** 다음 일정 늦음·도로 통제(eta_min_if_controlled 없으면 탈락)를 판정한다. 택시 소요·요금을 계산하지는 않는다 | TO/replan.py:306-351 · TO/itinerary_changes.py:464-474 · 호출처 TO/mobility/team.py:79 · TO/trip_watch.py:159 · 택시 선택지 예 TO/scenarios/seoul_day_taiwan_friends.json:114
M9 | r | 불확실(약한 P) | 등록의 move_too_short 가 고객이 보낸 택시 선택지 eta_min 으로 이동 길이만 비교한다(M1 등록과 같은 일반 검사). 택시를 따로 판정하는 코드는 아님 | TO/itinerary_checks.py:70-77,147-154
M9 | g | 유지 N | 엔진 후보에 택시 없음, 설문 택시 선호는 버린다 | TO/mobility/wiring.py:95-110
M9 | a | 불확실 | 엔진이 늦음 판정 때 「안 되면 택시」 문구를 소요 계산 없이 붙인다 — 이것이 고객에게 나가는 경로는 확인 못 함 | E/verify_time.py:2462-2463,2491-2493
M9 | ev | 정정 | `wiring.py:153-157` 은 leg_planner 설명문이라 무관. car 를 안 넘기는 자리는 **E/runtime.py:166-167**(Verifier 생성에 car 인자 없음 → verify_time.py:260,273 기본값 None). runtime.py:153-160 은 라우터를 자전거용으로만 만든다 | E/runtime.py:153-167 · E/verify_time.py:260,273,1567-1568
M6 | g | 유지 P, 설명 정정 | P|버스: 최악 대기 = 배차 전부(= 정류장에 막 떠난 직후 도착)로 판정하고 「가장 늦은 출발」도 같은 최악값으로 역산 → **버스는 한 대 놓쳐도 늦지 않게 출발을 잡는다**(표의 「한 대 놓친 뒤는 계산 안 함」은 버스에 대해 틀림). 지하철 첫 승차는 시간표의 그 편 기준이고 놓치는 경우는 정책 버퍼(10분)에만 기댄다. 매우혼잡+조건 일행일 때만 다음 편, 환승은 최악 도착에서 다음 편. 코덱스 FULL 은 지하철 첫 승차 때문에 과장 | E/verify_time.py:50-53,598-607,612-649,827-839,2274-2337(2330 worst=True),2446-2505 · E/plan.py:651-659
T10 | r | 유지 N | 검색어 weekday·요일·(월)·월화수목금토일·DAYS·dow 를 TO/intake/ 와 trip_api 에서 찾았다. 입력 요일 표기를 날짜와 대조하는 코드 없음. intake 는 제목 고를 때 「(월)」 같은 요일 표기를 **지울 뿐** | TO/intake/assemble.py:326-332 · TO/intake/review.py:172-186(표시용 계산) · 놓칠 수 있는 것: LLM 추출 프롬프트가 요일을 읽어 날짜를 고치는 경우(TO/intake/llm_spans.py:19-26 은 date 역할만)
T10 | g | 유지 C | 날짜를 우리가 정하고 요일은 계산 — 대조할 입력 요일이 없다 | TO/trip_facts.py:84-85
W2 | 전 경로 | 유지 N | 검색어 축제·festival·공연·행사 취소·cancelled·event_cancel·우천 → 행사 취소 확인 코드 없음(tour_api.py:58 는 분류 이름표뿐). Activity 는 일부러 취소·순연을 판정 안 한다. 감시의 특보 대체(W1)가 결과적으로 야외 일정을 바꾸지만 「행사가 취소됐는가」의 확인은 아니다 | TO/activity/team.py:362-408 · INF/disruptions.py:162-181
M12 | g | 정정 N→P(약함) | P|웹 「일정 짜 줘」에서 고객 일정에 숙소가 **장소가 정해진 항목**으로 들어 있으면 그 항목과 짠 항목 사이 이동을 일반 장소처럼 계산한다(숙소로 알아보는 것은 아님). 숙소 지정 기능·하루 첫 출발·귀가 이동 생성은 없음 | TO/planner.py:1458-1511,744-806 · TO/trip_api.py:1296-1301
M12 | r | 정정 N→P(약함) | P|확인 화면은 같은 날 이웃한 두 항목 사이 이동을 모두 보므로, 숙소가 장소 있는 항목이면 그 앞뒤 이동도 계산된다. 「이름 없는 호텔」은 장소 없음으로 처리 | TO/intake/review.py:411-438 · TO/intake/moves.py:96-139 · TO/intake/pipeline.py:321
M12 | w | 유지 N | 감시에서 숙소를 위치로 쓰는 곳은 품절 매장 찾기(귀가 동선)뿐 | TO/itinerary_changes.py:857-861
M12 | ev | 정정 | `itinerary_changes.py:835-839` 는 활동 휴무 대체 통지 문구라 숙소와 무관 → 859-861 로. 엔진의 날 경계 미연결은 E/plan.py:868-874 맞음 | 같음
F5·G1·G4·G5 | 이동 엔진 플래그 | 유지(표 쪽) | party_of 는 size·fatigue_high(constraints.mobility_ease=needs_rest)·foreign(survey.domestic)만 채운다. infant·elderly·mobility_aid·luggage 를 채우는 코드는 엔진 밖 app/ 전체에서 0건, 프런트 src 0건(목업·백업 HTML 에만 있음). 구조화 입력 current_state.mobility 도 컨트롤러가 싣는 칸(TEAM_STATE_KEYS)에 없어 MCP·채팅으로도 안 들어온다. → 엔진 플래그를 PARTIAL 로 셀 근거 없음 | E/plan.py:152-169 · TO/mobility/wiring.py:167 · app/application/controller.py:87-92,148-152 · 검색어 infant|elderly|luggage|mobility_aid|wheelchair|stroller(엔진 폴더 제외)
T5 | r | 유지 P(등호 확인) | `gap = _minutes(end, later.starts_at)`, **`if gap < 0` 일 때만 overlap** → 끝==다음 시작(정확히 0분)은 겹침이 아니다. 0분은 두 항목이 모두 이동 항목이 아니고 두 장소의 구(district)를 둘 다 알며 서로 다를 때만 no_transfer_time | TO/itinerary_checks.py:140-146,156-164

## 2. Y·P·C 칸 과장 점검

O2 | g | 유지 Y(조건부) | 영업시간을 알 때만. before_opening 은 시작을 여는 시각으로 밀고, 아침 식사·after_last_entry·closed_day 는 장소 교체 | TO/planner.py:636-650,957-982
O2 | a | 유지 Y | 422 + 이유·완화 조건, 확인 화면 운영시간 줄 | TO/itinerary_checks.py:117-129 · TO/intake/review.py:197-218
O3 | g | 유지 Y | after_closing 이면 장소 교체(시작을 당기지 않음) | TO/planner.py:983-990
O3 | a | 유지 Y, 주의 추가 | 끝 시각을 `.time()` 으로만 비교 — 자정을 넘겨 끝나는 항목(23:30~00:30)은 after_closing 을 놓친다 | TO/itinerary_checks.py:110,121
T2 | g | 유지 Y | 식사 60분 + 이동 + 여유 10분, 겹침·이동 판정 | TO/planner.py:685-704,744-806
T5 | g | 유지 Y | 판정→고치기 최대 3회→이동 삽입 뒤 같은 판정 한 번 더, 못 맞추면 거절 | TO/planner.py:1342-1385
T5 | a | 유지 Y | 422 + 완화 조건, 확인 화면 겹침·늦게 닿음 | TO/itinerary_checks.py:143-146 · TO/intake/review.py:420-438
H1 | g | 정정 Y→P | P|read_at 은 **이번 계획에서 관광공사를 새로 읽은 곳만** 붙는다(영업시간을 이미 아는 곳은 안 읽음 — 요식 원장에서 올린 식당 등). 그리고 그 값은 원천이 갱신된 시각이 아니라 우리가 읽은 시각이다 | TO/planner.py:1083-1085,1108-1122,1137-1141
M1 | g | 유지 Y, 주의 추가 | 엔진이 꺼지면 직선거리÷80m/분 어림값이고 **60분에서 자른다** → 먼 구간은 짧게 잡힌다 | TO/planner.py:618-633,778-802
T8 | g | 유지 Y, 주의 추가 | 활동은 같은 곳(주소·30m·이름 첫 낱말+1.5km)까지, 식당은 **같은 행(키)**만 막는다 | TO/planner.py:397-409,1282-1285,1322 · TO/planner.py:1433-1449

## 3. N 칸 반증 결과(찾은 것)

P2 | g·r | 정정 N→P | P|요식 원장에서 **폐업**으로 적힌 식당은 원장 적재(rebuild) 때 코어 장소 행이 모든 요일 휴무로 덮인다 → 생성·등록·확인 화면이 closed_day(쉬는 날)로 거른다. 원장 밖 장소의 폐업·이전은 여전히 못 본다. 동기화는 적재 스크립트를 돌릴 때만 | MIG/222_dining_core_sync.sql:68-87 · scripts/dining/rebuild.py:102-104 · TO/itinerary_checks.py:111-114 · TO/intake/hours.py:65-67 · TO/intake/review.py:177-178
P2 | a | 보강 | 확인 화면 「쉬는 날」 줄도 같은 경로로 나간다 | 같음
O1 | r | 정정(공휴일 N→P) | P|확인 화면: **요식 원장과 이어진 식당**이 방문일이 공휴일(또는 설·추석 앞뒤 1일)이고 그 집의 명절 규칙이 없으면 「공휴일 조건이 있어요(…)」 경고 줄. 휴무로 판정하지는 않고 확정도 안 막는다 | TO/intake/hours.py:76-80,132-157 · TO/intake/review.py:189-191 · MIG/203_dining_holiday.sql:78-111,165-195
O1 | a | 보강 | 식당 팀 답에 「명절이나 공휴일이라 영업시간이 다를 수 있다」 경고(예약이 원장 식당일 때) | TO/dining/team.py:205-220
O1 | note | 정정 | 「공휴일 달력은 장소 휴무 판정에 연결되지 않음」 → 요식 원장 SQL 이 자체 달력(dn_holiday_stub)을 갖고 **식당 경고에만** 연결. 휴무 판정(is_closed_on)은 공휴일을 안 본다 | MIG/203_dining_holiday.sql:25-47 · MIG/201_dining_core_link.sql:109-138
O1 | 새 위험 | 불확실(코드만) | 원장→코어 동기화가 **적재 시점 다음 주 한 주**를 요일표로 굳힌다. 격주(둘째·넷째 월요일)·특정일 휴무가 그 주에 걸리면 **모든 그 요일이 휴무**로, 안 걸리면 휴무가 사라진다. 이 값을 생성·등록·확인 화면이 쓴다 | MIG/221_dining_core_promote.sql:19-51 · MIG/222_dining_core_sync.sql:62,75-81 · MIG/201_dining_core_link.sql:111-135
O4 | r | 정정 | P|REST 등록은 20분 여유 없음(표 그대로). 그러나 **확인 화면은 원장과 이어진 식당이면** 도착+20분이 라스트오더를 넘을 때 「마지막 주문이 지났을 수 있어요」, 라스트오더를 모르고 마감 60분 안이면 「마지막 주문을 확인해 주세요」 경고를 낸다(확정은 안 막음). 원장의 open_at_slot 은 자정 넘김 영업도 인정 | TO/intake/hours.py:22-23,139,147 · TO/intake/review.py:209-212 · MIG/201_dining_core_link.sql:230-343
O4·F3 | w note | 정정 | sweep_day·tick_once 는 app/ 호출처 0이 맞다. 「시험에서만」: sweep → tests/unit/travel/test_dining_sweep.py:103,122, tick → tests/integration/dining/test_dining_judgment.py:580 | 검색 범위 app·scripts·config·tests·eval 전부, 자르지 않음
O5 | g | 유지 P, 주의 추가 | 아침 후보 판정(_opens)은 하루 한 칸 `hours` 만 보고 요일표 `hours_week` 를 안 본다 → 요일표만 있는 곳(원장에서 올린 식당 전부)은 「모름」으로 들어가 hours_known=false 로 적힌다. 뒤의 check_itinerary 가 요일표로 before_opening 을 잡아 교체 | TO/planner.py:438-460,957-966
O4 | g note | 보강 | 원장 동기화의 break 는 **한 주에서 처음 찾은 요일의 브레이크를 모든 요일에** 쓴다 | MIG/221_dining_core_promote.sql:39-41,48-49
R1 | a | 유지 N | 원장 속성 목록에 reservation_required 가 있으나 채우는 스크립트가 없다(scripts/dining 검색 0). 화면은 모르는 태그를 원문 그대로 보이는 구조라 값이 생기면 표시만은 된다 | MIG/218_dining_michelin.sql:28-32 · frontend/apps/web/src/features/trip/trip-home.tsx:29-38
R4·R7 | note | 보강 | 원장 속성 max_party_size 도 스키마에만 있고 코드·적재 0건 | MIG/205_dining_attribute.sql:34-35 · 검색 app·scripts
C3 | note | 보강 | 미쉐린 적재가 card_payment=no(「현금만 가능」)를 원장에 넣지만 코어 attributes.payment 로 **동기화하지 않는다** → 등록·생성 판정에 안 쓰이고, 화면 태그는 yes 만 싣는다 | scripts/dining/make_michelin_sql.py:105-108 · MIG/222_dining_core_sync.sql:68-82 · TO/place_info.py:67-69
F1·G5 | note | 정정(설명) | dining.check_conditions 는 「도달 불가」가 맞다 — 컨트롤러가 그 기능을 고를 길이 없다(itinerary_route 는 .itinerary/.itinerary_question 만, intent 5종은 'dining.' 으로 안 시작, 기본은 check_open). **혹시 불리면** 조건 목록이 늘 비어 「요청한 조건이 없어 별도 확인 없이 진행할 수 있습니다」로 답한다(거짓 안심) | TO/itinerary_team.py:84-88 · app/core/registry.py:104-128 · TO/dining/team.py:91,248-263 · app/application/controller.py:87-92
G5 | g | 유지 P, 주의 추가 | 「아이」 부분 문자열로 찾아 「아이스크림·아이돌·아이쇼핑」에도 술집·포차를 뺀다. 설문 party(여행자 구성)는 안 쓴다 | TO/planner.py:224,251-253 · TO/survey.py:46
W1 | w | 보강 | 날씨형 재난문자(호우 등)도 날씨 영향 장소에 이상으로 센다(키 없으면 not_connected) | INF/disruptions.py:183-213

## 4. FACTS 8개

FACT1 | 정정 | 「웹 입구는 결제·예산·식이 조건을 안 싣는다」 → **지금 화면이 안 보낼 뿐 서버 입구는 받는다.** `POST /v1/web/trips` 는 CreateTrip 몸통 전체(constraints 포함)를 받는다. 읽은 일정 확정(confirm)·「일정 짜 줘」(plan) 두 입구만 survey 만 싣는다. 프런트 src 는 constraints.survey 만 보낸다 | TO/trip_api.py:1216-1217,1266-1269,1360-1373 · frontend/apps/web/src/features/trip-registration/trip-registration.tsx:87 · MCP 는 constraints 를 안 다룸(TO/mcp_server.py 검색 0)
FACT2 | 정정(보강) | 「재판정은 Case 버전에만」은 맞지만 **기본 일꾼에도 재판정 없는 경로가 돈다**: `--only` 없이 돌 때 03:00 새벽 확인(trip_dawn)이 들어가고 이것은 pending.apply_or_ask(재판정 없음)로 쓴다. 고객 채팅 창구(TripDesk)도 append_version 을 직접 부른다. Case 버전도 되돌리기(full_items)·고객이 고른 변경은 재판정을 건너뛴다 | scripts/run_sweepers.py:101-110 · TO/dawn_check.py:38,168 · TO/pending.py:426-465 · TO/trip_desk.py:273,301 · TO/itinerary_actions.py:49,163-173
FACT3 | 정정 | sweep.py·tick.py 는 「app/ 호출처 0, 시험에서만」 맞음. **watch.py(TravelWatcher)는 시험에서도 0건** — .py 전체(app·scripts·config·tests·eval·legacy·_backup)에서 import 0 | 검색어 travel_ops\.watch · TravelWatcher · from \.watch import(자르지 않음, count 0) · TO/watch.py:95,282
FACT4 | 유지(보강) | theme·theme_details·indoor_outdoor·party·priority_details.food 는 판정에 안 쓴다. 단 「대부분」에서 빠진 쓰이는 것: on_disruption·pace(설문 머리말), **domestic→foreign**, **preferred_mobility·priority_details.mobility→이동 수단**, priority(활동 순위 가중, 표 G7) | TO/survey.py:4-13 · E/plan.py:166-168 · TO/mobility/wiring.py:99-110 · conds_from_survey 호출처: tests/unit/travel/test_dining_survey.py 뿐
FACT5 | 유지 | 위 F5·G4 줄 참조 | E/plan.py:152-169
FACT6 | 유지(보강) | 활동 대체 후보는 「제안」 모드일 때 모름을 경고로만 둔다(탈락 아님) | TO/replan.py:234-238,290-296
FACT7 | 유지 | check_itinerary 호출처는 등록·생성·intake(확인 화면·자동 추천·후보)·자동 변경 적용뿐. place_facts 일꾼(fill_missing_facts) 뒤에 재판정하는 호출 없음 | TO/trip_api.py:598 · TO/planner.py:860,1582 · TO/intake/review.py:304 · TO/intake/autofix.py:237 · TO/intake/candidates.py:230 · TO/itinerary_actions.py:73-74 · scripts/run_sweepers.py:116-117,130-136
FACT8 | 정정(근거·범위) | 근거 줄을 E/runtime.py:166-167 로. 「서비스 경로에 안 닿는다」는 **택시 소요 계산**에 대해선 맞지만, 일정에 실려 온 택시 선택지는 감시 대체 후보로 쓰인다(M9 w 줄) | 위 M9 줄

## 5. 표에서 빠진 큰 사실

NEW1 | 불확실(코드만) | 등록·확인 화면·자동 변경 전 재판정이 쓰는 영업시간 판정(check_itinerary)은 시각을 **서울 시각으로 바꾸지 않고** `.date()`·`.time()` 을 그대로 쓴다. 같은 결함을 장소 영업 판정(fits)은 고쳤다는 주석이 있다(DB 세션이 UTC 면 14:00 이 05:00 으로 읽혔다). DB 에서 다시 읽은 일정이나 「Z」로 보낸 시각이면 휴무·여는 시각 판정이 9시간 어긋날 수 있다. DB 세션 시간대는 확인 안 함 | TO/itinerary_checks.py:109-125 · TO/place_hours.py:89-109(fits 의 변환과 주석) · app/infrastructure/db/session.py(시간대 설정 검색 0)
NEW2 | 불확실(코드만) | 위 O1 「다음 주 한 주를 요일표로 굳힘」 + 확인 화면에서 원장의 그날 값(`hours`)보다 코어 요일표(`hours_week`)가 먼저 읽혀, 원장이 「그날 연다」고 해도 굳은 요일표가 「쉼」이면 쉬는 날로 보인다 | TO/intake/hours.py:149-155 · TO/place_hours.py:66-75
NEW3 | 사실 | 사람이 가장 흔히 겪을 결함 중 어느 경로도 판정하지 않는 것: **외부에서 받은 일정의 장소 사이 이동 시간**(이동 항목이 없으면 0분 간격·구가 다를 때만), **활동 장소의 공휴일 휴관**(관광공사 휴무 원문의 공휴일 조건은 원문 문자열로만 남고 판정 안 함 — 식당만 원장 경고) | TO/itinerary_checks.py:8-14,156-164 · TO/place_hours.py:118,195
NEW4 | 사실 | 엔진이 꺼진 상태의 어림값 이동은 60분에서 잘려 먼 구간을 짧게 잡는다(M1 주의와 같음) | TO/planner.py:628-631

## 이 검토가 놓칠 수 있는 것
- DB 를 조회하지 않았다: 원장에 폐업·격주 휴무·reservation_required 값이 실제로 몇 건인지, DB 세션 시간대가 무엇인지 모른다. NEW1·NEW2·P2 의 실제 영향 크기는 미측정.
- 깊이 보지 않은 행: P1·P3·O6·O7·T1·T3·T4·T6·T7·T9·H2·R2·R3·R5·R6·R8·R9·M2·M3·M4·M5·M7·M8·M10·M11·W3·W4·W5·F2·F4·G2·G3·G6·G7·L1·L2(인용 줄 일부만 확인). 이 행의 칸은 「유지」가 아니라 「미검토」다.
- 프런트는 src 의 키워드 검색만 했다(화면이 어떤 응답 칸을 실제로 그리는지 확인 안 함) — 「a(응답)」 칸의 노출 여부는 서버 응답 기준이다.
- M9 r·a, M12 g·r 의 P 는 「일반 검사가 우연히 덮는」 수준이라, 체크리스트가 「그 항목을 의식해 판정하는가」를 묻는다면 N 이 맞을 수 있다(기준 선택 문제).
- grep 은 동적 import·문자열 조립 호출을 못 잡는다(watch.py 0건 판정 포함).

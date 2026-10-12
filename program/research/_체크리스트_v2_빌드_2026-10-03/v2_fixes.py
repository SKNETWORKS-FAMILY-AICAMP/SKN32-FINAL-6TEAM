# -*- coding: utf-8 -*-
"""검토 전용 Claude 에이전트(적대적 반증)의 정정을 표에 덮어쓴다. ★반영한 것은 클로드(본 세션)가 줄을 직접 연 것(T5 0분 · 택시 car 인자 ·
watch.py 호출처 · /v1/web/trips · 시각대 변환 줄)과 검토자가 줄 번호까지 댄 것이다. 못 연 것은 「의심」으로 표시한다."""

FIX = {
 # 칸 글자가 바뀐 것
 "M9": {"w": "P|일정 항목의 경로 정의(route_def)에 택시 선택지가 소요와 함께 실려 있을 때만: 감시가 그 택시를 대체 후보로 보고 보낸 소요 그대로 다음 일정 늦음·도로 통제를 판정. 택시 소요·요금을 계산하거나 호출 가능·승차 위치를 보지는 않음",
        "ev": "TO/replan.py:306-351 · TO/itinerary_changes.py:464-474 · E/runtime.py:153-167 · E/verify_time.py:260,273,1567-1568",
        "miss": "경로 정의에 택시 선택지 없음=건너뜀 · 엔진은 car 서비스가 없어 MOB_W_CAR_ROUTER_DOWN(근거없음)",
        "note": "택시 소요 계산기(car.py)는 있으나 Verifier 생성(runtime.py:166)에 car 를 넘기지 않아 서비스 경로에 안 닿음. 등록의 move_too_short 는 고객이 보낸 택시 eta_min 으로 이동 길이만 비교하는 일반 검사이고 택시 판정이 아니라 N 으로 둠(코덱스는 PARTIAL, 검토자는 「약한 P」 — 기준 선택 문제)"},
 "M12": {"g": "P|웹 「일정 짜 줘」에서 고객 일정에 숙소가 장소가 정해진 항목으로 들어 있을 때만 그 항목과 짠 항목 사이 이동을 일반 장소처럼 계산(숙소로 알아보는 것은 아님). 숙소 지정·하루 첫 출발·귀가 이동 생성은 없음",
         "r": "P|확인 화면은 같은 날 이웃한 두 항목 사이 이동을 모두 보므로 숙소가 장소 있는 항목이면 앞뒤 이동도 계산됨. 이름 없는 호텔은 장소 없음으로 처리",
         "ev": "TO/planner.py:1458-1511,744-806 · TO/trip_api.py:1296-1301 · TO/intake/review.py:411-438 · TO/intake/moves.py:96-139 · TO/itinerary_changes.py:857-861 · E/plan.py:868-874",
         "note": "숙소를 위치로 쓰는 감시 코드는 품절 매장 찾기(귀가 동선)뿐. 일반 검사가 우연히 덮는 수준이라 「그 항목을 의식해 판정하는가」를 기준으로 하면 N 이 맞을 수 있음"},
 "H1": {"g": "P|이번 계획에서 관광공사를 새로 읽은 곳만 hours_read.read_at 이 붙음(영업시간을 이미 아는 곳·요식 원장에서 올린 식당은 안 읽음). 그 값도 원천이 갱신된 시각이 아니라 우리가 읽은 시각",
        "ev": "TO/planner.py:1083-1085,1108-1122,1137-1141 · TO/trip_reminders.py:160-176,334-337 · TO/dining/team.py:191-193"},
 "P2": {"g": "P|요식 원장에서 폐업으로 적힌 식당은 원장 적재(rebuild) 때 코어 장소 행이 모든 요일 휴무로 덮여 closed_day 로 걸러짐. 원장 밖 장소의 폐업·이전은 못 봄",
        "r": "P|같은 경로: 등록·확인 화면이 closed_day(쉬는 날)로 걸러짐(원장 식당만). 동기화는 적재 스크립트를 돌릴 때만",
        "ev": "INF/google_places.py:138-150 · TO/dawn_check.py:112-146 · TO/itinerary_changes.py:688-722 · MIG/222_dining_core_sync.sql:68-87 · scripts/dining/rebuild.py:102-104"},
 # 설명·근거만 정정·보강
 "O1": {"r": "P|보낸 hours_week 가 있을 때만. 확인 화면은 요식 원장과 이어진 식당이 방문일이 공휴일(설·추석 앞뒤 1일 포함)이고 명절 규칙이 없으면 「공휴일 조건이 있어요」 경고 줄(휴무로 판정하지는 않고 확정도 안 막음)",
        "a": "P|등록 거절 422 closed_day+완화 조건 · 확인 화면 휴무일 줄 · 채팅 「쉬는 날(원문)」 · 식당 팀 답 「명절이나 공휴일이라 영업시간이 다를 수 있다」 경고(원장 식당만)",
        "ev_add": "TO/intake/hours.py:76-80,132-157 · TO/dining/team.py:205-220 · MIG/203_dining_holiday.sql:78-111",
        "note": "공휴일 달력은 요식 원장 SQL 이 자체로 갖고(dn_holiday_stub) 식당 경고에만 연결됨. 휴무 판정(is_closed_on)은 공휴일을 안 봄. 활동 장소의 공휴일 휴관은 관광공사 원문 조건으로만 남고 판정 안 됨. ★의심(코드만): 원장→코어 동기화가 적재 시점 다음 주 한 주를 요일표로 굳혀, 격주·특정일 휴무가 그 주에 걸리면 매주 그 요일이 휴무가 되고 안 걸리면 휴무가 사라질 수 있음(MIG/221_dining_core_promote.sql:19-51)"},
 "O3": {"note_add": "끝 시각을 .time() 으로만 비교해 자정을 넘겨 끝나는 항목(23:30~00:30)은 after_closing 을 놓침(itinerary_checks.py:110,121)"},
 "O4": {"r": "P|REST 등록은 20분 여유 없음. 확인 화면은 요식 원장과 이어진 식당이면 도착+20분이 라스트오더를 넘을 때 「마지막 주문이 지났을 수 있어요」, 라스트오더를 모르고 마감 60분 안이면 「마지막 주문을 확인해 주세요」 경고(확정은 안 막음)",
        "ev_add": "TO/intake/hours.py:22-23,139,147 · TO/intake/review.py:209-212",
        "note_add": "원장 동기화의 break 는 한 주에서 처음 찾은 요일의 브레이크를 모든 요일에 씀(MIG/221_dining_core_promote.sql:39-49). 하루 점검(sweep_day)·방문 전 점검(tick_once)은 app/·scripts/·config/ 에 호출처 0건이고 시험(tests/)에서만 돎"},
 "O5": {"note_add": "아침 후보 판정(_opens)은 하루 한 칸 hours 만 보고 요일표 hours_week 를 안 봄 → 요일표만 있는 곳(원장에서 올린 식당 전부)은 「모름」으로 들어가 hours_known=false 로 적히고, 뒤의 check_itinerary 가 요일표로 before_opening 을 잡아 교체(planner.py:438-460,957-966)"},
 "M1": {"note_add": "엔진이 꺼진 어림값은 직선거리÷80m/분이고 60분에서 잘려 먼 구간을 짧게 잡음(planner.py:628-631)"},
 "M6": {"g": "P|버스: 최악 대기 = 배차 전부로 판정하고 가장 늦은 출발도 같은 최악값으로 역산 → 버스는 한 대 놓쳐도 늦지 않게 출발을 잡음. 지하철 첫 승차는 시간표의 그 편 기준이고 놓치는 경우는 정책 버퍼 10분에만 기댐(매우 혼잡+조건 일행일 때만 다음 편)",
        "ev": "E/verify_time.py:827-839,2274-2337,2446-2505 · E/plan.py:651-659 · TO/intake/moves.py:41-44",
        "note": "코덱스 FULL 은 지하철 첫 승차 때문에 과장. 확인 화면 tight 경고는 시간표로 검증 못 한 구간에만"},
 "T5": {"r": "P|겹침은 gap<0 일 때만 overlap 이라 끝==다음 시작(정확히 0분)은 겹침이 아님. 0분은 두 항목 모두 이동 항목이 아니고 두 장소의 구를 둘 다 알며 서로 다를 때만 no_transfer_time. 이동 항목이 있으면 계획 수단 eta_min 보다 짧을 때 move_too_short. 이동 항목 없는 구간의 소요는 모름→통과"},
 "T8": {"note_add": "식당은 같은 행(키)만 막고 같은 곳 판정은 활동만(planner.py:397-409,1433-1449)"},
 "R1": {"note_add": "원장 속성 목록에 reservation_required 가 있으나 채우는 스크립트가 없음(MIG/218_dining_michelin.sql:28-32). 값이 생기면 화면 태그는 원문 그대로 표시"},
 "R7": {"note_add": "원장 속성 max_party_size 도 스키마에만 있고 코드·적재 0건(MIG/205_dining_attribute.sql:34-35)"},
 "C3": {"note_add": "미쉐린 적재가 card_payment=no(현금만)를 원장에 넣지만 코어 attributes.payment 로 동기화하지 않아 등록·생성 판정에 안 쓰임(scripts/dining/make_michelin_sql.py:105-108, MIG/222_dining_core_sync.sql:68-82)"},
 "C1": {"note": "이동 요금(fare_krw)은 계산·표시만 하고 예산 합에 안 들어감. 웹 화면은 예산을 안 보냄(서버의 /v1/web/trips 입구는 constraints 를 받음)"},
 "C2": {"note": "사용자가 결제 수단을 한 값(card/cash)으로 줄 때만 동작. 웹 화면은 결제 조건을 안 보냄(서버 입구는 받음)"},
 "F1": {"note_add": "★위험: dining.check_conditions 는 컨트롤러가 고를 길이 없어 도달 불가인데, 혹시 불리면 조건 목록이 늘 비어 「요청한 조건이 없어 별도 확인 없이 진행할 수 있습니다」로 답함(거짓 안심) — TO/dining/team.py:248-263 · TO/itinerary_team.py:84-88"},
 "G5": {"note_add": "「아이」 부분 문자열로 찾아 「아이스크림·아이돌」에도 술집·포차를 뺌. 설문 party 는 안 씀(planner.py:224,251-253)"},
 "W1": {"note_add": "날씨형 재난문자(호우 등)도 날씨 영향 장소에 이상으로 셈(키 없으면 not_connected, disruptions.py:183-213)"},
}

SOURCES_NOTE = ("방법 셋을 겹쳤습니다. ① 하위 조사 3개(Claude, 코드를 열어 66행을 길별로 판정) ② Codex gpt-6-luna(읽기 전용, v1 「아직 없음」 34 + 「이미 판정」 5 = 39행 반증) "
                "③ 검토 전용 Claude(opus) 에이전트(적대적 반증: 갈린 판정 7개 · Y 칸 · N 칸 · 공통 사실 8개).")

CROSS = [
 "Codex 는 본계정 쿼터가 2026-10-04 12:00 까지 소진돼 알트 계정으로 돌렸고, 알트는 gpt-6-luna 만 받아(sol·5.x 모델 거부) 규칙의 기본 단계(sol)보다 한 단계 낮은 모델입니다. 같은 단계 두 계정 교차는 못 했습니다. 검토자: 기계(Codex 알트 gpt-6-luna) · 기계(Claude 서브에이전트) — 사람이 봤다고 쓰지 않습니다.",
 "Codex 와 하위 조사의 「아직 없음」 34행 판정은 25행이 처음부터 일치했고 9행이 갈렸습니다. 줄을 열어 가린 결과: 코덱스가 맞은 2행(M9 택시 감시, M12 숙소 — 둘 다 「약한 P」로 정정), 하위 조사가 맞은 7행(코덱스가 놓친 C3·R7·F3, 코덱스가 이동 엔진 플래그나 날씨 감시를 같은 확인으로 센 W2·F5·G1·G4). C3 는 itinerary_checks.py:176-183 을 직접 열어 확인했습니다.",
 "v1 「서버가 이미 판정」 5가지(P1·T5·M10·W1·W3)는 Codex·하위 조사 모두 「제한된 조건만」이라 범위를 좁혀야 한다고 봤습니다(5/5).",
 "검토자가 칸 글자를 바꾼 것 6개: M9 감시 N→P · M12 생성·등록 N→P · P2 생성·등록 N→P · H1 생성 Y→P. 설명·근거 줄을 정정·보강한 항목 15개 이상. 클로드가 직접 줄을 열어 확인한 것: T5 0분 간격(gap<0 일 때만 겹침) · 택시 car 인자 미전달(runtime.py:166) · watch.py 호출처 0건 · /v1/web/trips 가 constraints 를 받음 · 영업시간 판정에 시각대 변환 없음.",
 "★검토자도 66행을 다 깊이 보지는 못했습니다. 약 31/66(47%)행을 줄 단위로 확인했고 35행은 「미검토」입니다(P1·P3·O6·O7·T1·T3·T4·T6·T7·T9·H2·R2·R3·R5·R6·R8·R9·M2~M5·M7·M8·M10·M11·W3~W5·F2·F4·G2·G3·G6·G7·L1·L2). 이 35행은 하위 조사 1개(와 일부는 Codex)만 검증한 것입니다.",
 "기준 선택 문제: M9·M12 의 「약한 P」는 일반 검사가 우연히 덮는 수준입니다. 체크리스트가 「그 항목을 의식하고 판정하는가」를 묻는다면 N 이 맞습니다. 이 문서는 M12 는 P, M9 는 감시만 P 로 뒀습니다.",
]

FACTS2 = [
 ("지금 웹 화면은 결제·예산·식이 조건을 서버에 안 보낸다", "서버 입구(POST /v1/web/trips)는 constraints 전체를 받는다. 읽은 일정 확정·「일정 짜 줘」 두 입구는 survey 만 싣고, 프런트도 constraints.survey 만 보낸다. MCP 는 constraints 를 다루지 않는다 → 웹·MCP 경로에서 C1·C2·C3 검사는 사실상 꺼져 있다", "TO/trip_api.py:1216-1217,1266-1269,1360-1373"),
 ("감시는 두 벌이고 재판정은 한 벌에만, 그것도 일부 길에만 있다", "Case 버전(trip_watch_cases.py)은 자동 변경 전에 일정 전체를 check_itinerary 로 다시 판정한다. 그러나 기본 일꾼에도 재판정 없는 경로가 돈다 — 03:00 새벽 확인(trip_dawn)은 pending.apply_or_ask 로 바로 쓰고, 고객 채팅 창구(TripDesk)도 일정 판을 직접 쓴다. 되돌리기·고객이 고른 변경도 재판정을 건너뛴다", "TO/itinerary_actions.py:49,54-59,153-173 · TO/pending.py:426-465 · TO/dawn_check.py:38,168 · TO/trip_desk.py:273,301 · scripts/run_sweepers.py:101-110"),
 ("코드는 있는데 아무도 부르지 않는 것", "하루 점검(dining/sweep.py)·방문 전 확인(dining/tick.py)은 app/·scripts/·config/ 에 호출처 0건이고 시험에서만 돈다. 장소 변경 감시(watch.py TravelWatcher)는 시험에서도 0건 — .py 전체에서 import 가 없다", "TO/dining/sweep.py · TO/dining/tick.py · TO/watch.py:95,282"),
 ("설문 필드는 일부만 판정에 쓰인다", "theme · theme_details · indoor_outdoor · party · 음식 세부는 안 쓰이고, 설문→식이 조건 변환(conds_from_survey)은 시험에서만 부른다. 쓰이는 것: pace(밀도) · 내국인 여부(→외국인 표시) · 선호 이동수단(→계산기 수단) · priority(활동 순위 가중)", "TO/survey.py:4-13 · TO/mobility/wiring.py:99-110 · E/plan.py:166-168"),
 ("이동 계산기의 일행 조건(유아·고령·짐·보행보조)은 채우는 곳이 없다", "party_of 는 인원·피로·외국인만 채운다. 엔진 밖 app/ 와 화면 코드에 채우는 곳이 0건이고, 컨트롤러가 이동 구조화 입력(current_state.mobility)을 싣지도 않는다 → 도보 상한을 낮추는 규칙이 사실상 안 쓰인다", "E/plan.py:152-169 · app/application/controller.py:87-92,148-152"),
 ("모름을 다루는 방식이 경로마다 다르다", "영업시간 모름: 등록·생성은 통과(생성은 hours_known 공개), 감시 대체 후보는 식당 탈락·활동 통과. 결정 15(「값을 모르는 상황을 만들지 않는다」)와 어긋나는 곳", "TO/itinerary_checks.py:4-21 · TO/replan.py:234-238,290-296"),
 ("등록 뒤에 채워진 값으로 기존 일정을 다시 판정하지 않는다", "check_itinerary 의 호출처는 등록·생성·intake(확인 화면·자동 추천·후보)·자동 변경 적용뿐이다. place_facts 일꾼이 운영시간을 채워도 그 값으로 기존 일정을 재판정하는 호출이 없다", "TO/trip_api.py:598 · TO/planner.py:860,1582 · scripts/run_sweepers.py:116-136"),
 ("택시 소요 계산기는 이동 판정기에 조립되지 않는다", "car.py 는 있으나 Verifier 생성에 car 를 넘기지 않아 소요·요금 계산에는 안 닿는다. 다만 일정에 택시 선택지가 소요와 함께 실려 오면 감시 대체 후보로는 쓰인다(M9)", "E/runtime.py:153-167 · E/verify_time.py:260,273,1567-1568 · TO/replan.py:306-351"),
 ("★의심(코드만): 영업시간 판정이 시각을 서울 시각으로 바꾸지 않는다", "check_itinerary 는 starts_at.date()·.time() 을 그대로 쓴다. 같은 결함을 장소 영업 판정(fits)은 고쳤다는 주석이 있다(DB 세션이 UTC 면 14:00 이 05:00 으로 읽혔다). DB 에서 다시 읽은 일정이나 「Z」로 보낸 시각이면 휴무·여는 시각 판정이 9시간 어긋날 수 있다. DB 세션 시간대는 확인하지 못했다", "TO/itinerary_checks.py:109-125 · TO/place_hours.py:89-109"),
 ("가장 흔한 결함 중 어느 길도 판정하지 않는 것", "외부에서 받은 일정의 장소 사이 이동 시간(이동 항목이 없으면 0분 간격·구가 다를 때만), 활동 장소의 공휴일 휴관(관광공사 원문 조건으로만 남음)", "TO/itinerary_checks.py:8-14,156-164 · TO/place_hours.py:118,195"),
]

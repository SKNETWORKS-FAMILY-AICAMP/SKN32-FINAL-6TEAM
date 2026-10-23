// cs test_plans.py의 PLANS/CATEGORIES 원문을 사용합니다. 날짜만 화면 시험 기준으로 고정합니다.
export const PREPARED_PLAN_CATALOG = {
  "enabled": true,
  "realtime_enabled": false,
  "catalog_version": "seoul-text-v3",
  "scenarios": [
    {
      "code": "test1",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "서울 2일 기본 일정",
      "description": "궁궐·시장·박물관과 다음 날 일정을 확인합니다.",
      "category": "general",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 2일 여행 · 4명\n\n1일차 · 2026-10-01\n09:00~10:30 경복궁 관람\n12:30~13:30 광장시장 점심\n15:00~16:30 국립중앙박물관 관람\n\n2일차 · 2026-10-02\n10:00~11:00 북촌한옥마을 산책\n12:00~13:00 인사동 점심\n14:00~15:30 창덕궁 관람"
    },
    {
      "code": "test2",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "겹치는 일정",
      "description": "서로 겹치는 방문 시간을 확인합니다.",
      "category": "time",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n09:00~11:00 경복궁 관람\n10:30~12:00 국립중앙박물관 관람\n12:30~13:30 광장시장 점심"
    },
    {
      "code": "test3",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "늦은 궁궐 방문",
      "description": "야간 방문이 실제 운영시간에 맞는지 확인합니다.",
      "category": "hours",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n12:00~13:00 광장시장 점심\n21:00~22:00 경복궁 관람"
    },
    {
      "code": "test4",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "화요일 궁궐 방문",
      "description": "화요일의 휴무·운영 정보를 조회합니다.",
      "category": "hours",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-06\n10:00~11:30 경복궁 관람\n12:30~13:30 광장시장 점심"
    },
    {
      "code": "test5",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "정해지지 않은 숙소",
      "description": "호텔 이름을 정하지 않은 일정의 장소 확인을 살펴봅니다.",
      "category": "place",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n09:00~09:30 호텔 조식\n10:30~12:00 경복궁 관람\n12:30~13:30 광장시장 점심"
    },
    {
      "code": "test6",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧은 이동 간격",
      "description": "멀리 떨어진 방문지 사이의 짧은 이동 간격을 확인합니다.",
      "category": "mobility",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:00 국립중앙박물관 관람\n11:05~12:00 경복궁 관람\n12:30~13:30 광장시장 점심"
    },
    {
      "code": "test7",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "종료 시각 생략",
      "description": "종료 시각이 없는 일정의 확인·수정을 살펴봅니다.",
      "category": "input",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n09:00 경복궁 관람\n12:30 광장시장 점심\n15:00 국립중앙박물관 관람"
    },
    {
      "code": "test8",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "같은 장소 재방문",
      "description": "같은 날 같은 장소를 두 번 방문하는 일정을 확인합니다.",
      "category": "general",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n09:00~10:00 인사동 산책\n12:00~13:00 광장시장 점심\n16:00~17:00 인사동 산책"
    },
    {
      "code": "test9",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "예약이 있는 방문",
      "description": "예약 표시가 있는 일정의 보존·수정을 확인합니다.",
      "category": "general",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:30 경복궁 관람\n12:30~13:30 광장시장 점심\n19:00~20:00 N서울타워 관람 · 예약 있음"
    },
    {
      "code": "test10",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "원문 순서가 다른 일정",
      "description": "입력 순서와 방문 시각이 다른 일정을 확인합니다.",
      "category": "input",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n15:00~16:30 국립중앙박물관 관람\n09:00~10:30 경복궁 관람\n12:30~13:30 광장시장 점심"
    },
    {
      "code": "test11",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "서울 7일 일정",
      "description": "최대 7일 일정의 날짜 전환·목록을 확인합니다.",
      "category": "general",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 7일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:30 경복궁 관람\n\n2일차 · 2026-10-02\n10:00~11:30 국립중앙박물관 관람\n\n3일차 · 2026-10-03\n10:00~11:30 북촌한옥마을 산책\n\n4일차 · 2026-10-04\n12:00~13:00 광장시장 점심\n\n5일차 · 2026-10-05\n10:00~11:30 창덕궁 관람\n\n6일차 · 2026-10-06\n10:00~11:00 청계천 산책\n\n7일차 · 2026-10-07\n19:00~20:00 N서울타워 관람"
    },
    {
      "code": "test12",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "활동과 식사",
      "description": "서울의 활동·식사·이동을 함께 확인합니다.",
      "category": "general",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:30 북촌한옥마을 산책\n12:00~13:00 광장시장 점심\n15:00~16:30 국립중앙박물관 관람\n19:00~20:00 N서울타워 관람"
    },
    {
      "code": "test13",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "여유 있는 도심 산책",
      "description": "시간 겹침·장소 미정 없이 여유를 둔 기본안입니다.",
      "category": "normal",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:00 청계천 산책\n14:00~15:00 인사동 산책"
    },
    {
      "code": "test14",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "여유 있는 박물관 방문",
      "description": "장소와 종료 시각을 정하고 이동 여유를 둔 기본안입니다.",
      "category": "normal",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 1일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~12:00 국립중앙박물관 관람\n16:00~17:00 N서울타워 관람"
    },
    {
      "code": "test15",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "하루 한 곳씩 서울 2일",
      "description": "하루에 한 곳씩 방문해 날짜 전환을 확인하는 기본안입니다.",
      "category": "normal",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 2일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:00 청계천 산책\n\n2일차 · 2026-10-02\n10:00~12:00 국립중앙박물관 관람"
    },
    {
      "code": "test16",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "숙소가 있는 서울 2일",
      "description": "이름이 있는 호텔 체크인이 든 일정으로 숙소 후보와 바꾸기를 확인합니다.",
      "category": "general",
      "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 2일 여행 · 4명\n\n1일차 · 2026-10-01\n10:00~11:30 경복궁 관람\n15:00 더 플라자 호텔 서울 체크인\n\n2일차 · 2026-10-02\n11:00~12:30 N서울타워 관람"
    },
    {
      "code": "test17",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 시각 줄 사이 「택시 타고 갈게요」",
      "description": "시각+장소 줄 사이에 이동 수단 한 문장이 끼어 있습니다.",
      "category": "mixed_list",
      "expected": "10/16 지금 구조: 두 곳은 읽고 「택시」는 이동 수단으로 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10/1(목)\n10:00 경복궁\n택시 타고 갈게요\n12:30 토속촌삼계탕"
    },
    {
      "code": "test18",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 하루 일정에 이동·조건·성향 문장",
      "description": "하루 목록 사이에 걷기 · 지하철 · 「아이가 있어서」 · 「비 오면 실내」 문장이 섞여 있습니다.",
      "category": "mixed_list",
      "expected": "10/16 지금 구조: 다섯 곳은 읽지만 「지하철로 이동」이 일정이 되고 익선동이 한 번 더 생겨요. 걷기·아이·비 조건은 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10/1(목) 하루 일정\n09:30 창덕궁\n걸어서 익선동으로\n12:00 익선동 점심\n14:00 서울공예박물관\n(아이가 있어서 오래 걷는 건 빼 주세요)\n16:30 인사동 쌈지길\n지하철로 이동\n19:00 을지로 노가리골목\n비 오면 저녁은 실내로 바꿔 주세요"
    },
    {
      "code": "test19",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 2박 3일, 날마다 자유 문장",
      "description": "사흘 목록에 버스 · 택시 · 「15시 전에 끝내 주세요」 같은 문장이 섞여 있습니다.",
      "category": "mixed_list",
      "expected": "10/16 지금 구조: 아홉 곳은 읽지만 「택시로 이동」·「전에 끝내 주세요」가 일정이 되고, 버스·마치는 시각 조건은 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "1일차 10/1(목)\n11:00 북촌한옥마을\n버스 타고 남산으로\n15:00 남산골한옥마을\n18:30 N서울타워\n\n2일차 10/2(금)\n아침은 숙소에서 늦게 먹고\n11:00 국립중앙박물관\n13:00 이촌동 점심\n택시로 이동\n15:30 반포한강공원\n\n3일차 10/3(토)\n10:00 덕수궁\n12:00 정동 점심\n공항 가야 해서 15시 전에 끝내 주세요"
    },
    {
      "code": "test20",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 7일, 하루 두세 곳과 메모",
      "description": "최대 기간(7일) 목록에 날마다 메모 한 줄이 섞여 있습니다.",
      "category": "mixed_list",
      "expected": "10/16 지금 구조: 7일 18곳을 날짜대로 읽지만 「공항철도 타고 인천공항」이 일정이 되고, 메모(한복·비·자전거)는 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10/1(목)\n15:00 명동 롯데호텔 서울 체크인\n19:00 명동교자 저녁\n도착일이라 가볍게\n\n10/2(금)\n10:00 경복궁\n12:30 통인시장\n15:00 국립민속박물관\n한복 입고 다닐 거예요\n\n10/3(토)\n10:00 창덕궁\n12:30 익선동 점심\n15:00 종묘\n\n10/4(일)\n11:00 국립중앙박물관\n14:00 용산가족공원\n비 오면 박물관에 더 있을게요\n\n10/5(월)\n10:00 서울숲\n12:30 성수동 카페거리\n16:00 뚝섬한강공원\n자전거 빌려서 탈 거예요\n\n10/6(화)\n10:30 롯데월드\n18:00 석촌호수 산책\n19:30 롯데월드타워 서울스카이\n\n10/7(수)\n10:00 남대문시장\n12:00 체크아웃\n공항철도 타고 인천공항"
    },
    {
      "code": "test21",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 「낼 11시 경복궁 갓다가」",
      "description": "줄임말 · 오타가 섞인 한 줄에 상대 날짜(내일)가 있습니다.",
      "category": "typo_line",
      "expected": "10/16 지금 구조: 두 곳은 읽지만 날짜(내일)를 비우고 「1시」를 새벽 1시로 읽어요. 이름에 「갓다」「ㄱㄱ」이 붙어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "낼 11시 경복궁 갓다가 1시 통인시장 ㄱㄱ"
    },
    {
      "code": "test22",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 띄어쓰기 없는 하루 한 줄",
      "description": "「담주 토욜」 · 인원 · 다섯 곳이 한 줄에 붙어 있습니다.",
      "category": "typo_line",
      "expected": "10/16 지금 구조: 인원 4명은 읽지만 날짜(담주 토욜)를 비우고 3시·6시를 새벽으로 읽어요. 점심 장소가 창경궁 항목에 붙어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "담주 토욜 10시반 창경궁 보고 점심은 혜화역근처 아무데나 3시 낙산공원 올라갓다가 6시 대학로 연극보러가여 4명"
    },
    {
      "code": "test23",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 이틀이 한 줄에",
      "description": "두 날의 일정이 「담날」로만 나뉜 한 줄입니다.",
      "category": "typo_line",
      "expected": "10/16 지금 구조: 여섯 곳을 모두 첫날로 읽고(「담날」을 나누지 못함) 2시·5시·1시를 새벽으로 읽어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10월 1일날 아침 9시 남대문시장 구경 12시 갈치조림골목 2시 명동성당 5시 남산케이블카 담날 10시 서울숲 1시 성수동카페거리 ㅎㅎ"
    },
    {
      "code": "test24",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 「비 온다고 해서 실내 위주로」",
      "description": "장소 없이 날짜 · 조건만 있는 두 문장입니다.",
      "category": "paragraph",
      "expected": "10/16 지금 구조: 일정이 0개예요. 날짜(모레)·실내 조건을 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "모레 하루 서울 가요. 비 온다고 해서 실내 위주로 다니고 싶어요."
    },
    {
      "code": "test25",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 1박 2일, 「둘째 날은 알아서」",
      "description": "기간 · 인원 · 이동 성향 · 짜기 요청이 한 문단에 있습니다.",
      "category": "paragraph",
      "expected": "10/16 지금 구조: 기간(1박 2일)만 읽고 일정은 0개예요. 인원·택시 성향·「둘째 날은 알아서」 요청을 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10월 1일부터 1박 2일로 서울 가요. 어른 둘에 초등학생 하나예요. 첫날은 오전에 경복궁 보고 점심은 근처에서 먹고, 오후엔 국립민속박물관 가려고요. 아이가 많이 걸으면 힘들어해서 이동은 웬만하면 택시로 할게요. 둘째 날은 알아서 짜 주세요."
    },
    {
      "code": "test26",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 4박 5일, 조건이 많은 문단",
      "description": "숙소 미정 · 날별 행선지 · 계단 피하기 · 귀가 시각 · 비 오는 날 조건이 긴 문단에 있습니다.",
      "category": "paragraph",
      "expected": "10/16 지금 구조: 기간·인원은 읽지만 일정 세 개가 문장 조각이에요. 날별 행선지·계단·귀가 시각·비 조건을 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10월 1일에 도착해서 4박 5일 있어요. 부모님 모시고 셋이 가요. 숙소는 아직 못 정했고 광화문 근처면 좋겠어요. 첫날은 도착이 오후 3시라 저녁만 먹고 쉴게요. 둘째 날은 창덕궁 후원이랑 종묘, 셋째 날은 국립중앙박물관에서 하루 종일 있고, 넷째 날은 남산 쪽으로 가고 싶어요. 아버지가 무릎이 안 좋으셔서 계단 많은 곳은 빼 주시고 매일 저녁 7시 전에는 숙소로 돌아가고 싶어요. 비 오는 날은 실내 일정으로 바꿔 주세요. 마지막 날은 오전에 짐 싸고 12시에 공항으로 가요."
    },
    {
      "code": "test27",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 날짜,시간,장소 두 행",
      "description": "쉼표로 나눈 가장 짧은 표입니다.",
      "category": "csv",
      "expected": "10/16 지금 구조: 두 곳은 읽지만 머리줄의 「장소」가 일정 하나로 더 생겨요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "날짜,시간,장소\n2026-10-01,10:00,국립중앙박물관\n2026-10-01,13:00,전쟁기념관"
    },
    {
      "code": "test28",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 메모 칸에 이동·조건",
      "description": "메모 칸에 「택시로 이동」 · 「비 오면 생략」이 들어 있는 하루 표입니다.",
      "category": "csv",
      "expected": "10/16 지금 구조: 여섯 곳은 읽지만 메모 칸이 이름에 붙고(「경복궁,한복 대여」) 머리줄의 「장소」가 일정으로 생겨요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "날짜,시간,장소,메모\n2026-10-01,09:00,경복궁,한복 대여\n2026-10-01,11:30,국립고궁박물관,\n2026-10-01,13:00,토속촌삼계탕,택시로 이동\n2026-10-01,15:00,통인시장,\n2026-10-01,17:30,청와대 사랑채,걸어서\n2026-10-01,19:30,광화문광장,비 오면 생략"
    },
    {
      "code": "test29",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 영어 머리줄 TSV 3일",
      "description": "탭으로 나눈 영어 머리줄 표에 영어 · 한글 장소와 교통 칸이 섞여 있습니다.",
      "category": "csv",
      "expected": "10/16 지금 구조: 여덟 곳을 모두 첫날로 읽고(일차 칸을 쓰지 못함) 교통 칸이 이름에 붙어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "Trip start\t2026-10-01\t3 people\t\nDay\tTime\tPlace\tTransport\n1\t10:00\tGyeongbokgung Palace\tsubway\n1\t13:00\t광장시장\twalk\n1\t16:00\tDongdaemun Design Plaza\tsubway\n2\t09:30\tChangdeokgung Palace\tbus\n2\t12:30\t익선동\twalk\n2\t15:00\tJongmyo Shrine\twalk\n3\t11:00\tLotte World Tower\tsubway\n3\t14:00\t석촌호수\twalk"
    },
    {
      "code": "test30",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 날짜와 일정 배열",
      "description": "앱에서 내보낸 듯한 가장 짧은 JSON 입니다.",
      "category": "json",
      "expected": "10/16 지금 구조: 시각은 읽지만 이름에 JSON 기호가 붙어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "{\"date\": \"2026-10-01\", \"plan\": [\"10:00 창덕궁\", \"13:00 광장시장\"]}"
    },
    {
      "code": "test31",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 시작·끝 시각이 있는 배열",
      "description": "title · start · end 칸으로 된 하루 일정 배열입니다.",
      "category": "json",
      "expected": "10/16 지금 구조: 시각은 읽지만 일정 이름이 JSON 조각이 되고 시작·끝이 일정 둘로 나뉘어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "[\n  {\"title\": \"덕수궁 관람\", \"start\": \"2026-10-01T09:30\", \"end\": \"2026-10-01T11:00\"},\n  {\"title\": \"서울시립미술관\", \"start\": \"2026-10-01T11:30\", \"end\": \"2026-10-01T13:00\"},\n  {\"title\": \"정동 점심\", \"start\": \"2026-10-01T13:00\", \"end\": \"2026-10-01T14:00\"},\n  {\"title\": \"서울역사박물관\", \"start\": \"2026-10-01T15:00\", \"end\": \"2026-10-01T16:30\"},\n  {\"title\": \"광화문광장 산책\", \"start\": \"2026-10-01T19:00\"}\n]"
    },
    {
      "code": "test32",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 3일 계획과 「요청」 칸",
      "description": "기간 · 인원 · 날별 일정과 이동 · 추천 요청이 든 JSON 입니다.",
      "category": "json",
      "expected": "10/16 지금 구조: 시각은 읽지만 모두 첫날로 읽고 이름이 JSON 조각이에요. 「저녁 식당」이 일정으로 생기고 지하철·인원은 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "{\"trip\": {\"start\": \"2026-10-01\", \"days\": 3, \"people\": 4},\n \"plan\": [\n  {\"day\": 1, \"time\": \"10:00\", \"place\": \"국립중앙박물관\"},\n  {\"day\": 1, \"time\": \"14:00\", \"place\": \"이태원\"},\n  {\"day\": 2, \"time\": \"10:00\", \"place\": \"서울숲\"},\n  {\"day\": 2, \"time\": \"13:00\", \"place\": \"성수동 카페거리\"},\n  {\"day\": 3, \"time\": \"11:00\", \"place\": \"코엑스 별마당도서관\"},\n  {\"day\": 3, \"time\": \"13:00\", \"place\": \"봉은사\"}\n ],\n \"요청\": \"이동은 지하철로 하고, 둘째 날 저녁 식당은 추천해 주세요\"}"
    },
    {
      "code": "test33",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 한 칸에 하루 통째",
      "description": "엑셀에서 복사한 한 행 — 일정 칸 하나에 하루가 다 들어 있습니다.",
      "category": "excel_memo",
      "expected": "10/16 지금 구조: 일정이 0개예요. 한 칸에 든 하루를 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10/1\t오전 경복궁, 점심 통인시장, 오후 서촌 산책\t택시"
    },
    {
      "code": "test34",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 칸 안 줄바꿈이 있는 3일 메모",
      "description": "엑셀 칸 안의 줄바꿈이 따옴표로 묶여 붙여진 3일 메모입니다.",
      "category": "excel_memo",
      "expected": "10/16 지금 구조: 날짜별로 일곱 곳을 읽지만 3시·2시·1시를 새벽으로 읽고 비고 칸이 이름에 붙어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "Date\t일정\t비고\n10/1\t\"10시 창덕궁\n12시 익선동 점심\n3시 종묘\"\t지하철\n10/2\t\"11시 국립중앙박물관\n2시 이태원\"\t비 오면 실내\n10/3\t\"10시 서울숲\n1시 성수 카페\"\t"
    },
    {
      "code": "test35",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 마크다운 표 두 행",
      "description": "채팅에 붙인 마크다운 표입니다.",
      "category": "pasted_table",
      "expected": "10/16 지금 구조: 두 곳을 읽고 날짜를 물어요(원문에 날짜가 없어 맞는 동작). 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "| 시간 | 장소 |\n|---|---|\n| 10:00 | 덕수궁 |\n| 12:00 | 서울시립미술관 |"
    },
    {
      "code": "test36",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 이모지 목록 하루",
      "description": "📍 · ⏰ · ▶ 기호가 붙은 메신저식 목록입니다.",
      "category": "pasted_table",
      "expected": "10/16 지금 구조: 다섯 곳과 시각은 읽지만 이름에 「▶」·이모지가 붙어요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "📍 10/1(목)\n⏰ 10:00 ▶ 홍대입구역\n⏰ 11:00 ▶ 연남동 경의선숲길 🌳\n⏰ 13:00 ▶ 망원시장 🍢\n⏰ 15:30 ▶ 망원한강공원\n⏰ 19:00 ▶ 합정역 저녁 🍽"
    },
    {
      "code": "test37",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 날짜 칸이 있는 2박 3일 표",
      "description": "날짜 · 시간 · 장소 · 메모 칸의 마크다운 표 아홉 행입니다.",
      "category": "pasted_table",
      "expected": "10/16 지금 구조: 아홉 곳을 날짜·시각대로 읽어요. 메모(걸어서·예약함·비 오면 생략)는 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "| 날짜 | 시간 | 장소 | 메모 |\n|---|---|---|---|\n| 10/1 | 10:00 | 경복궁 | 수문장 교대식 |\n| 10/1 | 12:30 | 토속촌삼계탕 | |\n| 10/1 | 15:00 | 북촌한옥마을 | 걸어서 |\n| 10/2 | 10:00 | 롯데월드 | |\n| 10/2 | 18:00 | 석촌호수 | |\n| 10/2 | 19:30 | 롯데월드타워 서울스카이 | 예약함 |\n| 10/3 | 10:00 | 서울숲 | |\n| 10/3 | 12:30 | 성수동 카페거리 | |\n| 10/3 | 15:00 | 뚝섬한강공원 | 비 오면 생략 |"
    },
    {
      "code": "test38",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 세 번 나눠 보낸 말",
      "description": "「내일 갈 거예요」 · 시각 · 끼니를 한 줄씩 보낸 모양입니다.",
      "category": "multi_message",
      "expected": "10/16 지금 구조: 서울숲을 읽고 날짜(내일)는 비워 둬요. 「점심은 성수에서」는 시각 없는 일정이 돼요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "내일 갈 거예요\n10시 서울숲\n점심은 성수에서"
    },
    {
      "code": "test39",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 덧붙이며 보낸 하루",
      "description": "「아 그리고」로 덧붙이고 이동 방법을 마지막에 보낸 모양입니다.",
      "category": "multi_message",
      "expected": "10/16 지금 구조: 세 곳은 읽지만 2시를 새벽으로 읽고 「서울」이 일정으로 하나 더 생겨요. 걷기 성향은 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 일정 보낼게요\n10/1 목요일\n9시 반 경복궁\n12시 토속촌\n아 그리고 2시에 국립현대미술관 서울관\n저녁은 아직 못 정했어요\n이동은 다 걸어서 할게요"
    },
    {
      "code": "test40",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 사흘을 나눠 보낸 말",
      "description": "날짜 줄과 일정 줄을 따로따로 보낸 3일 모양입니다.",
      "category": "multi_message",
      "expected": "10/16 지금 구조: 날짜별로 읽지만 1시·2시·6시·4시를 새벽으로 읽고 「까지만요」가 일정이 돼요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "일정이요\n10월 1일\n10시 국립중앙박물관\n1시 이촌동 점심\n10월 2일\n11시 창경궁\n2시 대학로\n6시 혜화 저녁\n10월 3일\n10시 여의도 더현대 서울\n1시 여의도한강공원\n마지막 날은 4시까지만요"
    },
    {
      "code": "test41",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 일정 하나와 질문",
      "description": "일정 한 줄과 운영 여부 질문이 함께 있습니다.",
      "category": "mixed_request",
      "expected": "10/16 지금 구조: 경복궁은 읽지만 질문 문장이 이름에 붙고 질문으로 알아보지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10월 1일 10시 경복궁 가요. 그날 문 여나요?"
    },
    {
      "code": "test42",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 오전은 정했고 오후는 채워 주세요",
      "description": "정한 일정 · 「알아서 채워」 요청 · 예약 질문이 한 글에 있습니다.",
      "category": "mixed_request",
      "expected": "10/16 지금 구조: 창덕궁·인원은 읽지만 익선동 항목에 「오후는 알아서 채워 주세요」와 질문이 붙어요. 짜기 요청을 알아보지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10월 1일(목)에 넷이 가요. 10시 창덕궁, 12시 반 익선동 점심까지 정했고 오후는 알아서 채워 주세요. 창덕궁 후원은 예약해야 하나요?"
    },
    {
      "code": "test43",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 2박 3일 짜기 + 예약 + 이동 질문",
      "description": "짜기 요청 · 예약해 둔 일정 · 체크인 · 공항 시각 · 이동 시간 질문이 섞여 있습니다.",
      "category": "mixed_request",
      "expected": "10/16 지금 구조: 짜기 요청·기간은 읽지만 일정 두 개가 문장 조각이고 모두 첫날이에요. 공항 시각·질문은 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10월 1일부터 2박 3일 일정 짜 줘. 커플이고 야경 좋은 곳 위주로. 첫날 오후 3시에 롯데호텔 서울 체크인하고, 둘째 날 저녁 8시에 롯데월드타워 서울스카이 예약해 뒀어. 마지막 날은 오후 2시까지 김포공항 가야 돼. 택시 타면 명동에서 김포공항까지 얼마나 걸려?"
    },
    {
      "code": "test44",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 「남산타워 말고 롯데타워로」",
      "description": "보낸 뒤 장소를 바꾸는 말이 이어 붙어 있습니다.",
      "category": "correction",
      "expected": "10/16 지금 구조: 정정을 반영하지 못해요 — 남산타워가 남고 롯데타워가 하나 더 생겨요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10/1 10시 남산타워 12시 명동 점심\n아 남산타워 말고 롯데타워로 바꿀게요"
    },
    {
      "code": "test45",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 하루 목록 뒤 순서 바꾸기",
      "description": "목록 끝에 「순서 바꿀래」 정정이 있습니다.",
      "category": "correction",
      "expected": "10/16 지금 구조: 네 곳은 읽지만 「순서 바꿀래」 정정을 반영하지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "1일차 10/1\n10:00 경복궁\n12:00 광장시장\n15:00 창덕궁\n17:00 인사동\n아 순서 바꿀래 창덕궁 먼저 가고 경복궁은 오후에"
    },
    {
      "code": "test46",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "김 · 이틀 일정 뒤 빼기·날짜 정정",
      "description": "이틀 목록 뒤에 한 곳 빼기와 날짜 바꾸기가 이어집니다.",
      "category": "correction",
      "expected": "10/16 지금 구조: 여섯 곳은 읽지만 낙산공원 빼기·둘째 날 미루기를 반영하지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "10/1\n09:00 창경궁\n11:00 대학로\n14:00 낙산공원\n18:00 혜화 저녁\n10/2\n10:00 서울숲\n13:00 성수동 카페거리\n아 낙산공원은 빼고 그 시간에 이화벽화마을 갈게요\n그리고 둘째 날은 하루 미뤄 주세요"
    },
    {
      "code": "test47",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 시각 없는 「오늘 저녁에 잠실 가서」 한 줄",
      "description": "실제 접수에 많은 시각 없는 한 줄 — 오늘 · 지금 기준 요청입니다.",
      "category": "real",
      "expected": "10/16 지금 구조: 잠실·석촌호수를 오늘 날짜로 읽어요(시각 없음). 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "오늘 저녁에 잠실 가서 밥 먹고 석촌호수 한 바퀴 돌고 올 거야"
    },
    {
      "code": "test48",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "짧음 · 시각+장소 두 줄",
      "description": "날짜 없이 저녁 일정 두 줄만 보낸 모양입니다.",
      "category": "real",
      "expected": "10/16 지금 구조: 두 곳과 시각을 읽고 날짜를 물어요(원문에 날짜가 없어 맞는 동작). 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "19:00 을지로 노가리골목\n20:30 청계천 산책"
    },
    {
      "code": "test49",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 화면 예시를 고친 1일차 목록",
      "description": "화면 예시 형식(「1일차 · 날짜」)을 조금 고쳐 보낸 모양입니다.",
      "category": "real",
      "expected": "10/16 지금 구조: 다섯 줄을 날짜·시각대로 읽어요(체크아웃도 일정 하나). 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "1일차 · 2026-10-01\n10:00 창덕궁 관람\n13:00 광장시장 점심\n15:00 롯데호텔 서울 체크인\n\n2일차 · 2026-10-02\n11:00 N서울타워\n11:00 체크아웃"
    },
    {
      "code": "test50",
      "mode": "prepared_text",
      "catalog_version": "seoul-text-v3",
      "name": "보통 · 장소 없이 조건만 있는 2박 3일",
      "description": "기간 · 인원 · 이동 수단 · 마치는 시각 조건만 있고 장소가 없는 요청입니다.",
      "category": "real",
      "expected": "10/16 지금 구조: 기간은 읽지만 「21시 전에 끝내 주세요」가 21시 식사 일정이 되고 인원·대중교통·짜기 요청은 읽지 못해요. 입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.",
      "text": "서울 2박 3일, 성인 3명입니다. 대중교통으로 다니고 매일 21시 전에 일정을 끝내 주세요. 관광과 식사를 적당히 섞어 주세요."
    }
  ]
};

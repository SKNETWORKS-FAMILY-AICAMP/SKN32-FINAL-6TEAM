# 가게 이름 없는 식사 줄 — 테스트 서버(guguroute.devroro.click) 확인 화면 실측 · 2026-10-18

손님 세션(필수 약관 2개만 동의 · 항로 지킴이 끔) · 등록 안 함. 값은 각 접수의 `GET /v1/web/trip-intakes/{id}` 응답(화면이 읽는 것과 같다).

| # | 접수 | 원문 줄 | 서버 결과(판 · 종류 · 장소 · 출처 · 분류 · 장소 줄) |
|---|---|---|---|
| D1 | 8245f0dd | 경복궁 보고 나서 점심 | rev2 · dining 「점심」 12:00 · 파티스리 데시데 · customer_pick · 디저트카페 · ok「직접 고른 곳이에요 · 카카오 지도에서 찾았어요」 · 운영시간 unknown · 화면 「모두 확인했어요」 |
| D2 | 41bf4254 | 12:30 광장시장 근처 식당에서 점심 | rev1 · dining · 순희네빈대떡 · dining_ledger · ok「가게 이름이 없어 순희네빈대떡으로 잡았어요」 · 영업 11:00–21:00 ok |
| D3 | d796285a | 11:00 성수동 카페거리 | rev2 · **dining**(활동이어야 함) · 탐광 · dining_ledger · warn「우리 식당 목록 정보로 「탐광」을 찾았어요」 |
| D3 | | 점심은 서울숲 근처에서 | dining 「서울숲」 12:00 · 체다앤올리 · dining_ledger · warn(확인 필요) |
| D3 | | 18:00 성수 근처 맛집에서 저녁 | dining · 무브모브 카페 · customer_pick · 카페 · ok「직접 고른 곳이에요」 |
| D4 | f37b1956 | 남산 내려와서 명동에서 점심 | rev2 · dining 「명동」 12:00 · 백제삼계탕 · customer_pick · ok「직접 고른 곳이에요」 |
| D4 | | 19:00 저녁은 숙소 근처 아무 데나 | dining · 장소 없음 · bad「장소를 정하지 못했어요」(계획에 숙소 없음) |
| D5 | 6de67101 | 보라매공원 근처 점심 | **activity 「보라매공원」 12:00 · tour_api 관광지 · ok — 점심(식사)이 없다** |
| D6 | 0ec01694 | 롯데월드 보고 나서 점심 | rev2 · dining 「점심」 · 도미노피자 롯데월드점 · customer_pick · ok「직접 고른 곳이에요」 |
| D7 | d9b012da | 점심 먹고 경복궁 / 14:00 경복궁 | **activity 경복궁 09:00 + 경복궁 14:00 — 점심이 없고 경복궁이 둘** |
| D7 | | 18:00 광화문 근처에서 저녁 | dining · 무구옥 · dining_ledger · ok「가게 이름이 없어 무구옥으로 잡았어요」 |

코드 근거(origin/develop `140ccbc8`)
- `components/intake/autofix.py::_pick` — 자동 추천이 고른 곳을 `source: "customer_pick"` 로 저장 → `review.py:153` 이 「직접 고른 곳이에요」를 쓴다.
- `components/intake/candidates.py::_kakao_places` — 카카오 분류 FD6(음식점) · **CE7(카페)** 를 모두 `kind="dining"` 으로 표시.
- `components/intake/candidates.py::_team_dining_places` — 요식 팀 대체안은 원래 식당의 원장 번호(`_dining_uid`)가 있을 때만 부른다 → 가게 이름 없는 식사는 팀에 묻지 않는다.

화면 쪽(같은 날 관찰): 같은 탭에서 두 번째 계획을 보내거나 뒤 탭에서 보내면 `/intakes/starting` 이 `GET /v1/web/trip-intakes/starting → 422` 를 부르고 POST 없이 「계획을 서버로 보내고 있어요」에 멈춘다(재현 2회 + 뒤 탭 3개). 새 탭 · 앞 탭에서는 정상. 입력 칸은 앞 계획을 임시 저장에서 되살려 새 글이 뒤에 붙는다.

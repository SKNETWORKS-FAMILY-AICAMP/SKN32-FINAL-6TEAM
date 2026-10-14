---
document_id: t_current_dining_01
title: 식당 이름이 없는 식사 일정
scope: travel_dining
version: 2026-10-12.1
pii_class: none
effective_from: '2026-10-12'
source_uri: internal://tripilot/current-travel/dining
customer_answers:
  식당 이름이 없는 식사 일정: 한식 점심처럼 식사 종류만 적었다면 식당 후보에서 가게를 정해야 해요. 근처 관광지를 식당으로 대신 연결하지 않아요.
    식당 위치를 찾은 것과 예약 완료는 별개예요.
---

현재 여행 안내의 제한과 확인 방법입니다. 근거: wiki/teams/team-boundary.md, wiki/external/rest-endpoints/web-access.md, app/domains/travel_ops/components/conversation/trip_replies.py.

## 식당 이름이 없는 식사 일정
식당 이름 없이 한식 점심만 적으면 어떻게 하나요? 식당과 관광지는 어떻게 구별하나요? 식사 종류나 지역만 적힌 항목에는 가게 이름이 없습니다. 식당 후보에서 실제 가게를 확인해야 하며, 근처 관광지의 좌표를 식당 좌표로 대신 쓰지 않습니다. 식당과 카페는 요식 자료에서 확인하고, 음식점이 아닌 관광지는 식사 장소로 확정하지 않습니다. 같은 이름의 관광지와 음식점이 있을 때에는 식사라는 일정 종류에 맞는 장소를 찾습니다. 식당의 위치와 운영 정보가 확인된 것과 업체 예약이 완료된 것은 다릅니다. 예약 여부는 여행에 입력된 표시 또는 업체의 확인 자료로 확인하며, 장소를 찾았다는 이유만으로 예약 완료라고 안내하지 않습니다.

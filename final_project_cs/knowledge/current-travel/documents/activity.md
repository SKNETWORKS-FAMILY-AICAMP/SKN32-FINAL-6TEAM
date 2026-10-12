---
document_id: t_current_activity_01
title: 관광지와 활동 장소 확인
scope: travel_activity
version: 2026-10-12.1
pii_class: none
effective_from: '2026-10-12'
source_uri: internal://tripilot/current-travel/activity
customer_answers:
  관광지와 활동 장소 확인: 예약 없는 산책이나 관람도 확인할 수 있어요. 장소와 방문 시각을 운영시간·휴무 자료와 대조해요. 무료라는 이유만으로
    언제나 방문 가능하다고 안내하지 않아요.
---

현재 여행 안내의 제한과 확인 방법입니다. 근거: wiki/teams/team-boundary.md, wiki/external/rest-endpoints/web-access.md, app/domains/travel_ops/components/conversation/trip_replies.py.

## 관광지와 활동 장소 확인
관광지와 활동 장소는 무엇을 확인하나요? 예약 없는 활동도 가능한가요? 활동 일정에는 자연 명소, 문화 시설, 레포츠와 쇼핑 장소가 포함됩니다. 예약이 없는 산책이나 관람도 일정 항목으로 확인할 수 있습니다. 장소 이름, 위치, 방문 시각과 확인된 운영 조건을 대조합니다. 무료 또는 무예약이라는 표현만으로 모든 날짜와 시각에 방문할 수 있다고 단정하지 않습니다. 운영시간과 휴무 자료가 있으면 해당 방문 날짜와 비교하고, 행사나 임시 휴무 정보는 확인된 출처의 값으로 안내합니다. 이름이 같은 장소나 지점이 여러 곳이면 구별할 수 있는 위치를 확인해야 하며, 찾지 않은 영업시간이나 입장 조건을 만들지 않습니다.

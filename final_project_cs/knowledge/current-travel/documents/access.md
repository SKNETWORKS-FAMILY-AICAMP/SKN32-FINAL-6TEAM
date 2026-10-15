---
document_id: t_current_access_01
title: 동행자의 이용 조건 확인
scope: travel_access
version: 2026-10-12.1
pii_class: none
effective_from: '2026-10-12'
source_uri: internal://tripilot/current-travel/access
customer_answers:
  동행자의 이용 조건 확인: 방문할 장소와 이동 구간을 기준으로 이용 조건을 확인해야 해요. 위치나 운영시간을 찾았다는 이유만으로 휠체어 이용 가능을
    보장하지 않아요. 필요한 조건을 알려 주시면 확인할 항목을 구분할 수 있어요.
---

현재 여행 안내의 제한과 확인 방법입니다. 근거: wiki/teams/team-boundary.md, wiki/external/rest-endpoints/web-access.md, app/domains/travel_ops/components/conversation/trip_replies.py.

## 동행자의 이용 조건 확인
휠체어로 이용할 수 있나요? 동행자 조건은 어떻게 알려 주나요? 휠체어 이용, 보행의 어려움이나 동행자의 접근 조건은 방문할 장소와 이동 구간에 따라 확인해야 합니다. 관광지 또는 식당이라는 분류만으로 접근 가능하다고 보장하지 않습니다. 출입구, 계단과 이동 경로 등 필요한 조건은 실제 확보한 장소 정보와 고객이 알려 준 조건을 대조합니다. 같은 장소라도 출입구와 이용 구역이 다를 수 있으므로 확인되지 않은 시설을 있다고 안내하지 않습니다. 위치와 운영시간을 찾았다는 사실만으로 접근성 검증이 완료되었다고 말하지 않습니다. 고객의 건강 상태를 추정하거나 의료 판단을 만들지 않으며, 여행 이용 조건 확인에 필요한 정보만 사용합니다.

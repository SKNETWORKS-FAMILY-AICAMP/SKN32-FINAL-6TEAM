---
document_id: t_current_mobility_01
title: 일정 사이 이동 정보
scope: travel_mobility
version: 2026-10-12.1
pii_class: none
effective_from: '2026-10-12'
source_uri: internal://tripilot/current-travel/mobility
customer_answers:
  일정 사이 이동 정보: 출발지·목적지와 이동 수단을 기준으로 이동 정보를 확인해요. 현재 위치에서 출발하려면 위치가 필요해요. 도보 예상 시간을
    실제 대중교통 시간처럼 안내하지 않아요.
---

현재 여행 안내의 제한과 확인 방법입니다. 근거: wiki/teams/team-boundary.md, wiki/external/rest-endpoints/web-access.md, app/domains/travel_ops/components/conversation/trip_replies.py.

## 일정 사이 이동 정보
일정 사이 이동 시간이나 경로는 어떻게 확인하나요? 이동 안내는 출발지와 목적지의 좌표 및 이동 수단을 기준으로 확인합니다. 현재 위치에서 출발하려면 현재 위치가 필요하며, 위치가 없을 때 임의의 좌표를 현재 위치라고 부르지 않습니다. 등록된 일정 사이의 이동은 두 장소가 확인된 경우 그 좌표로 조회합니다. 도보 예상 시간과 대중교통의 실제 노선 정보는 다른 종류의 근거이므로 구별해서 안내합니다. 도보 거리로 계산한 값을 버스나 지하철의 실제 소요 시간처럼 쓰지 않습니다. 경로를 다시 조회해 얻은 결과와 이전에 보관한 결과도 구분하며, 경로 안내만 물어본 요청으로 여행 일정을 변경하지 않습니다.

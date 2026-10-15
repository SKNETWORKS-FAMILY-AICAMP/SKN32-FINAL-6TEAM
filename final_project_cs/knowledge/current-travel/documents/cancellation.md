---
document_id: t_current_cancellation_01
title: 업체 취소 조건과 일정 변경 구분
scope: travel_cancellation
version: 2026-10-12.1
pii_class: none
effective_from: '2026-10-12'
source_uri: internal://tripilot/current-travel/cancellation
customer_answers:
  업체 취소 조건과 일정 변경 구분: 위약금과 환불은 해당 예약의 취소 조건을 확인해야 해요. 일정에서 장소를 바꿔도 업체 예약이 자동으로 취소되지는
    않아요. 확인하지 않은 무료 취소 기한이나 환불 금액을 약속하지 않아요.
---

현재 여행 안내의 제한과 확인 방법입니다. 근거: wiki/teams/team-boundary.md, wiki/external/rest-endpoints/web-access.md, app/domains/travel_ops/components/conversation/trip_replies.py.

## 업체 취소 조건과 일정 변경 구분
취소하면 위약금이 있나요? 일정에서 빼면 예약도 취소되나요? 여행 일정의 항목을 바꾸거나 제외하는 것과 업체 예약을 취소하는 것은 서로 다른 처리입니다. 업체 취소 기한, 위약금과 환불 금액은 해당 예약에 등록된 조건이나 확인된 업체 자료로만 판단합니다. 장소의 종류만 보고 공통 무료 취소 기한을 만들지 않습니다. 예약 조건을 확인하지 않은 상태에서는 특정 시간 전까지 무료라는 약속이나 일정 비율의 환불을 보장하지 않습니다. 채팅에서 장소를 바꿨다는 응답은 업체 예약, 결제 또는 환불이 자동 완료되었다는 의미가 아닙니다. 업체 거래는 별도 권한과 필요한 승인 경계를 확인하며, 조회만 한 질문으로 취소를 실행하지 않습니다.

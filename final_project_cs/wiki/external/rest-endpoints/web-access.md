---
type: reference
title: 고객 채팅의 업무 재개·읽기 재전송
status: draft
domain: travel
---

# 고객 채팅의 업무 재개·읽기 재전송

`POST /v1/cases/{id}/messages`의 message는 `Controller.resume`의 답변 본문에 전달됩니다. 업무 되묻기는 `waiting_input`이며 고객 웹 응답도 대기를 완료로 위장하지 않습니다. 담당 Team의 실행과 필수 계산이 불가하면 HTTP 503 `team_unavailable`로 실패합니다.

여행 채팅은 업무 변경·업무 되묻기를 Controller/Team 경로로 보냅니다. 순수 조회는 읽기 경로에서 처리하므로 특정 업무 Team이 없어도 저장된 일정 읽기를 유지할 수 있습니다. 읽기 도중 새 필수 계산을 요청하면 해당 계산의 가용성 관문이 적용됩니다.

같은 request_id의 동일 원문만 재전송할 수 있습니다. 저장된 원문 해시와 다르면 409입니다. 최초 업무 접수 중단은 같은 Case로 복구하고, 실행 중인 업무를 임의로 다시 실행하지 않습니다. 명시한 업무·토큰 답변과 최근 질문 형식에 맞는 암시적 답변을 구분합니다.

복수 사실 문의·범위 조회가 중단되면 처음 읽기 해석과 스냅샷을 사용합니다. 해석·일정판이 맞지 않으면 409로 거절합니다. 대상 교정과 스냅샷은 같은 ROUTED 이벤트의 state_patch에 저장합니다. 복구 스냅샷에 고객 원문·좌표를 추가하지 않으며 위치 의존 문의는 자동 복구하지 않습니다.

일반 업무 변경은 Core의 동시성·멱등 적용 계약을 유지합니다. 업체 예약·결제 승인을 우회하는 계약은 추가하지 않았습니다.

[Team 실행 계약](../../teams/team-contract/plugin-availability.md), [실제 HTTP 재개 회귀](../../../tests/e2e/test_web_conversation_resume.py), [읽기 복구 회귀](../../../tests/e2e/test_recovery_read_merge_web.py).

# S-OPS-UNKNOWN-RUNBOOK 조사·작성 리포트

## 결론

절차서는 코드에 실제로 존재하는 `outbox.status='unknown'` 경로를 기준으로
작성했다. `customer_cases.status`에는 `unknown`이 없으므로 “unknown Case 목록”
화면이나 Case 상태 전이는 존재하지 않는다.

## 확인 근거

| 확인 대상 | 실제 확인 내용 |
|---|---|
| timeout 기록 | `app/infrastructure/messaging/worker.py`에서 `TimeoutError`, `ConnectionError` 발생 시 `UPDATE outbox SET status='unknown', last_error=...` |
| 재실행 여부 | worker는 `status='pending'`만 claim하며 unknown 분기에서 return한다. 자동 재큐잉 코드는 없다. |
| DB 상태 | `001_schema.sql`의 `outbox.status`는 text, `action_status` enum에는 별도로 unknown이 있으나 worker가 갱신하는 대상은 outbox다. |
| Case 전이 | `app/domain/events.py`의 EventType에는 unknown이 없고, `waiting_external`에서 `VALID_CALLBACK -> resuming`, `WAIT_EXPIRED -> escalated`가 실제 전이표다. |
| 단일 진입점 | `app/core/transition.py:transition_case()`가 projection UPDATE와 `case_events` append를 수행한다. |
| Case 화면 | `/ui/cases`, `/ui/cases/{case_id}`, `/ui/cases/{case_id}/trace` 존재. trace는 `case_events`를 표시한다. |
| 운영 요약 화면 | `/ui/admin`은 outbox 상태별 건수만 표시한다. unknown 행 상세/확정 기능은 없다. |
| API | `/v1/cases`, `/v1/cases/{case_id}` 등 Case API는 존재하지만 outbox unknown 조회·재판정 API는 없다. |
| provider 도메인 경로 | 특정 결제·배송 provider 콘솔/조회 endpoint 연동은 `app/`에서 확인되지 않았다. 문서에 가상 경로를 넣지 않았다. |

## 절차서에 반영한 운영 판단

1. SQL은 실제 `outbox` 컬럼과 tenant 범위를 사용해 unknown 행과 `last_error`를
   찾도록 했다.
2. payload에 `case_id`가 있는 경우에만 Case 화면과 trace를 연계하도록 했다.
3. provider 완료 확인 시 `waiting_external`에서 사람이
   `EventType.VALID_CALLBACK`을 `provider_ref` payload로 호출하는 실제 계약을
   제시했다.
4. 완료되지 않았거나 확인 불가하여 외부 대기를 명시적으로 끝내야 하는 경우에는
   실제 전이표에 있는 `EventType.WAIT_EXPIRED`를 사용해 `escalated`로 보낸다.
5. outbox 행 자체를 `delivered`로 바꾸는 운영 API가 없으므로 직접 UPDATE나
   자동 재시도를 절차로 제안하지 않았다.

## 제한 사항

현재 코드에는 사람이 provider 확인 결과를 outbox 상태 또는 action request에
반영하는 전용 API/화면/CLI가 없다. 따라서 이 문서는 “어디서 unknown을 찾고,
어떤 실제 Case 이벤트 계약으로 후속 상태를 남길 수 있는가”까지를 문서화하며,
provider별 업무 완료를 시스템이 자동 확정한다고 주장하지 않는다.

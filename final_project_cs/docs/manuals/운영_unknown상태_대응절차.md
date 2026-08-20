# provider timeout `unknown` 상태 대응 절차

## 1. 적용 범위와 결론

이 저장소에서 `unknown`은 Case 상태가 아니다. `customer_cases.status`의 enum에는
`unknown`이 없으며, provider 호출을 담은 **outbox 메시지의 상태**로만 기록된다.
따라서 `unknown`은 “provider가 성공했는지 실패했는지 우리 쪽에서 확인하지 못한
상태”를 뜻한다. 성공으로 간주하거나 실패로 단정하지 않는다.

`app/infrastructure/messaging/worker.py`의 `OutboxWorker.process_once()`가
`TimeoutError` 또는 `ConnectionError`를 받으면 해당 `outbox` 행을
`status='unknown'`으로 바꾸고 `last_error`를 남긴다. 이 분기에는 재큐잉이 없고,
`unknown`을 다시 읽는 pending 조회에도 포함되지 않는다. 자동 재실행하지 않는다.

## 2. 발견 절차

### 2.1 SQL로 대상 찾기

운영 DB에서 현재 tenant를 명시해 다음을 실행한다. `outbox`의 실제 스키마에 있는
컬럼만 조회한다.

```sql
SELECT message_id,
       topic,
       dedupe_key,
       payload_json,
       attempts,
       last_error,
       locked_at,
       created_at
FROM outbox
WHERE tenant_id = '<TENANT_ID>'
  AND status = 'unknown'
ORDER BY created_at;
```

Case와 연결되는 메시지라면 `payload_json` 안의 `case_id`를 확인한 뒤 아래처럼
Case 및 이벤트를 함께 조회한다.

```sql
SELECT cc.case_id, cc.status, cc.version, cc.updated_at,
       o.message_id, o.topic, o.payload_json, o.last_error
FROM outbox AS o
LEFT JOIN customer_cases AS cc
  ON cc.tenant_id = o.tenant_id
 AND cc.case_id = (o.payload_json ->> 'case_id')::uuid
WHERE o.tenant_id = '<TENANT_ID>'
  AND o.status = 'unknown';
```

위 쿼리는 `payload_json.case_id`가 없는 메시지도 보여주며, 그런 행의 Case 연결은
`NULL`이다. 임의의 Case를 추측해 연결하지 않는다.

### 2.2 제공되는 화면과 API

- `/ui/admin`: tenant 범위의 outbox 상태별 **건수**를 보여준다. `unknown` 행의
  message_id, topic, payload, last_error를 보여주는 화면은 아니다.
- `/ui/cases`: Case 목록 화면이다. `customer_cases.status`를 표시하지만
  `unknown` 필터는 없다.
- `/ui/cases/{case_id}`: Case 상세와 현재 `state_json`을 본다.
- `/ui/cases/{case_id}/trace`: 해당 Case의 append-only `case_events` 타임라인을
  본다.
- `/v1/cases`, `/v1/cases/{case_id}`: Case 조회 API는 있으나 outbox 조회 API는
  없다. `unknown` outbox를 조회하거나 재판정하는 전용 API도 없다.

따라서 운영자는 SQL로 `outbox` 행을 찾고, Case ID가 있을 때만 위 Case 화면/API와
trace를 보조 자료로 사용한다. 애플리케이션 로그의 별도 검색 API나 전용 trace
화면은 현재 없다. timeout 예외의 문자열은 `outbox.last_error`에 저장된다.

## 3. 사람이 확인할 항목

1. `message_id`, `topic`, `dedupe_key`, `attempts`, `last_error`, `payload_json`을
   기록한다. payload에 있는 provider 식별자나 업무 식별자를 이용해 어느 외부
   provider의 어느 작업인지 특정한다.
2. payload에 `case_id`가 있으면 `/ui/cases/{case_id}`와
   `/ui/cases/{case_id}/trace`에서 마지막 Case 상태, `version`, 마지막 이벤트,
   `provider_ref`/`state_json`을 확인한다.
3. 이 코드베이스에는 결제·배송 등 특정 외부 provider의 콘솔 연동, provider별
   조회 API, provider별 운영 화면이 구현되어 있지 않다. 그러므로 실제 확인은
   해당 `topic`/payload가 가리키는 외부 provider의 공식 운영 콘솔 또는 공식
   조회 절차에서 사람이 수행한다. 이 프로젝트 문서에는 존재하지 않는
   provider 이름·콘솔 경로·endpoint를 가정하지 않는다.
4. provider에 `provider_ref` 또는 동등한 업무 식별자로 조회해 “완료”, “미완료/실패”,
   “조회 불가” 중 하나를 명시적으로 기록한다. timeout 사실만으로 완료를 추정하지
   않는다.

## 4. 확인 결과별 조치

### 4.1 provider가 완료했다고 확인한 경우

현재 Case가 `waiting_external`이고 provider 결과를 callback으로 반영해야 하는
흐름이라면, 사람이 확인한 근거를 payload에 넣어 `EventType.VALID_CALLBACK`을
`transition_case()`로 호출한다. 이 이벤트의 필수 payload는 `provider_ref`이며,
`waiting_external -> resuming` 전이를 만든다. 이후 정상적인 resume 흐름에서
`EventType.RESUMED`가 `resuming -> running`으로 이어진다.

저장소에는 이 작업을 수행하는 운영자용 HTTP API나 CLI가 없으므로, 아래는 실제
코드의 함수·이벤트·payload 계약을 사용한 수동 실행 예시다. 실행 전 Case의 최신
version을 읽고, 실제 provider 조회 근거를 `state_patch`에 남긴다.

```python
from uuid import UUID

from app.domain.events import EventType
from app.infrastructure.db.session import get_connection
from app.core.transition import transition_case

tenant_id = "<TENANT_ID>"
case_id = UUID("<CASE_ID>")
provider_ref = "<PROVIDER_REFERENCE>"

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, version FROM customer_cases "
            "WHERE tenant_id=%s AND case_id=%s",
            (tenant_id, case_id),
        )
        status, version = cur.fetchone()
    if status != "waiting_external":
        raise RuntimeError(f"expected waiting_external, got {status}")
    with conn.transaction():
        transition_case(
            conn,
            tenant_id=tenant_id,
            case_id=case_id,
            expected_version=version,
            event_type=EventType.VALID_CALLBACK,
            payload={
                "provider_ref": provider_ref,
                "state_patch": {
                    "manual_provider_check": "confirmed_completed",
                    "manual_provider_check_actor": "<OPERATOR_ID>",
                },
            },
            actor_type="human",
            actor_id="<OPERATOR_ID>",
        )
```

이 호출은 Case 이벤트를 기록할 뿐이며, `outbox.status`를 `delivered`로 바꾸거나
provider 작업을 재실행하지 않는다. 현재 코드에는 unknown outbox를 사람이
확정된 결과와 연결해 outbox 자체를 종결하는 지원 절차가 없다. 그 사실을 리포트에
남기고, 직접 DB UPDATE로 보정하지 않는다.

### 4.2 provider가 미완료 또는 실패라고 확인한 경우

`unknown`을 성공으로 바꾸지 않는다. 현재 `waiting_external` Case에는
`VALID_CALLBACK` 외에 `WAIT_EXPIRED`가 허용되며, 후자는
`waiting_external -> escalated` 전이를 만든다. “provider가 성공하지 않았다”는
사람의 확인을 근거로 해당 이벤트를 명시적으로 호출한다.

```python
transition_case(
    conn,
    tenant_id=tenant_id,
    case_id=case_id,
    expected_version=version,
    event_type=EventType.WAIT_EXPIRED,
    payload={"wait_reason": "external_callback"},
    actor_type="human",
    actor_id="<OPERATOR_ID>",
)
```

위 코드는 앞의 예시처럼 `with conn.transaction():` 안에서 실행해야 한다. 이
프로젝트의 전이표에는 `waiting_external`에서 곧바로 `failed` 또는 `resolved`로
가는 provider 전용 이벤트가 없다. `escalated` 이후의 고객 응대·보상·재처리는
별도 승인과 도메인 절차로 처리하며, 자동 재실행으로 대체하지 않는다.

### 4.3 provider도 결과를 모른다고 하는 경우

결과를 확인할 수 없으면 성공/실패 어느 쪽으로도 전이하지 않는다. `unknown`
outbox 행, provider의 답변, 조회 시각, 조회자, 사용한 provider 식별자를 사건
기록으로 보존하고 담당자에게 escalation한다. Case가 `waiting_external`인 경우
확인 불가를 외부 callback 대기 만료로 명시적으로 종결해야 할 때만
`WAIT_EXPIRED(wait_reason="external_callback")`를 사람이 호출한다. 그렇지 않으면
Case의 현재 상태와 outbox `unknown`을 유지한다.

## 5. 금지 사항과 주의점

- `customer_cases`를 직접 `UPDATE`하지 않는다. 상태 변경은
  `transition_case()`만 사용한다.
- `case_events`를 직접 INSERT/UPDATE/DELETE하지 않는다. 위 함수가 append-only
  이벤트와 projection 갱신을 함께 처리한다.
- `outbox`의 `unknown`을 `delivered`, `pending`, `failed`로 직접 UPDATE하지
  않는다. 현재 운영자용 outbox 확정 API가 없기 때문이다.
- timeout 뒤 worker를 다시 실행해 재시도하지 않는다. worker의 pending 조회는
  `status='pending'`만 대상으로 하며, `unknown`은 자동 회수되지 않는다.
- `action_requests.status`에도 DB enum 값 `unknown`은 정의되어 있지만, 현재
  `app/` 코드에서 provider timeout 시 그 값을 기록하는 경로는 확인되지 않았다.
  이번 절차의 직접 대상은 worker가 기록하는 `outbox.status='unknown'`이다.

## 6. 근거 파일

- `app/infrastructure/messaging/worker.py` — timeout/연결 오류 시 outbox unknown 기록
- `app/infrastructure/db/migrations/001_schema.sql` — outbox, case, event 스키마
- `app/domain/events.py` — EventType 및 허용 상태 전이
- `app/core/transition.py` — Case 상태 변경 단일 진입점
- `app/presentation/ui/routes.py` — `/ui/cases`, Case trace, `/ui/admin`
- `app/presentation/api/cases.py` — 실제 제공되는 `/v1/cases*` API
- `CLAUDE.md §0.2, §0.3` — timeout 성공 추정 금지 및 transition_case 단일 진입점

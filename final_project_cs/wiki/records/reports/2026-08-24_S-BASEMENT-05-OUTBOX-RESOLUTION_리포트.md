# S-BASEMENT-05-OUTBOX-RESOLUTION 구현 리포트

## 구현 내용

- `005_outbox_resolution.sql`로 `outbox`에 `resolved_at`, `resolved_by`, `resolution_note`, `resolution`을 추가했다.
- `POST /v1/outbox/{message_id}/resolve`를 추가했다. `action:approve` scope가 필요하며, tenant의 미해결 `unknown` 행에 해결 근거만 기록한다.
- 해결 API는 `outbox.status`를 변경하지 않고, Case 전이·provider 재발행도 수행하지 않는다.
- `/ops/outbox` 화면과 POST 폼을 복원하고 기존 `theme.py`의 카드·pill·색상 체계를 사용했다. unknown 메시지는 자동 재실행하지 않는다는 안내와 함께 표시된다.
- worker는 guardrails의 `reliability.outbox_stale_processing_seconds`(300초)를 넘긴 `processing` 행을 `unknown`으로 되돌리고 lock을 해제한다. 자동 재실행은 하지 않는다.
- 운영 절차서의 “전용 화면·API가 없다”는 설명을 실제 `/ops/outbox` 화면/API 기준으로 갱신했다.

## 검증

추가한 전용 검증:

- API 인증 없음 → 401, scope 없음 → 403
- 정상 resolve → `resolved_at`/`resolved_by`/`resolution`/`resolution_note` 기록 확인
- resolve 이후 `outbox.status`가 계속 `unknown`이고 Case를 변경하지 않는지 확인
- 오래된 `processing` lock이 worker cycle 후 `unknown`으로 회수되는지 확인
- `/ops/outbox` HTML 렌더링과 해결 폼 확인

결과: 전용 테스트 `16 passed`.

요청한 전체 명령 `python -m pytest -q -m "not live"` 결과:

```text
370 passed, 3 failed, 3 deselected
```

기준으로 제시된 `359 passed`보다 11개 많은 `passed`가 관측됐다. 실패 3건은 이번 변경과 무관한 기존 RAG 통합 테스트이며, 실행 환경이 `api.openai.com` 네트워크 연결을 차단해 발생했다. `/v1` 표면 테스트는 구현 목록을 갱신한 뒤 통과했다. 이번 작업 관련 표면/API와 전용 테스트는 통과했다.

# S-PAYMENT-TIMEOUT-MOCK 검증 리포트

검증일: 2026-08-20

## 결과

`MockProviderPublisher`는 네트워크 호출 없이 `success`, `timeout`, `connection_error` 모드를 제공한다. 결제 topic outbox 행을 실제 PostgreSQL에 넣고 `OutboxWorker.process_once()`로 전달한 결과는 다음과 같다.

- timeout: `outbox.status='unknown'`, `attempts=1`, `last_error` 기록
- connection error: 동일하게 `unknown` 기록
- 두 transport 오류 모두 두 번째 `process_once()`에서 publisher가 다시 호출되지 않음
- 운영 절차서의 unknown 조회와 Case join으로 해당 message를 확인
- 사람이 `transition_case()`로 `VALID_CALLBACK`을 호출하면 `waiting_external -> resuming`
- 사람이 `transition_case()`로 `WAIT_EXPIRED`를 호출하면 `waiting_external -> escalated`
- 정상 모드 대조군은 `outbox.status='delivered'`가 되고 publisher가 1회 호출됨

신규 통합테스트는 5개이며 모두 통과했다.

## 스키마 확인 사항

절차서 SQL의 `ORDER BY created_at`은 현재 `outbox` 실제 스키마에 `created_at`이 없어 그대로는 실행되지 않는다. 테스트는 조회 조건과 결과 컬럼은 유지하고, 실제 존재하는 `available_at`으로 정렬해 같은 unknown 행을 찾았다. Case join의 `payload_json ->> 'case_id'` 패턴은 그대로 실행되어 해당 Case를 찾았다.

## 전체 검증

실행 명령:

```text
python -m pytest -q -m "not live"
```

실행 전 기준으로 요청에 제시된 수치는 `329 passed, 0 failed`였다. 현재 workspace에서 실행한 실제 결과는 아래와 같다. 신규 테스트 5개를 포함해 `324 passed`였고, 신규 테스트 실패는 없었다.

```text
.E...................................................................... [ 21%]
.........................................................EEEEEE..... [ 42%]
............................. ........................................... [ 63%]
.................FFF.................................................... [ 85%]
..................................................                       [100%]
3 failed, 324 passed, 3 deselected, 2 warnings, 11 errors in 45.06s
```

실패·오류는 기존 환경 문제로 확인됐다.

- 기존 RAG 통합테스트 3건: `api.openai.com` 네트워크 접근 차단으로 embedding 호출 실패
- 기존 e2e 11건: `C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2` 접근 권한 오류
- `3 deselected`: 기존 live 계열 제외

기존 worker timeout 처리(`worker.py`)와 `docs/release_checklist.md`는 수정하지 않았다.

# S-UNKNOWN-OPS-SCREEN 구현 리포트

## 변경 사항

- `003_outbox_resolution.sql`에 nullable resolution 기록 컬럼을 추가했다. 모든 구문은 `IF NOT EXISTS`라 재실행 가능하다.
- `POST /v1/outbox/{message_id}/resolve`를 추가했다. `action:approve` scope를 재사용하고, tenant 밖은 404, unknown이 아닌 같은 tenant 행은 409로 거부한다.
- `/ops/outbox`에 unknown 목록, payload 요약, 오류·시도 횟수·경과 시간과 세 가지 사람 선택지를 추가했다. note는 브라우저와 서버에서 모두 필수다.
- tenant navigation에 Outbox unknown 링크를 추가했다.
- 사람이 하류 시스템에서 직접 전달 여부를 확인한 뒤 처리하는 런북을 추가했다. 자동 재시도는 없다.

## 테스트

추가 테스트: `tests/integration/api/test_outbox_resolution.py` (7개 수집)

재현 명령:

```powershell
python -m compileall -q app tests
python -m pytest --collect-only -q tests/integration/api/test_outbox_resolution.py
python -m pytest -q tests/integration/api/test_outbox_resolution.py
python -m pytest -q
```

실제 출력 요약:

```text
7 tests collected in 1.16s

tests/integration/api/test_outbox_resolution.py: 7 errors
psycopg.OperationalError: connection to server at "127.0.0.1", port 5433 failed:
FATAL: the database system is starting up

full suite: 22% 진행 후 120초 제한으로 종료
........................................................................ [ 22%]
...................................................
```

수집 및 컴파일은 통과했다. 통합 테스트와 전체 스위트의 최종 pass 수는 PostgreSQL이 정상 기동된 환경에서 위 명령을 다시 실행해야 확인할 수 있다.

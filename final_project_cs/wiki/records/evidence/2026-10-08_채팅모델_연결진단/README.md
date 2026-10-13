# 채팅 모델 연결 읽기 전용 진단 증거

기존 실제 채팅 2건 모두 요청 해석 실패 답변으로 저장됐고, cs 프로젝트 서버의 모델 상태 조회는 연결 상대가 끊는 오류로 실패했다.

| 확인 | 상태 | 진행 |
|---|---|---|
| 실행 서비스 | 실행 중 | 5/5 = 100% |
| 최근 채팅 실패 기록 | 확인 | 2/2 = 100% |
| 모델 상태 읽기 | 연결 실패 확인 | 2/2 = 100% |

## 저장 범위

- 관측일: 2026-10-08. 배포 사본 검토 기준은 `bf42b659`이며, 현재 작업 폴더의 미완료 변경을 배포판으로 간주하지 않았다.
- [observations.json](observations.json)은 기존 도구 결과의 비식별 출력과 필요한 메타데이터를 보존한다. 이번 증거 정리 때 재조회하지 않았다.
- 원래 진단 명령은 원격 연결 실행기로 cs 프로젝트 서버의 실행 상태, API/worker 로그, DB SELECT, 모델 상태 GET만 읽었다. 실행기의 실제 연결주소·계정·접속 식별자는 기록하지 않았다.
- 원시 API/worker 로그와 개인 채팅 본문은 저장하지 않았다. 따라서 이 파일은 원본 로그 파일이 아니라, 진단 때 출력한 비식별 결과의 보존본이다.

## 조회한 명령과 조건

cs 프로젝트 서버의 이미 승인된 운영 작업 환경에서 사용한 읽기 명령의 본체는 아래와 같다. 아래 명령은 증거 설명이며 이번 정리 단계에서 실행하지 않았다.

```sh
docker compose ps --format json
docker compose logs --since 30m tripilot-api tripilot-worker
docker compose logs --since 60m tripilot-api tripilot-worker
```

로그 원문을 출력하지 않고, 메모리에서 채팅 경로의 HTTP 상태와 오류 패턴만 집계했다. 최초 대소문자 무시 `ERROR` 검색 32건은 `errored:0`까지 포함해 잘못된 분모였다. 이후 대소문자를 구별한 최근 60분 조회에서는 `ERROR`, `Traceback`, `op_stream`이 확인되지 않았다. 이는 해당 로그 범위의 결과이며, 모델 해석 실패가 없다는 뜻은 아니다.

DB SELECT는 아래와 같다. 개인 식별자나 채팅 본문을 출력하지 않은 운영 집계이며, 애플리케이션 고객 조회 경로로 사용한 쿼리가 아니다.

```sql
SELECT role,count(*) FROM trip_chat_turns
WHERE created_at > now()-interval '2 hours' GROUP BY role;

SELECT status,count(*) FROM customer_cases
WHERE created_at > now()-interval '2 hours'
AND state_json ? 'trip_message' GROUP BY status;

SELECT coalesce(state_json->'decision'->>'failed','none'),count(*)
FROM customer_cases
WHERE created_at > now()-interval '2 hours'
AND state_json ? 'trip_message' GROUP BY 1;

SELECT count(*) FILTER (WHERE text LIKE '%해석 모델 응답 오류%'),
count(*) FILTER (WHERE text LIKE '%해석하지 못했%'),count(*)
FROM trip_chat_turns
WHERE created_at > now()-interval '2 hours' AND role='assistant';

SELECT coalesce(state_json->'decision'->>'action','none'),count(*)
FROM customer_cases
WHERE created_at > now()-interval '2 hours'
AND state_json ? 'trip_message' GROUP BY 1;
```

`decision.failed` 값은 원문을 출력하지 않고 오류 클래스·HTTP 상태·이미 알려진 연결 오류 문구의 존재 여부로만 분류했다. 초기 `state_json ? 'request_id'` 조회는 빈 결과였으나 실제 표시는 `trip_message` 아래에 있으므로 이를 진단 근거로 쓰지 않고 위 쿼리로 다시 확인했다.

cs 프로젝트 서버 API 실행 환경에서 `get_settings()`로 값을 읽고, 주소·키 값은 출력하지 않았다. 첫 키 검사에서 개인용 `openai_api_key`를 배포용으로 잘못 이름 붙였으므로 `openai_api_key_server`로 재확인했다. 두 필드 모두 미설정이었다. 최종 출력은 `settings_followup_correct_fields`에 보존했다.

모델 조회 본체:

```python
import httpx
from app.core.settings import get_settings

settings = get_settings()
for endpoint in ("/api/ps", "/api/tags"):
    # 주소는 운영 설정에서 읽었으며 출력하지 않았다.
    response = httpx.get(settings.ollama_base_url.rstrip("/") + endpoint, timeout=5)
```

각 요청의 예외 클래스는 `ReadError`였다. 후속 `/api/ps` 읽기에서는 예외와 원인 예외의 클래스 및 `reset by peer` 존재 여부만 출력해 연결 상대가 끊었음을 확인했다. 생성·예열 경로는 호출하지 않았다.

## 검토한 코드 경로

아래는 배포 사본 `.tmp/full-release-20261008/release/final_project_cs/` 아래에서 읽은 경로다. 운영 접속 정보는 포함하지 않았다.

- `app/domains/travel_ops/entry/trip_api.py:1843` — 채팅 메시지 POST와 SSE 선택.
- `app/domains/travel_ops/entry/trip_api.py:1862` — 해석 결과 처리, 대화 저장, 웹 응답.
- `app/domains/travel_ops/entry/trip_api.py:1894` — SSE HTTP 응답과 작업 흐름.
- `app/domains/travel_ops/components/conversation/trip_messages.py:636` — 해석 모델 실패를 상담 실패 안내로 반환하는 분기.
- `app/infrastructure/ollama_chat.py:81` — 구조화 모델 호출과 연결 예외 처리.
- `app/infrastructure/ollama_chat.py:161` — 자동 전환이 꺼져 있을 때 `OllamaChat` 사용.
- `app/infrastructure/llm_failover.py:439` — 배포용 키만 사용하는 자동 전환 구성.
- `frontend/apps/web/src/lib/live/gateway.ts:332` — 채팅 SSE 요청과 받은 답변 저장.
- `frontend/apps/web/src/features/trip/trip-chat.tsx:41` — 요청 실행 및 최종 답변을 화면 데이터에 반영.

## 결론의 한계

기존 채팅 요청 도착과 실패 답변 저장은 확인했다. 어느 중간 연결이나 GPU 모델 프로세스가 연결을 끊는지는 확인하지 않았다. 새 고객 메시지 전송·유료 모델 호출·사용자 브라우저 조작·재시작·설정 변경·푸시·복구를 하지 않았으므로, 새로운 요청의 SSE 수신부터 최종 화면 표시까지는 재현하지 않았다.

mock 서버 시험: 안 했음.

실서버 확인 (서버 응답): 했음 — 기존 채팅 기록, 실행 상태, 모델 상태 읽기만 확인. 상담 복구 성공은 확인하지 않았다.

---
type: report
title: 계획 읽기 정상 API 연결 — process·설정·공급자 스트림
status: draft
domain: travel
---

# 계획 읽기 정상 API 연결 절

2026-10-24 23:14 KST 검증. **정상 고객 입구의 로컬 연결을 구현·검증했습니다. 운영 활성화·실모델·실제 DB 저장 완료는 아닙니다.** 이전 [순수 경계 체크포인트](2026-10-24_plan-reading-restoration.md)의 API 미연결 부분을 잇는 절입니다.

## 결과

- 등록된 `POST /v1/web/trip-intakes` handler → background의 실제 `process` → 실제 `read_source` → 실제 `OllamaChat.structured_stream`까지 실행했습니다. DB와 HTTP 스트림만 대역으로 바꿨으며 앱/서비스를 기동하지 않았습니다. 미사용 helper를 추가한 것이 아닙니다.
- 접수 구간은 기존 `chat_factory` 결과를 `agent`로 함께 전달하는 한 줄만 부분 패치했습니다. `_web_view`/메시지 consumer/`response/writing.py`/conversation은 이 절에서 수정하지 않았습니다.
- `process`가 관리 설정을 읽어 agent 모드·출력 토큰 예산·첫 응답/멈춤/전체/진행 정책을 `read_source`에 전달합니다. 정상 mode는 `on`. 미설정/미조립 스트림 공급자는 `reading_not_configured`, 모델 연결/시간 초과는 `reading_model_failed` fatal입니다. 실패를 규칙 preview 성공으로 바꾸지 않습니다.
- 최종 정정(남산타워 → 롯데타워)이 실제 API 경로에서 반영됩니다. 모델 실패는 줄 읽기로 같은 호출을 다시 보내지 않습니다. 읽기 성공 뒤 장소 조회 실패는 기존 `blocked` 근거에 남고 검사 장애는 별도 `review_error` 경계입니다. review는 등록 성공이 아니며 일정 등록은 기존 confirm/plan 요청에 남습니다.
- `sources[].reading`의 기존 줄 읽기 키를 보존하고 `agent` 결과를 추가했습니다.
- Ollama NDJSON / OpenAI SDK 실제 스트림 어댑터와 FailoverChat의 스트림 입구를 최소 추가했습니다. 첫 응답/멈춤/전체 한도, 불완전 종료/출력 잘림/거절의 명시 실패를 시험했습니다. 유료 넘김은 기존 breaker·예산·PII 가림을 재사용하고, 유료 예산 gate 부재는 실패합니다. 로컬의 받다 만 답을 API 답과 합치지 않습니다.

## Git·계약·기존 변경 보존

[공유 계약](../../external/plan-reading-restoration.md)에 실제 연결/실패/운영 경계를 **config·공급자 코드보다 먼저** 추가했습니다. 참고 저장소 `D:/Documents/파이널스페이스`의 Git `7d503bfb6` / `502da503c` 원문을 확인했습니다. C 작업트리 Git에는 두 revision이 없어 D의 이력을 읽기 전용으로 조회했습니다. 전체 파일/commit을 통복사하지 않았습니다.

- 정책: 참고판의 `mode="on"`, `num_predict=3072`, stream `15/5/120/5`초를 관리 YAML로 선별 복원했습니다. 과거 chunk 길이·prefill 자동 적용은 가져오지 않았습니다. 새 모델명·주소·운영 임계값을 Python 기본값으로 만들지 않았습니다.
- 수정 전 원본 6개와 SHA-256 manifest는 현재 프로필 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-reading-api/before/`에 보존했습니다.
- AST 비교: pipeline의 기존 정의 중 변경은 `process`, `view`뿐입니다. `read_source`, edit/restore/등록/고객 운영시간 함수는 이번 절 전 상태와 동일합니다. 두 공급자의 기존 nonstream 메서드도 AST가 동일하며 stream 메서드만 추가했습니다.
- `assemble.py`, `hours.py`, `direct_schedule.py`는 이전 dirty 백업과 바이트 동일입니다. 기존 고객 운영시간 검증 19/19 = 100%입니다.
- SQL 전체 migrations 하위에서 `905*`와 `llm_agent` 중복을 확인한 뒤 `pending/905_intake_claims_llm_agent.sql` 파일만 만들었습니다. 현 028의 네 method에 `llm_agent`만 추가하며, 이력판의 별도 `trip` method는 범위 밖이라 넣지 않았습니다. **DB 적용은 하지 않았습니다.**

## 실행 결과

| 범위 | 결과 | 로그 |
|---|---:|---|
| 최종 intake/읽기/응답 관련 지정 unit | **303/303 = 100%, exit 0** | `final-core-green-v2.log` |
| 그중 신규 API 경로·실패·조회/등록 분리 | 9/9 = 100% | 동일 |
| 그중 신규 공급자 스트림/불완전 종료/시계 | 9/9 = 100% | 동일 |
| 그중 기존 고객 운영시간 | 19/19 = 100% | 동일 |
| 확장 실행(기존 공급자 시험도 포함) | **358/362 = 98.90%, exit 1** | `final-green-v2.log` |

확장 실행의 나머지 4개는 기존 `test_http_*`가 loopback HTTP 서버에 연결하려다 격리 runner의 socket 차단에 걸렸습니다. 제품 assertion 실패가 아니라 이번 검증의 금지 경계이며, 통과/skip으로 바꾸거나 전체 분모에서 없애지 않았습니다. 서버/loopback 허용을 추가해 재실행하지 않았습니다. 해당 공급자 기존 지정 시험만 보면 55/59 = 93.22% 통과·4건 차단입니다. 따라서 **확장 suite 전체 GREEN이라고 보고하지 않습니다.**

최종 303개는 이전 부모의 285개와 신규 18개입니다. 전체 프로젝트·DB·실모델·운영 완료율이 아닙니다. 결과와 파일별 집계는 [verification.json](../evidence/2026-10-24_plan-reading-api-activation/verification.json), 실패/성공 원본 로그는 [증거 폴더](../evidence/2026-10-24_plan-reading-api-activation/)에 보존했습니다.

### TDD·오류 기록

- `red1.log`: 정상 등록 API가 agent를 호출하지 않아 `calls == 0` 실패 → `green1.log` 1 pass.
- `red2.log`: 실제 Ollama 공급자에 structured_stream 없음 → `green2.log` 2 pass.
- `red3c.log`: FailoverChat이 primary의 stream으로 새어 경로 relay/넘김 누락, OpenAI stream 없음 → `green3.log` 4 pass. 앞 `red3/red3b`의 잘못된 시험 import/생성자 인자도 원본 보존했고 기능 RED로 세지 않았습니다.
- `red4.log`: view에서 agent 보고 누락 → `green4.log` 10 pass.
- `red5.log`: Ollama의 완료 전 EOF/토큰 잘림을 JSON 성공으로 받음 → 최종 GREEN.
- `red6.log`: OpenAI의 완료 전 EOF를 성공으로 받음 → 최종 GREEN.
- 초기 확장 명령 `final-green.log`는 잘못된 기존 시험 파일 경로로 collection exit 4입니다. 수정한 명령과 결과를 별도 로그로 보존했습니다.
- 기본 Python 3.14에 tzdata가 없어 AST 집계의 시각 생성이 실패했고, 기존 scratch venv Python 3.12로 재실행했습니다. 기능 RED/시험 통과로 계산하지 않았습니다.

### 실제 최종 명령

cwd `C:/_proj/final_workspace/final_project_cs`:

```text
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-reading/run.py C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-reading-api/final-core-green-v2.log tests/unit/travel/test_plan_reading_api_activation.py tests/unit/travel/test_plan_reading_provider_stream.py tests/unit/travel/test_plan_reading_reference.py tests/unit/travel/test_plan_reading_restoration.py tests/unit/travel/test_intake*.py tests/unit/travel/test_travel_response_slice1.py
```

runner는 socket connect/connect_ex/create_connection·psycopg.connect를 차단하고 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider` 및 명시적 standalone_services만 사용합니다. glob이 펼쳐진 인자는 각 로그 첫 줄에 있습니다. `git diff --check` exit 0(기존 줄바꿈 경고만)도 확인했습니다.

## 수정 목록 (cs 기준)

- `app/domains/travel_ops/entry/trip_api.py`: 접수 task agent 주입 한 줄.
- `app/domains/travel_ops/components/intake/pipeline.py`: process 인자/정책/전달, view reading.agent 공개.
- `app/infrastructure/ollama_chat.py`, `llm_failover.py`: 기존 메서드 보존, structured_stream 추가.
- 신규 `app/infrastructure/model_stream.py`.
- `config/guardrails.yaml`: 위 reader/stream 관리 정책만 추가.
- 신규 `app/infrastructure/db/migrations/pending/905_intake_claims_llm_agent.sql`.
- 신규 `tests/unit/travel/test_plan_reading_api_activation.py`, `test_plan_reading_provider_stream.py`.
- 복원 계약 보완, 본 고유 보고서, 증거 폴더. 이전 dated 보고서는 덮어쓰지 않았습니다.

## 운영에 필요한 값·정확한 미완료

1. 기존 조립 경로의 `ollama_base_url`, `ollama_model`, timeout/keep_alive를 대상 환경에서 확인해야 합니다. 여기서는 운영 환경값/비밀값을 읽거나 바꾸지 않았습니다. 새 모델 기본값은 추가하지 않았습니다.
2. 유료 경로를 쓰려면 기존 `llm_failover_enabled`, 서버 전용 `openai_api_key_server`, `llm_failover_model`(또는 기존 `llm_model`), timeout/breaker 값과 등록된 예산 gate가 필요합니다. 외부 공급자의 실제 해당 모델/스키마 수용 여부·유료 전환 실호출은 미검증입니다.
3. 실제 DB method 제약과 pending 905 번호/내용을 검토·승인 후 별도 적용해야 합니다. 적용 전 DB에서는 `llm_agent` 저장이 제약 위반할 수 있으며 unit으로 DB 저장 가능을 주장하지 않습니다.
4. 남은 줄 대체 읽기는 기존 `chat.json` 경로를 유지했습니다. 정상 D-025 structured stream 연결을 구현한 것이며 이력판의 모든 json_stream/전체 모델 운용 정책을 통복원한 것은 아닙니다.
5. 외부 모델/DB·서비스 기동/재시작/배포·UI/e2e·전체 프로젝트 관문·커밋·푸시는 수행하지 않았습니다. root wiki/index/handoff 갱신은 부모 담당입니다.
6. prefill 자동 적용·숙소 추천·성향 설문 배선·계획 재등록 기능은 범위 밖이며 추가하지 않았습니다.

로컬 연결 절의 추가 사용자 결정은 필요하지 않습니다. DB 적용/실모델/운영 반영은 기존 금지 범위를 유지하며 별도 승인·검증이 필요합니다.

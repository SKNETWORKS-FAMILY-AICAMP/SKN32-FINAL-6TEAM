---
type: report
title: 날씨 후속 실제 공급자 읽기 포트 배선
status: draft
domain: travel
---

# 날씨 읽기 공급자 배선 — 로컬 격리 검증

2026-10-24 23:24 KST. 대상 `C:/_proj/final_workspace/final_project_cs`. 부모의 로컬 적용 재승인 범위에서 구현했으며 외부 예보·실모델·DB·서비스·배포 완료를 뜻하지 않습니다.

## 결과

- 기존 지정 목록 **188/188 = 100%** 재실행, exit 0.
- 배선·소비자·예산/캐시·기상 소스 관련 격리 unit **114/114 = 100%**, exit 0.
- 두 목록을 중복 없이 합친 21개 파일 **302/302 = 100%**, exit 0, skip·pytest warning 없음. 고유 node id 302개를 프로그램으로 검산했습니다.
- 새 배선 시험 10개는 실제 `handle_trip_message`→`_run_decision`→기존 `read_requests.reply`를 통과하며 저장소·모델·전이는 합성 in-memory 경계로 대체했습니다. 웹·agent 라우터 함수도 실제 호출했습니다. ASGI 서비스/앱은 시작하지 않았습니다.

## 계약·실제 연결

구현보다 먼저 [weather-wiring.md](../../external/weather-wiring.md)를 작성했습니다.

`composition.build_domain_routers`의 기존 정상 소스 조립을 공유하는 lazy `sources()`를 두고 `weather.forecast`를 `weather_lookup_factory`로 전달했습니다. `check_factory`와 문의는 같은 소스 객체를 재사용합니다. 기존 cache-only·low-priority 점검 factory는 그대로 별도입니다.

`build_travel_sources(get_settings())`의 기존 공급자 순서/WeatherChain·rate limiter·DB 예산·응답 캐시/TTL·proxy 조립을 재사용합니다. 새 URL·모델·임계값·무음 fallback·직접 HTTP는 추가하지 않았습니다. 소스 생성은 조회가 아니며 forecast는 검증된 읽기 항목의 좌표·시각으로만 호출됩니다. 설정이 공급자를 만들지 못하면 None을 그대로 전달합니다.

## 수정 목록

기존 파일 4개:

1. `app/composition.py`: 기존 정상 소스 공유 및 forecast 읽기 포트 factory.
2. `app/domains/travel_ops/entry/trip_api.py`: factory 인자 1줄, agent/web 메시지 호출의 weather 인자 각 1줄만 추가.
3. `app/domains/travel_ops/components/conversation/trip_messages.py`: 정상 결정 및 기존 읽기 복구에 weather 포트 인자만 전달. duplicate 응답/response 소비자 변경을 보존했습니다.
4. `.../conversation/fact_read_retry.py`: 선택 인자와 `_run_decision` 전달만 추가. snapshot 검증·완료 중복 정책은 그대로입니다.

신규 파일: `tests/unit/travel/test_weather_wiring.py`, `test_weather_wiring_router.py`, 계약 위 문서, 이 보고서 및 아래 증거 폴더.

`trip_api`의 시작 백업/현재 AST 비교에서 변경 함수는 `build_trip_router`, `message`, `_web_message_result`뿐이었습니다. `_web_view`·접수 관련 함수는 동일합니다. core Controller·action·DB·설정·기상 adapter·writer에는 수정하지 않았습니다. 기존 dirty/다른 child 변경을 통째로 덮지 않았습니다.

## 확인한 보호

- 정상 메시지가 가짜 forecast에 정확한 위도·경도·항목 시작시각을 전달하고 공통 writer complete/answered로 종료합니다.
- 웹의 다른 고객 소유 여행은 404로 거절되며 provider factory/forecast 모두 호출되지 않습니다. 기존 agent `trip:write` dependency는 유지했습니다. endpoint 직접 호출 unit은 FastAPI 인증 전체 검증과 구분합니다.
- 공급자 미연결/조회 실패는 `weather_source_unavailable`/`weather_sources_failed`, writer partial/failed로 남습니다.
- 동일 완료 요청은 저장 답을 재생하며 forecast 1회만 유지합니다. 업무 controller 실행은 시험에서 금지했습니다.
- TTL 만료/이전 판 focus는 모델 추측 대상이 있어도 조회하지 않습니다. 기존 188개의 snapshot·판·업무 격리 보호도 통과했습니다.
- 미완료 순수 읽기만 기존 snapshot 검사를 거쳐 동일 포트를 복구합니다.
- 실제 기존 OpenMeteo adapter + BudgetedLimiter + ResponseCache + 가짜 transport를 정상 메시지에 꽂아 첫 호출 예산 차감, cache hit의 무조회·무차감, TTL 만료 뒤 소진 예산의 transport 차단을 확인했습니다. 기존 단위 시험은 Chain 전환·전체 실패·timeout 무재시도·확인시각·캐시 TTL도 확인합니다.

## RED → GREEN·실패 시도

[실행 증거 폴더](../evidence/2026-10-24_weather-wiring/):

- `red-message.log`: weather_lookup 미지원 TypeError로 1건 RED, exit 1.
- `green-message.log`, `green-message-v2.log`: 합성 Conn.fetchall 부재 및 fixture의 잘못된 completed 상태로 실패한 중간 시도. 실제 정본 종료 상태 resolved로 fixture를 고쳤으며 제품 로직을 우회하지 않았습니다.
- `green-message-v3.log`: 최초 메시지 보호 5/5 GREEN.
- `red-router.log`, `red-router-v2.log`: 좁은 guardrail patch 이전 import 순서/closure `_log_turn` 오인으로 인한 시험 설정 오류를 포함합니다. 기능 RED 근거로 세지 않습니다.
- `red-router-v3.log`: factory 인자 부재 2건·composition 포트 부재 1건의 실제 RED, exit 1.
- `green-router.log`: router/composition 3/3 GREEN.
- `regression-188.log`, `regression-unit-only.log`, `regression-combined-302.log`: 위 최종 회귀.
- `regression-wiring-sources.log`: 확대 목록에서 **115 통과·DB 의존 fixture 5건 오류**, exit 1. `test_shared_source_cache.py`의 DB 정리 fixture가 차단기에 걸렸습니다. 실제 DB 연결은 실행되지 않았고 허용하지 않았습니다. 이 5건을 최종 unit 분모에 숨겨 넣거나 통과로 세지 않았습니다. 최종 302는 해당 DB 의존 파일을 제외한 명시 목록입니다.
- `results.json`, `manifest.json`, `backup-manifest.json`, `wiring-only.diff`, `isolated-runner.py`: 집계·백업 해시·이번 child의 시작 상태 대비 diff·실제 runner.

각 로그 첫 줄에는 정확한 pytest 파일/옵션, 끝에는 EXIT_CODE가 있습니다. 실제 공통 명령(cwd는 cs):

```text
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s2-run.py <증거폴더/고유로그.log> <로그 첫 줄의 tests/ 목록>
```

Python 3.12.15·pytest 8.4.2 기존 격리 venv를 재사용했습니다. `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`; socket connect/connect_ex/create_connection와 psycopg.connect를 차단하고 정확한 stdlib Windows socketpair 호출만 허용했습니다. 지정 tracked 파일 `git diff --check` exit 0(저장소 LF/CRLF 안내만 있음).

기존 파일 백업: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/weather-wiring/backup/`.

## 남은 검증·부모 인계

실제 공급자 네트워크·API 키·실제 DB 예산/공유 캐시·실모델 질문 추출·실제 HTTP 인증·웹 UI·전체 contract/security·운영 배포는 미검증입니다. 외부 HTTP/LLM/DB, 앱/서비스 기동, 배포·커밋·푸시를 하지 않았습니다. DB 의존 확대 5건은 별도 승인 환경에서 확인해야 합니다.

root/cs index·log·handoff 통합 갱신은 부모에게 인계합니다. 이 보고서와 `weather-wiring.md` 및 고유 evidence 경로를 연결하고 부모 최신 병렬 변경 포함 독립 재실행을 진행해 주십시오. 단위 시험 결과를 실서비스 예보 확인 완료로 승격하면 안 됩니다.

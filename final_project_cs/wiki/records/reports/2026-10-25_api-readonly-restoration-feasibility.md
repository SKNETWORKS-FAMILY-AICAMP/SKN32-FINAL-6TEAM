---
type: report
title: API 기동 차단점 읽기전용 복원 가능성 재조사
status: draft
domain: travel
---

# API 기동 차단점 — 읽기전용 재조사 (2026-10-25 01:06 KST)

## 결론

**이동 자료 부재는 이번 확인으로 정정해야 합니다.** 현재 루트의 `datasets/mobility/processed/mobility/`가 실제 존재하며 `MANIFEST_git_v1.json` 등록 **25/25 = 100%** 파일의 존재·SHA-256이 일치합니다. `engine/paths.py`는 서버 상대 경로를 CS cwd가 아니라 **실제 Git 루트**에 붙입니다. 따라서 기존 `2026-10-25_customer-web-approved-launch.md:40`의 “CS cwd에서 경로 없음 → 자료 차단”은 제품 경로 해석과 맞지 않습니다. 원래 기록은 동결하고 이 보고서로 보완합니다.

**지금 즉시 읽기만으로 재사용 가능한 완성 API 실행환경은 이번 제한 범위에서 확인하지 못했습니다.** 기존 승인 시험 venv는 선행 보고서에서 uvicorn·mcp 누락을 실제 확인했지만, 그 정확한 위치는 개인 프로필 scratch입니다. 이번에는 개인폴더 금지 범위를 지켜 그곳의 파일·패키지 메타데이터를 열거나 실행하지 않았습니다. `C:/_proj` 안의 지정 후보 runtime 경로는 존재하지 않습니다. API 기동·DB 연결·실모델 호출 완료를 선언하지 않습니다. 8042 연결 거부는 선행 보고서 관측이며 이번에 HTTP를 재실행하지 않았습니다.

## 범위와 보존

루트·CS AGENTS/CLAUDE/RULE, 두 wiki index, 지정 승인 기동 보고서, requirements, datasets 안내·mobility REPORT·manifest, 현재 조립·기동 경로와 실행 정의만 제한 추적했습니다. 전체 저장소 RE·개인폴더/모델/키 파일 읽기는 하지 않았습니다. 코드·설정 편집, 패키지 설치, 자료 생성·다운로드, DB/TCP probe·로그인·SQL, 모델/외부 HTTP, 앱 실행은 **0회**입니다. 신규 보고서만 작성했습니다. root wiki·인계 정리는 부모 담당입니다.

## 실제 자료 위치와 복원 필요 여부

- 제품 루트: `C:/_proj/final_workspace`.
- 서버가 받는 기존 설정 문자열(선행 실측): `datasets/mobility/processed`.
- `app/domains/travel_ops/instances/mobility/engine/paths.py:33-42,74-81`: `.git/HEAD`가 있는 조상만 루트로 선택하고 상대 입력은 그 루트 기준입니다.
- 현재 `C:/_proj/final_workspace/.git/HEAD` **있음**, `final_project_cs/.git/HEAD` **없음**. 따라서 서버의 실제 PROCESSED는 `C:/_proj/final_workspace/datasets/mobility/processed`이고 입력은 그 아래 `mobility/`입니다. cwd를 달리 보아 부재로 판정하면 안 됩니다.
- `MANIFEST_git_v1.json`: 현재 실제 파일 25개 모두 존재·SHA-256 일치. `manifest_v1.json`은 없으나 `engine/datacheck.py:95-104`가 기존 Git manifest를 읽으므로 새 manifest 생성은 필요하지 않습니다. manifest의 `src_dir=C:\final_project\data\travel\processed\mobility`는 과거 PC 값이며 현재 그 위치는 **없음**을 확인했습니다. 이를 복원 원본으로 사용하면 안 됩니다.
- 등록 25개 밖의 `subway_realtime_stations_20260902_v1.json`, `road_graph_v2/nodes.jsonl.gz`, `road_graph_v2/edges.jsonl.gz`, `road_graph_v2/turn_restrictions_v1.json`은 정확 경로의 **존재만** 확인했습니다. 이 네 파일의 내부 내용·sidecar 결합 해시까지 통과했다고 주장하지 않습니다.
- 실제 원문 출처 문서 `datasets/mobility/raw/osm_20261012_v1/REPORT.md`, `raw/subway_train_precision_20261012_v1/REPORT.md`, `raw/official_distance_20261008/manifest-v2.json`도 존재합니다. 이번 범위에서는 큰 PBF/원문 전량을 검사하지 않았습니다.
- `datasets/mobility/REPORT.md:56-59`의 재생성 명령은 `python datasets/mobility/scripts/reduce_75.py --src <DATA_DIR>\travel\processed\mobility --clean`이나, **실제 현재 원본 DATA_DIR가 확정되지 않았고 --clean은 재작성/삭제 동작**입니다. 현재 완전한 가공 묶음이 있어 실행할 이유가 없습니다. `--write`, 재다운로드, fake/empty 데이터 생성도 필요하지 않습니다.

읽기전용 확인에 따른 자료 복원 명령: **없음 — 현 위치 자료를 그대로 사용**. 임의 환경변수 override·설정 변경도 하지 않았습니다. 향후 별도 승인 후 현재 runtime으로 정본 `python -m app.domains.travel_ops.instances.mobility.engine.datacheck`를 실행할 수 있으나, CLI는 `.env`/DATA_DIR를 따로 읽는 경로(`paths.py:89-98`)이므로 서버 설정과 같은 자료를 가리키는지 먼저 확인해야 합니다. 이번에는 제품 모듈 실행 없이 표준 라이브러리로 manifest 파일들을 직접 해시했습니다.

## 의존성과 격리 설치 경계

- 정본 `final_project_cs/requirements.txt`: 직접 고정 항목 **35개**. SHA-256 `23e7b5f370b2d4b4d4aa758f040cb7e69ebeb9e073df7ee7f25bd6c181d86a6a`.
- API 필수 누락으로 선행 실측된 두 항목의 정확 선언: `uvicorn[standard]==0.35.0`(10행), `mcp[cli]==1.28.1`(31행). `app.py:95-97`, `composition.py:594-601`, `mcp_server.py:41-44`에 따라 MCP feature flag를 꺼도 라이브러리 import/표면 조립을 건너뛰는 설치 우회가 되지 않습니다.
- requirements는 직접 버전 pin 목록이지 전이 의존성·wheel·Python/플랫폼을 완전 고정한 hash lock이 아닙니다. CS/루트 top-level 및 deploy/docker/scripts의 targeted filename 검사에서 추가 Python lock을 찾지 못했습니다. 저장소 전역에 없다고 일반화하지 않습니다.
- 선행 승인 환경은 Python **3.12.15 AMD64**, 기본 실행기는 선행 실측 **3.14.7 ARM64**입니다. 원래 3.12/x64 검증 환경을 새 격리 venv로 유지하는 것이 보수적이며 기본 3.14/ARM64에 전체 requirements를 무작정 설치하는 것은 권고하지 않습니다.
- 이번에 존재가 없었던 정확 후보: `final_workspace`, `파이널스페이스`, `guguroute` 각각의 `.venv/Scripts/python.exe`, `final_project_cs/.venv/Scripts/python.exe`, `scratch/travel-writing-s1-venv/Scripts/python.exe`; 추가 `test_workspace/.venv/Scripts/python.exe`, `test_workspace/scratch/travel-writing-s1-venv/Scripts/python.exe`. 이 bounded 후보 검사만으로 모든 C:/_proj runtime 부재를 주장하지 않습니다.
- 기존 보고서의 실제 승인 venv는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe`로 식별됩니다(`2026-10-24_travel-writing-slice1.md:60-65`). 이번 개인폴더 금지 때문에 새 readback하지 않았습니다. 기존 시험 venv를 덮어 설치하지 않아야 합니다.

추가 승인 시 최소 설치 제안은 **새 격리 환경에 두 누락 직접 pin과 resolver가 요구하는 전이 의존성만 추가**하고 기존 승인 환경의 설치 목록과 현재 requirements를 대조하는 것입니다. 정확한 전이 추가/변경량은 metadata·resolver를 이번에 실행하지 않아 미확정입니다. 전체 requirements의 평가/자료가공 전용 numpy/scipy/sklearn/pandas/osmium/pyproj 등을 API 복구만을 위해 새로 전부 설치해야 한다는 근거는 없습니다. 반대로 두 패키지만 설치하면 완전 앱 기동을 보증한다는 뜻도 아닙니다.

승인 후 사용할 명령 형태(지금 실행하지 않음):

```text
<실존 재확인한 Python 3.12 AMD64> -m venv <새 API 전용 격리환경>
<새 격리환경>/Scripts/python.exe -m pip install "uvicorn[standard]==0.35.0" "mcp[cli]==1.28.1"
```

위 두 줄은 기존 설치 subset을 새 환경에 보존/재현한 뒤의 추가 단계이며, 빈 venv에 두 패키지만 넣는 것으로 모든 의존성이 채워진다는 복원 레시피가 아닙니다. 새 환경 재현에는 기존 metadata 읽기 범위 승인과 설치계획 확정이 먼저 필요합니다. 현 시점에는 실행 가능한 완전 offline wheelhouse·transitive lock이 확인되지 않았습니다.

## 정본 실행 정의와 startup 부수효과

정본 `scripts/ops/jobs.py:116-128`과 CS `.claude/launch.json`의 stable 항목은 고객 API `python -m uvicorn app.presentation.api.app:app --port 8042`입니다. 향후 승인 환경·CS cwd에서 이 정의를 사용하고 loopback을 명시할 수 있습니다. `acop-all`/전체 ops DEFAULT_JOBS는 sweepers·outbox·daily_feedback까지 포함하므로 **사용 금지**입니다. UI launch의 postgres 절대 경로는 과거 `playdata2` PC 값이므로 현재 DB 실행 위치로 채택하지 않았고 개인폴더도 확인하지 않았습니다.

| 경로 | 정적으로 확인한 효과/경계 |
|---|---|
| `app/presentation/api/app.py:44-96,146` | import 즉시 create_app → classifier/controller/domain routers/MCP 조립. 단순 함수 정의만 읽는 파일이 아님. 이번 import 실행 안 함 |
| `composition.py:523-563,371-397` | OpenAITeamLLM·ReadToolbox·외부 자료 어댑터 생성·도메인 hooks·mobility preload. controller에 DB 연결 factory를 전달. API 기동만으로 sweepers/outbox worker를 시작하는 호출은 확인 경로에 없음 |
| `OpenAITeamLLM.__init__` 19-29행 | guardrails 읽기. DB·모델 호출은 complete(31-86행) 안: active prompt DB 읽기 → OpenAI chat HTTP → audit DB 쓰기. 따라서 사용자 문의 실행은 별도 DB·실모델 승인 경계 |
| `db/session.py:18-22` | psycopg.connect는 get_connection context 진입 시점. factory 전달 자체와 실제 DB 접속을 구분 |
| `base.py:440-467`, `source_budget.py:151-166` | limiter·cache·CallBudget 인스턴스 조립. 예산 reservation은 acquire→try_reserve에서 DB 사용. constructor 조립을 실제 외부 조회 성공으로 해석하지 않음 |
| `mobility/wiring.py:59-80,105-121` | manifest 검사·자료 메모리 적재. local router 설정이면 daemon warm thread가 생길 수 있음(84-102행). 서버 시작이 완전히 무부수효과인 것은 아님 |
| **`engine/runtime.py:277-284` → `engine/car.py:251-254`** | **유효 GraphHopper URL이 http로 시작하면 startup 중 `/info`에 urllib HTTP(5초 timeout)를 실제 호출할 수 있음.** “모든 HTTP는 첫 고객 요청 이후”라는 보증은 잘못임. 현재 유효 mobility_gh_url은 이번에 private env를 읽지 않아 미확정. 빈 기본값만으로 실제 빈 값이라 추정하지 않음 |
| `app.py:19-27` → `mcp_server.py:546-549` | lifespan은 MCP session_manager.run. build_surface의 DB authentication closure는 요청 시 `get_connection()` 사용(533-544행). MCP SDK가 이번 환경에 없어 그 내부 lifespan까지 무부수효과 인증하지 않음 |
| `/health` (`app.py:112-113`) | 함수 본문은 단순 status 반환. 실제 생성이 선행 차단을 넘었다는 것과 DB/모델 준비 완료를 구분해야 함 |

확인한 고객 진입점·조립 경로에서 자동 migration/DB 초기화 SQL 호출은 발견하지 못했습니다. **전체 transitive import의 DB/HTTP/파일 부수효과 없음 인증은 아닙니다.** 이번 10분 이하 bounded 정적 검토로 실서비스 전체를 안전 인증하지 않습니다. 특히 GraphHopper startup HTTP 조건을 먼저 해결하지 않고 앱을 실행하면 안 됩니다. 외부 모델 연결도 임의 fallback·기능 끄기로 회피하지 않습니다.

## 다음 추가 승인 요청 — 최대 3개

1. **API 전용 새 격리 runtime 준비**: 기존 승인 Python/venv의 정확 metadata만 읽는 예외 범위와 새 venv 경로를 지정하고, 현 pin 기준 누락 uvicorn/mcp 및 실제 필요한 전이 패키지 설치·lock 기록을 승인해 주셔야 합니다. 기존 시험 venv·제품 requirements는 변경하지 않습니다. 이동 자료 생성/복원 승인은 필요하지 않습니다.
2. **실 DB 경계**: DB를 사용하는 고객 기능 수락 전 `127.0.0.1:5433/acop_cs`의 정확 서버/클러스터 위치를 별도 확인하고, 최소 읽기 접속·필수 schema 존재 확인 범위를 승인해야 합니다. 과거 launch의 postgres.exe/pgdata를 실행하거나 905 migration·DB 쓰기/재기동까지 포함시키지 않습니다. 앱 HTTP 서빙 승인은 이 DB 승인과 다릅니다.
3. **실 네트워크/모델 경계**: 먼저 비밀값을 노출하지 않는 유효 `mobility_gh_url` allowlist readback이 필요합니다. 값이 있다면 그 정확 endpoint의 startup `/info` 1회 접근, 이후 고객 수락에 사용할 실모델/외부 원문 전송·비용 범위를 별도 승인해야 합니다. 미승인 동안 그 경로를 호출하지 않고 fallback/기능 OFF로 우회하지 않습니다.

API 앱 기동 자체는 기존 승인 사실을 유지하되, runtime 준비와 유효 startup 외부 연결 범위를 확인하기 전에는 실행하지 않습니다. 읽기 조사로 **자료 오판 1건을 정정**했으며, 의존성·DB·실모델/HTTP 수락과 전체 제품 완료는 계속 열려 있습니다.

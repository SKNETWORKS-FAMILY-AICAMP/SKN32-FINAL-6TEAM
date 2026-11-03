---
type: report
title: API 전용 격리 runtime 실제 설치와 안전 기동전 확인
status: draft
domain: travel
---

# API 전용 격리 runtime 설치 — 2026-10-25

## 결론

**승인된 새 환경 의존 설치는 실제 완료했습니다.** Python 3.12.15 AMD64 새 venv에 기존 시험 환경의 runtime subset과 `uvicorn[standard]==0.35.0`, `mcp[cli]==1.28.1` 및 필요한 전이 의존성을 설치했습니다. pip install exit 0, pip check exit 0(`No broken requirements found.`), 순수 의존성 import **12/12 = 100%**입니다. 단, **전체 앱 import/실제 API 기동 완료는 아닙니다.**

유효 Settings의 `mobility_gh_url`은 **빈 문자열**이었습니다. 실제 제품 설정을 그대로 읽었고 override하지 않았습니다. GraphHopper `/info` 연결은 실행하지 않았습니다. 네트워크·DB·파일쓰기·자식프로세스·스레드 시작을 차단한 앱 import는 실제 이동 자료 검사·적재 경로를 지난 뒤 **로컬 라우터 warm daemon thread 시작 경계**에서 멈췄습니다. 여기까지 DB/network 시도는 없었으며, 전체 조립·MCP lifespan의 이후 안전성까지 통과했다고 일반화하지 않습니다. 차단을 풀거나 기능을 끄고 기동하지 않았습니다.

기존 시험 venv는 전후 **8,168/8,168 = 100% 파일 SHA-256 동일**, 추가·삭제·변경 0입니다. 기존 frontend 3100 프로세스 `proc_9063bcbba4ec`에 종료·재기동·설정변경 명령을 보내지 않았습니다. 이 작업에서 해당 서비스 HTTP 재확인은 하지 않았습니다.

## 경로와 정정 준수

- 제품 실제 CS 경로: `C:/_proj/final_workspace/final_project_cs`. 요청의 `cs`는 약칭이며 `C:/_proj/final_workspace/cs` 실제 디렉터리는 없습니다.
- 원 시험 환경: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv` — metadata·설정·해시 읽기만 했습니다.
- **새 API runtime**: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/api-runtime-20261025-014236/venv`.
- 실행기: 위 경로의 `Scripts/python.exe`; 원 pyvenv.cfg가 가리키는 실존 3.12.15 base Python으로 새 환경을 만들었습니다. `sys.version`은 AMD64, 실행파일 PE machine은 `0x8664`입니다. `platform.machine()`의 ARM64는 호스트 값으로, 이를 인터프리터 ARM64라고 판정하지 않습니다.
- [읽기전용 복원 가능성 정정](2026-10-25_api-readonly-restoration-feasibility.md)을 따릅니다. 루트 mobility 자료 25개 해시 증거가 이미 있으며 **복원·재다운로드·manifest 생성은 필요하지 않습니다.** 이번에는 자료를 생성하거나 경로 override하지 않았습니다.

## 계획 검토 → 실제 설치

[전체 증거 폴더](../evidence/2026-10-25_api-runtime-20261025-014236/)에 다음을 보존했습니다.

1. `original-metadata.json`: 원 환경 43개 distribution의 version/Requires-Dist.
2. `plan.json`, `subset.txt`: 원 runtime 관련 37개 distribution의 정확 버전 재현 + 정본 uvicorn/mcp 두 extra 선언. 원 pip·pytest·pytest-asyncio·pluggy·iniconfig·Pygments는 최초 직접 subset에서 제외했습니다. Pygments는 MCP CLI → rich 전이 의존성으로 다시 설치되었습니다.
3. `dry-run.json`, `dry-run.log`: 최초 resolver dry-run exit 0. MCP crypto extra가 cryptography 최신판 50.0.2를 선택하여 **설치 전에** 정본 43.0.0으로 제약했습니다. 제품 pin은 바꾸지 않았습니다.
4. `dry-run-reviewed.json`, `dry-run-reviewed.log`, `plan-review.json`: 정본 `cryptography==43.0.0`과 설정된 외부 프록시 런타임을 위한 `socksio==1.0.0` 추가 후 재검토 dry-run exit 0. resolver backtracking으로 기존 starlette 0.47.3과 양립하는 sse-starlette 3.0.3을 선택했습니다. 기존 runtime pin 변경·정본 pin 충돌은 없습니다.
5. `resolved-lock.txt`: 검토된 **62개** install 대상 이름/버전. 새 환경에서 이 제약과 subset extra 선언으로 실제 설치했습니다.
6. `install-result.json`, `install.log`, `install-report.json`: 실제 설치 명령과 exit 0, distribution artifact URL·hash를 포함한 pip report.
7. `freeze.txt`: pip 자체를 포함한 **63개** 최종 freeze. `pipcheck.txt`: `No broken requirements found.`. `versions.txt`: 정본 두 패키지와 fastapi/pydantic/crypto/socksio 버전 확인.

`numpy==1.26.4`는 원 runtime의 pgvector 의존성이므로 재현했습니다. API와 무관한 scipy/sklearn/pandas/osmium/pyproj/shapely 전체 설치는 하지 않았습니다. 이 환경은 full requirements 환경이 아니라 승인된 API runtime subset입니다. `canonical-comparison.json` 기준 정본 직접 pin 35개 중 설치 20개는 모두 일치하고 불일치 0입니다. 나머지 15개(sqlalchemy, pglast, alembic, langchain-core, scipy, scikit-learn, python-docx, openpyxl, pandas, shapely, pyproj, osmium, pytest, pytest-asyncio, pytest-xdist)는 이 subset에 없습니다. 따라서 업로드 문서의 lazy DOCX/XLSX 경로까지 준비 완료라고 주장하지 않습니다.

## 안전 검증과 유효 endpoint

`safe_probe.py`는 bytecode 생성을 끄고 audit hook으로 DNS/접속/bind/자식프로세스/파일쓰기를 차단한 상태에서 다음 실제 라이브러리 import를 실행했습니다.

`uvicorn`, `mcp`, `mcp.server.fastmcp`, `fastapi`, `pydantic`, `pydantic_settings`, `psycopg`, `pgvector`, `openai`, `tiktoken`, `cryptography`, `socksio` — **12/12 PASS**, 차단 이벤트 0. 이는 라이브러리 로딩 검증이지 실모델 호출/DB 연결 시험이 아닙니다.

실제 `app.core.settings.get_settings()`를 원 제품 `.env`/`.env.apikeys` 및 현재 process 환경 우선순위 그대로 사용했습니다. 설정파일 원문이나 다른 설정값은 출력하지 않았습니다. `safe-probe.json`의 안전 출력은 다음과 같습니다.

```json
{
  "scheme": "",
  "host": null,
  "port": null,
  "path": "",
  "credentials": null,
  "query": null,
  "fragment": null
}
```

`gh_configured=false`입니다. 향후 값이 바뀌면 이 증거를 재사용하지 말고 같은 마스킹 방식으로 재확인해야 합니다. URL 인증정보/query/fragment가 있다면 probe는 `[REDACTED]`만 출력합니다.

## 전체 앱 import가 멈춘 정확한 경계

`guarded_app_import.py`는 Settings를 바꾸지 않고 socket/DNS/bind/DB connect/파일쓰기/자식프로세스/thread.start를 거부했습니다. 출력은 예외 원문을 버리고 종류와 파일/행만 기록하여 비밀값 노출을 피했습니다.

실제 경로:

`app.py:146 create_app → app.py:54 build_controller → composition.py:563 → _configure_mobility_once:268 → wiring.py:117 configure → wiring.py:80 _warm_local_router → wiring.py:102 threading.Thread.start`

결과는 `RuntimeError`, `blocked_events=["thread.start"]`입니다. 자료 검사/적재는 그 앞 단계에서 실행되었으나 전체 mobility 모든 부가자료 정합성을 별도 인증한 것은 아닙니다. 순수 import 조건에서는 로컬 warm thread도 부수효과이므로 멈췄습니다. 가짜 데이터·가짜 기능·feature OFF·다른 설정값으로 통과시키지 않았습니다. DB 접속·GraphHopper HTTP·모델/외부 원문 전송·905·배포·커밋·푸시는 0회입니다.

**남은 경계**: 로컬 warm thread를 포함하는 실 앱 조립 및 MCP lifespan은 아직 미실행 구간입니다. 기존 API 기동 승인을 폐기했다는 뜻은 아니지만, 이번 부수효과차단 순수 import 검증은 통과하지 못했습니다. 이후 기동을 진행하려면 네트워크/DB 차단을 유지하는 추가 조립 검증과 thread의 로컬 자료 읽기·자원 사용 경계를 별도로 확인해야 하며, 실제 DB/모델/외부 서비스 사용은 별도 승인 없이는 계속 금지입니다.

## 보존과 변경 범위

- `original-venv-before.json`, `original-venv-after.json`, `original-venv-comparison.json`: 전후 8,168파일 hash 동일.
- `requirements-sha256.txt`: `23e7b5f370b2d4b4d4aa758f040cb7e69ebeb9e073df7ee7f25bd6c181d86a6a` — 선행 정정 보고서 정본과 동일.
- 제품 코드/settings/requirements를 수정하는 명령은 실행하지 않았습니다. 원 보고서는 동결 유지했습니다.
- 신규 파일은 이 CS 고유 보고서, CS 고유 evidence 폴더, active profile scratch의 새 venv·검증 스크립트·로그뿐입니다. 루트 상태 문서·인계 정리는 부모 담당입니다.

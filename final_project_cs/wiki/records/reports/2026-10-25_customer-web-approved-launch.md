---
type: report
title: 승인 고객 웹 실제 기동·API 차단점
status: draft
domain: travel
---

# 승인 고객 웹 기동 — 2026-10-25 00:55 KST

## 결론

고객 웹 production artifact를 **http://127.0.0.1:3100/** 에 실제 기동했습니다. GET `/`, `/start`, `/trips`, `/support` **4/4 = 100% HTTP 200**, 첫 JS chunk **1/1 = 100% HTTP 200**입니다. 브라우저 확인은 부모 담당이며 이 보고서는 HTTP 서빙 확인입니다. **실고객 API는 기동하지 못했으며 live 기능 연결은 불가합니다.** 가짜 API·fixture 서버는 기동하지 않았습니다.

## 활성 경로·프로세스 이관

- 활성 cwd: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-approved-launch-20261025/production-web`
- 활성 dist: 위 폴더의 `.next-live-hours`; build ID `rK1hjflG-Yj0CVaBDmd_8`.
- Node: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-web-response-status/node.exe`, 실측 v24.10.0 x64.
- Node listener PID **25360**, loopback `127.0.0.1:3100`만 LISTENING. 관리 background PID **23084**.
- 추적 핸들 **`proc_9063bcbba4ec`**, `process_manage handoff` 결과 **handed_off**. 부모 소유권 이관을 확인했으므로 child 종료에 묶인 서비스로 남기지 않았습니다. 부모는 이 핸들로 poll/log를 이어갈 수 있습니다.
- 원본 최신 `cs-web-response-status/session-fence-20261025/clean-web`을 새 전용 폴더로 복사했습니다. 원본 생성물 삭제·청소·재빌드·서비스 종료/재시작은 하지 않았습니다. 기존 node_modules는 junction으로 재사용했습니다.
- 입력 **381/381 = 100%** SHA256이 기존 검증 manifest·현재 제품 소스·기존 clean-web과 일치하며 새 사본도 같은 입력을 검증했습니다. private `.env*`는 사본에 없습니다. 과거 exit 0 production build를 새 build 실행인 것처럼 보고하지 않습니다.

실제 실행 명령(cwd는 위 활성 경로):

```bash
NEXT_DIST_DIR=.next-live-hours NEXT_PUBLIC_DATA_MODE=live NEXT_PUBLIC_MAP_PROVIDER=osm NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-web-response-status/node.exe node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3100
```

실행은 `set -o pipefail`과 `tee <evidence>/web-server.log`를 포함한 추적 background session입니다. 로그에서 Next.js 16.3.5, Ready 657ms를 확인했습니다. 빌드된 브라우저 chunk의 API 목적지는 실제 **`http://127.0.0.1:8042`**입니다. runtime NEXT_PUBLIC 값만 바꾸어 이미 빌드된 목적지를 바꿨다고 주장하지 않습니다.

## API 실행 정의·실측 차단점

현재 코드의 고객 API 진입점은 `app.presentation.api.app:app`; `scripts/ops/jobs.py:122`의 실행 정의는 `python -m uvicorn app.presentation.api.app:app --port 8042`입니다. 관리 앱/worker/sweeper는 이번 실행 대상이 아닙니다. 이 명령은 실행하지 않았습니다.

- 현재 OS listener 관찰: 8042·5433 LISTENING 없음. API `GET http://127.0.0.1:8042/health`는 **WinError 10061 연결 거부**. DB에는 TCP probe/SQL/로그인조차 하지 않았습니다.
- 기본 Python 3.14.7 ARM64에는 uvicorn/fastapi/psycopg/pydantic_settings가 없습니다.
- 기존 승인 시험용 `scratch/travel-writing-s1-venv/Scripts/python.exe`를 발견해 실제 확인: **Python 3.12.15 AMD64**, fastapi/psycopg/pydantic_settings는 있으나 **uvicorn·mcp 없음**. `app.py`는 create_app에서 MCP 표면을 무조건 조립하므로 해당 실행 의존성이 필요합니다. 설치하지 않았습니다.
- 이 venv로 `app.core.settings.get_settings()`만 읽었으며 앱/조립/DB를 import 실행하지 않았습니다. 설정은 CS `.env`, `.env.apikeys`를 읽는 현재 Settings 경로 그대로입니다. 민감 값은 출력하지 않았습니다.
- 실제 설정: LLM provider `openai`, activity judge `rule`, CORS `http://127.0.0.1:3100,http://localhost:3100`; mobility_data_dir **`datasets/mobility/processed`는 현재 CS cwd에서 존재하지 않음**. 조립 `composition.py:562-563` → mobility `configure_from_settings` → `configure`의 자료 검사는 파일 부재 때 MobilityUnavailable로 서버 기동을 거부합니다. 다른 자료 경로로 임의 대체하거나 설정을 꺼서 기동하지 않았습니다.
- DB 설정은 비밀번호 없이 endpoint만 확인: `127.0.0.1:5433/acop_cs`. 설정 존재를 DB 연결/스키마/905 준비 완료로 해석하지 않습니다.

정적 검토한 app lifespan은 MCP surface lifespan이며, create_app은 production controller·도메인 router·MCP를 조립합니다. 확인한 OpenAITeamLLM/DbResponseCache 생성자는 즉시 모델/DB를 호출하지 않지만, **전체 transitive startup 무부수효과 인증은 하지 않았습니다**. startup DB write·migration이 있다고 지어내지 않으며, 반대로 전체 안전하다고 보증하지 않습니다. 현재 확정 설치·자료 차단점을 우회하지 않고 API를 보류했습니다. 재개 시 승인된 실행 환경/의존성·자료 경로를 확정하고 startup 전체 부수효과를 먼저 검토해야 합니다. DB 읽기 연결, 905 적용, 실모델·외부 원문 전송·유료 네트워크·배포는 별도 승인 상태를 유지합니다.

## 증거·남은 범위

증거 루트: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-approved-launch-20261025/`

- `audit.py`, `audit.log`, `input-readback.json`: 현재 소스/빌드 입력·엔진·안전한 설정 확인.
- `prepare.py`, `production-web/`: 새 고유 production artifact. junction 생성 stdout 디코딩은 CP949/UTF-8 차이 경고가 있었으나 명령 exit 0, 후속 Next 기동·HTTP/asset 성공으로 junction 사용을 확인했습니다.
- `web-server.log`: 지속 서버 로그.
- `readback.py`, `health-readback.json`, `health-readback.log`, `home.html`: 실제 HTTP·listener·compiled API URL readback.
- `backend-preflight.log`: 기존 Python venv의 실제 버전/모듈/현재 Settings 읽기. 제품 서버 실행 로그가 아닙니다.

고객 웹 HTTP 서빙과 실API/DB/모델 업무 수락은 분리합니다. 부모가 위 실제 URL에서 브라우저를 확인하되 새 게스트/일정/문의 등록·설정 변경 등 실데이터 변경은 이번 확인에 포함하지 않습니다. 제품 frontend/backend 코드는 수정하지 않았으며 root wiki는 부모에게 맡깁니다. 새로운 cs 보고서와 profile scratch 산출물만 추가했습니다.

---
type: guide
title: 로컬 셋업
description: PostgreSQL은 Windows 서비스가 아니고 Docker는 없다. 이 두 가지를 먼저 안다
status: draft
tags: [data]
owners: [human:미배정]
domain: neutral
---

# 로컬 셋업

## 먼저 알아야 할 것 둘

`[실측]` 2026-08-12 확인

**하나 — Docker가 설치돼 있지 않다.** `docker/compose.yml`로 DB를 띄우는 전제는 이 기계에서 성립하지 않는다. 로컬 PG를 쓰고 compose 파일은 재현용으로만 남긴다.

**둘 — PostgreSQL이 Windows 서비스가 아니다.** conda env `pgv`에서 뜬 프로세스다. **재부팅 후 안 떠 있을 수 있다.**

## 환경

| | 값 |
|---|---|
| PostgreSQL | 16.14 · `127.0.0.1:5433` |
| extension | `vector` · `pgcrypto` |
| DB | **`acop_cs`** `[정정 2026-09-10]` `acop` 으로 적혀 있었다. 개발 서버는 `.claude/launch.json` 의 **`acop-cs-ui` · 8042** |
| Python | 3.12.7 |

## ★ PostgreSQL이 안 떠 있을 때 — 기동 절차

`[실측]` `wiki/records/manuals/2026-08-12_1520_환경_기동절차.md`(2026-08-13 실측)에서. 위에 "재부팅 후 안 떠 있을 수 있다"고만 있고 **어떻게 띄우는지가 이 wiki에 없었다.**

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5433          # 떠 있나
$bin  = "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin"
$data = "C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

**`-o "-p 5433"`를 빠뜨리면 5432로 뜬다.** `postgresql.conf`에 `port`가 없어서다. 2026-08-13에 이걸 몰라 5432로 띄우고 "connection refused"를 계속 봤다.

| 알아야 할 것 | |
|---|---|
| **데이터 디렉터리가 저장소 밖이다** | `_unified_mall_3/data/pgdata`. `acop`은 그 클러스터 안에 있고 **`insurance_*`·`mall_vec` 등 옆 프로젝트 DB와 같은 서버**다. 이 서버를 내리면 옆 프로젝트도 멈춘다. triPilot은 `acop`만 쓴다 |
| 비정상 종료 후 | 기동 때 자동 복구가 돈다(`automatic recovery in progress … redo done`). fsync에 **40초 이상** 걸릴 수 있으니 `pg_ctl start`가 느려도 기다린다 |
| 기동 후 | **건수를 대조하고 작업을 재개한다.** `knowledge_documents=25 · knowledge_chunks=306`(cs `CLAUDE.md` §5). 원본 매뉴얼의 `payments=30·knowledge_chunks=300`은 옛 도메인 값이라 지금과 다르다 |
| extension | `vector`·`pgcrypto`는 **마이그레이션이 만든다.** `CREATE EXTENSION`을 손으로 치지 않는다 — 마이그레이션이 유일한 경로여야 재현된다 |

### 앱이 관리하는 서버로 띄우기 `[2026-10-03]`

`pg_ctl` 을 도구(Bash·PowerShell) 안에서 띄우면 그 도구 작업이 끝날 때 DB 도 같이 죽는다. 앱의 실행 설정에 올려 두면 도구와 상관없이 산다.
`final_project_ui/.claude/launch.json` 에 아래 항목을 넣고(**경로는 PC마다 달라 커밋하지 않는다**) `preview_start {name: "tripilot-db"}` 로 띄운다.

```json
{ "name": "tripilot-db", "runtimeExecutable": "<conda env>/Library/bin/postgres.exe",
  "runtimeArgs": ["-D", "<pgdata 폴더>", "-p", "5433"], "port": 5433 }
```

- 순서는 DB → `tripilot-api`(8042) → `tripilot-web`(3100).
- 앱에서 끄면 강제 종료라 다음 기동 때 자동 복구가 돈다(40초쯤). 옆 프로젝트 DB 와 같은 서버라 함부로 끄지 않는다.
- 실행 도구가 포트를 웹 요청으로 확인해서 로그에 `invalid length of startup packet` 이 쌓인다 — 이상이 아니다.

## psql이 PATH에 없다

`[실측]` conda env 안에 있다.

```powershell
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop_cs
```

## 임베딩 차원

```
text-embedding-3-small = 1536차원
knowledge_chunks.embedding vector(1536)
```

**모델을 바꾸면 DDL과 적재분을 함께 바꿔야 한다.**

## 마이그레이션

재실행이 안전하다. 전부 `IF NOT EXISTS`다.

→ [../data/migrations.md](../data/migrations.md)

## 개발 서버

`[실측]` `.claude/launch.json`의 `acop-ui`

```
포트 8041 · --reload
/ → /ui/cases (307)
```

## 임시 파일

`[실측]` **상위 폴더에 `.tmp_*`를 흩뿌리지 않는다.**

```
final_workspace/.tmp/     ← 워크스페이스 임시물은 전부 여기
```

저장소 안 스크래치는 저장소 밖 세션 임시 폴더를 쓰고 **커밋되지 않게** 한다. 남길 산출물이면 `docs/` 제자리에 둔다.

## ★ [2026-09-03] 원본에만 있던 함정 셋

`[실측]` `wiki/records/manuals/2026-08-12_1520_환경_기동절차.md` 에서 이관.

### 1. `.env` 를 BOM 없이 저장한다

**PowerShell 의 `Set-Content -Encoding UTF8` 은 BOM 을 붙인다.**

```
첫 줄 키가 ﻿ACOP_DATABASE_URL 이 되어 인식되지 않는다
```

`[실측]` **2026-08-12 에 실제로 겪었다.**

```powershell
[System.IO.File]::WriteAllText("$PWD\.env", $text, (New-Object System.Text.UTF8Encoding($false)))
```

**눈에 안 보이는 세 글자 때문에 DB 연결이 안 된다.** 오류 메시지도 "키가 없다"고만 나온다.

### 2. anaconda base 를 옆 프로젝트와 공유한다

> **버전을 강제로 올리면 옆 프로젝트가 깨진다.**

**설치 전에 이미 있는 버전을 확인하고, 충돌하면 리포트에 적는다.**

```powershell
python -m pip install -r requirements.txt
```

`[실측]` 2026-08-12 확인 — `pydantic 2.13.4` · `psycopg 3.3.4` · `tiktoken`.

★`[2026-09-24]` **`acop_composer` 는 `requirements.txt` 로 안 깔린다.** `app/composer_host.py`(관리용 빌드
`app.entrypoint:app` 과 그 시험)가 import 하는데, 소스는 `final_project_sample/acop_composer/` 에 있다.
★`pip install -e final_project_sample` 로 깔지 않는다 — sample 의 `app` 패키지까지 깔려 cs 의 `app` 과 겹친다.
CI 와 같은 방식으로 **경로만 붙인다** — `final_project_cs` 폴더에서 실행한다(현재 폴더가 경로의 맨 앞이라 cs 의 `app` 이 이긴다):

```powershell
$env:PYTHONPATH = (Resolve-Path ..\final_project_sample).Path
```

`[실측]` 이 PC 는 sample 이 편집 모드로 깔려 있어 이 문제가 안 드러났다 — 깨끗한 환경(CI)에서 처음 드러났다.

**`faster-whisper` 가 `onnxruntime` 미설치를 경고하는데 이 프로젝트와 무관한 옆 프로젝트 의존성이다.** 무시한다.

### 3. 점검은 스크립트가 한다

```powershell
python -m scripts.check_env
```

**전 항목 OK 여야 다음으로 간다.**

`[실측]` **단 extension 2건 FAIL 은 마이그레이션 전에는 정상이다.** 이걸 모르면 멀쩡한 상태를 고장으로 오해한다.

## ★ 시험(pytest) — 이동 자료 없이 돈다 `[2026-10-12]`

**이동 자료(지하철 시간표 등 약 93MB)는 받지 않아도 된다.** 시험은 기본으로 이동 계산기를 끄고 돈다
(`tests/conftest.py` 가 `ACOP_MOBILITY_DATA_DIR` 를 비운다). GitHub 검사(CI)도 같은 조건이다.

| 무엇을 | 어떻게 |
|---|---|
| DB | 빈 DB 하나(`pgvector` 확장 가능한 PostgreSQL) → `python -m app.infrastructure.db.migrate` → `python -m scripts.register_prompts` |
| 빠른 관문(develop 과 같음) | `python -m pytest tests/architecture tests/contract tests/unit -q` 그리고 `python -m pytest tests/security -q` |
| 전체(main 과 같음) | `python -m pytest -q` (실제 모델을 부르는 `live` 는 `pytest.ini` 가 뺀다) |
| 환경값 | CI 와 같게 — `.github/workflows/ci-main.yml` 의 `env` 칸(시험용 가짜 값)과 위 `PYTHONPATH` |

**이동을 거치는 시험을 새로 쓸 때** — 앱을 만든 직후 시험용 고정 구간을 명시한다. 안 하면 이동 팀이
「엔진 미준비」로 거절해 503 `team_unavailable`(`reason: engine_unavailable`)이 난다([plugin-availability](../teams/team-contract/plugin-availability.md) — 직선거리 어림으로 대신하지 않는 것이 계약이다).

```python
from tests.helpers.plugin_bindings import publish_fixed_mobility

client = TestClient(create_app(...))
publish_fixed_mobility(client.app, source="내_시험_이름")            # 구간마다 5분 · 앞 일정 끝나고 출발
# 일정 짜기처럼 「다음 일정 시작 − 이동 − 여유」 출발 규칙을 보는 시험은 도착 여유를 준다
publish_fixed_mobility(client.app, source="내_시험_이름", arrival_buffer_min=MOVE_BUFFER_MIN)
```

**실제 시간표로 돌려 보고 싶을 때만** 자료 폴더를 직접 지정한다 — 셸에서 `ACOP_MOBILITY_DATA_DIR=<자료 폴더>/datasets/mobility/processed`.
느려진다(2026-10-12 일정 짜기 시험 묶음: 꺼짐 33초 → 켬 약 10분 `[실측 1회]`). 실제 자료로 하는 확인은 자료가 붙어 있는 개발 기계의 cs 프로젝트 서버(화면·API)에서 한다.

`[실측]` 2026-10-12 develop 의 이동 팀 「엔진 미준비 거절」 변경 뒤, 자료 없는 CI 에서 이동을 거치는 e2e 시험 45건이
깨졌다(요식 PR 도 같이 붉어짐). 위 고정 구간을 넣어 고쳤다.

## 관계

- [run.md](run.md) — 실행 명령
- [troubleshooting.md](troubleshooting.md) — 막히면
- [../data/migrations.md](../data/migrations.md) — DB 준비

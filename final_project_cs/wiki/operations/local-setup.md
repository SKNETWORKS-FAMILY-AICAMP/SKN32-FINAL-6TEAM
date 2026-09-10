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
| **데이터 디렉터리가 저장소 밖이다** | `_unified_mall_3/data/pgdata`. `acop`은 그 클러스터 안에 있고 **`insurance_*`·`mall_vec` 등 옆 프로젝트 DB와 같은 서버**다. 이 서버를 내리면 옆 프로젝트도 멈춘다. A-COP은 `acop`만 쓴다 |
| 비정상 종료 후 | 기동 때 자동 복구가 돈다(`automatic recovery in progress … redo done`). fsync에 **40초 이상** 걸릴 수 있으니 `pg_ctl start`가 느려도 기다린다 |
| 기동 후 | **건수를 대조하고 작업을 재개한다.** `knowledge_documents=25 · knowledge_chunks=306`(cs `CLAUDE.md` §5). 원본 매뉴얼의 `payments=30·knowledge_chunks=300`은 옛 도메인 값이라 지금과 다르다 |
| extension | `vector`·`pgcrypto`는 **마이그레이션이 만든다.** `CREATE EXTENSION`을 손으로 치지 않는다 — 마이그레이션이 유일한 경로여야 재현된다 |

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

**`faster-whisper` 가 `onnxruntime` 미설치를 경고하는데 이 프로젝트와 무관한 옆 프로젝트 의존성이다.** 무시한다.

### 3. 점검은 스크립트가 한다

```powershell
python -m scripts.check_env
```

**전 항목 OK 여야 다음으로 간다.**

`[실측]` **단 extension 2건 FAIL 은 마이그레이션 전에는 정상이다.** 이걸 모르면 멀쩡한 상태를 고장으로 오해한다.

## 관계

- [run.md](run.md) — 실행 명령
- [troubleshooting.md](troubleshooting.md) — 막히면
- [../data/migrations.md](../data/migrations.md) — DB 준비

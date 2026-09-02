---
type: guide
title: 로컬 셋업
description: PostgreSQL은 Windows 서비스가 아니고 Docker는 없다. 이 두 가지를 먼저 안다
status: draft
tags: [data]
owners: [human:미배정]
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
| DB | `acop` |
| Python | 3.12.7 |

## psql이 PATH에 없다

`[실측]` conda env 안에 있다.

```powershell
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop
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

## 관계

- [run.md](run.md) — 실행 명령
- [troubleshooting.md](troubleshooting.md) — 막히면
- [../data/migrations.md](../data/migrations.md) — DB 준비

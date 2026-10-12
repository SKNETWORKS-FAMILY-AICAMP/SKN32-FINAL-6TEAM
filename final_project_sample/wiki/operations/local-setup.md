---
type: runbook
title: 처음부터 띄우기
description: sample을 로컬에서 실행하는 데 필요한 것과 실제로 확인된 절차
status: draft
tags: [release]
domain: neutral
---

# 처음부터 띄우기

`[실측]` 2026-09-02에 실제로 띄워 확인했다. **이 문서의 명령은 전부 돌려 본 것이다.**

## Docker 는 안 쓴다

`docker/compose.yml`이 있지만 **로컬 개발 환경에 Docker 가 없다.**

```
$ docker --version
command not found
```

컨테이너화는 배포 단계 몫이다. **로컬은 Postgres 를 직접 띄우고 Python 을 직접 돌린다.**

## 필요한 것

`[실측]` `python scripts/check_env.py` 로 11개 항목을 확인한다.

| 항목 | 확인된 값 |
|---|---|
| Python | 3.12.7 |
| PostgreSQL | **16.14** |
| extension | `vector` · `pgcrypto` 둘 다 설치됨 |
| 테이블 | `public` 스키마 20개 |
| 임베딩 차원 | 1536 (DDL `vector(1536)` 과 일치해야 한다) |
| 토큰 예산 | 12000 (`guardrails.yaml` 과 일치) |

### `.env` 가 있어야 한다

`[실측]` 13개 키가 들어간다.

```
ACOP_DATABASE_URL          ACOP_SECRET_KEY
ACOP_LLM_PROVIDER          ACOP_COMPOSER_JWT_SECRET
ACOP_OPENAI_API_KEY        ACOP_COMPOSER_ISSUER_SECRET
ACOP_LLM_MODEL             ACOP_GUARDRAILS_PATH
ACOP_EMBEDDING_MODEL       ACOP_ENV
ACOP_LLM_TEMPERATURE       ACOP_TENANT_ID
ACOP_LLM_SEED
```

**`.env` 는 커밋하지 않는다.**

### 환경 점검이 1건 실패한다

```
[FAIL] v4 원문 대조   찾을 수 없음: A-COP_구현계획서(4).md
```

`[실측]` **기능과 무관하다.** 워크스페이스 루트의 옛 계획서 파일을 찾는 검사이고, 그 파일이 지금 없다. 나머지 10개는 통과한다.

`[미확보]` 이 검사를 지울지 경로를 고칠지 정해지지 않았다.

## 띄우기

```bash
python -m uvicorn acop_basement.presentation.api.app:app --port 8077
```

`[실측]` 기동 로그.

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8077
```

Composer 는 따로 띄운다.

```bash
python -m uvicorn app.config_service:app --port 8078
# [정정 2026-09-10] acop_composer.service_app:app 로 적혀 있었다 — 그 모듈엔 app 객체가 없고
#   팩토리 create_config_service_app(host) 만 있다. 실행 대상은 app/config_service.py 의 app 이다
```

**두 프로세스다.** basement 가 실행 기반이고 Composer 가 설정을 바꾸는 입구다. → [../composer/write-channel.md](../composer/write-channel.md)

`[실측]` `compose.yml` 주석이 이유를 적어 둔다.

> Composer `_WRITE_LOCK` is process-local; keep one Uvicorn worker.

**워커를 늘리면 쓰기 잠금이 프로세스마다 따로 생긴다.**

## 관계

- [run.md](run.md) — 떴는지 어떻게 확인하나
- [troubleshooting.md](troubleshooting.md) — 안 뜰 때
- [../index.md](../index.md) — 지식 지도

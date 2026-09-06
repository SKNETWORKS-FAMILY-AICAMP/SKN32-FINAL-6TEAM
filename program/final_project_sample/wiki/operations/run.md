---
type: runbook
title: 떴는지 확인하기
description: 실제로 호출해 확인한 경로와 응답 코드. 인증 없이 볼 수 있는 것과 아닌 것
status: draft
tags: [release, api]
---

# 떴는지 확인하기

`[실측]` 2026-09-02. 아래 코드는 전부 실제 응답이다.

## 인증 없이 되는 것

```bash
curl -s http://127.0.0.1:8077/health
{"status":"ok"}
```

| 응답 | 경로 | |
|---|---|---|
| 200 | `/health` | |
| 200 | `/docs` | OpenAPI 화면 |
| **307** | `/` | → `/ops/cases` 로 보낸다 |
| 200 | `/ops/cases` · `/ops/approvals` · `/ops/voc` · `/ops/outbox` | **운영 화면 4종** |

**루트가 `/ops/cases` 로 넘어간다.** 이 서버의 첫 화면은 운영자 화면이다.

## 인증이 필요한 것

```bash
curl -s http://127.0.0.1:8077/v1/cases
{"error":{"code":"unauthenticated","message":"authentication required"}}
```

| 응답 | 경로 |
|---|---|
| 401 | `/v1/*` 전부 |
| 401 | `/introspection` |

**`/ops/*` 화면은 열리는데 `/v1/*` API 는 막힌다.** → [../composer/auth-scope.md](../composer/auth-scope.md)

## 개발 키 만들기

`[실측]` 키는 `.env` 에 적는 게 아니라 **scope 마다 유도된다.**

```python
key = HMAC-SHA256(ACOP_SECRET_KEY, scope)
```

`presentation/security.py:31-33`. 서버는 제시된 값을 SHA-256 해싱해 대조한다 (`:39-43`).

```python
from acop_basement.presentation.security import _development_key
print(_development_key("case:read"))
```

`[실측]` scope 는 11개다.

```
action:approve  case:read      case:write
composer:read   composer:validate  composer:write
mcp:read        ops:introspect ops:reload
subscription:read  technical:read
```

### 인증이 걸린 것을 확인한 결과

```bash
curl -H "Authorization: Bearer $KEY" http://127.0.0.1:8077/v1/cases
```

| 키 | 경로 | 응답 | 뜻 |
|---|---|---|---|
| 없음 | `/v1/cases` | **401** | 인증 필요 |
| `case:read` | `/v1/cases` | **422** | **인증 통과.** 파라미터가 모자람 |
| `case:read` | `/introspection` | **403** | **scope 부족** — `ops:introspect` 가 필요 |

**401 → 403 → 422 로 갈리는 게 중요하다.** 인증 실패와 권한 부족과 요청 오류를 구분한다.

## Composer 확인

```bash
python -m uvicorn acop_composer.service_app:app --port 8078
```

| 응답 | 경로 |
|---|---|
| 200 | `/health` · `/docs` |
| **401** | `/composer/catalog` |
| 405 | `/composer/changes` (GET). **POST 전용이다** |

`[실측]` 경로 8개.

```
POST /auth/token
GET  /composer/catalog     GET  /composer/current
POST /composer/changes     POST /composer/validate
POST /composer/apply       POST /composer/toggle
GET  /health
```

**`/composer/toggle` 이 따로 있다.** 전체 설정 교체가 아니라 항목 하나만 켜고 끄는 경로다. → [../composer/write-channel.md](../composer/write-channel.md)

## 관계

- [local-setup.md](local-setup.md) — 띄우기 전에 필요한 것
- [troubleshooting.md](troubleshooting.md) — 안 뜰 때

---
type: guide
title: 어떻게 띄우나
description: sample을 혼자 실행하는 법. cs 없이 성립해야 하므로 여기가 자족적이어야 한다
status: draft
tags: [release]
---

# 운영 — 어떻게 띄우나

**이 영역이 가장 자족적이어야 한다.** cs가 나간 뒤 sample을 처음 켜는 사람이 여기만 보고 띄울 수 있어야 한다.

## 무엇이 있나

`[실측]` 2026-09-01.

```
acop_basement/presentation/api/app.py     API 진입점
acop_composer/service_app.py              Composer 독립 실행
dist/basement/                            배포본
```

**`dist/`가 있다는 건 이미 패키징된다는 뜻이다.**

## 문서

`[실측]` **네 문서 다 실제로 띄워 보고 썼다.** 2026-09-02.

| 문서 | 답하는 질문 |
|---|---|
| [local-setup.md](local-setup.md) | 무엇이 있어야 뜨나 |
| [run.md](run.md) | 떴는지 어떻게 확인하나 |
| [packaging.md](packaging.md) | `dist/` 가 어떻게 만들어지나 |
| [troubleshooting.md](troubleshooting.md) | 안 될 때 |

## 실측 요약

| 항목 | 값 |
|---|---|
| Python · PostgreSQL | 3.12.7 · **16.14** |
| Docker | **없다.** 로컬은 Postgres 직접 |
| 테스트 | **469 passed, 1 deselected in 43.89s** |
| 프로세스 | **2개** — basement · Composer |
| scope | 11개 |

```
GET /health          200
GET /                307  → /ops/cases
GET /ops/cases       200
GET /v1/cases        401  → 키 붙이면 422
GET /introspection   403  (scope 부족)
```

**401 → 403 → 422 로 갈리는 게 인증이 제대로 걸렸다는 증거다.**

## 관계

- [../index.md](../index.md) — 지식 지도
- [`../../../final_project_cs/wiki/operations/index.md](../../../final_project_cs/wiki/operations/index.md) — cs 쪽 같은 영역

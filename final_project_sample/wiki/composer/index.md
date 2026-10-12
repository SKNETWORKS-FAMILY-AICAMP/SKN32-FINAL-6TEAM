---
type: guide
title: 설정을 누가 어떻게 바꾸나
description: Composer는 basement 설정을 바꾸는 유일한 통제 입구다. sample이 먼저 검증하고 cs로 이식한다
status: draft
tags: [architecture, api, security]
domain: neutral
---

# Composer — 쓰기채널

**basement 설정을 바꾸는 유일한 경로다.** 아무 데서나 설정을 고칠 수 있으면 basement가 무슨 상태인지 아무도 모른다.

## 구성

`[실측]` `acop_composer/`

| 파일 | 무엇 |
|---|---|
| `api.py` | HTTP 진입점 |
| `auth.py` | 인증·scope |
| `catalog.py` | 무엇을 바꿀 수 있나 |
| `service.py` | 검증·적용 |
| `service_app.py` | 독립 실행 |

UI는 별도 패키지다 — `packages/acop_composer_ui/`.

## 경계가 테스트로 고정돼 있다

`tests/architecture/test_composer_ui_package_boundary.py`

**UI가 basement를 직접 만지면 실패한다.** UI → Composer → basement 순서만 허용된다.

## 이식 관계

```text
sample                         cs
  Composer 쓰기채널     ──→     이식
```

**sample에서 먼저 만들고 cs로 옮긴다.** 이 방향은 안 바뀐다 — cs가 나가도 여기가 원본이다.

## 문서

| 문서 | 답하는 질문 |
|---|---|
| [write-channel.md](write-channel.md) | 설정을 바꾸는 경로가 왜 하나인가 |
| [auth-scope.md](auth-scope.md) | 누가 무엇을 바꿀 수 있나 |
| [ui-boundary.md](ui-boundary.md) | UI 가 넘으면 안 되는 선 |

## 관계

- [../index.md](../index.md) — 지식 지도
- [`../../../wiki/decisions/D-006-composer-ownership.md](../../../wiki/decisions/D-006-composer-ownership.md) — 소유 결정

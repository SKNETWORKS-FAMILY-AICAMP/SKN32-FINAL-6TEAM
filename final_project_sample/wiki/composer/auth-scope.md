---
type: concept
title: Composer 인증 주체와 scope 판정
description: 누가 Composer 기능을 호출할 수 있으며 요청 scope를 어떻게 판정하는지 설명한다.
status: draft
tags: [architecture, api, security]
domain: neutral
---

# Composer 인증 주체와 scope 판정

Composer 권한은 JWT의 `scope` 목록에 필요한 문자열이 정확히 들어 있는지로 판정한다. `[실측]` scope 사이의 상속 관계나 와일드카드 판정은 없으며, 요구된 문자열이 목록에 없으면 403 `scope_denied`다. `acop_composer/auth.py:71-77`

기능별 요구 권한은 다음과 같다.

| 기능 | 필요한 scope |
|---|---|
| 현재 선언 조회 | `composer:read` `[실측]` |
| 카탈로그 조회 | `composer:read` `[실측]` |
| 후보 선언 검증 | `composer:validate` `[실측]` |
| 전체 선언 적용 (`/apply`) | **`composer:admin`** `[실측 2026-09-06]` — D-011 전엔 `composer:write`였다 |
| 인스턴스 변경 | `composer:write` `[실측]` |
| Team·모듈 토글 | `composer:write` `[실측]` |
| 이력 조회 (`/revisions`) | `composer:read` `[실측 2026-09-06]` |
| 이력의 revision 으로 복원 (`/restore`) | **`composer:admin`** `[실측 2026-09-06]` |

근거: `acop_composer/api.py:202-204`, `acop_composer/api.py:228-230`, `acop_composer/api.py:317-319`, `acop_composer/api.py:392-401`, `acop_composer/api.py:415-417`

## 토큰을 발급할 수 있는 주체

`[실측]` `/auth/token`은 `Authorization: Bearer <issuer secret>`을 요구한다. 이 값은 `composer_issuer_secret`과 일치해야 한다. 누락되거나 형식이 다르면 401 `unauthenticated`다. `acop_composer/auth.py:27-33`, `acop_composer/auth.py:80-85`

`[실측]` issuer secret을 가진 호출자는 비어 있지 않은 `sub`와 하나 이상의 scope를 요청할 수 있다. 요청한 scope가 guardrail의 `security.scopes` 목록에 없으면 422 `invalid_scope`다. `acop_composer/auth.py:17-20`, `acop_composer/auth.py:34-36`

`[미확보]` 실제 환경에 설정된 `security.scopes` 목록과 issuer secret의 배포·보관 주체는 허용된 파일에서 확인하지 않았다.

`[실측]` 발급 코드는 issuer secret 보유자와 요청의 `sub`가 같은 사람 또는 시스템인지 확인하지 않는다. 따라서 이 코드 안에서는 issuer secret을 가진 호출자가 임의의 비어 있지 않은 `sub`와 구성된 scope 조합을 요청할 수 있다. `acop_composer/auth.py:27-49`

## 토큰에 들어가는 값

`[실측]` 발급되는 토큰은 HS256으로 서명되며 다음 claim을 포함한다. `acop_composer/auth.py:13-14`, `acop_composer/auth.py:40-49`

- `sub`: 요청자가 제출한 주체 식별자 `[실측]`
- `aud`: `final_project_sample` `[실측]`
- `scope`: 요청한 문자열 목록 `[실측]`
- `iat`: 발급 시각 `[실측]`
- `exp`: 만료 시각 `[실측]`
- `jti`: 새 UUID 문자열 `[실측]`

`[실측]` TTL은 `security.composer_jwt_ttl_minutes`에서 읽으며 15분 이상 60분 이하여야 한다. 범위를 벗어나면 토큰 발급이 `RuntimeError`로 실패한다. 응답의 `expires_in`은 분 단위 TTL에 60을 곱한 초 값이다. `acop_composer/auth.py:37-50`

## 요청을 인증하는 순서

1. `[실측]` `Authorization` 헤더가 `Bearer `로 시작하는지 확인한다. 누락되면 401이다. `acop_composer/auth.py:53-55`
2. `[실측]` `composer_jwt_secret`으로 HS256 서명을 검증하고 audience가 `final_project_sample`인지 확인한다. `acop_composer/auth.py:56-60`
3. `[실측]` `sub`, `aud`, `scope`, `iat`, `exp`, `jti`가 모두 존재해야 한다. 서명·audience·만료·형식 검증 오류는 401로 변환된다. `acop_composer/auth.py:56-63`
4. `[실측]` `sub`는 비어 있지 않은 문자열이어야 하고 `scope`는 문자열로만 이루어진 목록이어야 한다. `acop_composer/auth.py:64-68`
5. `[실측]` 엔드포인트가 요구하는 scope가 목록에 정확히 포함되어야 한다. 없으면 인증 성공과 별개로 403이다. `acop_composer/auth.py:71-76`

`[실측]` E2E 검사는 토큰 누락을 401로, 다른 scope를 403으로, 만료 토큰과 다른 비밀키로 위조한 토큰을 각각 401로 거부하도록 요구한다. `tests/e2e/test_composer_write_channel.py:78-120`

## 변경할 수 있는 대상

`[정정 2026-09-10]` 이 줄은 「`composer:write` 토큰은 `/apply`, `/changes`, `/toggle` 을 호출할 수 있다」고 적고 있었다 — **`/apply` 가 틀렸다.** `/toggle`·`/changes` 는 **`composer:write`**, `/apply`·`/restore` 는 **`composer:admin`** 이다(`acop_composer/api.py` — 각 경로의 `require_composer_scope`). 항목 하나를 켜고 끄는 것과 **선언 전체를 갈아끼우거나 되돌리는 것**은 다른 행위라 권한을 갈랐다(D-011). 성공한 변경의 감사 이벤트에는 JWT의 `sub`가 `actor`로 기록된다. `acop_composer/api.py:317-319`, `acop_composer/api.py:375-383`, `acop_composer/api.py:415-437`

`[실측]` 중앙 설정 서비스에서 실제 변경 대상은 JWT claim이 아니라 `X-Deployment-Id` 헤더가 정한다. 헤더가 없으면 요청을 거부한다. `acop_composer/api.py:62-83`, `acop_composer/service_app.py:34-41`

`[실측]` 발급된 JWT에는 deployment 식별 claim이 없으며, scope 검사도 deployment와 토큰 주체의 관계를 확인하지 않는다. `acop_composer/auth.py:41-48`, `acop_composer/auth.py:71-76`

`[미확보]` 특정 `sub`가 특정 deployment만 변경하도록 제한하는 외부 네트워크 정책이나 별도 인가 계층은 허용된 파일에서 확인되지 않았다. 이 코드 범위에서는 유효한 `composer:write` 토큰과 대상 헤더가 변경 권한 판정에 사용된다.

`[실측]` 읽기 scope로 `/changes`를 호출하면 403이어야 한다는 E2E 검사가 있다. `tests/e2e/test_composer_catalog_changes.py:208-213`

`[미확보]` 허용된 테스트 파일의 현재 실행 성공 여부는 확인하지 않았다.

## ★ [2026-09-06] `composer:admin` — 통째 교체는 운영자 것이 아니다

`[실측]` [D-011](../../../wiki/decisions/D-011-composer-v3-gap.md) 결정의 구현. `config/guardrails.yaml` `security.scopes`에 `composer:admin`을 더했고, `tests/security/test_scope_contract.py`가 그 집합을 고정한다.

| scope | 할 수 있는 것 | 누구 |
|---|---|---|
| `composer:write` | 항목 **하나** — `/toggle`·`/changes`(create·update·delete·enable·disable) | 운영자 화면 |
| `composer:admin` | 선언 **전체** — `/apply`(통째 교체) · `/restore`(이력의 revision 으로) | 설치·복원·이관하는 관리자. 운영 UI 에 버튼을 두지 않는다 |

`composer:write`로 `/apply`나 `/restore`를 부르면 403이다 — `tests/e2e/test_composer_write_channel.py::test_apply_needs_admin_scope_write_is_not_enough`, `::test_restore_needs_admin_scope`. 위 표의 `acop_composer/api.py` 줄 번호는 이 변경으로 밀렸다.

## 관계

- 권한 검사를 통과한 변경이 저장되는 과정은 [write-channel.md](write-channel.md)를 참조한다.
- UI가 인증 뒤에도 서버 검증 책임을 침범하지 않게 하는 경계는 [ui-boundary.md](ui-boundary.md)를 참조한다.

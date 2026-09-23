---
type: decision
title: 운영 화면(/ui/*)은 로그인한 운영자만 — 쓰기는 그 운영자의 scope 로
description: 화면이 scope 키를 스스로 만들어 쓰던 구조라 /ui 에 닿으면 누구나 승인할 수 있었다. 운영자 계정·서명 쿠키·scope 검사로 막고, 승인자를 실제 운영자 id 로 남긴다
status: draft
tags: [security, auth, ui]
owners: [human:미배정]
domain: travel
---

# D-CS-007 운영 화면에 로그인을 둔다

`[결정 2026-09-23]` 사용자가 「cs 에서 할 개발 작업을 마저 하라」고 해서, 남은 것 중 가장 위험한
이것을 골라 **내가 설계를 정했다.** 앞서 여러 문서가 「남은 구멍」으로만 적어 두고 있었다
(`actions/approval.md` · `teams/booking-handoff.md` · 위임 리포트 §미해결).

## 무엇이 문제였나

`/ui/*` 에는 로그인이 없었다. 그런데 쓰기 버튼 셋은 **서버가 scope 키를 스스로 만들어** API 를 불렀다.

```python
token = _development_key("action:approve", settings.secret_key)   # routes.py — 승인·바깥함
... _call_api(..., scope="delegation:write")                      # 위임
```

- `/ui` 에 닿기만 하면 **인증 없이 승인·바깥함 해소·위임을 할 수 있었다.**
- 승인자·처리자는 전부 `ui-operator` 로 남아 **누가 눌렀는지 알 수 없었다.**
- 위임은 설정 스위치(`ui_delegation_write_enabled`, 기본 꺼짐)로만 막고 있었다. 승인과 바깥함은 그것도 없었다.

같은 이유로 2026-08-18 에 Composer 화면을 지웠다(D-CS-001). 이번에는 지우지 않고 **앞에 문을 단다** —
승인 화면은 이 제품이 사람을 거치게 하는 자리라 없앨 수 없다.

## 정한 것

| | |
|---|---|
| 계정 | 설정 `ACOP_UI_OPERATORS`(`.env`, git 이 무시). `[{id, password_hash, scopes}]`. 만드는 법 `python -m scripts.ui_operator --id <id>` — 비밀번호는 **직접 입력**(두 번, 12자 이상) |
| 비밀번호 | **원문을 어디에도 두지 않는다.** PBKDF2-SHA256, 600,000회, 소금 16바이트. 반복 횟수가 해시 문자열에 적혀 나중에 올려도 옛 해시가 안 깨진다 |
| ★기본 | **계정이 하나도 없으면 아무도 못 들어온다.** 로그인 화면이 「닫혀 있다」고 말한다 |
| 세션 | 서명 쿠키 `acop_ui` — HMAC-SHA256(`secret_key`) · 만료 8시간 · `HttpOnly` · `SameSite=Strict` · https 면 `Secure` |
| ★권한을 거두면 | **다음 요청부터** 반영된다. 쿠키의 scope 와 지금 설정의 scope 의 **교집합**만 쓰고, 계정이 빠지면 쿠키가 무효다. 쿠키만 믿으면 거둬도 8시간 버틴다 |
| 쓰기 | 승인·바깥함 해소 = `action:approve`, 위임 변경 = `delegation:write`. 없으면 **403 + 사유, 아무것도 안 바뀐다** |
| ★기록 | 승인자·처리자·위임 행위자 = **로그인한 운영자 id.** 위임 폼의 `actor_id` 칸은 믿지 않는다(남의 이름으로 맡길 수 있다) |
| 로그인 실패 | 없는 id 와 틀린 비밀번호를 **같은 문장·같은 시간**으로(어느 id 가 있는지 안 알려 준다). 5회 틀리면 15분 잠금(프로세스 안) |
| `?next=` | **`/ui`·`/ops` 로만** 돌려보낸다. 바깥 주소를 받으면 우리 로그인 화면이 피싱 발판이 된다 |
| 로그아웃 | **POST.** GET 이면 남의 페이지가 끼운 이미지 한 장으로도 로그아웃된다 |
| 수치의 자리 | `config/guardrails.yaml` `security.ui_session_hours` · `ui_login_max_failures` · `ui_login_lock_minutes` (RULE.md §3.1) |

`ui_delegation_write_enabled` 스위치는 **지웠다.** 막아 둔 이유(로그인이 없다)가 사라졌고, 이제 scope 가 막는다.

## 버린 것

| 안 | 왜 버렸나 |
|---|---|
| 운영자가 API 키(Bearer)를 붙여 넣는다 | 키가 scope 하나에 하나라 운영자가 여러 개를 들고 다녀야 하고, **누가 눌렀는지**가 여전히 안 남는다(키에 사람이 없다) |
| 외부 인증(OAuth·SSO) | 붙일 공급자가 정해지지 않았다. 지금 필요한 것은 「아무나 못 누른다」와 「누가 눌렀나」 둘이다 |
| 역방향 프록시의 기본 인증 | 배포 형태가 정해지지 않았고, 앱이 **운영자를 모른 채** 승인자를 남기게 된다 |

## ★이 결정이 **막지 않는 것**

- **`/scenario/*`**(시연 시작·다음·메시지·운영 조회)는 `/ui` 밖이라 이 관문에 안 걸린다. 시나리오 설정 스위치
  뒤에 있고, 켜 두면 인증 없이 시연 테넌트를 만들고 읽는다. `[미해결]`
- **CSRF 토큰은 없다.** `SameSite=Strict` 쿠키에 기대고 있다 — 오래된 브라우저는 그 속성을 모른다.
- **로그인 잠금은 프로세스 안**이다. 앱을 다시 띄우면 풀리고, 앱이 여럿이면 따로 센다.
- 로컬은 http 라 쿠키에 `Secure` 가 안 붙는다. 바깥에 열 때는 https 앞단이 있어야 한다.
- 화면은 scope 를 확인한 **뒤** 여전히 서버 안에서 키를 만들어 API 를 부른다. 같은 프로세스 안 호출이라 두었다.

## 관계

- 실측 — [2026-09-23_운영화면_로그인.md](../records/evidence/2026-09-23_운영화면_로그인.md)
- 앞선 같은 이유의 결정 — [D-CS-001](D-CS-001-composer-ui-removal.md)
- 인증 경계 — [../external/auth-boundary.md](../external/auth-boundary.md)

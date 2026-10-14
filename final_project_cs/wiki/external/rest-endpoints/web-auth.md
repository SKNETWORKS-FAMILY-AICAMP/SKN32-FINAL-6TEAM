---
type: contract
title: 브라우저 인증·키·동의
description: 호출 주체와 책임별 REST 요청·응답 계약
status: draft
domain: travel
---

# 브라우저 인증·키·동의

### 소셜 로그인 — `/v1/web/auth/*` `[2026-10-03]` (구글 먼저)

`[실측]` 구현 `app/domains/travel_ops/modules/web_account/web_auth_api.py`(HTTP) · `web_auth.py`(저장 · 규칙) · `app/infrastructure/oauth_providers.py`(업체와 말하기) · 저장 마이그레이션 043 · 시험 `tests/e2e/test_web_social_login.py`(17) ·
`tests/unit/travel/test_oauth_providers.py`(15). 계약의 출처는 ui 세션의 [백엔드 요청서](../../records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md)이고 웹 화면은 이 모양 그대로 연결돼 있다. 설정 · 콘솔 절차는 [google-login-setup.md](../../operations/google-login-setup.md).
★**소셜 로그인은 「키를 받아 오는 또 하나의 길」이다** — 키와 모든 `/v1/web/*` 인증(`X-User-Key`)은 바뀌지 않는다. 계정을 사용자에 **붙여** 두면 키를 잃어도 · 새 기기에서도 그 계정으로 같은 사용자의 여행을 연다.

| 경로 | 키 | 뜻 |
|---|---|---|
| `GET /v1/web/auth/providers` | 없음 | `{providers: [{id}]}` — **설정이 끝난 업체만**(클라이언트 ID · 비밀값이 둘 다 있어야 한다). 하나도 없으면 **빈 목록**(404 가 아니다) |
| `POST /v1/web/auth/{provider}/start` | `link` 만 필수 | `{mode: login\|link, client_nonce(무작위 32~256자), turnstile_token?}` → `{authorize_url}`. 업체 없음 404 `provider_not_enabled` · nonce 짧음 422 `invalid_client_nonce` · `link` 에 키 없음 401 · **키 없는 `login` 은 사람 확인**(Turnstile — 토큰 없으면 422 `human_check_required`, 틀리면 403, 머리말 `X-Turnstile-Token` 도 받는다 · 비밀키가 없는 개발 환경은 건너뛴다) |
| `GET /v1/web/auth/{provider}/callback?code&state` | — | **브라우저 이동 전용** — 업체가 돌려보내는 곳. 어떤 결과든 **웹으로 302**: `{웹 주소}/auth/done?ticket=…` 또는 `?error=` (`cancelled` 고객이 취소 · `denied` 업체가 거절 · `already_linked_elsewhere` · `failed` 그 밖 전부). 머리말 `Cache-Control: no-store` · `Referrer-Policy: no-referrer` |
| `POST /v1/web/auth/exchange` | 없음 | `{ticket, client_nonce}` → `{outcome: signed_in\|created\|linked, provider, trips, user_key?, notice?}`. `signed_in` · `created` 일 때만 `user_key`(**이 기기용 새 키**). 만료 · 재사용 · nonce 불일치 · 모르는 표는 모두 410 `ticket_invalid`(어느 쪽인지 가르지 않는다) |
| `GET /v1/web/auth/links` | 키 | `{links: [{provider, linked_at}]}` — 계정 이름 · 이메일은 없다 |
| `DELETE /v1/web/auth/{provider}` | 키 | 연결 해제(키와 여행은 그대로) → 200 `{links}`(남은 연결). 안 붙어 있으면 404 `not_linked` |

- **한 바퀴**: `start`(시작 기록 저장) → 업체 로그인 화면 → `callback`(`state` 를 한 번만 꺼내 코드를 고유 번호로 바꾸고 연결 · 일회용 표) → `exchange`(표를 한 번만 받고 키 발급).
- ★**`user_key` 는 「현재 유효한 키」가 아니라 이 기기용 새 키다** `[계약 보정]` — 키 원문은 해시로만 저장돼 다시 돌려줄 수 없다. 옛 키를 거두면(`rotate`) 다른 기기가 끊기므로 키를 **하나 더한다**(`web_session.add_key`). 한 사용자의 유효한 키는 `security.web_auth_keys_per_user`(10)개까지 — 넘으면 가장 오래된 키부터 거둔다.
- **보안**: ①로그인 CSRF 막기 — 표는 시작한 브라우저가 만든 `client_nonce` 의 해시와 같이 저장되고 교환할 때 같은 값이 와야 한다(틀린 시도는 표를 태우지 않는다) ②`state` · PKCE(`S256`) · OIDC `nonce` — `state` 는 서버가 만들고 해시만 저장, 한 번만 · 10분(`security.web_auth_state_seconds`), 표는 60초(`web_auth_ticket_seconds`)
  ③**ID 토큰은 업체 공개키(JWKS)로 서명 · 발급자 · 대상 · 만료 · nonce 를 모두 확인**한다(RS256 만 — 다른 알고리즘 · 서명 없는 토큰 거절) ④돌려보낼 웹 주소는 **서버 설정**(`ACOP_WEB_ORIGIN`, 비면 `ACOP_WEB_ALLOWED_ORIGINS` 의 첫 값 — 없으면 콜백이 503 `web_origin_not_configured`)이고 요청 값(`return_to` 등)으로 바꿀 수 없다
  ⑤저장은 업체 이름과 `sub` 의 **HMAC 해시**(`secret_key` 로)뿐 — 이메일 · 이름 · 사진은 요청도 저장도 안 한다(스코프 `openid`) ⑥한 업체 계정은 **한 사용자에게만** — 다른 사용자에게 있으면 `link` 는 `already_linked_elsewhere`, **합치지 않는다** ⑦`start` · `exchange` 는 주소당 한 시간 `security.web_auth_per_ip_hour`(30)번씩(**늘 켜져 있다**, 429 `too_many_auth` + `Retry-After`) ⑧키 없는 `login` 이 새 사용자를 만들 때는 키 발급과 같은 한도(`too_many_sessions`)를 거친다 — 걸리면 `?error=failed`.
- 계정이 붙은 사용자는 **회원**이라 게스트 정리가 지우지 않는다(시험으로 확인). CORS 는 `DELETE` 를 연다(웹이 다른 출처일 때 연결 해제).
- `[미확보]` ①실제 구글과 이어 본 기록 — 클라이언트 ID · 비밀값이 있어야 한다(없으면 `providers` 가 빈 목록) ②카카오 · 네이버 · 디스코드는 구현하지 않았다(`oauth_providers.configured()` 에 업체 한 줄 + 설정 칸이다 — 카카오 · 네이버가 OIDC `sub` 를 주는 설정이 우리 앱 종류에서 되는지는 확인 전) ③운영 배포 주소 — 콜백 주소 등록에 필요하다.

### 브라우저 세션 쿠키 — `/v1/web/auth/session*` `[결정 2026-10-04 사용자]`

`[실측]` 시험 `tests/e2e/test_web_cookie_session.py`(27) · 결정 기록 [D-CS-011](../../decisions/D-CS-011-browser-session-cookie.md). 구현 `app/domains/travel_ops/modules/web_account/web_cookie.py`(저장 · 규칙) · `web_auth_api.py`(HTTP) · 저장 마이그레이션 044 `web_sessions`.
★**브라우저는 키를 저장소에 두지 않는다.** 로그인 상태는 서버가 내려주는 **HttpOnly 쿠키 하나**다 — 페이지의 스크립트(지도 SDK · 확장 · XSS)가 읽지 못한다. 키(`X-User-Key`)는 **에이전트(MCP)와 옛 호출자용**으로 남는다(웹이 옮겨 가는 동안 둘 다 받는다).
★「로그인하면 다시 인증하면 되니 토큰을 오래 들고 있을 이유가 없다 · 로그인 안 한 게스트는 세션을 잃어도 받아들인다」가 사용자 결정이다 — 복구 수단은 없다.

| 경로 | 인증 | 뜻 |
|---|---|---|
| `POST /v1/web/auth/session` | 쿠키 없음 | 게스트 세션을 만든다 → `201` + `Set-Cookie`. 이미 유효한 쿠키가 있으면 새로 안 만들고 현재 세션을 `200` 으로 돌려준다. **사람 확인(Turnstile)과 주소당 한 시간 발급 한도는 `POST /v1/web/session` 과 같다**(`human_check_required` 422 · `too_many_sessions` 429) |
| `POST /v1/web/auth/adopt` | `X-User-Key` 만(쿠키 없음) | 옛 키 사용자를 **쿠키 세션으로 옮긴다** → `201` + `Set-Cookie`. 키는 거두지 않는다(에이전트가 쓸 수 있다). 웹은 성공하면 저장소의 키를 지운다. 틀린 키 `401` · 주소당 한 시간 한도(`too_many_auth`) |
| `GET /v1/web/auth/me` | 쿠키 | 현재 세션 — `{kind: guest\|member, csrf_token, idle_expires_at, absolute_expires_at, guest_idle_hours?}`. `guest_idle_hours` 는 게스트일 때만(화면이 「이 기기에서 N시간 안 쓰면 사라져요」를 보이게). 쿠키가 없거나 만료면 `401 unauthenticated` |
| `POST /v1/web/auth/logout` | 쿠키 + CSRF | 서버의 세션 행을 거두고 쿠키를 지운다 → `200 {status: "signed_out"}`. 게스트가 로그아웃하면 그 여행은 다시 열 수 없다(보존 시간이 지나면 지워진다) |
| `POST /v1/web/auth/exchange` **(확장)** | 없음 | 몸통에 `session: "cookie"` 를 더하면 `signed_in` · `created` 일 때 **키 대신 쿠키 세션**을 준다(`Set-Cookie`, 응답에 `user_key` 없음, `kind: "member"` · `csrf_token` 가 실린다). 요청에 게스트 쿠키가 함께 오면 그 세션은 **거두고** 새로 발급한다(세션 고정 공격 방지). 몸통에 없거나 `"key"` 면 지금까지처럼 `user_key` 를 준다 |

**쿠키.** 값은 무작위 256비트(서버에는 SHA-256 해시만). 운영(공개 주소가 `https`) = 이름 `__Host-tripilot_sid` · `Secure` · `HttpOnly` · `SameSite=Lax` · `Path=/` · **`Domain` 없음**. 개발(`http`) = 이름 `tripilot_sid_dev` · `Secure` 없음 — 나머지 같다(`__Host-` 는 `Secure` 가 있어야 한다). `Max-Age` = 절대 수명 — ★`[2026-10-04 사용자 결정]` **게스트 쿠키에는 `Max-Age` 가 없다**(브라우저 세션 쿠키 — 브라우저를 닫으면 브라우저가 지운다. ChatGPT 로그아웃 상태와 같은 모양). 회원 쿠키만 `Max-Age`(절대 수명)가 있다. 게스트가 구글 계정을 `link` 하면 `exchange`(`session:"cookie"`) 응답이 **같은 쿠키 값을 `Max-Age` 와 함께 다시** 내리고 몸통은 `kind: member`. 이름·`Secure` 여부는 `ACOP_PUBLIC_BASE_URL` 이 정한다.
`SameSite=Lax` 인 까닭: 구글 로그인에서 돌아오는 첫 이동에 `Strict` 쿠키가 안 붙는다(제안 — 조사 합의).

**누구인지 가르는 순서**(`/v1/web/*` 전부 — 한 곳에서). ① 쿠키와 `X-User-Key` 가 **같이 오면 `400 ambiguous_credentials`**(조용히 고르지 않는다) ② 쿠키만 → 세션 행을 찾아 **유휴·절대 수명**을 확인(만료·거둠·없음은 모두 `401 unauthenticated` + 쿠키 삭제 `Set-Cookie`) ③ 키만 → 지금까지처럼(CSRF 면제 — 브라우저가 자동으로 붙이지 않는다) ④ 둘 다 없으면 `401`.
**수명**(운영 API 로 바꾼다 — 아래 이름): 유휴 = 마지막 사용 뒤 — 게스트 `web.guest_idle_hours`, 회원(소셜 계정을 붙인 사용자) `web.member_idle_hours`; 절대 = 만든 뒤 `web.session_max_hours`. 만료 판단은 **쓸 때** 한다(바꾼 값이 곧 적용 · 30초 캐시). 「마지막 사용」은 세션이 인증한 요청이다 — **계획서 링크 열람 · 자동 감시 · 외부 호출은 사용으로 세지 않는다.** 마지막 사용은 `web.session_touch_seconds`(기본 60초)보다 잦게 쓰지 않는다.

**CSRF**(쿠키로 인증된 **쓰기** 요청 `POST·PUT·PATCH·DELETE` 만 — 읽기는 면제). 둘 다 통과해야 한다: ①`Origin` 이 허용 출처(`ACOP_WEB_ALLOWED_ORIGINS` · `ACOP_WEB_ORIGIN`)여야 한다 — 없으면 `Sec-Fetch-Site` 가 `same-origin`/`same-site` 여야 한다 ②헤더 `X-CSRF-Token` 이 그 세션의 토큰과 같아야 한다(`HMAC-SHA256(서버 비밀, "csrf|" + 세션 해시)` — 저장하지 않고 다시 계산, 상수 시간 비교). 토큰은 `session`·`adopt`·`me`·`exchange` 응답에 실린다(웹은 **메모리에만** 둔다). 어긋나면 `403 csrf_failed`. `GET` 으로는 상태를 바꾸지 않는다.
**CORS.** `allow_credentials=true` — 출처는 허용 목록 그대로(와일드카드 불가), 허용 머리말에 `X-CSRF-Token` 을 더한다. 웹은 모든 호출에 `credentials: "include"` 를 붙인다(개발의 `127.0.0.1:3100 ↔ :8042` 는 **출처는 다르지만 같은 사이트**라 쿠키가 간다 — `localhost` 와 `127.0.0.1` 을 섞지 않는다).

- 세션의 종류(`kind`)는 **쓸 때 계산한다**: 소셜 계정이 하나라도 붙어 있으면 `member`, 아니면 `guest` — 게스트가 소셜 계정을 `link` 하면 같은 세션이 다음 요청부터 회원 수명을 받는다(여행도 그대로).
- 소셜 `link` 시작 · `GET /v1/web/auth/links` · `DELETE /v1/web/auth/{provider}` 도 쿠키로 열린다(CSRF 규칙 그대로).
- ★한계: HttpOnly 는 **자격을 읽히지 않게** 할 뿐, 페이지에 악성 스크립트가 있으면 그 스크립트가 사용자 대신 요청을 보내는 것(세션 라이딩)은 막지 못한다. 훔친 쿠키를 다른 기기에서 쓰는 것도 만료·거둠까지는 막지 못한다 — Chrome 의 기기 묶음 세션(DBSC)은 그 위에 나중에 얹는 보강이다(`[미확보]` Safari·Firefox 미지원, 2026-10-04 조사).

### 게스트(로그인 안 한 사용자) · 여행 삭제 · 게스트 정리 `[결정 2026-10-04 사용자]`

`[실측]` 구현 `app/domains/travel_ops/modules/web_account/guest_policy.py`(제한) · `trip_delete.py`(삭제) · `guest_cleanup.py`(정리) · `itinerary.py`(감시 · 안내 대상에서 게스트 제외) · 시험 `tests/e2e/test_guest_and_trip_delete.py`(16). 결정 [D-CS-011](../../decisions/D-CS-011-browser-session-cookie.md) — **보존 시간 초기값의 공식과 근거도 거기 있다.**
★**게스트 = 웹으로 만든 사용자(`customers.external_id` 가 `web:` 로 시작) 중 소셜 계정이 하나도 안 붙은 사용자.** 소셜 계정을 `link` 하면 그 순간부터 회원이다(여행도 그대로). 에이전트 API 로 만든 고객과 시드는 게스트가 아니다.

| | 게스트 | 회원 |
|---|---|---|
| 여행 | **1개**(`web_guard.guest.max_trips`) — 사용자 행을 잠가 **동시 생성까지** 막는다. 넘으면 `403 guest_trip_limit` + 본문 `login_required: true` · `cap` · `existing` | 제한 없음 |
| 여행 기간 | 시작은 오늘부터 **365일 안**(`403 guest_trip_too_far`), 길이는 **7일 안**(`403 guest_trip_too_long`) | 제한 없음 |
| 감시 · 일정 안내 | **안 한다**(`active_trip_ids` · `due` 에서 뺀다 — 외부 호출 비용) | 한다 |
| 세션 유휴 수명 | `web.guest_idle_hours`(기본 **168시간**) | `web.member_idle_hours`(기본 168시간) |
| 마지막 사용 뒤 데이터 | 아래 「게스트 정리」로 지운다 | 안 지운다 |
| 에이전트 키 | 없다(2단계 — 로그인 사용자만) | 있다(2단계) |

`403 guest_*` 는 모두 본문 `{"error": {"code", "message", "login_required": true, …}}` 이다 — 화면이 「로그인하면 더 만들 수 있어요」를 보인다.

**`POST /v1/web/trips/{trip_id}/delete`** — 쿠키 세션 또는 키(웹 쓰기는 CSRF). 몸통 없음.
```
200 {"trip_id": "...", "status": "deleted"}
404 {"error": {"code": "not_found", "message": "resource not found"}}   ← 남의 여행 · 없는 여행 · 이미 지운 여행(있는지도 말하지 않는다 · 두 번째 호출도 404)
401 unauthenticated · 403 csrf_failed
```
- **즉시 완전 삭제**(숨김 · 유예 없음). **한 트랜잭션**이고 `trips` 행을 잠근다. `trips` 를 지우면 `itinerary_versions` · `itinerary_items` · `pending_changes` 가 CASCADE 로 사라진다.
- **외래키가 없어 이름을 대어 지우는 표**: `trip_chat_turns` · `place_open_checks` · `dining.dn_notice` · `trip_intakes`(그 여행 것만, 자식 `intake_*` 는 CASCADE) · `places.trip_scope`(이 여행 전용 장소 행 — 외부 값이라 다른 고객에게 재사용하면 안 된다) · 바깥함 `trip.notice`(`dedupe_key` 가 `{trip_id}:` 로 시작 — 알림 문장에 일정이 실려 있어 **대기분만이 아니라 전부**). `trip_id` 가 NULL 인 옛 행은 고객 번호만으로 지우지 않는다. 새 표가 여행 번호 칸을 들고 생기면 걸리는 목록 시험이 있다.
- **운영 쪽은 지우지도 가리지도 않는다**: `case_events` 는 append-only. 그 여행을 가리키는 **열린 Case**(`state_json.subject_ref.id`)는 전이표가 허용하는 **정상 전이만으로 `cancelled` 까지 닫는다**(가장 짧은 길 · 이유 `trip_deleted` · 행위자 `trip_delete`) — ★`resolved`/`completed` 를 거치지 않는다(안 한 일을 끝냈다고 기록하게 된다): `running` → `guardrail_escalated` → `escalated` → `cancelled_by_user`. 해결된 Case 는 기록이라 그대로다.
- ★`[2026-10-04 사용자 결정]` **계획서 내려받기** — `GET /plan/{trip_id}?t=…&download=1` 은 같은 페이지를 `Content-Disposition: attachment`(파일 이름 `triPilot-<제목>.html`, 경로 글자 제외)로 준다. 로그인 없음 · 링크가 곧 자격 · 틀린 토큰은 404. 이 HTML 은 외부 파일 없이 혼자 열린다(밖으로 나가는 것은 지도 링크뿐). 게스트 데이터는 보존 시간 뒤 지워지니 **파일로 가져가게 하는 것**이 게스트의 보관 수단이다.
- 계획서 링크는 토큰 행이 없어(HMAC) 여행이 사라지면 조회에서 404 다. ★`[미구현]` **「만료됨」 안내 화면**(삭제된 여행의 유효한 옛 링크에만, 틀린 링크는 404)은 만들지 않았다 — 지금은 404 다. 흔적 한 줄을 남겨야 해서 따로 정한다([open-items](../../../../wiki/delivery/open-items.md)).
- ★`[미구현]` ①MCP 삭제 도구(`travel.mcp.write_enabled` 뒤) ②바깥함이 **보내기 직전**에 여행이 아직 있는지 다시 보는 것(삭제와 겹친 알림이 이미 밖으로 나가는 경우는 회수되지 않는다) — 요청서 구현 지침 4 · 7. ③`case_events.payload_json` 에 마스킹 안 된 고객 문장이 없는지 DB 에서 세어 보는 것(지침 8).

**게스트 정리** — 되잡기 작업(`python -m scripts.run_sweepers --only web_guard`)이 한다. 옛 「빈 키 정리」(`idle_key_*`, 2026-09-28 · 여행 0건인 키만 · 기본 꺼짐)를 **이것이 대신한다**(설정 `web.idle_key_days` · `web.idle_key_cleanup_enabled` 는 걷었다).
- 대상: 게스트. 「마지막 사용」 = 사용자 행 생성 · 키의 발급/사용 · 세션의 마지막 사용 중 **가장 늦은 때**(계획서 링크 열람 · 자동 감시 · 외부 호출은 사용이 아니다).
- 지우는 때: 마지막 사용 + `web.guest_idle_hours` 뒤. **일정이 남은 게스트**는 `min(마지막 일정 종료, 마지막 사용 + web_guard.guest.trip_keep_max_days(180일)) + web_guard.guest.trip_grace_days(3일)` 까지 둔다 — 세션은 끝났어도 계획서 링크와 알림이 그때까지 산다. 상한이 「지금」이 아니라 「마지막 사용」 기준이라 날짜를 빌미로 영구히 남지 않는다. 일정 종료가 비면 시작 시각을 종료로 본다.
- 사용자마다 따로 한 트랜잭션: 여행(위 삭제와 **같은 함수**) · 접수 · 세션 · 키 · 사용자 행(프로필은 CASCADE). 사용자 행을 가리키는 외래키 14개 중 13개가 「가리키면 거부」(서버 DB 조회 2026-10-04) — **Case 같은 기록이 가리키면 사용자 행 한 줄만 남긴다**(이메일 · 이름 없는 무작위 `web:` 번호). 결과 `{candidates, held_for_trips, customers_deleted, customers_kept, trips_deleted}`.
- 꺼져 있으면(`web.guest_cleanup_enabled`) `{"skipped": "disabled"}` — 아무것도 안 지운다. **복구 수단이 없어 삭제 전 유예(소프트 삭제)도 없다.**
- **관리 콘솔에서 조절**(운영 API `/admin/limits` — 위): `web.guest_idle_hours` · `web.member_idle_hours` · `web.session_max_hours`(시간, 1~8760) · `web.guest_cleanup_enabled`. 바꾼 값은 30초 안에 적용된다(세션 수명은 쓸 때 계산해 이미 만든 세션에도 곧 적용).

### 에이전트 키 — `/v1/web/agent-keys*` `[결정 2026-10-04 사용자 — D-CS-012]`

`[실측]` 시험 `tests/e2e/test_web_agent_keys.py`(12) · 결정 기록 [D-CS-012](../../decisions/D-CS-012-agent-auth-claude-style.md) · 구현 `app/domains/travel_ops/modules/web_account/web_agent_keys.py`(저장 · 규칙) · `web_agent_keys_api.py`(HTTP) · 저장 마이그레이션 045 `web_agent_keys`. 개인 AI(MCP · 사용자 API)가 **본인 여행의 작업만** 하는 문이다. 쿠키는 브라우저 전용이라 에이전트는 키를 헤더로 보낸다.
★**만드는 것은 로그인한 사용자(회원)가 브라우저(쿠키 세션)에서만** 한다 — 에이전트 키 · 옛 사용자 키로는 못 만들고(`403 cookie_required`), 게스트는 못 만든다(`403 member_only` + `login_required: true`).

| 경로 | 인증 | 뜻 |
|---|---|---|
| `GET /v1/web/agent-keys` | 쿠키(회원) | `{keys: [{key_id, name, scope, created_at, expires_at, last_used_at, status}]}` — `status` = `active` · `expired` · `revoked`. 키 원문은 없다 |
| `POST /v1/web/agent-keys` | 쿠키(회원) + CSRF | 몸통 `{name(1~60자), scope: "read"\|"write", expires_days?(1~90, 기본 90)}` → `201 {key_id, name, scope, created_at, expires_at, key, notice}`. ★`key`(`acop_a_…`)는 **이 응답에만** 나온다(서버엔 SHA-256 해시만). 활성 키가 `security.web_agent_keys_per_user`(10)개면 `409 agent_key_limit` |
| `DELETE /v1/web/agent-keys/{key_id}` | 쿠키(회원) + CSRF | 폐기 → `200 {key_id, status: "revoked"}`. 남의 키 · 없는 키는 같은 `404 not_found` |

**키를 쓰는 법**: 머리말 `Authorization: Bearer acop_a_…` 또는 `X-User-Key: acop_a_…`(MCP `/mcp/` 도 같다 — URL 에 키를 넣지 않는다). 없는 키 · **만료** · 폐기는 모두 같은 `401 unauthenticated`. 쿠키와 같이 오면 `400 ambiguous_credentials`. 서버용 scope 키(`require_scope`)를 `Bearer` 로 보내도 웹 경로는 안 열린다(`401`).
**권한**: ①`read` 키는 읽기(`GET`)만 — 쓰기 요청은 `403 agent_scope` ②어느 키든 **계정 관리 경로는 못 연다** — `/v1/web/auth/*` · `/v1/web/session*` · `/v1/web/profile*` · `/v1/web/agent-keys*` → `403 agent_forbidden` ③`write` 키의 쓰기 도구(MCP)는 `travel.mcp.write_enabled` 스위치가 켜져 있을 때만 등록된다(기본 꺼짐) ④마지막 소셜 연결을 해제하면 그 사용자의 에이전트 키를 **모두 거둔다**.
- 옛 사용자 키(`acop_u_…`, 만료 없음)는 그대로 둔다(웹이 쿠키로 옮겨 가는 동안) — 에이전트용으로는 새 키를 쓰게 안내한다.
- 2단계 OAuth(`/.well-known/*` · `/oauth/*`)는 [D-CS-012](../../decisions/D-CS-012-agent-auth-claude-style.md) 에 설계만 있다 — 에이전트 키와 같은 검증 · 권한 판정으로 합칠 예정.

### 약관 동의 기록 · 사용 조건 — `/v1/web/consents` `[2026-10-05 사용자 지시 — ui 세션 요청서]`

- **항목 여섯**: 필수 `service_terms`(서비스 이용약관) · `privacy`(개인정보 수집·이용) / 선택 `sensitive`(민감정보 — 종교 · 식사 제한) · `location`(개인위치정보) · `alert_channel`(알림 채널 정보 — 디스코드 웹훅 · 텔레그램 대화) · `service_improvement`(서비스 개선용 정보 이용). 기본 약관 버전은 `2026-10-10.1`이고 운영자가 보유기간을 바꿨다면 `+ret{N}`이 붙는다. 버전이 오르면 필수가 `ok:false` 로 돌아가 **다시 동의**해야 한다. 선택 항목은 앱을 막지 않는다. 개선 항목은 기본 false이며 이전 동의로 대신하지 않는다.
- `GET /v1/web/consents` → `{current_version, required: ["service_terms","privacy"], items: [{code, agreed, version, agreed_at}…여섯], ok}` — `ok` = 필수가 모두 **지금 버전으로** 동의됨. 기록이 없는 항목은 `agreed:false`.
- `[2026-10-08 사용자 지시]` 같은 GET에 `Accept: text/event-stream`을 붙이면 동의 확인 진행을 SSE로 보낸다. 인증은 스트림 시작 전에 검사하며 새 사용자를 만들지 않는다. `accepted` → `stage(consent_records)`(DB 동의 기록 조회) → `stage(consent_version)`(현재 약관 버전 조회) → `stage(consent_required)`(필수 항목 확인) → `result`(기존 JSON과 같은 본문). 오래 기다릴 때는 기존 실시간 진행 규칙의 `beat`·시간 초과·열린 연결 상한을 적용한다. 오류는 `error`로 끝내고, JSON 요청은 기존 응답을 유지한다. 웹은 최신 약관 읽기·세션 확인·브라우저 사본 맞춤까지 실제 완료한 단계만 세며, 기존 화면 위 작은 진행 카드로 보여 준다.

- `POST /v1/web/consents` 본문 `{version, items: [{code, agreed, text_sha256}]}` — **보낸 항목만 바꾼다.** `text_sha256` = 동의할 때 화면에 보여 준 약관 전문의 sha256(소문자 16진수 64자 — 증빙으로 저장). 오류: 버전이 지금과 다르면 409 `terms_version_changed`(응답에 `current_version`) · 모르는 코드 422 `unknown_code` · 해시 모양 422 `invalid_text_sha256` · 그 밖의 모양 422 `invalid_items` — **하나라도 틀리면 하나도 기록하지 않는다.** 바뀐 것이 없는 항목은 줄을 더하지 않는다. 필수 항목을 `agreed:false` 로 보내면 기록하고 `ok:false`.
- **세션이 있으면 된다**(게스트 · 회원 · 옛 키) — 쿠키로 쓰면 CSRF 까지 본다. **에이전트 키로는 못 한다**(`403 agent_forbidden` — 동의는 사람이 브라우저에서 한다).
- **기록은 추가만 한다**(`consent_events` · 마이그레이션 046): `tenant_id · user_id · session_kind(guest|member|key) · code · agreed · terms_version · text_sha256 · at · ip_hash · user_agent`. 철회도 새 줄. **DB 트리거가 UPDATE 를 늘 거절하고 DELETE 는 보관 기간 정리만 허용한다.** 현재 상태는 사용자 · 코드별 가장 최근 줄(`consent_current` 뷰). 주소는 원문이 아니라 서버 비밀로 만든 해시(`ip_hash`)뿐 · 사용자 행에는 외래키를 걸지 않는다(게스트가 정리돼도 증빙이 남는다). 보관 `consent.evidence_retention_days`(기본 1,825일 = 5년 — ui 세션 추천값, 법무 확인 전) 뒤 상시 정리 작업(`run_sweepers` 의 웹 방어 단계)이 지운다.
- **사용 조건(게이트)**: 설정 `consent.gate_enabled`(**기본 꺼짐** — 웹이 동의 화면을 내보낸 뒤에 켠다. 켜기 전에는 아무것도 안 바뀐다). 켜면 필수 동의가 **지금 버전으로** 없는 사용자의 호출은 `403 {"error": {"code": "consent_required", "message": "약관에 동의해야 쓸 수 있어요", "current_version", "required"}}` — 게스트 · 회원 · 옛 키 · 에이전트 키(**키 주인의 동의**를 따른다 — 주인이 철회하면 키도 막히고 다시 동의하면 풀린다) 모두. MCP 도구는 같은 REST 를 부르므로 같은 규칙을 탄다. **면제**: `/v1/web/consents` · `/v1/web/auth/*`(소셜 로그인 · 세션 만들기) · `/v1/web/session` · 건강 확인 · 공개 여행계획서 링크 · 메신저 웹훅(이들은 사용자 인증을 거치지 않아 게이트에 닿지 않는다).
- **철회 효과**(동의 기록과 **한 트랜잭션** — 기록만 남고 삭제가 안 되거나 그 반대가 되지 않는다): `alert_channel` → 저장한 디스코드 웹훅 삭제 · `sensitive` → 여행의 식사 제한(`trips.constraints.dietary`)과 설문 음식 답(`survey.priority_details.food`) 삭제(다른 칸은 그대로) · `location` → 위치 점 삭제(위치 수집 구현이 `consents.PURGERS["location"]` 에 등록 — 아직 없다). `[미확인]` 설문 답이 다른 복사본(일정 버전 스냅샷 · 접수 원문)에도 남는지는 확인하지 않았다.
- **아직 없는 것**: 위치 받기 `POST·DELETE /v1/web/trips/{id}/location` · 멈춘 지점 `GET …/location/stops`(같은 요청서의 2·3부) · 텔레그램 연결 삭제 효과. 약관 전문의 법적 검토는 **변호사 검토 전**(약관 초안은 웹 쪽 작업).

- `[2026-10-10 로컬 구현]` 개선 자료 추출은 일반 게이트가 꺼져 있어도 **필수 둘과 개선 항목 모두의 현재 버전 동의**를 검사한다. 필수 또는 개선 동의 철회 시 같은 tenant의 검토 대기 합성 후보를 동의 기록과 한 트랜잭션에서 폐기한다. 원본 보유기간은 늘리지 않는다. 승인 전 내보내기 차단·누적 생성 예산·검토 기한 등은 [서비스 개선 자료 처리](../../operations/service-improvement.md)가 정본이다. 배포·실제 이용자 합성·실제 심의 완료를 뜻하지 않는다.

### 약관의 보관 기간 · 파기 — `/v1/web/legal/retention` · `/admin/retention` `[2026-10-07 사용자 결정 — uiux 전달]`

`[실측]` 약관 화면의 「보관 기간 확정 전」 안내를 빼려고 **보관 기간 다섯 칸을 확정하고 서버가 그 약속대로 지우게** 했다. 값은 사용자가 2026-10-07 에 확정한 추천값이다(**변호사 검토는 아니다**).

| 칸(`key`) | 약관 문장(한국어) | 값 | 서버가 지키는 곳 |
|---|---|---|---|
| `member_idle_days` | 회원이 지우거나 탈퇴를 요청할 때까지, 마지막 이용 후 1년이 지나면 파기 | 365일(30~3650) | `member_cleanup`(아래) |
| `case_follows_trip` | 여행 · 게스트 자료가 지워질 때 함께 파기 | 고정 문장(스위치 `retention.case_follows_trip`) | `trip_delete.purge_cases` · 회원 · 게스트 정리 |
| `consent_days` | 기록한 때부터 5년 | 1825일(365~3650) | 이미 있던 `consents.purge_expired`(매분 도는 `web_guard` 안) — 이 값을 읽도록 바꿨다 |
| `location_points_days` | 여행 종료 후 7일 | 7일(1~365) | **지울 대상이 아직 없다**(서버에 위치 저장 기능이 없음 — 값만 약관에 쓴다) |
| `location_proof_months` | 기록한 때부터 6개월 | 6개월(1~60) | 위와 같다 |

- **`GET /v1/web/legal/retention`**(공개 · 키 없음 · 개인 정보 없음) → `{revision, terms_version, cells:[{key, label_ko, label_en, value, unit(days|months|null), default, editable, text_ko, text_en, min?, max?}]}`. 문장은 **값에서 만들어** 값과 따로 놀지 않는다(1년 · 5년 · 7일 · 6개월 · 영어 `1 year` …). 웹은 이 문장을 읽어 약관에 끼운다.
- **`GET /admin/retention`**(운영 앱 · `limits:read`) → 위 내용 + `history[]`(`{revision, changed:{칸:[이전,새]}, actor, key_id, reason, at}`) + `purge:{mode, runs[]}`(정리 모드와 최근 정리 기록의 건수).
  **`PATCH /admin/retention`**(`limits:write`) `{expected_revision, actor, reason, changes:{칸: 숫자|null}}` — `null` = 기본값으로. 운영자 · 이유가 비면 422 `actor_required`/`reason_required` · 모르는 칸 · 고정 칸 422 `unknown_cell` · 숫자가 아니면 422 · 범위 밖 422 `out_of_range` · 옛 판 409 `stale_revision`. **기본값과 같아지는 값은 「바꿈」이 아니다**(판 · 이력 불변). 감사: 누가(`actor` + 부른 키 `key_id`) · 언제 · 왜 · 이전 → 새 값, 덧붙이기만(056 `legal_retention_history`).
- ★**약관 버전**: 값이 **실제로 바뀌면** `revision` 이 +1 되고 약관 버전이 `기본 버전+ret{revision}`(예 `2026-10-07.1+ret1`)이 된다 — 같은 버전 이름으로 다른 글에 동의했다는 기록이 생기지 않게. 옛 버전으로 동의를 보내면 409 `terms_version_changed`(현재 버전을 싣는다) — **웹은 상수가 아니라 `GET /v1/web/legal/retention` 의 `terms_version`(또는 `GET /v1/web/consents` 의 `current_version`)을 읽어 보낸다.** 기본 버전은 `config/guardrails.yaml` `consent.terms_version`(이번에 `2026-10-07.1`)이고 웹 상수와 **같은 푸시**에 올린다. 값을 되돌려도 글이 한 번 바뀐 적이 있으므로 버전은 계속 오른다.
- **회원 자료 정리**(`modules/web_account/member_cleanup.py` · 실행 `scripts/run_sweepers.py --only retention`, 평소엔 `web_guard` 안에서 **하루 한 번**): 대상 = 소셜 계정이 붙은 웹 사용자 중 마지막 이용 후 `member_idle_days` 가 지난 사람. **「마지막 이용」 = 사용자 행 생성 · 소셜 연결 · 키의 발급/사용 · 세션의 마지막 사용 · 에이전트 키의 발급/사용 중 가장 늦은 때**(계획서 링크 열람 · 자동 감시 · 외부 호출은 이용이 아니다 — 약관에 이 한 문장을 쓰면 된다). 지우는 것: 여행(일정 · 대화 · 접수 · 알림 · 전용 장소 · 그 여행의 처리 기록) · 여행이 안 된 접수 · 활동 기록 · 장소 별칭 · 프로필(웹훅 · 복구 이메일 · 텔레그램) · 소셜 연결 · 세션 · 키 · 에이전트 키 · 남은 처리 기록 · 사용자 행. **동의 기록은 지우지 않는다**(증빙 — 자기 보관 기간). 에이전트 API 고객 · 시드 · 게스트(게스트 정리 몫)는 안 건드린다.
  ★**모드**(`retention.purge_mode`, 관리 화면 `/admin/limits` 의 한 칸 — 같은 감사 기록): `off` · **`dry_run`(기본 — 대상을 세기만 하고 `retention_runs` 에 표별 건수를 남긴다, 아무것도 안 지운다)** · `on`. **`on` 은 사용자가 dry_run 의 건수를 보고 승인한 뒤에만 켠다.** 한 번에 `retention.purge_batch`(100)명.
- **처리 기록(Case) 파기**: 전에는 여행을 지워도 처리 기록이 남았다. 이제 여행 삭제 · 게스트 정리 · 회원 정리가 그 자료의 Case 와 딸린 줄(`case_events` · `action_requests` · `agent_runs`)을 **지운다**(`trip_delete.purge_cases` — `case_events` 를 지우는 유일한 곳, append-only 는 DB 가 지킨다(마이그레이션 904) — 이 파기만 그 트랜잭션에서 `app.case_events_purge` 로 문을 연다). 열린 Case 는 먼저 정상 전이로 `cancelled` 까지 닫는다. `retention.case_follows_trip: false` 면 옛 동작.
- **게스트 정리의 변화**: Case 가 사용자 행을 붙들어 사용자 행 · 프로필(웹훅 · 복구 이메일)이 남던 것을 고쳤다. 다른 기록(옛 쇼핑몰 표 등)이 가리켜 행이 남는 경우에도 프로필 · 연결 · 키는 먼저 지운다.
- ★**아직 안 한 것**: ①접수 원문 `intake_sources.keep_until`(30일)과 `security.retention_days`(90)는 여전히 읽는 코드가 없다 — 회원 · 게스트의 접수는 사용자 정리 때 같이 지워지지만 **회원이 살아 있는 동안의 오래된 접수**는 안 지운다(약관 문장이 약속하는 범위 밖이라 두었다) ②위치 점 · 위치 확인자료 파기(위치 저장 기능이 생길 때) ③회원 탈퇴 기능(없음 — 문의로만) ④x600 서버의 cs 프로젝트 서버에서 정리가 도는지 · 백업에 지운 자료가 남는지는 확인하지 못했다.
- 시험 `tests/e2e/test_legal_retention.py`(22) · `tests/e2e/test_guest_and_trip_delete.py`(처리 기록 파기 · 게스트 프로필) · `tests/e2e/test_consents.py`.


## 관계

- [REST 안내](index.md) — 계약 지도

---
type: plan
title: 사용자 표시 이름 — 변경 계획(담당자 확인 요청)
description: 게스트 · 회원 모두에게 겹치지 않는 표시 이름을 자동으로 주고, 운영 앱은 이름으로 사용자를 보이며, 토큰은 인증에만 쓰도록 서버 · 웹 · 운영 앱을 바꾸는 계획
status: draft
tags: [api, ui, customer-operations]
domain: travel
---

# 사용자 표시 이름 — 변경 계획 (담당자 확인 요청)

- 작성: 2026-10-16 · Choi-Sangwook(UI · 검증)
- 받는 분: `web_account` 담당. `modules/web_account` 30커밋 중 28, `admin_snapshot.py` · `customer/profile.py` · `043_web_social_auth.sql` 작성자.
- **상태: 계획 — 담당자 확인 전, 작업 시작 안 함.** 확인을 받은 뒤 서버 변경도 작성자가 직접 하고, 끝나면 이 문서에 결과를 적는다.
- 기준 판: `role-eval-ui` = `role-manager` `2bee4df6`

## 1. 왜 바꾸나

- 운영 앱이 사용자를 내부 ID(`customer_id`, UUID)로만 보여서, 운영자가 「누가 누구인지」 알아볼 수 없다.
  - 문의 · 예약 승인 · 위임 · 사용자 화면이 모두 `userId`로 표시된다(`frontend/apps/admin/src/features/workflows/screens.tsx:86,115,207,208`).
  - 데이터는 `admin_snapshot.py:28-35`가 만든다.
  - 이 값은 비밀 토큰(사용자 키)이 아니라 보안 문제는 아니다. 사람이 읽을 수 없는 것이 문제다.
- 웹의 프로필 이름 줄은 서버가 닉네임을 주지 않아 「로그인한 사용자」 · 「게스트」로만 나온다(`frontend/apps/web/src/lib/profile.ts:37-40`).
- 닉네임 저장 API가 없어 프로필 수정 화면의 저장은 꺼져 있다(`frontend/apps/web/src/features/profile/profile.tsx:275-287`).

## 2. 지금 상태 (코드로 확인한 사실)

| 항목 | 지금 | 근거 |
|---|---|---|
| 사용자 표 | `customers` 칸은 `customer_id` · `tenant_id` · `external_id` · `email_hash` · `created_at`. **이름 칸 없음** | 마이그레이션의 `CREATE TABLE IF NOT EXISTS customers` |
| 사용자 행을 만드는 곳(서비스 코드) | `web_session.new_customer()` 한 곳. 게스트 키 발급(`issue`)과 소셜 로그인의 새 사용자가 모두 이 함수를 거친다 | `modules/web_account/web_session.py:31-36,57-59` |
| 사용자 행을 만드는 곳(스크립트) | `seed_travel.py` · `replay_scenario.py` · `try_case.py` · `measure_delegation_scope.py` · `measure_notice_phrases.py` | `INSERT INTO customers` 검색 |
| 인증 | 사용자 키(`acop_u_…`, 해시만 저장) · 세션 쿠키. 이름과 무관 | `web_session.py:20-61` · `web_cookie.py` |
| 소셜 로그인 | 업체 고유 번호(`sub`)의 HMAC 해시만 둔다. **이메일 · 이름 · 사진은 요청하지도 저장하지도 않는다** | `043_web_social_auth.sql` 머리 주석 |
| 프로필 API | `GET /v1/web/profile` · `PUT /v1/web/profile`(부분 갱신 — 칸이 없으면 안 건드림, 모르는 칸은 422). 응답에 닉네임 없음 | `entry/trip_api.py:2264-2304` · `components/customer/profile.py:166-171` |

## 3. 정한 것 (2026-10-16 사용자 결정)

1. **모든 사용자(게스트 · 회원)에게 겹치지 않는 표시 이름을 자동으로 준다.** 모양은 「단어 + 숫자」다. 예: 「느긋한 참새 27」 · 「산책하는 비둘기 104」. 단어는 구구루트(새 이름 후보)의 느낌에 맞춘다.
2. **토큰은 인증 수단으로만 쓴다**(지금과 같다). 이름은 인증 · 권한 판단에 쓰지 않는다. 이름은 바뀔 수 있어서 기록 · 추적은 계속 `customer_id`로 한다.
3. **회원도 자동 이름을 받는다.** 로그인이 끝나면 프로필 수정 화면으로 보내 이름을 바꾸게 한다.
   - 이메일 · 구글 이름은 받지 않는다. `043`의 「개인정보 최소」 원칙을 그대로 지킨다.
4. **운영 앱은 사용자를 이름만으로 보인다.** ID는 사용자 상세 화면에만 둔다.

## 4. 서버 — 바꾸거나 더할 것 (작업: 작성자 · 담당자 확인 뒤)

| # | 할 일 | 제안 | 확인 부탁 |
|---|---|---|---|
| S1 | 이름 칸 | `customers.display_name text`(NULL 허용) 추가 + `(tenant_id, lower(display_name))` 고유 인덱스(NULL 제외). 번호는 `migration-plan.json` 규칙대로 | 칸을 `customers`에 둘지 `customer_profiles`에 둘지 — 제안은 `customers`(고유 인덱스 · 운영 조회가 쉬움) |
| S2 | 자동 이름 | `new_customer()`가 행을 만들 때 이름도 넣는다. 형용사 목록 × 새/동물 목록 + 1~999. 고유 인덱스에 걸리면 다시 뽑는다(몇 번 뒤에는 숫자 자리를 늘림) | 단어 목록을 코드에 둘지 설정에 둘지 |
| S3 | 기존 사용자 채우기 | 이름 없는 행에 한 번 채운다(마이그레이션 또는 한 번 돌리는 스크립트). 스크립트가 만든 행도 이것으로 채운다 | 마이그레이션 안에서 할지 따로 할지 |
| S4 | 프로필 API | `GET /v1/web/profile` 응답에 `nickname`을 넣는다. `PUT /v1/web/profile`에 `nickname` 칸을 더한다(기존 부분 갱신 규칙 그대로). 앞뒤 공백 제거 · 2~20자. 겹치면 409 `nickname_taken`, 비우기(null · 공백만)는 422 | 허용 문자 · 길이, **게스트도 바꿀 수 있게 할지**(제안: 모두 허용 — 규칙이 하나) |
| S5 | 소셜 로그인 | 게스트가 로그인해 회원이 되면 게스트 이름을 그대로 쓴다. 새로 만들어진 회원은 S2로 이름을 받는다. 기존 회원 로그인은 이름이 그대로다. 웹이 「처음 로그인」을 알 수 있게 교환 응답의 결과(`created` / 전환 / `signed_in`)를 지금처럼 싣는다 | 전환(게스트 → 회원) 결과를 웹이 구분할 수 있는지 |
| S6 | 운영 앱 데이터 | `admin_snapshot.py`의 `users[]`에 `displayName`을 넣는다. 문의 · 승인 · 위임은 화면이 `users`에서 id로 이름을 찾는다(서버는 `users`에만 싣는 쪽). 사용자 상세에는 `customer_id`도 그대로 | 문의 · 승인 · 위임 항목에도 이름을 직접 실을지 |
| S7 | 시험 | 자동 이름 부여 · 겹칠 때 다시 뽑기 · PUT 검증(409/422) · 기존 행 채우기 · snapshot 이름 | — |
| S8 | 문서 | `rest-endpoints/web-auth.md`(또는 프로필 절) · `admin-screen-api.md` · 이 문서의 상태 | — |

바꾸지 않는 것: 사용자 키 · 세션 쿠키 · `customer_id` · 소셜 연결 표(해시만) · 이메일/이름 미수집 · MCP · 개인 AI 쪽 동작.

## 5. 화면 — UI 몫 (서버가 끝난 뒤)

- **W1 웹**
  - 메뉴 · 마이페이지 이름 줄에 서버 닉네임을 보인다.
  - 프로필 수정 화면의 저장을 켠다. 닉네임만이고, 이미지는 계속 「준비 중」이다.
  - **처음 로그인이면 로그인 완료(`/auth/done`) 뒤 프로필 수정으로 보낸다.** 저장하거나 건너뛰면 원래 가려던 화면으로 간다.
  - 이 흐름은 별도로 진행 중인 로그인 · 약관 동선 수정(ST4F-601 — 로그인 먼저 · 가려던 화면으로)과 함께 맞춘다.
  - 409 「이미 쓰는 이름이에요」 안내를 넣는다.
- **W2 운영 앱**
  - 사용자 목록 · 문의 · 예약 승인 · 위임에서 사용자를 이름으로 보인다(`data.users`를 쓰는 곳 9곳).
  - ID는 사용자 상세에만 둔다. 이름으로 검색할 수 있게 한다.
- **W3 시험**
  - 모방 서버(`tests/live/stub-server.mjs`)에 닉네임을 더한다.
  - 웹 · 운영 앱 브라우저 시험을 맞춘다.

## 6. 확인 부탁 (요약)

1. S1 이름 칸 위치(`customers` vs `customer_profiles`).
2. `new_customer()` 말고 서비스 코드에서 사용자 행을 만드는 곳이 있는지.
3. S4 닉네임 규칙(문자 · 길이)과 게스트 변경 허용 여부.
4. S5 「처음 로그인」(새 회원 · 게스트 전환) 구분 방법.
5. S6 운영 앱 데이터에 이름을 싣는 위치.
6. 이 계획에서 놓친 영향(이름이 노출되면 안 되는 곳 등).

확인해 주시면 S1 → S2 · S3 → S4 · S5 → S6 → 시험 → 문서 순서로 진행하고, 웹 · 운영 앱 화면(W1 · W2)을 맞춘다.

## 관계

- [소셜 인증과 게스트 여행 보관](web-auth-transfer.md) — 게스트 → 회원 전환 계약
- [운영 앱 화면 API](admin-screen-api.md) — 운영 앱 데이터 협의
- [화면별 API 연동](web-screen-api.md) — 웹 화면 협의 상태

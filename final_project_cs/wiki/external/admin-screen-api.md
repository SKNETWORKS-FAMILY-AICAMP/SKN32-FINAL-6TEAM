---
type: contract
title: 운영 앱 API 계약
description: 고객 앱과 분리된 개발·QA 운영 앱의 인증과 API 경계
status: draft
domain: travel
---

# 운영자 웹앱 연동 계약

2026-10-08 사용자 요청. 고객 웹앱과 별도 프로세스인 운영 앱에만 아래 경로를 등록한다.
고객 쿠키·고객 API 키는 운영자 인증으로 사용하지 않는다. 운영자 설정이 비어 있으면 닫힌다.

| 경로 | 계약 |
|---|---|
| GET /admin/api/session | 로그인 전 CSRF 토큰 또는 로그인한 운영자 id·scope·CSRF |
| POST /admin/api/login | operatorId, password; X-CSRF-Token 이중제출; 로그인 실패 잠금 |
| POST /admin/api/logout | 서명 세션 기반 CSRF 확인 뒤 쿠키 삭제 |
| GET /admin/api/snapshot | ops:introspect 권한; 현재 테넌트에 한정한 관리자 화면 자료 |
| GET /admin/api/api-limits | ops:introspect 권한; 현재 프로세스의 API 일·월 ENV 한도와 기본값·DB 기록. [세부 계약](api-environment-limits.md) |
| POST /admin/api/commands | model.ts의 13가지 명령. 서버에서 입력·권한·대상·사유 재검증 |
| GET /v1/web/support/notices | 고객 API의 공개 공지·점검 상태; 고객 인증정보 불필요 |
| GET /v1/web/support/notices/board | `[2026-10-17 사용자 결정 · ST4F-604]` 고객 웹 「공지사항」 게시판; 고객 인증정보 불필요. 운영 앱 「공지 목록」의 공지 중 **게시를 시작한 것만** `{notices: [...]}` 로 낸다 — 게시 중(`status: "posted"`) 먼저, 종료(`"ended"`) 그다음, 각각 게시 시작이 늦은 것부터. 예약(시작 전)과 작성 운영자(`author`)는 내지 않는다. 판정은 운영 앱 목록과 같다(한국 시각 시작 ≤ 지금 < 끝이면 게시 중, 끝 ≤ 지금이면 종료). 쪽 나누기는 화면이 한다(서버는 전체 목록). UI·검증 담당 추가 — 매니저 검토 전 |
| GET /v1/web/support/inquiries | 고객 인증으로 본인 문의와 답변 조회 |
| POST /v1/web/support/inquiries | 고객 인증·CSRF; requestId UUID, title, body, language; 동일 요청은 같은 문의 반환 |

쓰기 권한: 사용자·문의·공지·점검 설정은 limits:write, 승인은 action:approve,
위임은 delegation:write, 발송 해소는 action:approve. 점검은 ops:introspect.
승인·위임·발송 해소는 기존 고객 API를 설정된 운영용 키로 호출한다. 새 privileged 키를 만들지 않는다.
운영자 id는 서명 쿠키에서 읽고 요청 몸통의 actor를 받지 않는다. 비밀키는 브라우저로 보내지 않는다.

자료는 admin_records에 테넌트·종류·id 단위로 저장하고, 변경 전후와 사유는
append-only admin_audit에 같은 트랜잭션으로 저장한다. 차단·채팅 한도·점검은 고객 요청 관문에서도 검사한다.
한도 예외의 today는 한국 날짜가 바뀌면 만료된다. 외부 호출 상한은 기존 계측 meter와 DB 예산 소스에 설정 가능하며
원래 과금계정 전체 상한보다 낮추는 방향으로 적용한다(`[2026-10-15]` DB 예산 소스는 호출 기록이 없어도 된다 · `api-cap-clear` 로 지정 해제 — [API 환경설정 한도](api-environment-limits.md)).
`[2026-10-15 사용자 지시]` 채팅 하루 한도(「② 채팅 하루 한도」 · 사용자별 예외)는 **0 이 한도 없음**이다. 저장한 적이 없으면 화면이 보여 주는 기본값
(가드레일 `web_guard.limits.message.per_key_day`)을 그대로 적용한다 — 전에는 저장값이 없으면 한도 없이 통과해 화면 숫자와 실제가 달랐다.
save-limits의 rules는 실제 운영에서 빈 목록만 받는다. 안전 감시 주기 편집은 비활성화하며 채팅 한도만 저장한다. 실제 예약 승인은 기존 상태기계를 통과한다.

CPU·메모리·요청 지연처럼 계측하지 않은 값은 null(미계측)이며 0으로 꾸미지 않는다.
연결 실패는 명시적으로 오류를 표시하고 데모로 대체하지 않는다. demo 모드만 예시 자료를 허용한다.
문의 작성·답변 조회 및 활성 공지는 고객 인증으로 본인 테넌트·본인 문의만 접근한다.
기존 제한값과 보관 설정은 /admin/limits 및 /admin/retention 계약을 그대로 재사용한다.


## 기존 운영 기능 연결

- GET/PATCH `/admin/api/settings/limits`, `/settings/retention`: 각각 limits:read / limits:write.
  기존 운영 앱의 `/admin/limits`, `/admin/retention` API를 설정된 운영용 키로 호출한다. 운영용 키(`ACOP_OPS_API_KEYS`)에 limits:read · limits:write 가
  없으면 503 「운영용 제한 설정 키가 설정되지 않았습니다」다 — 오라클 서버의 키 생성기(`deploy/arm/admin_env.py` `OPS_SCOPES`)에 `[2026-10-15]` 두 scope 를 더했다.
- GET/PATCH `/admin/api/source-policy`, GET `/admin/api/diagnostics`(+ `/{지문}/customers|events`, PATCH `/{지문}/resolution`): 관리자웹앱 중계(Next `admin/api/[...segments]`)가
  `[2026-10-15]` 전까지 이 경로를 404 로 막아 「자료 조회 정책」 · 「결함 사후 분석」 화면이 열리지 않았다.
  `actor`는 몸통 값을 믿지 않고 서명된 운영자 id로 덮어쓴다. expected_revision 충돌 계약을 유지한다.
- GET `/admin/api/cases`, `/cases/{case_id}`: case:read. 기존 접수·이벤트·근거 조회를 재사용하며 변경 명령은 제공하지 않는다.
- 고객 문의·사용자 정책과 채팅 횟수는 고객 외래키 ON DELETE CASCADE로 기존 고객 보관 정리와 함께 지워진다.
  이 마이그레이션을 적용하는 것만으로 고객 자료를 지우지는 않는다. 운영 감사는 append-only로 유지하며 본문은 개인정보 가림 규칙을 적용한다.

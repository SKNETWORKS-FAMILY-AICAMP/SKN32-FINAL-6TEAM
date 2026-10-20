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
| GET /admin/api/users/{customer_id}/trips/{trip_id} | ops:introspect; 테넌트·고객·여행을 함께 확인한 여행 기본 정보 |
| GET /admin/api/users/{customer_id}/trips/{trip_id}/chat | 같은 권한·소유 확인; 저장된 대화를 turn_id 오름차순 조회. after=0, limit=100(최대 200), turns·next_after 반환 |
| GET /admin/api/users/{customer_id}/trips/{trip_id}/plans/{view} | 같은 권한·소유 확인; view=initial은 version=1, current는 조회 시점 latest_version. plan·as_of 반환 |
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

### 여행 상세 조회 — 2026-10-17 사용자 요청

사용자 상세의 여행 이름·상세 링크에서 `/users/{customer_id}/trips/{trip_id}`로 이동한다. 대화 내역·처음 여행계획·현재 여행계획은 독립적으로 읽으며 각 영역에 읽는 중·빈 기록·실패·다시 읽기를 제공한다. 직접 주소 진입·새로고침·뒤로 가기를 지원한다.

대화의 정본은 `trip_chat_turns`다. 고객·guguroute 응답·작성 시각·연결된 접수 ID를 보이고 본문을 자르지 않는다. 대화는 커서로 이어 읽으며 다른 여행·고객의 기록을 합치지 않는다. 저장하지 않은 대화나 보관 기간이 지난 기록을 복원했다고 표시하지 않는다. 외부 AI에서만 나눈 대화와 여행 등록 전 대화는 이 표의 조회 범위가 아니다.

처음 계획은 최초 등록한 1판이다. 1판이 보관되지 않았으면 `plan=null`이며 가장 오래 남은 다른 판으로 대신하지 않는다. 현재 계획은 같은 읽기 트랜잭션 안에서 여행 최신 포인터와 해당 판의 항목을 조회한다. 항목은 순서·종류·시작/종료·제목·장소·고정 여부와 허용된 이동·비용 설명을 반환한다. 변경 이유·작성 시각·판 번호를 함께 표시한다. 조회 시각 이후 변경은 다시 읽기로 확인한다.

운영자 서명 세션과 `ops:introspect` 권한을 검사한다. 테넌트·고객·여행이 맞지 않으면 404, 잘못된 ID·커서는 422다. 응답은 `Cache-Control: no-store`이며 개인정보 가림을 유지한다. 운영 조회용 DB 연결을 재사용한다. 조회는 고객 채팅 한도·여행 내용·감시 상태를 변경하지 않고 외부 API·모델을 부르지 않는다. 새 DB 표·마이그레이션은 필요하지 않다. 고객 앱에는 이 경로를 등록하지 않는다.

이동 항목은 저장된 `detail.option`을 우선하고, 없으면 `route_def.planned`의 선택 경로를 읽어 수단·소요 시간을 표시한다. 선택되지 않은 후보와 내부 처리용 detail 값은 노출하지 않는다. 처음 계획의 일정 항목은 1판 정본이며, 장소 이름·주소는 현재 보관된 장소 메타데이터다. 저장하지 않은 과거 장소 메타데이터까지 복원하는 기능은 아니다.

구현 담당·계약 검토: 이번 Codex 작업자가 매니저 API·화면 계약을 함께 검토한다. 독립 검토 완료를 뜻하지 않는다. 구현·시험·운영 반영 상태는 [날짜별 기록](../records/reports/2026-10-17_admin-trip-detail.md)에 구분한다.

- GET/PATCH `/admin/api/settings/limits`, `/settings/retention`: 각각 limits:read / limits:write.
  기존 운영 앱의 `/admin/limits`, `/admin/retention` API를 설정된 운영용 키로 호출한다. 운영용 키(`ACOP_OPS_API_KEYS`)에 limits:read · limits:write 가
  없으면 503 「운영용 제한 설정 키가 설정되지 않았습니다」다 — 오라클 서버의 키 생성기(`deploy/arm/admin_env.py` `OPS_SCOPES`)에 `[2026-10-15]` 두 scope 를 더했다.
- GET/PATCH `/admin/api/source-policy`, GET `/admin/api/diagnostics`(+ `/{지문}/customers|events`, PATCH `/{지문}/resolution`): 관리자웹앱 중계(Next `admin/api/[...segments]`)가
  `[2026-10-15]` 전까지 이 경로를 404 로 막아 「자료 조회 정책」 · 「결함 사후 분석」 화면이 열리지 않았다.
  `actor`는 몸통 값을 믿지 않고 서명된 운영자 id로 덮어쓴다. expected_revision 충돌 계약을 유지한다.
- GET `/admin/api/cases`, `/cases/{case_id}`: case:read. 기존 접수·이벤트·근거 조회를 재사용하며 변경 명령은 제공하지 않는다.
- 고객 문의·사용자 정책과 채팅 횟수는 고객 외래키 ON DELETE CASCADE로 기존 고객 보관 정리와 함께 지워진다.
  이 마이그레이션을 적용하는 것만으로 고객 자료를 지우지는 않는다. 운영 감사는 append-only로 유지하며 본문은 개인정보 가림 규칙을 적용한다.

## 여행 초안 원문 — 2026-10-18 사용자 요청

여행 상세의 기존 세 탭에 「입력한 초안 원문」 탭을 추가한다. 최초 등록된 구조화 계획(1판)과 고객이 입력한 초안 원문은 구분한다. GET `/admin/api/users/{customer_id}/trips/{trip_id}/draft`는 동일한 운영자 권한·테넌트·고객·여행 검사를 적용한다. 해당 여행의 최초 원본 접수(`trip_intakes.trip_id` 일치, 같은 고객, `reopen_trip_id IS NULL`, 접수 시각·ID 순)와 그 접수의 `intake_sources`를 입력 순서대로 읽는다. 수정 화면을 다시 연 접수나 다른 여행의 원문을 대신 보여 주지 않는다.

응답은 `draft`(접수 ID·접수 시각·sources)와 `as_of`다. sources에는 원본 ID·입력 순서·종류·파일명·보관된 `text`·받아쓰기 여부를 담는다. 초안 문구와 줄바꿈은 보관된 transcript를 그대로 읽되 기존 개인정보 가림을 적용한다. 첨부에서 추출·받아쓴 글은 입력한 텍스트와 구분해 표시한다. 저장 경로·원본 파일의 내부 위치·임의 detail은 노출하지 않는다. 보관되지 않은 원문은 명시적인 빈 상태로 표시하며 최초 계획을 원문으로 재구성하지 않는다.

초안도 독립 로딩·실패·다시 읽기를 제공하며 GET만 허용한다. 고객 한도·일정·감시 상태 변경이나 외부 API·모델 호출을 하지 않는다. 새 저장 표는 만들지 않는다. 담당과 계약 검토는 이번 작업자가 수행하며 독립 검수로 표시하지 않는다.

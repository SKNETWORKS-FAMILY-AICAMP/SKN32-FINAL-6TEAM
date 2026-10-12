# 운영자 웹앱 연동 계약

2026-10-08 사용자 요청. 고객 웹앱과 별도 프로세스인 운영 앱에만 아래 경로를 등록한다.
고객 쿠키·고객 API 키는 운영자 인증으로 사용하지 않는다. 운영자 설정이 비어 있으면 닫힌다.

| 경로 | 계약 |
|---|---|
| GET /admin/api/session | 로그인 전 CSRF 토큰 또는 로그인한 운영자 id·scope·CSRF |
| POST /admin/api/login | operatorId, password; X-CSRF-Token 이중제출; 로그인 실패 잠금 |
| POST /admin/api/logout | 서명 세션 기반 CSRF 확인 뒤 쿠키 삭제 |
| GET /admin/api/snapshot | ops:introspect 권한; 현재 테넌트에 한정한 관리자 화면 자료 |
| POST /admin/api/commands | model.ts의 13가지 명령. 서버에서 입력·권한·대상·사유 재검증 |
| GET /v1/web/support/notices | 고객 API의 공개 공지·점검 상태; 고객 인증정보 불필요 |
| GET /v1/web/support/inquiries | 고객 인증으로 본인 문의와 답변 조회 |
| POST /v1/web/support/inquiries | 고객 인증·CSRF; requestId UUID, title, body, language; 동일 요청은 같은 문의 반환 |

쓰기 권한: 사용자·문의·공지·점검 설정은 limits:write, 승인은 action:approve,
위임은 delegation:write, 발송 해소는 action:approve. 점검은 ops:introspect.
승인·위임·발송 해소는 기존 고객 API를 설정된 운영용 키로 호출한다. 새 privileged 키를 만들지 않는다.
운영자 id는 서명 쿠키에서 읽고 요청 몸통의 actor를 받지 않는다. 비밀키는 브라우저로 보내지 않는다.

자료는 admin_records에 테넌트·종류·id 단위로 저장하고, 변경 전후와 사유는
append-only admin_audit에 같은 트랜잭션으로 저장한다. 차단·채팅 한도·점검은 고객 요청 관문에서도 검사한다.
한도 예외의 today는 한국 날짜가 바뀌면 만료된다. 외부 호출 상한은 기존 계측 meter에만 설정 가능하며
원래 과금계정 전체 상한보다 낮추는 방향으로 적용한다.
save-limits의 rules는 실제 운영에서 빈 목록만 받는다. 안전 감시 주기 편집은 비활성화하며 채팅 한도만 저장한다. 실제 예약 승인은 기존 상태기계를 통과한다.

CPU·메모리·요청 지연처럼 계측하지 않은 값은 null(미계측)이며 0으로 꾸미지 않는다.
연결 실패는 명시적으로 오류를 표시하고 데모로 대체하지 않는다. demo 모드만 예시 자료를 허용한다.
문의 작성·답변 조회 및 활성 공지는 고객 인증으로 본인 테넌트·본인 문의만 접근한다.
기존 제한값과 보관 설정은 /admin/limits 및 /admin/retention 계약을 그대로 재사용한다.


## 기존 운영 기능 연결

- GET/PATCH `/admin/api/settings/limits`, `/settings/retention`: 각각 limits:read / limits:write.
  기존 운영 앱의 `/admin/limits`, `/admin/retention` API를 설정된 운영용 키로 호출한다.
  `actor`는 몸통 값을 믿지 않고 서명된 운영자 id로 덮어쓴다. expected_revision 충돌 계약을 유지한다.
- GET `/admin/api/cases`, `/cases/{case_id}`: case:read. 기존 접수·이벤트·근거 조회를 재사용하며 변경 명령은 제공하지 않는다.
- 고객 문의·사용자 정책과 채팅 횟수는 고객 외래키 ON DELETE CASCADE로 기존 고객 보관 정리와 함께 지워진다.
  이 마이그레이션을 적용하는 것만으로 고객 자료를 지우지는 않는다. 운영 감사는 append-only로 유지하며 본문은 개인정보 가림 규칙을 적용한다.

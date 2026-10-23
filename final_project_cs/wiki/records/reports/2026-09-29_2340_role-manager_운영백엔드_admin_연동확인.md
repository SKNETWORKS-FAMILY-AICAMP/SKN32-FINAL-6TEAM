---
type: report
title: role-manager 운영 백엔드와 admin 연동 사전 확인
description: 원격 role-manager의 운영 기능을 현재 admin 데모와 대조한 코드 조사 결과. API 발주나 실제 연결 완료를 뜻하지 않는다
status: draft
domain: travel
---

# role-manager 운영 백엔드와 admin 연동 사전 확인

2026-09-29 23:40 KST · 수행 Codex · 상태: 코드 조사 완료, 실서버 연결 미검증.

## 확인 범위와 결론

[실측: Git·소스] `git fetch origin role-manager` 후 원격 최신은 **`5d7a3643137423e99b0c2da00945aee77442bb0c`**다. 커밋 시각은 2026-09-29 16:00:20 KST이며 이전 화면 기획 검토의 기준 커밋과 같다. 작업 체크아웃은 `role-eval-ui` **`38cd59d` + 미커밋 admin 구현**이다. 브랜치를 바꾸거나 병합하지 않고 `git show`·`git grep`로 비교했다.

운영 서버 분리, 기존 HTML 운영 화면, 웹 한도 관리, 승인·위임·발송 확인의 기존 기능은 있다. 새 admin 전체를 연결할 JSON API는 부족하다. 새 admin은 명시적인 demo 모드의 메모리 데이터만 사용하며 실제 서버용 gateway와 운영자 인증 연결은 없다. 따라서 백엔드 URL 한 줄만 바꿔 전체 화면을 실사용할 단계는 아니다.

[미확보] 이번에는 role-manager 서버·DB를 기동하거나 API를 호출하지 않았고 테스트를 실행하지 않았다. 아래의 ‘있음’은 고정 커밋에서 코드·라우터 등록을 확인했다는 뜻이다. 테스트 파일 존재와 실제 시험 통과를 구분한다. 전체 백엔드 완료율은 분모가 정해지지 않아 산정하지 않는다.

## 현재 서버 경계

| 구분 | 확인 결과 | 근거 — 이하 백엔드 줄번호는 모두 `5d7a364` |
|---|---|---|
| 운영 앱 | 기본 `127.0.0.1:8070`, 별도 프로세스. 루프백 외 요청 403. HTML 로그인·운영 화면과 `/admin/limits*`를 제공 | `app/ops_entrypoint.py:30–62`, `app/core/settings.py:102`, `app/composition.py:346–364` |
| 고객 API 앱 | 기본 8042. 승인·위임·outbox 처리 JSON API는 이쪽에 남아 있고 기존 운영 화면이 서버에서 HTTP로 호출 | `app/presentation/api/app.py:62–68`, `app/composition.py:287–343`, `app/presentation/ui/routes.py:700–719` |
| 새 admin | Next 앱 3300. demo gateway가 `snapshot`/`execute`를 메모리에서 처리. live 설정은 연결 미설정 | 현재 작업 파일 `frontend/apps/admin/src/lib/gateway.ts:7–10,39–45`, `src/components/AdminApp.tsx:42–51` |
| 미완료 경계 | 별도 기계·컨테이너 분리는 다음 단계. 기존 HTML 일부 조회는 DB를 직접 읽음. 운영자 신원을 서명해 고객 API로 보내는 개선도 결정 문서의 후속 항목 | `wiki/decisions/D-CS-008-ops-console-separate-app.md` |

## 화면 기획 A-01~A-15 대조

백엔드 경로는 모두 `final_project_cs/` 기준이다. ‘추가 필요’는 이번 조사에서 확인한 차이이며, API URL·요청/응답을 확정한 계약은 아니다.

| 항목 | 현재 확인된 구현 | 새 admin 연결에 필요한 일 |
|---|---|---|
| A-01 운영자 로그인 | 계정 해시·잠금·서명 쿠키와 HTML `/ui/login`, `/ui/logout` 있음. `app/presentation/ui/auth.py`, `routes.py:171–211` | 새 화면용 로그인·현재 세션·로그아웃 계약과 CSRF 처리. 기존 인증 로직 재사용 여부 합의 |
| A-02 사용자 목록·상세 | `web_user_keys`에 `customer_id`, 발급·마지막 사용·폐기 시각이 있음. `app/infrastructure/db/migrations/025_web_user_keys.sql:14–26` | 운영자용 목록·상세·여행 연결 조회. 키 재발급을 별도 사용자로 중복 집계하지 않도록 사용자 ID 기준 확정 |
| A-03 차단·해제 | `revoked_at`는 키 폐기/재발급에 사용. 사용자 차단 상태·API는 확인되지 않음. `app/modules/travel_ops/web_session.py:51–64` | 차단 저장·해제·요청 차단 적용. 재발급해도 차단이 유지되는지, 기존 감시를 중단할지 정책 필요 |
| A-04 채팅·웹 호출 집계 | `web_guard`가 일부 작업을 고객·IP 해시·서비스 단위로 집계. 모든 HTTP 경로의 집계는 아님. `web_guard.py:36,196–248` | 사용자별 채팅 및 경로별 웹 조회 API와 계측 범위. 현재 `usage_today`는 서비스 전체 합계만 반환 |
| A-05 기본·예외 한도 | `GET/PATCH /admin/limits`, `GET /admin/limits/events` 있음. 기본 한도와 적용 기능은 존재. `web_limits_api.py:69–127`, `web_guard.py:75–101` | 기존 한도 API 재사용 가능. 사용자별 예외 한도·기간은 추가 필요. 현재 admin의 채팅 한도와 실제 limit 이름의 대응 필요 |
| A-06 외부 API·LLM 사용량 | `external_call_budget`의 UTC 일·월 예산과 `llm_calls` 저장 기반 있음. **Google 지도 표시도 `POST /v1/web/map-load`로 예산을 예약함**. `migrations/027_external_call_budget.sql:12–20`, `call_budget.py:31–64`, `trip_api.py:1172–1194` | 운영자용 읽기 API, 출처 감시/채팅 구분, 비용·미계측 표현. UTC 예산과 KST 보고 집계를 구분. `map-load`는 사용량을 증가시키므로 조회 용도로 호출하면 안 됨 |
| A-07 외부 API 상한 변경 | 상한은 가드레일 설정에서 계산. 변경 API는 확인되지 않음. `call_budget.py:75–96` | 변경 가능 범위·권한·감사와 저장/실제 적용 API. 현재 무료 한도 보호 정책을 임의의 유료 사용 허용으로 바꾸지 않기 |
| A-08 감시 조절 | 예산 초과 호출 거절과 고정 속도 제한은 있음. 소진율 단계별 감시 간격 정책은 확인되지 않음. `call_budget.py:31–55`, `app/infrastructure/travel/ratelimit.py` | 규칙 저장뿐 아니라 실제 감시 스케줄 적용 및 적용 상태 조회. API별 조절 여부부터 합의 |
| A-09 서버·요청 지표 | 고객 `/health`는 `status:ok`, 운영 `/health`는 여기에 `app:ops`. `presentation/api/app.py:88–89`, `ops_entrypoint.py:60–62` | DB·외부 소스 진단, CPU/메모리/디스크·감시 상태, 경로별 오류·지연 집계. 현재 health를 전체 의존성 정상으로 표시하면 안 됨 |
| A-10 문의·답변·템플릿 | 현재 화면 모델에 해당하는 운영 문의 API/저장 모델은 라우트·마이그레이션 조사에서 확인되지 않음 | 사용자 접수/조회와 운영자 목록·답변·담당·상태·템플릿 저장 모두 필요. Case·VOC를 동일 기능으로 간주하지 않기 |
| A-11 공지·점검 | 서비스 공지·점검 API는 확인되지 않음. 여행별 `/v1/web/trips/{trip_id}/notices`는 여행 변경 알림. `trip_api.py:1196–1211` | 운영 저장/예약 게시, 사용자 웹 노출, 점검 적용 범위와 종료 동작. admin 화면만 저장해서는 고객에게 적용되지 않음 |
| A-12 운영 기록 | 한도 변경 이력과 고객별 위임 이력 등 개별 기록은 있음. `web_limits_api.py:114–127`, `delegation_api.py:135–148` | 전체 작업을 모으는 감사 조회·필터·보관 계약. 변경 API의 인증 운영자·전후 값·사유 저장 보장 |
| A-13 승인 | `POST /v1/cases/{case_id}/actions/{action_id}/approve`로 승인/거절 가능. 대기 목록은 HTML이 DB 조회. `presentation/api/cases.py:196–264`, `ui/routes.py:601–657` | 대기 목록/상세 JSON과 실제 `case_id`+`action_id` 제공. 승인 처리 사유 저장 보완(아래 상세) |
| A-14 위임 | 목록·고객 상세·grant·revoke JSON 모두 있음. `delegation_api.py:114–190` | 기존 API 재사용 우선. demo의 단순 active 토글을 `absent/live/revoked` 상태·고객 ID·위임 범위/사용액에 맞춰 변환. 위임 목록에는 신규 대상 고객 전체가 나오지 않으므로 사용자 조회와 연결 필요 |
| A-15 발송 확인 | `POST /v1/outbox/{message_id}/resolve` 있음. `unknown` 목록은 HTML이 DB 조회. `presentation/api/outbox.py:23–55`, `ui/routes.py:941–989` | 목록 JSON 추가. ‘확인 완료 포함’ 필터와 `resolved_at` 등 확인 정보를 포함해야 함. 확인 결과·확인자·근거만 기록하는 계약 유지. `confirmed_not_delivered`도 재발송 명령이 아님 |

## 연결 전에 바로잡을 차이

1. **Google 지도 표시 계측 설명** — 현재 admin `src/lib/demo/fixtures.ts:10`은 ‘미계측’이다. `role-manager`에는 `google_maps_dynamic_maps`의 예산 예약과 사용량 반환이 있다(`trip_api.py:1172–1194`). 정확한 상태는 ‘예산 예약 계측 있음 / 운영자용 조회 API 없음 / 공급자 청구 실측과는 별개’다. 앞선 기획·데모에서 이 경로를 놓친 부분이며 이번 조사에서 정정한다. `web.map_provider`의 OSM/Google 변경도 이미 limits 목록에 있다(`web_guard.py:97–100`).
2. **승인 사유** — 입력 모델에 `note`는 있으나(`cases.py:69–73`) 승인 저장·이벤트에는 전달되지 않는다(`cases.py:258–263`). 현재 admin의 필수 `reason`을 그 필드로 보내는 것만으로 영속 감사가 충족되지 않는다. 인증된 처리자와 사유를 함께 저장하는 보완이 필요하다.
3. **한도 저장 방식** — 서버는 `expected_revision`으로 충돌을 검출하며 409와 변경 후 적용 대기 시간을 반환한다. 현재 demo의 즉시 저장·단일 `chatLimit` 모델만으로는 이를 표시할 수 없다(`web_limits_api.py:30,73–112`, `wiki/external/rest-endpoints.md:400–423`). 채팅 기본값은 `web.message.per_key_day`에 대응하지만 `web.limits_enabled`와 IP·서비스 전체 한도도 집행에 관여한다. demo의 `save-limits`가 한 번에 저장하는 감시 단계는 이 API에 없다. API의 값 범위·사유 길이와 최대 30초 적용 지연도 화면 검증에 맞춰야 한다.
4. **서로 다른 운영 범위** — 외부 API 예산 표는 공급자 결제 계정 전체 기준으로 tenant 열이 없다(`migrations/027_external_call_budget.sql:9,12–20`). 고객별 호출량과 같은 범위로 합쳐 표시하지 않도록 응답에 집계 범위·시간대·계측 여부를 명시할 필요가 있다.
5. **접속 주소와 권한** — 운영 API 전부가 8070에 모인 상태가 아니다. 브라우저에 scope 키를 넣고 고객 API를 직접 호출하는 구조로 연결하지 않는다. 고객 API CORS도 운영 Bearer/PATCH용으로 열려 있지 않다(`presentation/api/app.py:46–48`). 새 admin 서버의 세션 확인·서버 측 중계와 백엔드 처리자 검증 계약부터 맞춘다.
6. **LLM 비용과 외부 API 집계 단위** — 비용 열이 있다고 실제 비용이 기록되는 것은 아니다. 확인한 OpenAI/local_ft 기록 경로는 토큰·지연을 보내지만 비용을 전달하지 않는다(`app/infrastructure/llm/openai.py:96–101`, `local_ft.py:95–100`, `db/repository.py:135–137`). 비용 미확보를 0원으로 바꾸지 않는다. Google Places도 검색/상세가 별도 meter이므로(`app/infrastructure/travel/google_places.py:40–41`) demo의 한 행에 합치기 전에 단위와 무료량 적용을 정해야 한다.
7. **승인·발송 결과의 의미** — 승인 응답은 Case의 갱신 상태이며 예약 실행 완료를 보장하지 않는다(`cases.py:261–264`). 기존 outbox HTML 조회는 `resolved_at IS NULL`인 건만 반환한다(`ui/routes.py:261–269`). 현재 admin의 ‘확인 완료 포함’은 이 SQL을 그대로 JSON으로 옮기기만 해서는 충족되지 않는다.

관련 명세에도 정합성 보완이 있다. `rest-endpoints.md:421–422`의 한도 이름 목록은 코드에 존재하는 `web.map_provider`를 빠뜨렸다. `D-CS-007-ui-operator-login.md:63,66`의 CSRF 없음·동일 프로세스 호출 설명은 현재 `routes.py:62–68,181–184,684–724` 및 D-CS-008의 후속 구현과 다르므로 과거 설명으로 구분해야 한다. 이번에는 해당 문서를 수정하지 않았다.

## 이후 API 요청의 권장 순서 — 제안, 아직 발주하지 않음

1. **인증·공통 계약**: 운영자 세션/권한, 서버 측 중계, 인증된 처리자 귀속, CSRF, 오류 형식, 페이지/검색/기간 조건, 사용자 ID와 tenant 범위.
2. **기존 기능 연결**: 한도·한도 이력, 위임 조회/변경, health를 먼저 재사용. 승인·outbox는 목록 JSON을 추가하고 승인 사유 저장을 보완. 기존 엔드포인트를 중복 생성하지 않기.
3. **사용자 운영**: 목록/상세/여행 조회, 차단·해제, 사용자별 예외 한도 및 사용량 조회와 실제 요청 제한 적용.
4. **사용량·감시·서버**: API/LLM 읽기 집계, 상한 변경, 감시 정책 저장 및 적용, 진단/요청 지표. 일·월/UTC·KST와 미계측을 응답으로 구분.
5. **고객 지원·게시**: 문의/답변/템플릿, 공지/점검, 사용자 웹 반영과 통합 운영 기록. 홈은 이 자료들을 집계하는 읽기 API로 구성.

프론트에서는 demo를 유지하면서 live gateway와 운영 세션을 구현해야 한다. API가 없는 화면을 demo 데이터로 성공 처리하지 않고 미지원 상태로 보여 주며, 현재 단일 snapshot 모델을 기능별 조회·실패 상태에 맞출 필요가 있다. 현재 모델은 화면 시연용이며 HTTP 계약이 아니다.

## 검증·변경·공유 상태

- [실측] 원격 fetch 성공. `git rev-parse origin/role-manager`는 `5d7a3643137423e99b0c2da00945aee77442bb0c`.
- [실측] `git rev-list --left-right --count 38cd59d...5d7a364`는 `88 1`. 두 브랜치는 단순 fast-forward 관계가 아니며 manager snapshot 전체를 이번 조사에서 가져오지 않았다.
- [실측] 라우트 선언·조립, 인증, API 모델, DB migration, 현재 admin 모델/gateway를 대조했다. ‘없음’은 해당 고정 커밋의 노출 라우트 및 관련 저장 모델에서 찾지 못했다는 뜻이며 배포 서버 상태에 대한 주장이 아니다.
- [미확보] role-manager 시험 실행·서버 기동·DB 적용·실제 브라우저 통합은 하지 않았다. 테스트 소스를 읽었다는 사실만으로 통과율을 만들지 않는다.
- 관련 시험 코드: `tests/architecture/test_ops_app_is_separate.py`, `tests/e2e/test_ops_app_two_processes.py`, `tests/e2e/test_web_guard.py:156–239`, `tests/e2e/test_web_api.py:581–607`.
- 앱 코드·기획서·API 계약은 수정하지 않았다. 조사 보고서와 wiki 로그만 로컬에 기록한다. 티켓 발행·팀원 메시지·API 발주·커밋·푸시는 하지 않았다.

## 관계

- 현재 화면 범위: [admin README](../../../frontend/apps/admin/README.md) · [화면 기획 §7](../../../frontend/apps/admin/SCREEN_PLAN.md#7-데이터-출처--다음-단계에서-api-계약으로-만들-목록).
- 현재 프론트 검증: [프론트와 HTML 시나리오 리포트](2026-09-29_2313_admin_프론트와_HTML_시나리오.md).
- 고정 커밋의 운영 분리 결정: [D-CS-008](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/5d7a3643137423e99b0c2da00945aee77442bb0c/final_project_cs/wiki/decisions/D-CS-008-ops-console-separate-app.md).
- 고정 커밋의 API 계약: [rest-endpoints.md](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/5d7a3643137423e99b0c2da00945aee77442bb0c/final_project_cs/wiki/external/rest-endpoints.md).

재현 예시(팀 저장소에서):

```powershell
git fetch origin role-manager
git rev-parse origin/role-manager
git show 5d7a364:final_project_cs/app/ops_entrypoint.py
git show 5d7a364:final_project_cs/app/composition.py
git show 5d7a364:final_project_cs/app/modules/travel_ops/web_limits_api.py
git show 5d7a364:final_project_cs/app/modules/travel_ops/web_guard.py
git show 5d7a364:final_project_cs/app/modules/travel_ops/trip_api.py
git show 5d7a364:final_project_cs/app/modules/travel_ops/delegation_api.py
git show 5d7a364:final_project_cs/app/presentation/api/cases.py
git show 5d7a364:final_project_cs/app/presentation/api/outbox.py
git grep -n -E '^ *@[a-zA-Z_]+\.(get|post|put|patch|delete|api_route)\(' 5d7a364 -- final_project_cs/app
```

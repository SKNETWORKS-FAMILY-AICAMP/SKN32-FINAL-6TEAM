# Booking admin OFF v2 — 작업/검증 기록 (독립 검토 전)

## 발견과 계약
- 제품 관리자 진입은 `frontend/apps/admin/src/components/AdminApp.tsx`의 `/settings`; 실행 포트는 admin `package.json`의 3300. Composer UI가 아니다.
- 설정 정본: `web_guard.specs()` → `web_limits_api` `/admin/limits` → `runtime_limits`, revision state, append-only events. 관리자 프록시가 operator session/CSRF를 확인하고 정식 `limits:read/write` 키를 서버 쪽에서 붙이는 기존 경로를 재사용한다.
- `settings_hook` reader는 `composition.wire_optional_features()`에서 web_guard.values에 연결된다. tenant는 공개 기능 조회의 서버 설정, 팀의 서버 ContextPack, action의 승인 실행 문맥에서 전달된다. 사용자 payload로 tenant를 바꾸지 않는다.
- 예약 전용 기본 OFF만 추가한다. TeamConfig.active, 팀 삭제, flight 등록, 숙소 전체 기능 중단은 변경하지 않는다.

## TDD 증거(최초 오류와 제품 RED를 구분)
- `red-settings.log`/`red-settings-configured.log`: 필수 합성 설정 누락으로 setup 오류. 기능 RED가 아니다.
- `red-settings-ready.log`: 설정 항목·reader 미구현의 정상 assertion RED(6건). 최소 spec/reader 추가 후 `green-settings.log` 통과.
- `red-boundaries.log`: Windows asyncio socketpair 차단의 fixture 오류 포함. 기능 RED와 분리했다.
- `red-boundaries-ready.log`: 실제 신규 예약 팀/도구/적용기 경계 부재로 assertion RED. 기존 정보 읽기 3개는 처음부터 통과했다.
- `green-api.xml`: 이름과 달리 실제 21건 중 5건 실패. OFF 답변에 근거가 비어 TeamResult 계약 검증이 실패했다. 적용된 runtime OFF 값의 출처·근거를 추가했다.
- `red-api.log`: 기본 OFF 설정은 보이지만 공개 features booking 키가 없어서 1실패. 인증/검증/tenant test는 통과. 공개 bool을 추가했다.
- `iteration-stays.xml`: 25건 중 1실패/24통과. standalone 숙소 검색 OFF 경계 부재. 실제 ToolContext.from_pack의 서버 일정 항목 문맥을 구분해 기존 숙소 일정 대안은 유지하고 standalone만 차단했다.
- `red-ui.log`: vitest의 기존 `.test.ts` 패턴으로 tsx 미수집. 수집 패턴을 확장한 `red-ui-collected.log`는 예약 전용 fieldset 미구현으로 정상 2실패. 실제 운영 설정 폼에 booking fieldset을 연결했다.

## 현재 검증 관측
- `final-feature.xml`: 신규 Python 25/25 통과, 실패/오류/skip 0. SQLite 디스크 대역으로 실제 FastAPI limits router·scope auth·tenant·revision·audit·캐시/reader·공개 기능을 실행했다. PostgreSQL 검증이라고 부르지 않는다.
- `admin-unit.log`: 실제 관리자 Vitest 41/41 통과(신규 UI 2개 포함). `admin-types.log` 오류 없음. `admin-lint.log`에는 변경하지 않은 overview/screens.tsx의 기존 unused import 경고 1개.
- `browser-result.json`: 실제 Edge DOM에서 제품 OperationsSettings + gateway + React Query, fetch만 대역으로 8/8 assertion 통과. default OFF → explicit ON 저장 → 현재 OFF 저장/재조회, revision·예약 key만 전송, stale/미인증 쓰기 거절. admin 서비스는 띄우지 않았다.
- `browser.log`의 첫 실패는 다른 설정을 찾는 exact text locator의 fixture 오류. label DOM 기준으로 고친 `browser-rerun.log`와 결과 파일을 별도로 보존했다.
- 확대 회귀 최초 `regression-initial.xml`: acop_composer import 경로 누락으로 1 collection error, 실행 통과 건수로 세지 않는다. 같은 격리 저장소 final_project_sample의 Composer **공통 인프라 패키지만** import 경로에 추가했다. 여행 업무 데이터/예시는 가져오지 않는다. 후속 결과는 최종 인계에서 구분한다.

## 환경
- 새 사본에서만 core.longpaths=true/core.autocrlf=false로 복구. `baseline-verification.json`: 18,996 tracked blob 전부 정확, index tree b5bfeeaf30426f9183bfba12f800434287d339b7 = 기준 commit tree, mismatch 0.
- Python 3.12 의존성 환경을 사용하며 실제 socket connect/connect_ex/create_connection·bind 및 psycopg.connect를 차단한다. stdlib _fallback_socketpair code object의 self-pipe만 예외다.
- 관리자 의존성은 새 격리 admin package-lock.json을 `npm ci --ignore-scripts`로 설치했다. 기존 사본 dependencies/lockfile 변경 없음.
- API 대역 첫 실행 pytest tmp_path가 시스템 Temp를 사용한 것을 확인했다. 후속 runner는 고유 --basetemp를 이 작업 scratch로 강제한다. 그 최초 임시 파일은 임의 삭제하지 않았다.

## 운영 경계
`http://127.0.0.1:3300` TCP connect_ex=10061, HTTP WinError 10061 연결 거부, netstat listener 없음. 현재 운영 OFF 저장·readback은 미완료다. 서비스 기동/재시작/실DB/외부 예약 API/배포/push는 하지 않았다. 3300 관리자 정상 접근과 정식 로그인/설정 쓰기 권한을 가진 세션이 필요하다. 복구/배포 승인은 별도다.

## 보존 경계 후속 교정
- 확대 최초 실행은 7,993건 중 실패 26·skip 128이었다. 상세 node/message는 scratch `regression-failures.json`에 전수 보존했다. 예약 활성 시나리오가 OFF 기본을 상속한 실패 23건과 제안 계약 1건, Git 실행 환경 WinError5 2건으로 구분했다.
- 예약 ON fixture는 `tests/unit/travel/booking/conftest.py`와 제안 필드 계약 파일 두 범위에만 명시했다. 다른 에이전트 팀과 기본/OFF 시험 전체를 전역 ON으로 바꾸지 않았다. MinGit은 프로세스 PATH에만 우선 지정했다.
- 추가 `red-preserve.xml`은 실제 기존 「내 숙소」 조회와 booked flight 일정 읽기를 각각 재사용해 2실패를 확인했다. lodging.assist 전체 차단을 없애 기존 my_stay/status를 유지하고 신규 search만 차단했다. flight는 booked/locked 분기를 먼저 보존한 뒤 새 후보/고르기 실행을 차단했다. 기존 booked lodging 일정 읽기와 6팀 Registry 유지도 함께 확인했다.
- `preserve-and-contract.xml` 재실행은 위 보존 경계·신규 스위치·API·Git ignore·실제 제안 필드 계약을 함께 검증한다. 제안0을 assertion 삭제로 감추지 않았으며 ON 상태의 실제 제안을 검사한다.
- ruff F/E9가 신규 API 대역 시험의 사용하지 않는 import 2개를 잡았다. 그 두 import만 제거하고 `ruff-final.log`를 다시 실행했다. 변경 전 freeze 중이던 확대 실행은 중단 기록으로 보존하며 성공 집계하지 않는다. 코드/시험 19파일을 새로 freeze한 후 동일 최종 묶음·관리자 검증을 다시 실행한다.
- `admin-check-results.json`: 최종 lint/type/Vitest/build/Edge 부품 DOM 각각의 개별 return code를 보존한다. 부품 screenshot은 전체 관리자 서비스 화면이나 실서버 저장의 증거가 아니다.
- 2026-10-25 00:02 KST 읽기 전용 재확인도 `/settings` connect_ex=10061/HTTP 연결 거부였다(`live-readonly-check.json`). 주소 미확보 문제가 아니라 알려진 3300 관리자가 현재 열리지 않는 문제다.
- 마지막 caller 감사에서 `flight.assist`도 규칙으로 기존 「예약 상태」를 처리함을 확인했다. `red-assist-status.log`는 새 검색과 달리 보존해야 할 기존 상태 조회가 OFF 문으로 차단되는 실제 assertion 실패다. 규칙 status 분기 뒤로 신규 검색 OFF 검사를 옮겼으며, dedicated status뿐 아니라 정상 assist 호출의 locked 조회를 회귀에 추가했다.
- 이전 `delivery-regression.xml`의 소유 문맥 None 시험 실패는 운영 코드를 None 허용으로 완화하지 않고 기존 ON 시험에 실제 ToolContext를 공급해 교정했다. 그 뒤 모든 변경을 다시 동결하고 `acceptance-core.xml`/`acceptance-regression.xml`로 최종 재실행한다. 이전 delivery/final 로그는 최종 동일해시 성과가 아니다.

## 2026-10-25 최종 동결 재검증 (운영 적용과 분리)
- 중단된 `acceptance-regression.log` 및 이전 frozen XML은 최종 근거에서 제외했다. scratch `booking_admin_off_v2/closure-*`가 마감 실행의 정본이다.
- 변경 코드·시험 20파일 SHA256이 기존 동결값 및 재실행 전후 모두 동일하다. 이번 마감에서 제품 코드 변경은 없다.
- Python 핵심 141/141=100%, 관리자 단위 41/41=100%, 실제 Edge 부품 DOM 8/8=100%; lint·tsc·build·ruff F/E9 종료코드 0. lint에는 기존 unused import 경고 1건이 남는다.
- 같은 runner·선택식으로 끝까지 실행: 후보 8,542건 중 8,202통과·1실패·339skip(추가 74 deselect), baseline 8,513건 중 8,173통과·동일 1실패·339skip(추가 74 deselect). 추가 29/29 통과, 누락 node 0, 신규 회귀 0. 확대 전체 GREEN은 아니다.
- 공통 실패는 `test_public_graph_has_all_three_unambiguous_non_passenger_exceptions`의 Git 밖 `datasets/mobility/processed/mobility/road_graph_v2/turn_restrictions_v1.json` 부재다. 같은 node와 경로 접두를 제외한 같은 오류를 확인했다. 자료를 조작하거나 시험을 제외하지 않았다.
- 과거 baseline 날짜 경계 2건 및 옛 None 문맥 fixture 1건은 이번 baseline/candidate 양쪽 동일 node에서 통과했다. 날짜 관련 제품 코드·시험은 바꾸지 않았다.
- 18,996 baseline tracked 파일과 19,004 candidate tracked 파일 전체의 디스크 바이트와 index blob 일치(누락·불일치 0)를 확인했다. 공통 TeamConfig·contracts는 그대로다.
- `/settings` HTTP는 여전히 WinError 10061 연결 거부, TCP 3300 listener 없음. 현재 환경 OFF 저장·재조회는 미완료이며 SQLite/fetch 대역의 OFF 저장 성공을 운영 성공으로 읽지 않는다. 서비스·실DB·외부 API·배포·push는 실행하지 않았다.
- 최종 patch·manifest·기계판독 결과·FINAL_HANDOFF는 활성 프로필 scratch `booking_admin_off_v2`에 생성한다. 부모 독립 검토와 운영 접근/권한 확보는 별도 후속이다.

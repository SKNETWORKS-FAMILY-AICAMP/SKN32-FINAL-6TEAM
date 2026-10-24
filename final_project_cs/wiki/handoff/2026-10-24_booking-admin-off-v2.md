# 예약 관리자 OFF v2 인계 — 독립 검토 전

## 변경
- 제품 관리자 `http://127.0.0.1:3300/settings`의 운영 설정 폼에 예약 전용 `travel.booking.enabled`를 연결했습니다. 기본은 false이고 기존 runtime_limits 저장소, 서버 소유 tenant·limits 권한·boolean 검증·revision·감사 이력·캐시 무효화 경로를 재사용합니다.
- 공개 features의 booking bool과 검색 도구/팀/승인 후 예약 action 실행 경계를 연결했습니다. 미구현 신규 예약 기능은 만들지 않았습니다.
- 기존 숙소 정보(my_stay)/status, booked·locked 숙소/항공 일정 조회·보존과 기존 예약 원문 접수/수동 저장은 유지합니다. 숙소 일정 대안 검토 전체를 차단하지 않습니다. flight/다른 팀을 삭제하거나 TeamConfig.active 공통 기본을 변경하지 않았습니다.
- 예약 ON 전용 기존 회귀 fixture는 booking 폴더와 제안 필드 계약에만 한정합니다. OFF 기본/전환·기존 읽기 보존은 별도 신규 시험에서 확인합니다.

## 증거·산출물
작업 scratch `booking_admin_off_v2`의 `manifest.json`, `test-comparison.json`, `frozen-code-tests.json`, `admin-check-results.json`, `browser-result.json`, `live-readonly-check.json`과 각 로그/XML이 증거입니다. [계약](../operations/booking-master-switch.md) · [최초 실패/원인 교정/최종 검증 기록](../records/reports/2026-10-24_booking-admin-off-v2.md).

## 운영/통합 보류
- 알려진 관리자 주소 3300은 읽기 전용 확인에서 WinError 10061 연결 거부였고 listener가 없었습니다. 실제 환경 OFF 저장·재조회는 하지 못했습니다.
- 서비스 정상 접근과 정식 관리자 로그인/설정 쓰기 권한 세션이 필요합니다. 로그인 필요시 정식 vault 경로를 사용하고 비밀을 문서·채팅에 남기지 않습니다.
- 서비스 기동/재시작/실DB/실외부 API/배포/push/공유본 누적 통합은 수행하지 않았습니다. 기존 후보도 보존했습니다.
- 부모의 독립 검토와 승인 전 누적 통합하지 마세요. 격리 SQLite API/Edge fetch 대역은 실제 PostgreSQL·관리자 서비스 운영 확인과 다릅니다.

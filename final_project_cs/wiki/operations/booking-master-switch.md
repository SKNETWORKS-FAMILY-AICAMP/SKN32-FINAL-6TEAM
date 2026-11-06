# 예약 마스터 OFF v2 — 격리 계약 (독립 검토 전)

기준 635cb3424c75f6621bf75430766f27083dfaa00e. 기존 후보와 원본은 보존한다.

- 제품 관리자 `/settings` → 웹 이용·서비스 설정의 정식 `/admin/limits` 계약을 사용한다.
- 예약 전용 `travel.booking.enabled`: bool, 기본 false. 기존 runtime_limits 저장·tenant/scope 인증·revision·감사·캐시 무효화를 재사용한다. 명시 true만 켠다.
- 공개 `/v1/web/features`에 booking bool을 제공한다. UI만이 아니라 검색 도구·예약 assist·handoff 준비·승인 후 적용 경계에서 OFF를 검사한다.
- flight.status, booking.verify 및 기존 예약 정보 수동 읽기/저장, locked 정보는 유지한다. 숙소 일정 검토·수동 호텔 저장 전체를 차단하지 않는다.
- 예약 생성 기능을 새로 만들지 않는다. flight 팀 및 전체 TeamConfig.active 기본값은 변경하지 않는다.
- OFF의 다른 프로세스 반영 지연은 기존 web_guard.cache_seconds 계약을 따른다. 이미 실행 중인 외부 거래의 취소를 뜻하지 않는다.
- http://127.0.0.1:3300 연결 시 WinError 10061, listener 미발견. 서비스를 기동하지 않는다. 현재 환경 OFF 적용은 미완료이며 실행 중 관리자와 정식 로그인/권한 세션 확보 뒤 저장·재조회가 필요하다.
- [독립 검토 인계](../handoff/2026-10-24_booking-admin-off-v2.md) · [실행 기록](../records/reports/2026-10-24_booking-admin-off-v2.md).

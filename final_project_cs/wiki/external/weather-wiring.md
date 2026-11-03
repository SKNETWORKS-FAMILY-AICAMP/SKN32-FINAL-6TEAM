---
type: contract
title: 문의 날씨 읽기 공급자 조립
status: draft
domain: travel
---

# 문의 날씨 읽기 조립 계약

2026-10-24 로컬 적용 범위. 외부 HTTP·모델·DB·서비스·배포 검증을 포함하지 않습니다.

- 조립 루트는 기존 `build_travel_sources(get_settings()).weather.forecast` 읽기 포트를 라우터의 `weather_lookup_factory`로 제공합니다. 새 URL·모델·가드레일 수치·대체 정책을 만들지 않습니다.
- 기존 기상 공급자 순서/Chain, shared rate limiter, DB 예산, 응답 캐시/TTL, outbound proxy 정책은 기존 소스 조립기를 그대로 사용합니다. 문의용 직접 HTTP 및 별도 무제한 provider는 금지합니다.
- API와 웹 메시지는 기존 인증·소유권 검사를 거친 뒤 공급자 포트를 전달합니다. 실제 forecast 호출은 검증된 읽기 대상의 좌표·조회시각으로 `read_requests.reply`에서만 일어납니다. 공급자 조립은 기존 라우터 lazy factory로 첫 메시지/점검 시 수행하며 자체 예보 조회는 하지 않습니다.
- 없는 포트는 기존 `weather_source_unavailable`, 공급자 실패는 기존 명시적 실패 근거와 writer failed/partial로 표시합니다. 성공 날씨·맑음·업무 변경으로 대체하지 않습니다.
- 완료된 동일 요청은 저장된 답만 재생하며 날씨를 다시 조회하거나 업무를 실행하지 않습니다. 복구 가능한 미완료 읽기는 기존 snapshot/버전 검증 뒤 동일 포트로 진행합니다. TTL·판이 틀린 후속 focus는 조회하지 않습니다.
- `trip_api` 최초 배선은 factory 인자 및 두 메시지 호출 인자로 한정했습니다. 이번 P2 후속은 agent `message` 안의 기존 여행 접근검사 선행만 추가합니다. `_web_view`, 접수/확인/통지, 응답 소비자, core Controller·action·DB는 변경하지 않습니다.

## P2 후속 경계 보완 — 2026-10-24

독립 검토에서 agent 메시지의 인자 평가 중 factory가 여행 접근검사보다 먼저 생성되고, Open-Meteo `hourly.time`이 dict이면 파싱 예외가 기존 Chain의 2차 조회를 막는 결함을 확인했습니다. 이는 외부 HTTP 호출 재현이 아닙니다.

- agent 메시지도 기존 tenant-scoped `TripStore.latest`/`_trip_or_404` 검사를 provider factory보다 먼저 수행합니다. 없는 여행·타 tenant는 동일 404이며 factory를 생성하지 않습니다. 정상 허용 요청의 lazy 재사용 수명은 유지합니다.
- Open-Meteo의 비어 있지 않은 `hourly.time`은 문자열 list여야 합니다. 잘못된 time 모양/원소, 제공된 시간별 필드의 비-list 또는 time과 다른 길이는 `malformed_hourly` miss와 기존 경고 로그를 남기고 `None`으로 반환합니다. 누락된 선택 필드는 기존 `None`, 정상 0 강수는 그대로 유지합니다. 빈 hourly는 기존 `empty_hourly`를 유지합니다.
- 이 파싱 유효성 실패는 기존 `FallbackWeather`의 다음 공급자 정책으로 전달합니다. 성공한 2차는 한 번만 호출하고 실제 `source`, `confirmed_at`, `fell_back_from`을 유지하며 1차의 `malformed_hourly` 기록을 지우지 않습니다. 두 소스 실패는 기존 `all_failed`와 문의의 `weather_sources_failed`/partial·failed를 유지합니다. broad exception fallback이나 새 재시도 정책을 추가하지 않습니다.

검증: 실제 정상 메시지 함수→기존 read_requests→가짜 forecast 포트의 좌표·시각, 인증/소유권 선행, 공급자 부재 partial, 중복/TTL/판 보호 및 기존 188개 지정 unit을 격리 실행합니다. root wiki 인계는 부모 담당입니다.

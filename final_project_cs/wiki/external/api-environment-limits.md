---
type: contract
title: API 환경설정 한도 조회
description: 운영 앱이 현재 설정 한도와 DB 사용 기록을 읽는 계약
status: draft
domain: travel
---

# 관리자 API 환경설정 한도 조회

2026-10-09: 구현과 선택한 백엔드 127/127·화면/중계 7/7 검증 완료. x600 서버 미배포. [리포트](../records/reports/2026-10-09_2256_API환경설정_한도조회.md).

관리자웹앱의 사용량 화면에서 현재 운영 프로세스가 읽은 API별 일·월 한도와 같은 이름의 DB 사용 기록을 비교한다. 호출 이력이 없어도 설정된 API는 표시한다.

- `GET /admin/api/api-limits` — 운영 앱에만 등록. 운영자 로그인과 `ops:introspect` 필요. 읽기 전용이며 외부 API 호출·예산 예약·설정 변경을 하지 않는다.
- `Settings.source_rate_limits()`의 전체 소스와 OpenAI 장애 대체 호출의 일·월 상한을 반환한다. 설정값은 현재 프로세스의 Settings에서 읽으며 ENV 파일을 다시 읽지 않는다. ENV 변경 이후 프로세스 재시작 전에는 이전 값이다.
- 각 기간 설정은 `env`, `value`, `origin`, `zero_meaning`으로 반환한다. `origin=configured`는 ENV 또는 초기화 인자로 지정된 값, `default`는 기본값, `absent`는 해당 설정 항목이 없다는 뜻이다. 파일별 출처는 추정하지 않는다.
- 일반 소스 일 한도 0은 간격 제한 안 함, ITS 월 한도 0은 미설정·세기만, OpenAI 장애 대체 상한 0은 호출 차단이다. 제공처의 무제한 무료 제공량으로 해석하지 않는다.
- `recorded.day/month`는 `budget_timezone` 기준 현재 일·월의 DB 사용량과 마지막 기록 상한·기록 시각이다. 공공 소스는 Asia/Seoul, OpenAI 장애 대체 호출은 UTC다. 기록이 없으면 null(미계측)이며 0으로 만들지 않는다. 이 상한은 마지막 호출 당시 값으로, 현재 ENV 설정값과 다를 수 있다. Google·Kakao 과금 단위는 별도 이름이므로 기존 API 현황에서 본다.
- `operator_cap`은 같은 이름에 설정된 운영자 일·월 상한이다. ENV 상한·DB 마지막 기록 상한과 구분한다. 모든 경로에 같은 이름의 한도가 걸린다고 보장하지 않는다.
- DB 조회에 실패하면 `usage_error`를 명시하고 ENV 설정은 계속 표시한다. DB 사용량은 미계측이다. 예외 원문·API 키·토큰·환경파일 내용은 반환하지 않는다.
- 목록은 현재 프로세스 기준이다. 여러 프로세스의 설정 일치나 다른 DB의 계정 사용량 합산을 증명하지 않는다.

응답: `as_of`, `timezone=Asia/Seoul`, `usage_error`, `limits[]` (`id`, `name`, `daily`, `monthly`, `budget_timezone`, `recorded`, `operator_cap`, `adjustable`, `adjust_note`).

## 운영자 상한 조정 — 2026-10-15

- 같은 화면의 각 줄에서 운영자 상한(하루 · 월)을 정하고 지운다 — 명령 `api-cap`(저장) · `api-cap-clear`(지정 해제, ENV 로 돌림). 사유는 필수이고 운영 기록에 남는다. 다음 호출부터 적용되며 재시작이 필요 없다.
- `adjustable=true` 는 호출 전 DB 예산을 확보하는 소스(가드레일 `travel.source_budget_sources`, `travel.source_budget_shared=true`, ENV 하루 상한 > 0)뿐이다. 그 밖의 소스는 운영자 상한이 실제 호출에 걸리지 않으므로 `adjust_note` 로 이유를 싣고 조정 단추를 만들지 않는다(Open-Meteo 날씨 · 대기질 · ODsay 등). 카카오 · 구글 · OpenAI 장애 대체는 전용 예산이라 「외부 API별 현황」에서 조정한다.
- 운영자 상한은 ENV 상한보다 **낮게만** 정한다(`admin_service.api_cap` 이 작은 쪽을 쓴다). 높게 보내면 422. 올리려면 `.env.apikeys` 를 바꾸고 cs 프로젝트 서버를 다시 띄운다. 호출 기록이 없는 소스도 정할 수 있다(전에는 한 번이라도 불린 API 만 됐다).
- 근거: [2026-10-15 관리자웹앱 점검 · 수정](../records/reports/2026-10-15_1830_관리자웹앱_점검_수정.md).

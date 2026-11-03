---
type: report
title: 라이팅 문의 3절 — 날씨·실내외 후속 보호 선별 통합
status: draft
domain: travel
---

# 날씨·실내외 후속 보호 — 로컬 격리 결과

2026-10-24 23:09 KST 기준. 구현·자체 검증: 날씨 후속 child. 부모 독립 재검증·계약 소비자 검토·운영 승인은 미완료입니다.

## 결론

**읽기 컴포넌트의 날씨·실내외 후속 보호를 최소 통합했고, 기존 문의 153건과 새 시험 35건을 합친 188/188 = 100%를 실제 격리 실행했습니다. 앱의 실제 날씨 공급자 연결·API·운영 기능 완료는 아닙니다.**

| 실행 범위 | 실제 결과 |
|---|---|
| 이전 미통합 33건 직접 RED 재현 | 3/33 = 9.09%, 실패 30, exit 1 |
| 첫 최소 통합 시도 | 32/33 = 96.97%, 실패 1, exit 1 |
| 현재 범위 조회 helper로 연결한 뒤 원래 33건 | 33/33 = 100%, exit 0 |
| 기존 2절 지정 핵심 회귀만 재실행 | 153/153 = 100%, exit 0 |
| 기존 153 + 후속 33 + writer 보존/실패 종결 확인 2 | 188/188 = 100%, exit 0 |
| conversation_work 포함 확대 회귀 | 229/233 = 98.28%, 기존과 동일한 실패 4, exit 1 |

최종 두 회귀는 skip·warning 없이 실행됐습니다. 위 분모에 DB·모델·앱·전체 계약/보안 시험을 포함하지 않습니다.

## 선별 근거·변경 목록

현재 대상은 `C:/_proj/final_workspace/final_project_cs`입니다. 참고 Git 객체 `27ea017c62eb4015a552d96bb59f0b98534daaa7`는 `C:/_proj/파이널스페이스`에서 읽기만 했습니다. [2절 부분 결과](2026-10-24_travel-writing-slice2-selective-inquiry.md)의 미통합 범위와 현재 프로필 scratch의 `travel-writing-s2/unintegrated-test_inquiry_weather_followup.py`를 기준으로 선별했습니다. 통째 복사·cherry-pick·reset은 하지 않았습니다.

이번 child가 수정한 기존 코드 3개:

- `app/domains/travel_ops/components/conversation/decision_unit.py`: weather 사실 종류, 단일 weather/outdoor의 null query, 유효한 날짜 scope, 최상위 읽기의 reads 보완. 명시/직전 reference를 보존합니다. 기존 시간 기준·변경/조건 보호 로직은 유지합니다.
- `.../conversation/fact_context.py`: 단일 weather/outdoor를 기존 명시 대상·직전 focus 검증에 연결합니다. 범위 질문은 기존 schedule 범위 소유자가 처리합니다.
- `.../conversation/read_requests.py`: 주입된 기상 조회 결과를 기존 공통 writer에 연결합니다. 현재 날씨의 명시 목적지는 유지하고 시각만 now로 조회합니다. 직전 대상이 만료·다른 판이면 모델 추측·화면 선택으로 조회하지 않습니다. 실내외 단일 조회는 등록 분류만 읽습니다.

신규 코드·시험:

- `.../conversation/weather_read.py`: 좌표의 유한수·범위·bool 배제, 실제 0 강수값 보존, 예보 시간·출처·확인시각 검증, 소스 부재/실패/예외의 명시적 오류 코드. 예외 로그에는 예외 종류만 남기며 성공 예보로 삼키지 않습니다.
- `tests/unit/travel/test_inquiry_weather_followup.py`: 이전 33건을 그대로 도입하고 scope·판·원래 request·성공/실패 종결 보존 확인 2건을 추가했습니다. 합성 자료와 결정론적 provider만 사용합니다. `saved_edit`는 기존 focus 입력 형태를 시험하는 이름일 뿐 저장 편집 실행기를 구현했다는 뜻이 아닙니다.

기상 조회 실패는 forecasts의 개별 오류를 그대로 남기고 질문에 `weather_forecast_incomplete`, writer에 failed/partial로 전달합니다. 실제 source가 없으면 `weather_source_unavailable`이며 맑음·성공으로 만들지 않습니다. 단일 실패 조회는 후속 focus를 만들지 않습니다. 원래 request는 계산·보정된 대상으로 덮지 않으며 기존 response_scope는 그대로 전달합니다.

## 현재 구현과 참고 코드의 차이

참고 코드의 `schedule_query.matching`은 현재 checkout에 없습니다. 첫 GREEN 시도에서 이 부재가 한 실패로 드러났습니다. 현재 `schedule_query.reply("schedule", ...)`가 검증된 범위에 대해 내는 `item_ids`로 대상을 연결했습니다. `schedule_query.py`를 바꾸거나 없는 helper·chat_edit 의존성을 가짜로 만들지 않았습니다.

**현재 `trip_messages.py`의 호출자는 `weather_lookup`를 주입하지 않습니다.** 이번 승인 범위에서 해당 앱 조립·API·인프라 공급자 연결을 추가하지 않았습니다. 따라서 실제 앱 경로는 weather 질문에 확인 불가를 명시하는 상태이며, 주입 provider를 사용한 로컬 unit 통과를 실서비스 예보 조회 완료로 확대하면 안 됩니다. 실제 공급자 연결은 부모의 별도 범위 판정·시험이 필요합니다.

`time_anchor.py`·`trip_messages.py`는 시작 백업과 SHA256이 동일합니다. 공통 writer `components/response/writing.py`는 이번 child가 수정하지 않았습니다. 다만 동시 다른 작업에서 빈 question id·unresolved 성공 종결 거부 검사가 추가돼 시작 백업과 SHA256이 달라졌습니다. 그 변경을 되돌리지 않았으며 최종 188/188은 해당 최신 writer와 함께 실행한 결과입니다. intake·trip_api·watch·Controller·TeamResult·배포 파일은 이번 child가 수정하지 않았습니다.

## 백업·실행 증거

시작 전 기존 dirty 파일별 백업·SHA256:

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s3-weather/backup/`

[manifest](../evidence/2026-10-24_travel-writing-slice3-weather/manifest.json)은 변경 대상 외에도 time_anchor·trip_messages·writer의 시작 상태를 보존합니다. [slice3-only.diff](../evidence/2026-10-24_travel-writing-slice3-weather/slice3-only.diff)는 이 child 시작 백업 기준이며 기존 dirty 전체를 이번 성과로 세지 않습니다.

[실제 로그·runner 폴더](../evidence/2026-10-24_travel-writing-slice3-weather/):

- `red-weather.log`: 실패 30/통과 3. collection 오류가 아니라 부재한 weather 모듈·인자·해석 지원의 본문 실패입니다.
- `green-weather-v1.log`: 실패 1/통과 32. 위 helper 부재를 숨기지 않은 실패 시도입니다.
- `green-weather-v2.log`: 원래 33건 통과.
- `regression-core-153.log`: 원래 지정된 12개 파일의 153건 통과.
- `regression-combined-188.log`: 원래 지정 12개 파일 + 새 시험 파일, 188건 통과.
- `regression-expanded.log`: 확대 229건 통과/4건 실패.
- `isolated-runner.py`: 실제 사용한 2절 runner 사본.

실제 실행 prefix(cwd `C:/_proj/final_workspace/final_project_cs`):

```text
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s2-run.py <고유 로그 경로> <해당 로그 첫 줄의 시험 파일들>
```

Python 3.12.15·pytest 8.4.2의 기존 프로필 scratch venv를 재사용했습니다. 추가 설치는 없습니다. runner는 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`로 DB conftest를 제외하고 앱 socket connect/connect_ex/create_connection·psycopg.connect를 차단합니다. Windows 표준 socketpair의 정확한 stdlib code object 호출만 허용하며 앱 loopback 차단과 실제 socketpair 생성도 시작 전에 확인합니다.

보조 실행에서 선택 인덱스 실수로 맨 첫 파일이 빠진 147건 통과 로그(`scratch/.../regression-153.log`)가 생겼으나 완료 근거로 사용하지 않습니다. 수정한 최종 `regression-core-153.log`는 실제 153건을 수집·실행했습니다. 대상 tracked 코드의 `git diff --check` exit 0입니다.

## 확대 실패와 미완료

확대 회귀의 4건은 2절 수정 전 baseline과 당시 확대 실행에 있던 동일한 `TeamUnavailable: mobility composition_unbound`입니다. 이번에 가짜 service binding을 만들거나 앱을 실행해 우회하지 않았습니다.

- `test_fresh_alternate_returns_real_proposal_without_mutating_read_model`
- `test_proposing_alternatives_waits_and_never_offers_original`
- `test_selecting_second_proposed_option_returns_its_proposal_once`
- `test_changed_proposed_option_is_asked_again_instead_of_silent_substitution`

남은 범위:

1. 부모의 최신 병렬 변경 포함 독립 재검증·고객용 partial 전달/진단정보 소비자 검토.
2. 실제 기상 공급자 조립·도구 예산·재시도 snapshot 및 API 호출 연결 검증. 이번은 주입 컴포넌트와 확인 불가 경계까지만 확인했습니다.
3. 현재 없는 저장 편집 실행·직접 변경 ID focus 생성은 미구현이며 이번 범위에서 도입하지 않았습니다.
4. 실제 모델 질문 추출 품질·DB·전체 contract/security·실제 웹·운영 검증.

root/cs index·log·handoff 및 공유 계약의 최종 갱신은 부모 담당으로 남겼습니다. 기존 2절 보고서는 당시 미통합 기록으로 유지했습니다. API/DB·외부 모델 호출, 앱/서비스 기동·변경, 운영 배포, 커밋·푸시는 하지 않았습니다. 이번 적용에서는 승인 거절·시간초과가 재발하지 않았습니다.

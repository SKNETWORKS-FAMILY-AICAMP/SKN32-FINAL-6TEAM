---
type: report
title: 저장된 변경 설명 — conversation 읽기 절
status: local-verified
domain: travel
---

# 변경 설명 읽기 — 로컬 구현·격리 unit 검증

2026-10-24. 담당: conversation 변경 설명 child. 독립 검토·운영 완료를 뜻하지 않습니다. [구현 전 계약](../../external/change-explanation.md).

## 결과

정상 `handle_trip_message → _try_decide → decision_unit → read_requests`에 `change_explanation` 읽기를 연결했습니다. 모델은 기존 의미 해석 호출에서 읽기 종류와 서버 제공 별칭만 고릅니다. 새 모델·쓰기 도구·업체 승인 권한은 없습니다. 실제 저장 포트는 unit의 합성 메모리 대역이며 실DB 사용은 금지했고 실행하지 않았습니다.

| 검증 범위 | 결과 |
|---|---:|
| 기존 21개 파일 문의·기상 회귀 목록 그대로 재사용 | 302/302 = 100% |
| 신규 정상 메시지 경로·안전·재전송 시험 | 29/29 = 100% |
| 결합 고유 node id, XML 프로그램 검산 | 331/331 = 100% |
| 실행 중 대상 conversation 소스·시험 SHA256 변화 | 없음 |

최종 exit 0, failure/error/skip 없음. 기존 302개 목록은 과거 `weather-wiring/regression-combined-302.log`의 실제 pytest 인자에서 `tests/` 접두로 추출했습니다. 옵션 인덱스로 잘라 목록을 잃지 않았습니다. `regression-manifest.json`에 22개 파일·실제 명령·전후 해시가 있습니다. 저장소 전체 suite·실DB·실모델·실화면·운영 검증 비율은 아닙니다.

## 구현한 읽기와 안전 경계

- `changes_of`는 기존 전후/이유에 저장 원인의 source·checked_at/confirmed_at·evidence 요약을 추가해 의미 해석기에 전달합니다. 프롬프트에서 원인 자료는 지시가 아님을 표시하고 기존 masking을 적용합니다.
- 새 `change_read.py`는 기존 TripStore의 버전·전후 항목·cause_json을 읽고, 그 버전의 case_id로만 기존 customer_cases에 SELECT 조인합니다. tenant/trip/판 SQL 조건과 customer 조건, 반환 Case tenant/customer를 확인합니다. 적용 증거는 `applied_actions[].result_ref == trip:{현재 trip}:v{해당 판}`일 때만 인정합니다. Case 상태가 resolved라는 이유만으로 적용 성공을 주장하지 않습니다.
- 원인 출처와 timezone 있는 ISO 확인 시각을 검사합니다. 여러 원인 중 하나라도 미확인이면 partial/failed입니다. 전후 이름·시각·판·저장 이유·저장 시각과 원인 확인 시각을 구분해 답합니다. 출처가 없으면 근거 없음을 명시합니다. 근거가 있는 저장판 조회 자체를 외부 기상의 현재 사실로 주장하지 않습니다.
- 명시적 변경판/항목, 현재 화면 선택, TTL·판·현재 여행 포함이 검증된 직전 focus를 구분합니다. previous의 모델 추측 별칭은 사용하지 않습니다. 불명·복수·만료·외부 항목·판변경·조회 중 버전 이동은 needs_input입니다. 최신 변경을 자동으로 고르지 않습니다.
- 변경 설명의 모호한 해석 후보는 기존 `fact_first`의 첫 사실 추정이나 업무 clarify 실행기에 보내지 않고, 대상 미정 읽기 질문으로 재질문합니다. 성공한 설명은 기존 chat_reply.focus에 현재 항목·판·시각을 보존합니다.
- 문의 작성기에 원래 read 요청·근거·판·질문별 종결을 전달하고 기존 공개 partial 투영을 그대로 사용합니다. 복합 변경 설명/체류시간과 미완료 읽기 스냅샷 복구·완료 duplicate를 정상 진입 경로에서 확인했습니다. 복구와 duplicate는 해석 모델 대역을 다시 부르지 않습니다.
- 시험의 append_version/enqueue_message/desk 변경 함수/controller 업무 포트는 호출 즉시 실패합니다. 새 읽기 SQL 대역도 SELECT 이외를 거부합니다. **이 읽기의 변경 업무·업체 승인·여행 outbox 직접 호출은 0회**입니다. 문의 Case 생성·전이는 기존 경계에서 대역으로 관찰했으므로, 코어 실제 DB 전이가 outbox를 만들지 않는다는 실DB 증거로 확대하지 않습니다. 그 기본 Case outbox 수정은 부모/다른 child 소유입니다.

## 변경 파일

- `app/domains/travel_ops/components/conversation/decision_unit.py`: 읽기 종류·별칭 schema·저장 원인 prompt·모호한 변경 설명 보호.
- `.../conversation/read_requests.py`: 변경 설명 질문별 읽기 결과를 기존 작성기에 공급.
- `.../conversation/trip_messages.py`: 정상 읽기에서 범위·판·문맥을 새 reader에 공급하는 작은 연결.
- 신규 `.../conversation/change_read.py`, `tests/unit/travel/test_change_explanation.py`.
- 신규 이 계약·보고서·[증거 폴더](../evidence/2026-10-24_change-explanation/).

수정 전 dirty 사본·SHA256은 프로필 scratch `change-explanation/before/`와 `manifest.json`에 있습니다. [child-only.diff](../evidence/2026-10-24_change-explanation/child-only.diff)는 이 시작 상태 대비입니다. time_anchor/weather_read/fact_read_retry는 시작 SHA256과 동일합니다. 공통 writer/public, trip_api, monitoring/actions/intake, root wiki/index/handoff는 수정하지 않았습니다. 기존 원문 scope·기상·공개 partial hunk를 덮지 않았습니다.

## RED/GREEN와 절차상 한계

[증거](../evidence/2026-10-24_change-explanation/)에 각 로그를 별도 보존했습니다.

- 최초 `red01.log`는 모델 대역이 실제 structured의 positional 서명을 받지 못한 fixture 결함이었습니다. 기능 RED로 세지 않습니다. 초기 `green01.log`도 이 오류 때문에 실패했습니다.
- 대역 수정 뒤 보존한 기존 decision_unit을 별도 프로세스로 로드한 `red01-valid.log`에서 읽기 미지원 실패를 재현하고 `green01-fixed.log`에서 정상 진입 통과를 확인했습니다. **최초 구현 전 유효한 RED를 확인하는 엄격한 순서는 첫 slice에서 충족하지 못했습니다.** 이를 나중 baseline 재현으로 숨기거나 완전한 TDD라고 주장하지 않습니다.
- 이후 RED02→GREEN02(직전 변경 focus), RED03→GREEN03(소유권/applied 불충분), RED04→GREEN04(후속 focus/최상위 읽기), RED05→GREEN05(원인 prompt), RED06→GREEN06b(출처·시각·모호성), RED07→GREEN07(복합 별칭·조회 중 판 이동)는 각각 실제 실패를 먼저 관측하고 구현했습니다. GREEN06 초기 회차는 기존 업무 clarify 유출로 실패했고 뒤 회차에서 해소했습니다.
- 마지막 2개 복합 읽기/스냅샷 복구 시험은 이미 구현된 동작의 추가 수용 검증이며 RED를 새로 주장하지 않습니다.

## 재실행 명령·격리

```text
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/change-explanation/regression-run.py
```

기존 Python 3.12.15/pytest 8.4.2 venv를 재사용했고 설치·requirements 변경은 없습니다. [실제 orchestration](../evidence/2026-10-24_change-explanation/regression-run.py), [실제 격리 runner](../evidence/2026-10-24_change-explanation/isolated-runner.py), [최종 로그](../evidence/2026-10-24_change-explanation/regression.log), XML·manifest·results.json을 보존했습니다. runner는 socket connect/connect_ex/create_connection 및 psycopg.connect를 차단하고 표준 Windows socketpair code object만 예외로 허용합니다. 앱 loopback 차단과 socketpair 생성도 먼저 검증합니다. root DB conftest는 confcutdir로 제외합니다. git diff --check 대상 3개 파일 exit 0입니다.

## 미완료·다음 검토

- 실모델의 자유 표현 해석 품질, 실제 DB SELECT/경합, 앱·화면·알림 채널/운영은 확인하지 않았습니다. 서버·서비스 시작, 실DB, 외부 HTTP/LLM, 배포·커밋·푸시는 실행하지 않았습니다.
- 알림 열람을 추정하지 않습니다. 알림 후 대상 없는 ‘왜 바꿨어?’는 유효한 구조화 focus/명시적 선택이 없으면 재질문합니다. 알림의 arbitrary response.followup을 인증 근거로 쓰거나 새 알림-채팅 저장 체계를 만들지 않았습니다. 기존 변경판/Case/applied 자료를 다시 읽는 절입니다.
- 기존 changes_of의 최근 판·비이동 항목 별칭 범위를 사용합니다. 삭제만 한 항목·현재판보다 오래된 변경을 자동 복구/선택해 설명하지 않고 재선택을 요청합니다. 이동 변경 전체를 새로 분류하는 확장은 하지 않았습니다.
- 새 읽기가 기존 customer 권한 API를 대체하지 않습니다. 기본 Case outbox 실동작과 부모 결합 트리 재검증, 독립 검토는 부모 소유입니다. 운영 완료와 첫 slice 엄격 TDD 완료는 주장하지 않습니다.

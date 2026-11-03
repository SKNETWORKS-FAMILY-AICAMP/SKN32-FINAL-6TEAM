---
type: report
title: 계획 읽기 기준선 복원 — D-025 순수 읽기·제안 경계
status: draft
domain: travel
---

# 계획 읽기 복원 결과

2026-10-24 22:52 KST 이후 검증. 담당: 계획 읽기 child. **부분 통합입니다. 정상 API 입구의 D-025 활성화·전체 최종 기준선·전체 라이팅 완료가 아닙니다.**

## 결과

[복원 계약](../../external/plan-reading-restoration.md)을 코드보다 먼저 작성하고, 참고 Git `7d503bfb6` / `502da503c`에서 필요한 읽기·원문 검사·제안 부분을 선별했습니다. 현재 dirty pipeline을 참고판으로 바꾸지 않았습니다.

- `pipeline.read_source(agent=…, agent_mode="on")`은 문장 안 최종 정정을 반영한 모델 계획을 기존 날짜·장소 조회로 보냅니다. 정정 전 규칙 항목을 다시 채워 넣지 않으며, 이동/조건/성향을 일정으로 끼워 넣지 않습니다.
- 원문 밖 인용 폐기, 인용의 시각 재계산, 같은 줄 규칙 시각 보충, 원문 예약번호·예약 상태 보존을 복원했습니다. `reading.agent`에 결과/사용 여부/갈래를 남깁니다.
- 모델 연결·시간 초과는 `reading_model_failed`로 드러나고 같은 모델을 줄 읽기로 재호출하지 않습니다. 답 모양 오류만 줄 읽기를 허용하며, 줄 읽기 제공자 부재·장애·잘못된 응답 모양도 성공 미리보기로 숨기지 않습니다.
- 주입한 `structured_stream`에 첫 응답·멈춤·전체 한도를 전달하고 원문 인용이 나온 줄 수를 진행으로 냅니다. 여러 길이 묶음 중 유료 경로로 넘어가면 처음부터 유료만으로 다시 읽는 reducer를 unit에서 확인했습니다. **실제 공급자 스트림/유료 호출을 실행한 것은 아닙니다.**
- `prefill.propose(review, claims=…, owners=…)`는 빈칸 담당의 제안만 반환합니다. 이미 찾은 장소·고정 일정·예약 일정은 자동 교체하지 않고 고객 값은 그대로 둡니다. **DB edit/자동 채움 적용/2회 재검사 루프는 통합하지 않았습니다.**

| 실제 로컬 검증 | 결과 |
|---|---|
| 최종 관련 unit 전체 실행 | 285/285 = 100%, 실패·skip 없음, exit 0 |
| 그중 선별 upstream 시험 | 22/22 = 100% |
| 그중 신규 TDD 시험 | 9/9 = 100% |
| 기존 고객 운영시간 시험 | 19/19 = 100% |
| 기존 dirty 백업과 규칙 읽기 출력 직접 비교 | 8/8 = 100%, 정확 일치 |

분모는 지정한 unit만입니다. 전체 프로젝트·DB·실모델·운영의 완료율이 아닙니다.

## 참고 이력과 선택 이유

| 근거 | 확인·처리 |
|---|---|
| `7d503bfb6` | D-025 통합 이해·원문 검사·빈칸 연결·먼저 채우기·905 SQL·trip_api/config 변경 묶음 확인. 이 절은 순수 읽기와 제안 경계만 선별 |
| `502da503c` | 스트리밍·멈춤·유료 전환 뒤 전체 다시 읽기·읽기 실패 계약 확인. agent reducer 및 명시적 실패 계약 복원. 공유 공급자 구현은 별도 경계 |
| 선행 `40bb97309`, `04b9c8abf`, `f510d2413`, `c0542de9e`, `c5340a125` | 끝 시각 전달·우리 장소 조회·각 팀 후보 연결 등이 선행됨. 새 읽기는 현재 로컬 조회 tail을 그대로 재사용하며 이 후보 엔진을 통째로 가져오지 않음 |
| `bb321b0cd` | `reading_prefs`→설문/제약 키 전달, assemble/planner/survey/trip_api/화면까지 의존. 성향 인용 보존과 실제 담당 설문 배선을 구분. 후자는 미통합 |
| `d618279f6` | 남은 줄 8줄 묶음/단계 상한은 `502da503c`가 대체함. 오래된 chunking 정책을 다시 활성화하지 않음 |
| `111963990`, `182b313cc` 계열 | 미정 숙소 공동 추천·예약 보호·먼저 채운 판 재검사 등 후속 의존 확인. 숙소 추천 전체를 현재 경계에 통복사하지 않고 고객 질문으로 유지 |
| `93fe02793` | 출발지 role·요청 시각 now·즉시 시작 후속과 conversation 다수 변경 확인. 별도 child와 충돌하는 conversation은 수정하지 않았으며 이 후속 전체는 미통합 |

참고 저장소 작업트리에 agent_read.py가 없어도 Git에는 구현돼 있습니다. 작업트리 부재를 미구현 근거로 쓰지 않았습니다. 10월 23일까지의 후속 로그 존재도 확인했으나 그 전체를 현재 복원 완료로 취급하지 않습니다.

## 실제 수정 파일

cs 기준:

- 신규 `app/domains/travel_ops/components/intake/{agent_read,fact_check,fragments,gaps,prefill}.py`
- 수정 `…/intake/pipeline.py`: `read_source` 해석 prefix와 agent→기존 날짜/장소 tail 연결, 보조 `_agent_booking_rows` / `_agent_rows`, 명시적 실패.
- 수정 `…/intake/review.py`: `picked_modes`에서 검증된 `llm_agent` 수단도 읽음. 기존 운영시간 dirty 변경 유지.
- 수정 `…/intake/llm_spans.py`: `spans` 목록이 없는 답을 빈 성공으로 처리하지 않는 최소 모양 검사.
- 신규 `tests/unit/travel/test_plan_reading_restoration.py`, `test_plan_reading_reference.py`.
- 신규 복원 계약·본 보고서·[실행 증거](../evidence/2026-10-24_plan-reading-restoration/).

root/index/handoff, conversation, response 작성기, trip_api/config, DB SQL, 프런트엔드는 이 child가 수정하지 않았습니다. DB 적용·서비스/앱 기동·재시작·외부 모델·운영 배포·커밋·푸시는 하지 않았습니다.

## 기존 dirty 운영시간 보존

수정 전 intake Python 29개를 현재 프로필 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-reading/`에 백업했고 `before.json`에 SHA-256을 기록했습니다. 저장소 안 `_backup`에 새 원본 백업을 만들지 않았습니다.

- 현재까지 원래 29파일 중 26파일은 바이트 해시 그대로입니다. `assemble.py`, `hours.py`, `direct_schedule.py`의 기존 dirty 변경은 통째로 동일합니다.
- pipeline의 기존 함수/클래스 53개(`read_source` 제외), review의 기존 함수 33개(`picked_modes` 제외)는 백업과 AST가 동일합니다. 따라서 고객 운영시간 `_checked_hours`·장소 변경 시 운영시간 제거·edit/restore·기존 process/view는 바뀌지 않았습니다.
- 실제 백업 모듈과 현재 모듈을 별도로 import하여 규칙 읽기 입력 8개 결과를 정확 비교했습니다. 실행 module.__file__도 [preservation.json](../evidence/2026-10-24_plan-reading-restoration/preservation.json)에 남겼습니다.
- `git diff --check`는 exit 0. 기존 LF→CRLF 경고는 있었으며 whitespace 오류는 없습니다.

## TDD·환경 실패 구분

각 로그는 [증거 폴더](../evidence/2026-10-24_plan-reading-restoration/)에 보존했습니다.

- `red1.log`: 최종 정정 upstream 시나리오가 현재 `read_source`의 agent 인자 부재로 1 fail → `green1.log` 1 pass.
- `red2.log`: 모델 실패 분류/답 모양 실패 갈래 2 fail → `green2.log` 3 pass.
- `red3.log`: 스트림 정책 미전달·줄 모델 장애를 삼키는 동작 2 fail. `green3.log`에서는 test double의 num_predict 필수 인자가 공급자의 선택 인자 계약과 달라 3 fail이 드러났습니다. fixture를 실제 선택 인자 계약으로 맞춘 `green3b.log`는 5 pass. 실패 로그를 지우지 않았습니다.
- `red4.log`: prefill 모듈 부재로 test 본문 1 fail(수집 오류 아님) → `green4.log` 6 pass.
- `reference.log`: 정확히 가져온 upstream 수단 시험이 `picked_modes`의 customer 전용 필터 때문에 1 fail/17 pass. 최소 필터 연결 뒤 GREEN.
- `red5.log`: 현재 화면 수단 어휘와 다른 transit 매핑·줄 제공자 없이 성공 처리 2 fail → `green5.log` 30 pass(추가 upstream 스트림 시험 포함).
- `red6.log`: 줄 읽기 답에 spans가 없어도 성공 처리 1 fail → 최종 GREEN에 포함.
- 최종 `final-green-after-refactor.log`: **285 pass, exit 0**, 현재 파일로 재실행.

선별 upstream 시험은 함수 본문의 기대값을 바꾸지 않았습니다. 관리 설정 활성화 시험은 실제 config/입구 미통합이므로 가져오지 않았습니다. 원래 correction 시험 helper는 새 JSON 스키마에 없는 requests-only 값을 주므로, 신규 회귀에서는 원문 근거가 있는 `pieces.kind=correction`을 넣어 최종 정정을 검증했습니다. 숙소 공동 추천/settle/실제 공급자 스트림/DB/e2e 시험은 범위 밖이며 skip 뒤 분모에서 뺀 것이 아니라 처음부터 지정하지 않았습니다.

초기 회귀의 PIL collection 오류는 기능 RED가 아닙니다. 그 뒤 `fitz`/fastapi 미설치와 conftest 차단으로 빠진 standalone 서비스 문맥 오류도 환경 문제였습니다. requirements에 고정된 Pillow 11.0.0·PyMuPDF 1.28.0·fastapi 0.116.1·python-multipart 0.0.20·PyJWT 2.13.0·pytest-asyncio 0.25.2를 기존 scratch 격리 venv에 추가하고, 현재 tests/conftest.py가 쓰는 `standalone_services()` 문맥만 runner에서 명시했습니다. 앱/팀 조립은 실행하지 않았습니다. 환경 실패 로그와 최종 성공은 별도 파일입니다.

### 실제 최종 명령

cwd: `C:/_proj/final_workspace/final_project_cs`

```text
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-reading/run.py C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-reading/final-green-after-refactor.log tests/unit/travel/test_plan_reading_reference.py tests/unit/travel/test_plan_reading_restoration.py tests/unit/travel/test_intake*.py tests/unit/travel/test_travel_response_slice1.py
```

Bash가 glob을 펼친 실제 파일 인자는 로그 첫 줄에 전부 남았습니다. runner는 socket connect/connect_ex/create_connection과 psycopg.connect를 차단하고 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider`로 DB fixture를 제외합니다. 원본 runner도 증거 폴더에 보존했습니다.

## 정확한 미완료·활성화 차단 경계

1. **현재 정상 API→process는 여전히 기존 reader입니다.** 새 경계는 명시적으로 agent를 주입한 `read_source`에서 동작합니다. trip_api의 agent 주입과 process/view의 reading.agent 공개 연결을 별도 통합해야 합니다. 단위 경계 통과를 고객 입구 복원 완료로 보고하지 않습니다.
2. `travel.intake_reader`/`travel.intake_reading` 관리 설정·공급자 배선을 통합해야 합니다. 새 모델 이름·토큰 수·타임아웃·chunk 길이 운영 기본값을 코드에 박지 않았습니다. 길이 미지정은 한 계획 한 번이며, 스트림 정책을 주입했는데 제공자가 지원하지 않으면 명시적으로 실패합니다.
3. 실제 `model_stream`/Ollama/FailoverChat와 남은 줄 스트림 구현은 아직 없으므로 **실제 멈춤 감시/유료 전환 완료가 아닙니다**. 현재는 주입 경계와 reducer만 시험했습니다.
4. `llm_agent` 저장에는 DB method 제약 확장이 필요합니다. 참고 SQL 905 내용을 확인했고 현재 migrations 하위에 `905*.sql`은 없지만, 새 SQL을 만들거나 DB에 적용하지 않았습니다. 실제 DB의 제약/번호 배정도 운영 담당 확인이 필요합니다.
5. `prefill.propose`는 호출 가능한 순수 제안 경계입니다. 정상 process의 담당 주입·제안 적용·재검증·새 판 저장·화면의 우리가 채움 표시는 연결되지 않았습니다. 자동 적용을 흉내 내어 완료 처리하지 않았습니다.
6. 성향/조건→실제 설문/제약 키(`bb321b0cd`), 숙소 공동 추천·즉시 시작 now/출발지 role 등 후속은 별도 영향 검토와 unit/DB 통합이 남았습니다. 새 공통 작성기로 계획서 최종 응답을 보내는 작업도 하지 않았습니다.

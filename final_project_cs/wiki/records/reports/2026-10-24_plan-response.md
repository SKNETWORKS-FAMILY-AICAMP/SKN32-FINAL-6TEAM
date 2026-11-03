---
type: report
title: 계획서 고객 최종 응대 — 실제 view·confirm 연결
status: draft
domain: travel
---

# 계획서 고객 응대 연결 절

2026-10-24 23:33 로컬 검증. **로컬 정상 handler 연결과 격리 unit 검증을 완료했습니다. 실DB 저장·실모델·운영 적용 완료가 아닙니다.** root wiki/index/handoff는 부모 담당이며 수정하지 않았습니다.

## 결과

- 구현 전에 [전용 계약](../../external/plan-response.md)을 작성했습니다. [공통 응대 계약](../../external/travel-response.md)의 `QuestionResult/ResponseInput/ResponseResult/write_response`를 새 `components/response/plan.py`에서 재사용합니다. 미사용 wrapper가 아니라 실제 `pipeline.view`와 등록된 `/v1/web/trip-intakes/{intake_id}/confirm`의 신규·중복 정상 반환 경로에 연결했습니다.
- review와 ready=true는 `review_required/needs_input/partial`입니다. 등록 성공으로 승격하지 않습니다. fatal·검사 장애·blocked 근거는 `failed/partial`입니다. confirmed view만으로 저장 완료를 만들지 않고 `confirmation_recorded/needs_input`으로 구분합니다.
- 실제 기존 `_create_trip`은 트랜잭션 종료 후 `_trip_view`를 읽지만, 기존 `mark_confirmed`는 별도 트랜잭션 UPDATE만 수행합니다. 이번 confirm 연결은 두 쓰기 종료 후 **소유자가 포함된 intake 상태·revision·trip 연결 재조회 + 현재 여행 소유권·내용 재조회**까지 확인해야 `registered/answered`를 작성합니다. 재조회 누락·불일치는 ValueError로 정상 성공 반환을 막으며, DB·작성 예외를 삼키거나 업무를 자동 반복하지 않습니다. 기존 예외 전달 경계는 유지했습니다.
- 중복 confirm은 기존 draft/소유권/여행 재조회를 사용하고 create·mark·모델을 다시 실행하지 않습니다. 작성 실패 뒤 같은 요청을 다시 보내는 시험에서도 create/mark는 각각 1회입니다.
- 기존 필수 응답 필드와 status·검토 자료는 그대로이며 선택 필드 `response`만 추가합니다. 새 고객 응대는 `answer/completion/question_status/execution_status` allowlist뿐입니다. 내부 scope/request/workflow/예약번호/원문/토큰/오류 상세를 새 response에 넣지 않습니다. 원래 상세 검토 화면의 원본 자료를 전면 삭제·정제하는 정책은 추가하지 않았습니다.
- 등록 본문 조립·판정·설문·고객 운영시간·승인·고정 항목은 기존 소유자의 처리를 그대로 거칩니다. 새 LLM 판단·prefill 자동 적용은 없습니다.

## 실제 검증

기존 격리 Python 3.12 venv와 `cache/scratch/plan-reading/run.py`를 재사용했습니다. socket connect/connect_ex/create_connection 및 psycopg.connect가 금지되며 명시적인 standalone_services 문맥에서만 실행했습니다. 앱·서비스를 기동하지 않았습니다.

| 최신 단일 실행 범위 | 결과 |
|---|---:|
| 전체 지정 회귀(최종 v4) | **318/318 = 100%, exit 0** |
| 그 안의 기존 요청된 회귀 | **303/303 = 100%** |
| 그 안의 이번 신규 handler/adapter 검증 | **15/15 = 100%** |
| 그 안의 기존 고객 운영시간 | **19/19 = 100%** |
| 백업 view와 동일 입력의 기존 키·값 비교 | **6/6 = 100%, exit 0** |

분리 행은 전체의 부분집합이며 합산 통과 수가 아닙니다. 과거 303 통과 기록을 더한 값이 아니라 최신 단일 실행에서 nodeid를 다시 수집·중복 검사했습니다. 전체 프로젝트/DB/운영 완료율은 아닙니다.

- 최종 [로그](../evidence/2026-10-24_plan-response/final-regression-v4.log), [nodeid·파일별 SHA256·실행 명령](../evidence/2026-10-24_plan-response/verification-v4.json), [동일 입력 호환 대조](../evidence/2026-10-24_plan-response/compatibility-v4.log).
- 최종 시험 직전/직후 선택된 소스·시험 SHA256은 모두 같았습니다. v3 실행 자체도 318 통과였지만 도중 다른 child의 `conversation/decision_unit.py`가 변경되어 wrapper 안정성 검증은 exit 1이었습니다. v3 기록을 남기고 **현재 결합 트리에서 v4를 새로 실행해 안정성까지 확인**했습니다. 그 파일을 수정·복구하지 않았습니다. v2/3/4의 수를 합산하지 않습니다.
- 실제 등록된 GET handler → 실제 pipeline.view → 실제 공통 writer, 실제 confirm handler → 실제 `_create_trip`/`_insert`/`mark_confirmed`를 실행했습니다. DB 연결·저장소·사전 draft/review 데이터 경계는 메모리 대역입니다. confirm의 실제 판정기는 유지했고 등록·표시의 보조 DB 경계만 대역으로 바꿨습니다. real DB commit/SQL 제약 보장은 아닙니다.
- 저장 실패·mark 실패·**mark 이후** 여행 재조회 실패·접수 연결 재조회 누락에서 완료 반환이 없음을 검증했습니다. 누락 입력은 기존 422 `intake_incomplete`를 유지하고 저장은 0회입니다. review_error/blocked 원값과 승인·고정·required input 스냅샷 사본 보존도 확인했습니다.
- `git diff --check` exit 0입니다. 기존 trip_api LF→CRLF 경고는 남았습니다.

### TDD·시행 오류 원본

[증거 폴더](../evidence/2026-10-24_plan-response/)에 보존했습니다.

- red1: 실제 view에 response 없음(KeyError) → green1.
- red2: fatal/검사 실패가 needs_input으로 나옴(2 assertion 실패) → green2.
- red3b: 실제 confirm이 response를 반환하지 않음(KeyError) → green3.
- red4: blocked 근거가 failed로 종결되지 않음 → green4, 최종 v4 전체 통과.
- red3은 시험 helper의 잘못된 import로 collection 오류였으며 기능 RED로 세지 않았습니다. import 수정 후 red3b가 실제 기능 실패입니다.
- 백업 diff 출력용 한 번의 `python -c`에 괄호 오타가 있었고 즉시 수정해 별도 실행했습니다. 제품 오류/시험 실패로 세지 않았습니다.

## 변경 파일·보존

cs 기준:

1. 신규 `app/domains/travel_ops/components/response/plan.py`.
2. `app/domains/travel_ops/components/intake/pipeline.py`: **view만** 기존 payload에 adapter 연결.
3. `app/domains/travel_ops/entry/trip_api.py`: **web_intake_confirm만** 부분 패치. 최신 구간을 다시 읽고 변경했으며 [백업 대비 차이](../evidence/2026-10-24_plan-response/trip-api-scoped.diff)에 이 절만 있습니다.
4. 신규 `tests/unit/travel/test_plan_response_adapter.py`, `test_plan_response_confirm.py`.
5. 신규 `wiki/external/plan-response.md`, 본 보고서, 고유 evidence 폴더.

수정 전 두 공유 파일 및 SHA256: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-response/{pipeline.py,trip_api.py,baseline.json}`. AST 비교상 기존 pipeline 함수 변경은 view뿐이며 API는 바깥 build_trip_router(중첩 본문 포함)와 web_intake_confirm뿐입니다. 기존 `_create_trip`, mark_confirmed, 등록 본문·고객 운영시간 처리 함수는 이 절 전과 같습니다. `response/writing.py`, `response/public.py`, `_web_view`, API 메시지 consumer, conversation, watch는 수정하지 않았습니다.

## 정확한 미완료·부모 후속

- DB 실적용·실제 transaction/제약·동시성·실모델·외부 HTTP는 미검증입니다. 기존 pending 905의 llm_agent 제약은 여전히 별도 승인·적용 전이며 이 절이 실DB 읽기/저장 완료를 뜻하지 않습니다.
- 별도 `/plan` 생성·등록 handler는 이번 소유 범위가 아니며 변경하지 않았습니다. confirm·검토 응대 연결을 전체 계획 생성/모든 API 연결 완료로 확대하지 않습니다.
- UI가 새 선택 response를 실제 표시하는지, 실사용 다국어·전체 승인/거래 시나리오·실서비스 에러 표시·e2e·전체 프로젝트 관문은 미검증입니다. 승인/고정 처리 함수 미변경과 선택 회귀/스냅샷 검증은 거래 승인 전체 검증을 대신하지 않습니다.
- 재조회 실패는 성공 문구를 금지하지만 기존 예외 경계를 통해 오류로 전파됩니다. 새 운영 복구 worker·자동 재시도·인프라 실패의 고객 상세 안내 정책은 추가하지 않았습니다.
- 서비스 기동/재시작/배포·커밋·푸시는 수행하지 않았습니다. 독립 검토와 부모의 최종 결합 트리 재실행·root 안내 갱신이 남습니다.

---
type: report
title: 고객 응대 소비 계약 — 완료 상태 전달·신규 사본 최소화
status: draft
domain: travel
---

# 고객 응대 소비 계약 결함 수정 절

2026-10-24 23:15 로컬 시간. 담당: 고객 소비 계약 child. 부모·웹 소비자 독립 검토는 대기입니다. 로컬 구현·격리 unit 결과이며 운영 완료가 아닙니다.

## 결론

기존 `status`·`answer`는 유지하면서 `response_status`와 순서 있는 `question_status`를 실제 작성 결과 → 저장 chat_reply → duplicate → 일반 웹 JSON/SSE에 연결했습니다. 개발 모드 꺼짐에도 partial이 남습니다. 개발 모드 켜짐에는 **신규 basis.response.scope와 questions[].request만 제외**하고 기존 근거와 나머지 신규 근거 스냅샷을 보존합니다. 작성기는 빈/공백 ID와 answered + unresolved 근거의 모순을 거부합니다.

| 검증 범위 | 실제 결과 |
|---|---|
| 기존 첫 slice 선택 파일을 최신 코드로 재실행 | 105/105 = 100%, 실패·skip 없음 |
| 기존 핵심 회귀 선택 파일을 최신 코드로 재실행 | 153/153 = 100%, 실패·skip 없음 |
| 핵심 153 + 다른 child 최신 날씨 시험 35 + 이번 소비 계약 시험 26 | 214/214 = 100%, 실패·skip 없음 |
| 수정 전 dirty writer 백업과 유효 입력 결과 전체 비교 | 8/8 = 100%, answer/more뿐 아니라 전체 dataclass 값 일치 |

105와 153은 214에 포함되는 중복 실행입니다. 합쳐 서로 다른 시험 수로 보고하지 않습니다. 최종 실행 전후 소스·선택 시험 파일 SHA256이 일치했습니다. 최종 코드의 날씨 생산자 연결과 엄격 writer가 함께 통과했으며, 이 시험 범위에서는 모순 거부 때문에 깨진 날씨 생산자가 없습니다.

## 계약·실제 연결

- [소비 계약](../../external/travel-response.md)을 구현보다 먼저 확장했습니다. 두 새 필드는 선택 사항이며 기존 응답에 완료를 추정해 넣지 않습니다.
- 공개 두 필드는 완료 enum과 질문별 종결 enum 배열뿐입니다. ID·원문·scope·evidence·target·workflow·token은 복사하지 않습니다. 잘못된 신규 상태는 ValueError로 드러내며 일반 답으로 조용히 바꾸지 않습니다.
- `trip_messages._run_decision`은 실제 basis에서 최소 상태를 뽑아 반환·chat_reply 저장 payload에 넣습니다. 같은 요청의 duplicate는 기존 choices/more/answer_web 허용 목록을 유지하면서 두 enum 필드만 검증해 전달합니다. 업무를 재실행하지 않습니다.
- `_web_view`는 dev 플래그를 적용하기 전에 상태를 투영합니다. JSON과 실제 SSE `result`는 기존 공유 `_web_message_result`를 그대로 사용합니다. SSE 처리기를 대역으로 교체하지 않았습니다.
- dev off의 basis/decision/basis_sources 제거 정책은 그대로입니다. dev on의 나머지 basis 전체를 deep-equality로 비교하고, basis.response는 scope/request만 빠진 결과와 비교했습니다. 원본 입력은 불변입니다. 기존 개발 근거를 전면 삭제하거나 정제하는 정책 변경은 없습니다.

## 정확한 변경 파일

cs 루트 기준:

- `app/domains/travel_ops/components/response/writing.py`: ID 공백 거부, answered/unresolved 모순 거부만 추가.
- `app/domains/travel_ops/components/response/public.py` 신규: 최소 상태 enum 투영·검증과 개발 basis의 신규 중복 사본 제외. 실제 호출 경로에서 사용합니다.
- `app/domains/travel_ops/entry/trip_api.py`: `_web_view`의 상태 투영·개발 basis 최소 제외 구간만 수정.
- `app/domains/travel_ops/components/conversation/trip_messages.py`: duplicate 반환, `_run_decision`의 chat_reply 저장·결과 반환 최소 구간만 수정.
- `tests/unit/travel/test_response_consumer_contract.py` 신규: 26개 격리 사례.
- `wiki/external/travel-response.md`: 선택 소비 필드·호환·공개 경계·엄격 writer 계약을 선행 추가.
- 이 보고서와 [증거 폴더](../evidence/2026-10-24_travel-response-consumer/).

`read_requests.py`, `decision_unit.py`, `fact_context.py`, `weather_read.py`는 이 child가 수정하지 않았습니다. root wiki/index/handoff, cs index/log도 수정하지 않았습니다. 동시 intake child가 같은 trip_api의 process 호출에 `agent=chat`을 추가한 hunk가 백업 대비 관측됐습니다. 이를 덮거나 이번 수정으로 집계하지 않았습니다. `consumer-only.diff`는 그 intake hunk를 제외하고, `observed-shared-files.diff`는 관측된 전체 공유 파일 차이를 구분해 보존합니다.

## TDD·검증 증거

[증거 폴더](../evidence/2026-10-24_travel-response-consumer/)의 로그는 덮어쓰지 않았습니다.

- `red-writer.log`: 4 fail(DID NOT RAISE). `green-writer.log`: 4 pass.
- `red-web.log`: 2 fail/4 pass. 이 최초 실행의 dev on에는 tuple/list 비교 fixture 차이도 있었습니다. JSON 경계에 맞게 fixture를 고친 뒤 코드 변경 전에 `red-web-v2.log`로 dev on/off 모두 response_status 누락 KeyError를 다시 확인했습니다(2 fail/4 pass). `green-web.log`: 6 pass.
- `red-duplicate.log`: 6 fail/7 pass. 실제 reducer 반환·저장과 duplicate의 상태 누락/잘못된 상태 무시를 확인했습니다. `green-duplicate.log`: 13 pass.
- 이후 writer/duplicate/legacy × dev on/off의 실제 JSON/SSE 비교, 네 종결 enum, 잘못된 내부 response를 추가 검증했습니다. 최종 `final-combined.log`: 214 pass(소비 시험 26 포함).
- `final-105.log`, `final-153.log`: 정확한 과거 선택 파일을 현재 파일로 각각 재실행했습니다. 각 로그 첫 줄에 전체 인자, 끝에 종료 코드가 있습니다.
- `writer-compatibility.json`: 수정 전 dirty 백업 writer와 현재 writer를 4종 종결 × social 유무로 전체 결과 비교했습니다.
- `final-run-manifest.json`: 최종 세 실행 전후 대상 소스·시험 SHA256 및 실제 선택 파일·종료 코드. `evidence-sha256.json`: 증거 파일 해시.
- 대상 `git diff --check` exit 0. trip_api에 Git LF→CRLF 경고만 있고 내용 오류는 없습니다.

### 재실행

cwd: `C:/_proj/final_workspace/final_project_cs`.

```
python C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-response-consumer/run_final.py
```

이 orchestration은 기존 격리 venv의 Python 3.12.15와 `travel-writing-s2-run.py`를 호출합니다. runner는 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`를 사용하고 앱 socket connect/connect_ex/create_connection와 psycopg.connect를 차단합니다. stdlib `_fallback_socketpair.__code__`가 직접 호출한 loopback 연결만 예외로 허용하며, 앱 loopback 차단과 socketpair 생성을 먼저 확인합니다. 새 의존성을 설치하지 않았습니다. 앱을 시작하지 않고 라우터 endpoint를 직접 호출하며, 저장소·인증·모델 경계만 시험 대역으로 주입했습니다.

## 백업·한계

기존 dirty 파일 사본: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-response-consumer/backup/`. `manifest.json`에 시작 SHA256을 보존했습니다. 프로젝트 내부 백업 디렉토리를 새로 만들지 않았습니다.

- 공개 enum 필드와 신규 scope/request 사본의 비노출을 합성 식별자·원문·토큰으로 확인했습니다. 기존 고객 answer 자체 및 기존 개발 basis/decision 전체를 정제하거나 안전하다고 인증한 것은 아닙니다.
- 예전 저장 chat_reply에 새 상태가 없으면 이를 조회/추정하지 않습니다. DB backfill은 없습니다.
- writer는 문장의 의미상 참/거짓이나 원문에서 질문 추출 누락까지 판단하지 않습니다. 미해결 evidence와 answered의 명시적 모순만 추가 거부합니다.
- 실제 DB·앱·외부 모델·브라우저 UI·운영 배포·전체 contract/security/suite는 검증하지 않았습니다. 서비스 시작/재시작, DB 변경, 외부 모델 호출, 커밋·푸시는 하지 않았습니다.
- 부모는 최소 공개 필드의 소비 계약과 공유 trip_messages 최소 hunk를 독립 검토해야 합니다. 추가 사용자 운영 승인 결정은 이 절에서 요청하거나 대행하지 않았습니다.

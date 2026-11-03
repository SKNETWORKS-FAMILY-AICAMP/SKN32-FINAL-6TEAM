---
type: report
title: 라이팅 2절 — 최신 문의 선별 통합의 부분 결과와 v165 쓰기 차단
status: draft
domain: travel
---

# 라이팅 2절 결과 — 부분 구현

2026-10-24 22:53 KST. 구현·자체 검증: 문의 선별 통합 child. 부모 독립 검토·운영 승인은 미완료입니다.

## 최종 결론과 확인 사항

**시간 대상 계산과 새 요청/대기 독립 처리를 현재 공통 작성기 연결에 보존 통합했습니다. v165 날씨·저장 수정 뒤 후속 보호는 미통합입니다. 전체 요청 완료·전체 제품 완료가 아닙니다.**

| 실제 실행 범위 | 결과 |
|---|---|
| 원래 1절 105건 + 이번 선별/추가 48건, 문의 핵심 회귀 | 153/153 = 100%, 실패·skip 없음 |
| conversation_work까지 넓힌 최종 회귀 | 194/198 = 97.98%, 실패 4, skip 없음 |
| 수정 전 conversation 백업으로 conversation_work 재실행 | 41/45 = 91.11%, 동일한 실패 4 |
| v165 선별 후속 시험의 통합 전 RED | 3/33 = 9.09%, 실패 30; 미통합 |

실모델·DB·웹·운영·전체 contract/security suite 검증을 이 분모에 포함하지 않습니다. 의존성 설치는 추가로 하지 않았습니다.

## 근거 커밋과 선별 범위

- 참고 저장소: `C:/_proj/파이널스페이스`의 Git 객체를 읽었습니다. 현재 대상은 `C:/_proj/final_workspace`, HEAD `efeb873a8`입니다. 참고 작업트리 전체 복사·무검토 cherry-pick·checkout·reset은 하지 않았습니다.
- `49dd6cb44dbb53f91a9b84aa1287549bc4ee2f05`: conversation의 입력 검증/지금 기준, 목적지와 조건 보호, 실행 미지원 행동 안내, 새 문의와 대기 재개 분리, retarget 억제, 문맥 보정 후 읽기 snapshot 일치만 선별했습니다. 설정·Ollama·예열·trip_api·RAG·배포·mobility는 제외했습니다.
- `011f4e7e3473838cfca0979940b3b77f1dc4c696 → af4a9723c03f7e85874bbd20aec25d75d34002e0`: 시간 기준 전용 칸·서버 계산·모델 답 대조를 선별했습니다. 현재 `read_requests`의 writer 결과 수집/최종 작성은 통째로 교체하지 않고 작은 부분 변경으로 연결했습니다.
- `27ea017c62eb4015a552d96bb59f0b98534daaa7`: 전체 conversation diff·계약·시험을 비교했습니다. 현재에는 `chat_edit.py`와 해당 편집 실행 경로가 없습니다. 저장 편집 완료 문장/직접 변경 ID/focus 기능을 흉내 내거나 intake/reopen 의존성을 임의로 끌어오지 않았습니다. weather/outdoor 읽기·만료 후 추측 금지 시험을 골라 RED를 관측했으나, 적용 도구가 사용자 승인 대기 시간 초과로 차단됐습니다. 도구는 **0 calls made**를 반환했고 해당 쓰기는 실행되지 않았습니다. 같은 쓰기를 재시도하거나 다른 도구로 우회하지 않았습니다.

## 보존한 변경과 이번 수정 파일

기존 dirty 수정이 다수인 작업트리에서 대상 conversation·관련 테스트·external 계약의 파일별 SHA256과 수정 전 사본을 먼저 보존했습니다.

백업: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s2/backup/`.
manifest: 같은 scratch의 `manifest.json`, [증거 사본](../evidence/2026-10-24_travel-writing-slice2/backup-manifest.json).

수정한 기존 코드(cs 기준):

1. `app/domains/travel_ops/components/conversation/case_dispatch.py`: 소유권 확인 뒤 완결된 새 요청만 분리. 원래 대기 업무를 실행하지 않음. 명시 목적지의 미적용 사실 안내.
2. `.../conversation/decision_unit.py`: 49dd 입력/조건/목적지 보호, 현재 시각 전달, 시간 기준 스키마/검증.
3. `.../conversation/read_requests.py`: 시간 기준 해석 결과를 기존 조회와 공통 writer에 연결. 원래 request는 보존하고 계산된 대상은 evidence/target에 별도 기록. 기준 미확정·만료·범위 밖이면 추측 대상으로 조용히 답하지 않음.
4. `.../conversation/trip_facts.py`: 기존 고객 운영시간 dirty 수정은 유지하고 retarget 인자/분기만 추가.
5. `.../conversation/trip_messages.py`: 새 문의 해석 재사용·현재 시각 전달·보정한 읽기 snapshot 대상 일치. 기존 `response_scope` 전달 유지.

신규 코드: `.../conversation/time_anchor.py` — af4a9723c의 전용 모듈을 선별 도입했습니다. 신규 회귀에서 종료시각 미등록 항목에 60분 체류를 발명하던 부분을 잡아, 확인된 시작시각만 사용하도록 최소 수정했습니다.

신규 시험 6개 파일(48개 사례): `test_decision_now_line.py`, `test_decision_unsupported_actions.py`, `test_fact_reply_no_retarget.py`, `test_time_anchor.py`, `test_inquiry_pending_isolation.py`, `test_inquiry_time_writer_preservation.py`.

계약: [travel-response.md](../../external/travel-response.md)에 실제 로컬 부분 구현·미통합 범위를 추가했습니다. 기존 승인·대기·scope·근거·원문 보존 의미는 유지합니다. 새 API 의무 입력이나 계약 버전은 만들지 않았습니다.

`components/response/writing.py`는 수정하지 않았습니다(SHA256 `363eadf2d8c5bb5c174e6b2a4beb20e0601f978f72c38a0191f761282a66dc7a`). intake/watch/trip_api/Controller/TeamResult/배포 코드는 수정하지 않았습니다. root/cs index·log·handoff는 부모 담당으로 남겼습니다. 다른 child가 만든 계획서 시험 파일은 이 child 변경에 포함하지 않습니다.

## RED → GREEN 및 실제 실행 증거

[증거 폴더](../evidence/2026-10-24_travel-writing-slice2/)에서 모든 이전 실패 로그를 보존했습니다.

- `red49.log`: 16 fail/1 pass. `green49.log`도 16 fail/1 pass인 **실패 시도**입니다. writer 때문에 read_requests hunk 적용 검사가 실패해 전체 패치가 적용되지 않았습니다. 파일별 선별 적용·수동 연결 뒤 `green49b.log`: 17 pass.
- `red-time.log`: 21 fail/1 pass. 시간 모듈은 lazy import로 각 시험 안에서 부재를 관측해 collection error로 숨기지 않았습니다. `green-time.log`: 시간 22 + 기존 writer 8 = 30 pass.
- `red-pending.log`: 4 fail. `green-pending.log`: 4 pass. 실제 resume_pending 경계에서 독립 문의 시 Controller·commit 미호출, 짧은 답·불완결 요청·타 고객 거절을 검증했습니다.
- `red-original-request.log`: 원래 질문 fact/reference/target이 계산값으로 덮인 1 fail. 원래 request를 별도로 writer에 전달해 해결했습니다.
- `red-missing-anchor.log`: 기준이 없는 previous 요청에서 모델 추측 대상으로 focus가 생기는 1 fail/1 pass. 계산 실패 시 되묻도록 수정하고 판 불일치·TTL 초과·미래 시각을 최종 회귀에서 검증했습니다.
- `red-no-invented-duration.log`: 종료시각이 없는 일정에 한 시간 체류를 만든 1 fail/4 pass. 임의 체류 기본값을 제거했습니다.
- `regression-core-v2.log`: 최종 문의 핵심 **153 pass**. `regression-final-v2.log`: 확대 **194 pass/4 fail**. 두 최종 로그 모두 앱 네트워크·DB 차단 runner를 사용했습니다.
- `red-weather.log`: 30 fail/3 pass. v165 쓰기 차단으로 GREEN이 없으며 완료 근거로 쓰지 않습니다. 미통합 시험은 제품 tests 디렉터리에 실패 상태로 남기지 않고 scratch의 `unintegrated-test_inquiry_weather_followup.py` 및 증거의 `unintegrated-weather-tests.txt`에 보존했습니다.
- `slice2-only.diff`: 이 절 시작 백업 대비 기존 파일 차이입니다. HEAD diff와 달리 기존 dirty 수정을 이번 성과로 세지 않습니다. `git diff --check`의 대상 conversation/test/계약 검사 exit 0입니다.

### 확대 회귀의 4건 실패

기존 `test_conversation_work.py`의 다음 시험은 현재 runner와 수정 전 conversation 백업 runner 모두에서 동일하게 `app/core/service_bindings.py:84 TeamUnavailable`로 실패했습니다.

- `test_fresh_alternate_returns_real_proposal_without_mutating_read_model`
- `test_proposing_alternatives_waits_and_never_offers_original`
- `test_selecting_second_proposed_option_returns_its_proposal_once`
- `test_changed_proposed_option_is_asked_again_instead_of_silent_substitution`

이들은 service binding을 설정하지 않은 격리 범위의 기존 실패이며 새 회귀로 단정하지 않습니다. 다만 실패를 분모에서 제외해 전체 GREEN이라고 보고하지 않습니다. `baseline-work.log`는 수정 전 conversation 패키지의 `__path__`를 scratch 백업으로 우선하여 실행했습니다. DB·실제 서비스 binding은 만들지 않았습니다.

### Windows 격리 runner

1절 venv(`travel-writing-s1-venv/Scripts/python.exe`, Python 3.12.15·pytest 8.4.2)를 재사용했습니다. 공통 pytest 옵션은 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`입니다. 각 로그 첫 줄에 정확한 선택 파일 목록과 마지막 줄에 exit code가 있습니다.

최초 `regression.log`는 39 fail/154 pass/16 warnings였고, 기존 runner의 전면 socket.connect 차단이 Windows asyncio의 내부 socketpair까지 막는 환경 결함이었습니다. traceback은 `socket._fallback_socketpair → csock.connect(127.0.0.1, 임시포트)`였습니다. 제품 코드로 우회하지 않았습니다.

새 scratch `travel-writing-s2-run.py`는 **호출자의 code object가 정확히 stdlib `_fallback_socketpair.__code__`인 loopback 연결만 허용**합니다. 앱의 loopback·외부 connect/connect_ex/create_connection·psycopg.connect는 계속 차단합니다. pytest 전에 앱 loopback 차단과 실제 socketpair 생성 모두 확인합니다. 일반 loopback 허용이 아닙니다. runner와 baseline wrapper의 [증거 사본](../evidence/2026-10-24_travel-writing-slice2/travel-writing-s2-run.py)을 남겼습니다.

실제 명령 prefix(cwd `C:/_proj/final_workspace/final_project_cs`):

```
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s2-run.py
```

그 뒤 로그 경로와 해당 로그 첫 줄의 시험 목록을 붙입니다. 읽기 전용 백업 재현은 동일 위치 `travel-writing-s2-baseline-run.py`를 사용합니다.

## 미완료·다음 확인

1. 승인 차단된 v165 weather/outdoor·만료 문맥 패치를 다시 승인받은 뒤 최소 통합해야 합니다. 이전 도구가 실행되지 않았으므로 weather_read·fact_context 수정이 있다고 가정하면 안 됩니다.
2. 저장 편집 후 ID 기준 완료 안내·직접 변경 focus는 현재 없는 chat_edit/edit 경로와 intake/reopen 의존성 검토가 필요합니다. 현재 범위 밖 파일을 통복사하지 않습니다.
3. 목적지/조건 보호와 현재 시각의 actual web/LLM 동작, retry/동시성 전체 경로, service binding이 있는 확대 시험은 별도 확인이 필요합니다.
4. af4a9723c의 모델 답 대조 정책은 선택 도입한 기존 정책이며 실제 모델 품질 전체 보장이 아닙니다. 날짜 범위 가장자리·복합 질문 추출 완전성의 추가 수용 기준도 부모 검토가 필요합니다.
5. 공통 작성기는 문의에만 연결된 상태입니다. 계획서·감시·실행 결과·알림 전체 구현 완료로 확대하지 않습니다.

서비스 기동·재시작, DB 변경, 외부 LLM, 운영 배포, 커밋·푸시는 하지 않았습니다.

---
type: report
title: 계획 읽기 공급자 안전 보완 — 취소·deadline·예산·PII·schema
status: draft
domain: travel
---

# 계획 읽기 공급자 안전 보완 절

2026-10-24T14:58:55Z 최종 집계. **지정 로컬 안전 결함을 수정했고, 기존 318개와 신규 안전 25개가 현재 결합 트리에서 통과했습니다. 실모델·실DB·운영 적용 완료는 아닙니다.** root wiki/index/handoff는 부모 담당이며 수정하지 않았습니다.

## 결과와 정확한 범위

| 항목 | 로컬 구현/대역 검증 | 남은 경계 |
|---|---:|---|
| 취소 상태·늦은 응답 close·추가 read 방지·비동기 close | 1/1 = 100% | 이미 블로킹 중인 실제 transport/close 강제 중단 불가 |
| 스트림 failover 절대 deadline·remaining 전달 | 1/1 = 100% | 실제 공급자/DB 지연 wall-clock 미검증 |
| 매 유료 시도 strict reserve·없음/오류 차단 | 1/1 = 100% | 실DB 예산 저장 미검증 |
| 실제 성공 backend/model provenance | 1/1 = 100% | 실모델 정체성/서버 운영 구성 미검증 |
| 자유 입력 PII 외부 전송 기본 차단 | 1/1 = 100% | 해제는 후속 사용자 확인 대상 |
| pending 905 미적용 schema 명시 실패 | 1/1 = 100% | 실제 schema 조회·migration 적용 없음 |

위 6/6은 이 절의 코드/대역 경계 분류이며 전체 제품·배포 완료율이 아닙니다.

- [공유 계약](../../external/plan-reading-restoration.md)에 안전 정책을 코드 수정보다 먼저 추가했습니다. 관리 설정은 `travel.intake_reader.external_fallback_enabled: false`입니다. 기존 다른 업무의 비스트림 `json/text/structured/see` 외부 전송 정책을 임의 차단하지 않았습니다.
- `StreamLifetime`은 collector와 transport producer가 취소 상태/응답 소유권을 공유합니다. timeout 후 획득한 응답은 읽기 전 producer가 닫으며, 이미 보유한 응답은 별도 daemon closer가 닫습니다. iterator는 producer finally에서 닫습니다. event 대역에서 늦은 Ollama/SDK 응답 close·read 0회·실제 worker 종료, 진행 중 read 종료 후 다음 read 0회, blocking close가 caller deadline을 늘리지 않음을 관찰했습니다.
- 스트림은 `min(reader max_seconds, 기존 failover total_seconds)`로 절대 deadline 하나를 만들고 모든 시도에 remaining을 전달합니다. first/stall도 remaining으로 제한합니다. gate reserve 후에도 시간을 다시 검사합니다. 새로운 모델·주소·timeout 수치를 추가하지 않았습니다.
- reader는 별도 `reader_budget`을 **매 시도마다** 확인합니다. 없음/예외/거절은 fail-closed이고 기존 global fail-open closure는 사용하지 않습니다. 조립은 같은 CallBudget/METER/cap 설정으로 엄격한 closure를 별도 생성합니다. 동일 DB 예외에서 global은 기존 True, reader는 False인 회귀도 통과했습니다.
- 성공 provenance는 실제 backend와 해당 chat.model을 담고 agent 보고가 이를 사용합니다. primary의 모델을 API 성공 모델로 잘못 보고하던 결함을 재현·수정했습니다. 직접 Ollama 성공도 경로/모델을 보고합니다.
- 이름·예약번호·구분자 없는 전화번호의 완전 비식별화를 보장할 수 없으므로 reader 외부 fallback을 기본 거부합니다. PII sentinel 3종을 user/system state에 넣은 시험은 외부 호출·예산 reserve 모두 0회입니다. 관리 설정의 정상 API에서도 로컬 실패 뒤 API 0회를 확인했습니다. 외부 허용=true는 비식별화 보장이 아니라 외부 전송 허용이며 이번에 켜지 않았습니다.
- 추가 독립 경계 점검에서 답 모양 오류 후 기존 줄 읽기의 `chat.json`이 원문을 외부로 보낼 수 있음을 확인했습니다. reader 전용 `reader_json`에 같은 차단/strict reserve를 적용했고, 직접 OpenAI 어댑터를 agent/줄 reader로 주입해 gate를 우회하는 경로도 호출 전 거부합니다. 일반 업무의 `chat.json`은 유지합니다.
- mode on/shadow에서는 모델·claim 삭제/쓰기 전에 실제 `pg_constraint`의 method 관련 CHECK를 읽는 준비 검사를 수행합니다. 알려진 양성 enum CHECK 구조·validated 상태·llm_agent 포함을 모두 요구합니다. 없음·옛 enum·음성 CHECK·미인식 형태·catalog 오류는 `reading_schema_not_ready`이며 줄 reader 성공으로 바꾸지 않습니다. status/stage의 접수 claim 및 fatal 기록은 기존대로입니다. SQL 905 파일/실DB는 변경하지 않았습니다.

## 최종 실행 결과

[verification.json](../evidence/2026-10-24_reader-provider-safety/verification.json)은 이전 318의 정확한 nodeid와 최신 실행 결과를 프로그램으로 대조했습니다. 겹치는 부분집합은 합산하지 않습니다.

| 같은 최종 단일 실행의 범위 | 결과 |
|---|---:|
| 전체 지정 24파일, 고유 nodeid 402개 | **398/402 = 99.005%, failed 4, exit 1** |
| 이전 계획 API·읽기 지정 303개 | **303/303 = 100%** |
| 이전 계획 최종 응대 포함 318개 | **318/318 = 100%** |
| 신규 안전 회귀 | **25/25 = 100%** |
| 기존 llm_failover + ollama 회귀 | **55/59 = 93.2203%, failed 4** |
| 기존 고객 운영시간(부분집합) | **19/19 = 100%** |

나머지 네 건은 기존 `test_http_a_closed_port_goes_to_the_api_quickly`, `test_http_a_slow_server_times_out_and_goes_to_the_api`, `test_http_a_503_server_is_retried_once_then_goes_to_the_api`, `test_http_a_healthy_server_answers_locally_and_the_api_is_not_touched`입니다. 최종 runner는 **bind까지 차단**하므로 HTTP 서버가 시작되기 전에 격리 오류로 실패했습니다. 네 실패와 전체 분모를 그대로 유지했고, 소켓 허용/skip 처리로 통과를 만들지 않았습니다. 전체 suite GREEN이라고 하지 않습니다.

부모 통합 prep에서 보고된 `test_failover_stream_restarts_on_api_and_masks_input` 실패는 기존 시험 fixture에 **명시적 reader_budget + 외부 허용=true**를 주입하여 해소했습니다. 제품 gate는 완화하지 않았으며 최종 402 실행에서 해당 nodeid가 passed입니다. 부모가 별도 보고한 5개 DB shared-cache fixture 오류는 이 절의 실행 목록에 없으므로 해결했다고 주장하지 않습니다.

- 최종 [pytest 원본 로그](../evidence/2026-10-24_reader-provider-safety/final-pytest.log), [JUnit](../evidence/2026-10-24_reader-provider-safety/final-result.xml), [node 결과](../evidence/2026-10-24_reader-provider-safety/final-node-results.json).
- 최종 실행의 **모든 app/config 및 선택 시험 파일 hash는 전후 동일**하며 collection 오류·deselection은 0개입니다. 전체 1296파일 snapshot에서는 실행 목록 밖 `tests/unit/travel/test_plan_generation_response.py`가 다른 작업으로 변경되어 global `tree_unchanged_during_run=false`를 그대로 남겼습니다. 자체 `scope_unchanged_during_run=true`는 이 절의 선택 범위만 뜻합니다. 앞 14:54 실행은 1295개 hash가 동일했지만 그 뒤 sibling의 `response/plan.py`와 `trip_api.py`가 바뀌어 14:58에 다시 실행했습니다. 어느 sibling 변경도 복구하거나 자신의 변경으로 집계하지 않았습니다. 부모 전체 통합 완료/전역 안정 증거는 아니며 prep runner의 `final_stable_evidence=false`도 그대로 보존합니다.
- `git diff --check` 지정 파일 exit 0입니다. 기존 LF→CRLF 경고는 남았습니다.

### 실행 명령

cwd `C:/_proj/final_workspace/final_project_cs`:

```text
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/reader-safety/final_verify.py
```

wrapper는 이전 318 manifest + 신규 안전 파일 + 기존 공급자 2파일을 중복 제거하고 부모의 `writing-integration-prep/run_integrated.py`를 새 manifest로 실행합니다. 실제 명령·runner hash·합성 unit 설정·정확한 stdlib socketpair 예외·app socket/psycopg/bind 차단 preflight는 [runner identity](../evidence/2026-10-24_reader-provider-safety/final-runner-identity.json)에 있습니다. 앱/DB/모델 서비스를 시작하지 않았습니다.

## TDD 증거·시행 오류

[증거 폴더](../evidence/2026-10-24_reader-provider-safety/)에 실패 로그를 덮지 않고 보존했습니다.

- red1: 늦은 Ollama read, 늦은 SDK 응답 누수, 동기 close deadline 초과 3건 → green1.
- red2: backend별 10초 재부여/만료 후 두 번째 호출 2건 → green2.
- red3c: 유료 2회/strict reserve 0회 재현 → green3. red3/red3b에는 시험의 잘못된 `status` 인자/`rate_limit` reason 사용이 포함되어 기능 RED로 세지 않았습니다. 재시도용 실제 reason `429`로 고친 red3c가 유효한 재현입니다. gate 없음/예외 및 조립 strict closure 부재는 red3에서 독립 재현했습니다.
- red4: 실제 API 성공인데 local-primary 모델 보고 → green4.
- red5: PII sentinel 외부 호출 발생 3건 → green5.
- red6: schema 검사 없이 review/모델 호출 5건 → green6.
- red7: 모양 오류 후 legacy line reader의 무제한 외부 호출 → green7.
- red8: 직접 공급자 성공 provenance 누락 → green8. 뒤 red9의 직접 OpenAI chunk `api_only` 비지원도 보존했습니다. 직접 API reader 자체에 예산 gate가 없는 더 근본적인 경계를 red10/red10b로 재현하여 reader 사용을 거부했습니다. 직접 API reader multi-chunk 지원을 구현했다고 주장하지 않습니다. transport 어댑터 단독 SDK 대역 시험은 기존대로 유지합니다.
- 최종 current tree에서 신규 25개와 이전 318개 모두 통과했습니다. 앞 399개 체크포인트는 이후 테스트 추가 전 기록이며 최종 402와 합산하지 않습니다.

## 변경 파일·보존

- `app/infrastructure/model_stream.py`, `ollama_chat.py`, `llm_failover.py`.
- `app/composition.py`: strict reader 예산 closure 등록 최소 변경.
- `app/domains/travel_ops/components/intake/agent_read.py`, `pipeline.py`: provenance·reader 정책·schema readiness/줄 reader 경계.
- `config/guardrails.yaml`: 외부 fallback false만 추가.
- 신규 `tests/unit/travel/test_reader_provider_safety.py`; 기존 `test_plan_reading_api_activation.py`의 catalog 양성 대역, `test_plan_reading_provider_stream.py`의 명시적 reader gate/외부 허용 fixture 보완.
- 공유 계약, 본 고유 보고서, 고유 evidence 폴더. root 안내·API handler·다른 child 파일은 수정하지 않았습니다.

수정 전 주 대상 8파일은 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/reader-safety/before/`에 보존했습니다. AST 비교상 pipeline 기존 정의 변경은 `process/read_source`뿐이며 `view`·등록/고객 편집/confirm 함수는 이 절 전과 같습니다. 두 공급자의 기존 nonstream 메서드 본문은 동일합니다. `_run/_record/wrap_from_settings`의 공통 변경은 위 회귀로 확인했습니다. 상세는 verification의 `ast_changes_since_child_backup`입니다.

## 남은 한계·확인 필요

1. 실제 transport의 이미 진행 중인 acquisition/read/close를 Python에서 강제 중단하지 않습니다. 반환하지 않으면 daemon과 자원이 남을 수 있습니다. 정상 반환/close 완료를 전제로 하는 수명 보장이지 서버 측 생성 취소 보장이 아닙니다. 임의 스레드 kill은 사용하지 않았습니다.
2. 기존 줄 reader_json의 진행 중인 비스트림 호출과 동기 예산 reserve DB 작업은 기존 driver timeout에 의존합니다. 다음 시도는 deadline으로 막지만, 실제 DB 지연까지 포함한 엄격한 caller wall-clock 상한은 이번 대역 검증으로 보장하지 않습니다.
3. schema 검사는 알려진 PostgreSQL method CHECK 표현을 엄격히 인정하는 fail-closed 점검입니다. 의미상 동등하나 다른 표현도 거부할 수 있으며 실제 환경 확인 후 조정해야 합니다. 다른 DB 제약/권한/동시 DDL까지 검증하는 저장 성공 보증은 아닙니다. **DB 실조회·pending 905 적용은 하지 않았습니다.**
4. 외부 fallback 해제는 **후속 사용자 확인 필요**입니다. 이름/예약번호/system state까지 완전 마스킹된다는 주장을 하지 않습니다. 운영 모델·예산/timeout 환경값·실제 provider 수용성도 미검증입니다.
5. 실모델/DB/외부 HTTP·서비스 시작/재시작·배포·커밋·푸시·UI/e2e·전체 프로젝트/부모 통합 관문은 수행하지 않았습니다. 부모의 최종 전체 범위 재실행과 root 인계가 남습니다.

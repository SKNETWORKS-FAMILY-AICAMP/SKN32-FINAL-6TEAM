---
type: report
title: L03 계획 읽기 reader 안전 — role-manager fb291b33 위 이식 후보
status: draft
domain: travel
---

# L03 계획 읽기 reader 안전 — role-manager 이식 후보 (staged, push 안 함)

**결론.** role-manager `fb291b33957a63d9b2e1bbcd7bfe2e1b687d933b` 위에 L03 을 staged 후보로 만들었다. 계획서 원문 읽기만 유료 대체가 기본 차단되고, 채팅 해석 · 채팅 「넣기」 · 감시 분류 계획의 넘김은 그대로다. 빠른 관문 `tests/unit` + `eval/tests` 9073/9073 = 100% 통과(skip 173, 실패 0). push · x600 · 로컬 서빙 변경 없음. 실모델 · 유료 호출 0회.

- 후보 트리: `cache/scratch/port-l03-20261026-071725/rm2` (detached fb291b33, index staged), tree `cf3bc8ad91f959cff7cfe99642593abf0f3c65c1`
- patch: `port-l03.patch` sha256 `419645a41bfc19191a2c35689f22eca9dee70607d144edacdf0e4906a2d02d08` (15파일 +1169 −108), 커밋 문안 `COMMIT_MSG.txt`
- 출처: `port/writer-on-develop` 4f565ffe2(묶음 2), 보고서 [2026-10-24_reader-provider-safety](2026-10-24_reader-provider-safety.md) · [2026-10-25_reader-stream-policy-omission-tdd](2026-10-25_reader-stream-policy-omission-tdd.md), 감사 [2026-10-26_로컬전용코드_vs_role-manager_감사](2026-10-26_로컬전용코드_vs_role-manager_감사.md) L03

## 계약 확인과 결정 (Codex CLI `codex exec`, text-only 2회)

| # | 질문 | 결정 | 근거 |
|---|---|---|---|
| 1 | 채팅 해석의 유료 넘김 | **유지**(바꾸지 않음) | `llm-failover.md` 표 「채팅 결정 단위 → 넘김 예」 · §6 가린 글 · §7 일반 예산 fail-open |
| 2 | 계획 읽기 유료 넘김 | **기본 차단**(`travel.intake_reader.external_fallback_enabled: false`). 켜기는 사용자 결정 | 로컬 안전 계약: 원문 이름 · 예약번호 · 구분자 없는 전화번호는 다 가려지지 않는다. D-025 의 「유료가 처음부터 읽는다」와 충돌 → D-025 · `llm-failover.md` 에 날짜 붙은 주석(7-1)으로 정리 |
| 3 | 채팅 「넣기」(`trip_desk._read_plan` → `agent_read.read`) | **채팅 계약 유지** — `purpose="chat_add"` 를 명시, 기본 `purpose="intake"` 는 엄격 | rm 은 스트림 없이 부르므로 묶음의 `validate_reader` 그대로면 x600 에서 `ReaderPolicyError` → `chat_edit._read_adds` 가 삼켜 한 곳 넣기로 조용히 떨어진다(port 가지에도 같은 잠복 결함 — x600 처럼 `FailoverChat` 일 때만 드러남) |
| 4 | rm fb291b33 감시 분류 계획(`feedback._ollama_structured` → `FailoverChat.structured_stream`) | **기존 넘김 유지** | 묶음은 `structured_stream`/`json_stream` 자체를 reader 로 바꿨다 → 감시 계획의 유료 넘김까지 막힌다. 그래서 reader 정책을 새 입구 `reader_structured_stream` · `reader_json_stream` · `reader_json` 으로 옮기고 일반 메서드는 rm 과 같게 뒀다. Codex 2차: 「타당」 |
| 5 | 묶음 3(날짜 인용 `anyOf`) | **뺐다 → L05** | Codex 1차는 포함, 2차 리뷰 P1: 스키마 enum 에 원문 줄이 실려 `masked(user)` 밖으로 유료에 나간다(채팅 「넣기」는 일반 넘김이라 직접 해당). 감사 L05 행도 「후보 묶음 3·9」. L05 이식 때 enum 을 유료 경로에서 빼야 한다 |
| 6 | 905 스키마 준비 검사 `_require_reader_schema` | 뺐다 | x600 DB 적용 · CHECK 표현 미확인 — 맞지 않으면 모든 계획 읽기가 `reading_schema_not_ready` |
| 7 | Ollama `done_reason` · native tokenizer | 뺐다 → L04 | 감사 L04 범위 |
| 8 | `model_stream.collect` 완료 통지 순서 | **고쳤다** | Codex 2차 P2: 응답 close 가 막히면 다 받은 답도 stall 오류. 완료를 먼저 알리고 닫는다 |
| 9 | `wiki/external/plan-reading-restoration.md` 저장소 추가 | 하지 않음(되돌릴 수 있음) | 링크 대상 보고서가 저장소에 없다. 대신 `llm-failover.md` 7-1 · D-025 주석 |

## hunk (fb291b33 대비)

- `app/infrastructure/llm_failover.py` — `_reader_attempt` contextvar(OpenAI SDK 시도마다 reader 예산 · 남은 시한), `_Backend.reader_budget`, `_run(deadline, reader, reader_external)`: reader 면 API 경로 `reader_external_disabled` 건너뜀 · 일반 예산 안 씀 · 시도마다 strict 예약 · 절대 시한, `_record` 에 실제 model, 새 `reader_json` · `reader_json_stream` · `reader_structured_stream`, `register_reader_budget_provider`, `wrap_from_settings` 가 reader_budget 을 붙임, OpenAI 스트림 `StreamLifetime`. `json_stream` · `structured_stream` · `structured_stream_validated` · `_streaming`(rm 53dea261 예열) 본문은 rm 그대로(문서 줄만).
- `app/infrastructure/model_stream.py` — `StreamLifetime`, 시한 · 취소 · close 를 daemon 으로, 완료 통지 먼저.
- `app/infrastructure/ollama_chat.py` — `_stream` 의 `StreamLifetime`, `reader_provenance`. rm 의 `wait_when_cold` · `structured_stream_validated` · `num_ctx` 는 그대로.
- `app/composition.py` — `_llm_failover_budget(fail_closed=)`, `_llm_reader_budget`, 등록에 rm 53dea261 `register_warm_starter` 와 함께.
- `intake/agent_read.py` — `ReaderPolicyError` · `validate_reader` · `READ_PURPOSES`, `read(external_fallback_enabled, purpose)`: 정책 wrapper 는 `reader_structured_stream` 으로만, provenance model.
- `intake/llm_spans.py` — 정책 wrapper 는 `reader_json_stream` · `reader_json` 으로만.
- `intake/pipeline.py` — `agent_reader_config` 에 외부 허용(가드레일 → 관리 콘솔), `read_source` 전달, `ReaderPolicyError` → `reading_model_failed`.
- `conversation/trip_desk.py` — `purpose="chat_add"` 한 줄.
- `config/guardrails.yaml` — `travel.intake_reader.external_fallback_enabled: false`.
- wiki — `final_project_cs/wiki/external/llm-failover.md`(표 한 칸 · 7-1), `wiki/decisions/D-025-plan-reading-model-understands.md`(날짜 주석 한 줄).

## 우회 없음 증명 시험 (전부 가짜 모델 · HTTP/DB 0)

`tests/unit/infrastructure/test_reader_policy_no_bypass.py`(신규, rm 경로):
- reader 입구 4종(`reader_json_stream` · `reader_structured_stream` · api_only · `reader_json`) 기본: 유료 · 일반 예산 · reader 예산 0회
- 식은 primary(rm 53dea261 `ModelNotLoaded` + 뒤 예열)도 유료 0회
- 켬: 다시 시도마다 strict 예약(일반 예산 0), 두 번째 예약 거부면 유료 다시 시도 없음, 유료로 가는 글은 가림
- 채팅 해석 `structured_stream_validated`: 가린 글로 유료 · 일반 예산 · strict 0 / 식은 primary 도 유료
- 일반 `structured` · `json` · `structured_stream` · `json_stream`: 기존 넘김
- 스트림 없는 정책 wrapper → `reader_stream_required`, reader 입구 없는 wrapper → `reader_stream_entry_missing`, `OpenAIChat` 직접 → `reader_unbudgeted_external`
- 줄 읽기 비스트림 · 스트림, 에이전트 스트림이 reader 입구로만 가는지(`current_path().op`)
- `__getattr__` 위임, 알 수 없는 purpose 거부, 실패 뒤 contextvar 비움, 동시 reader · 채팅 스레드 격리
- 채팅 「넣기」(`TripDesk._read_plan`): 가린 글로 유료 · 스키마에 원문 없음 · strict 0
- 감시 분류 계획(`feedback._ollama_structured`, fb291b33): 유료 넘김 유지
- 막힌 close 가 완료된 답을 stall 로 바꾸지 않음
`tests/unit/infrastructure/test_reader_provider_integration.py`(port, reader 입구 이름으로 맞춤): 늦은 응답 close · read 0, 공유 시한, SDK 다시 묻기 예약, gate 없음/예외, 조립 fail-closed, PII sentinel 3종, 진행 중 read 종료.
`tests/unit/travel/test_reader_stream_policy_required.py`(로컬 7개를 rm 판으로): rm `read_source` 는 스트림 정책을 가드레일로 채우므로 「명시 실패」 대신 reader 입구만 · 유료/예산 0 을 고정. `test_intake_reading_stream.py`: 팀 시험은 그대로, 기본 차단 · 명시 허용 짝 2개 추가.

## TDD · 관문

| 실행 | 결과 | 증거(`port-l03-20261026-071725/ev/`) |
|---|---:|---|
| RED, af608588 위(새 시험) | 48 failed / 68 | `red.log` · `red.xml` |
| RED, fb291b33 기준 트리(같은 상대경로로 잠시 복사 후 삭제) | 62 failed / 91 | `red-fb291.log` · `red-fb291.xml` |
| RED, Codex P2(port 원판 `model_stream`) | 1 failed / 1 (stall) | `red-p2.log` |
| GREEN, 대상 시험 + `test_llm_failover` · `test_chat_edit_reader` | 143/147, 실패 4 = `test_http_*`(runner 가 bind 차단; fast 관문에선 deselect) | `green3.log` · `green3.xml` |
| **빠른 관문** `tests/unit eval/tests -m "not live and not db and not slow"` | **9073/9073 = 100%**, skip 173, deselect 646, 실패 0 · 오류 0 | `gate-unit-cand.xml` sha256 `ab2643b4…7e83303` · `.log` |
| 전체 수집(e2e · integration · scenario 포함) 후보 vs 기준 | 실패+오류 1924 = 1924, 집합 동일(모두 DB 차단), 새 58 nodeid 전부 통과 | `gate-cand.xml` · `gate-base.xml` |
| ruff `--select F,E9`(바뀐 py) | 통과 | — |

runner `run_isolated.py`(socket connect/bind/listen · psycopg 차단, stdlib socketpair 만 예외, 환경변수 `PORTL03_ROOT`, 첫 줄에 root 출력), venv `date_risk_env_312`, `-p pytest_asyncio.plugin`.

## x600 동작 변화

- **바뀜**: 계획 담기 읽기(`agent_read` · `llm_spans`)에서 로컬 E4B 가 멈추거나 실패하거나 식어 있으면, 지금은 gpt-6-luna 가 처음부터 다시 읽지만 이식 뒤에는 유료로 넘기지 않고 「읽기 실패」(`reading_model_failed`, 다시 보내기)로 끝난다. 사유는 `current_path().reasons` 의 `reader_external_disabled`.
- **그대로**: 채팅 해석, 채팅 「넣기」, 감시 분류 계획, 번역 · 분류 · 후보 이유 등 일반 넘김(가린 글 · 일반 예산), 식은 모델 뒤 예열(53dea261), `num_ctx`(539cef63).
- 위험: x600 에서 E4B 가 자주 식거나 느리면 계획 읽기 실패가 늘 수 있다. 되돌리기는 관리 콘솔 `travel.intake_reader.external_fallback_enabled=true`(사용자 결정 필요).

## 남은 것

- 실 E4B · x600 확인 안 함(lease 0회). push 전 부모가 diff · XML 재확인.
- 묶음 3 은 L05 에서 enum 유료 노출을 해결한 뒤 이식. 905 검사 · L04 는 별도.
- `plan-reading-restoration.md` 저장소 반영 여부 미정.

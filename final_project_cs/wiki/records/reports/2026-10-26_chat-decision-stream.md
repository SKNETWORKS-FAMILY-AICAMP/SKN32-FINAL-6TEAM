# 2026-10-26 채팅 해석도 「답 조각 5초 끊김」 감시로 넘긴다 — 고정 9초 대기 폐지

- 작성: 2026-10-26 (KST), Claude Opus 하위 작업자. 사용자 승인: 「채팅 해석(`decision_unit.decide` → `chat.structured`)도 계획 읽기처럼 답 조각이 5초 넘게 끊기면 넘기는 방식으로」.
- 기준: role-manager `d3d0a063`(부모 376f2a67 — U01 · 전부과거 접수 가드 · extras 스위치). 커밋·푸시·x600 배포·로컬 서빙 교체는 하지 않았다(부모 몫).

## 결론

1. 채팅 해석은 이제 로컬 9초(`llm_failover_primary_timeout_seconds`) 고정 대기가 아니라 **답을 조금씩 받으며** 첫 조각 · 조각 사이 · 맨 위 상한을 본다.
   값은 가드레일 `travel.chat_decision_stream`(first_token_seconds 8 · stall_seconds 5 · max_seconds 15, 근거는 그 주석).
2. 구조화 답은 그대로다 — Ollama `format` = 해석 스키마, 유료는 엄격 `json_schema`. 받은 답은 경로 안에서 스키마 검사(`validate_structured`)와
   근거 검사(`edit_intent.validate`)를 거친다. 틀리면 그 한 호출만 다음 경로로 넘기고 서킷에는 세지 않는다(기존 `structured_validated` 와 같다).
3. 넘김 계약 그대로 — 끊기면 받다 만 답을 버리고 유료가 처음부터 다시 답한다. 끝내 못 답하면 `DecisionFailed`.
   **고정 대기 호출로 조용히 다시 부르지 않는다.** 로컬 모델이 안 올라와 있으면 곧바로 다음 경로(계획 읽기와 같다).
4. 실 E4B 3회: 세 번 모두 **같은 원출력 · 같은 결정**. 지시문 캐시가 없던 첫 호출은 12.0초 걸렸다 — 예전 9초 고정이었다면 유료로 넘어갔을 정상 답이다.

## 바꾼 것

| 파일 | 내용 |
|---|---|
| `app/infrastructure/ollama_chat.py` | `OllamaChat.structured_stream_validated` — `structured_stream`(format=스키마) → `validate_structured` → `validate_content` |
| `app/infrastructure/llm_failover.py` | `OpenAIChat.structured_stream_validated`(같은 검사) · `FailoverChat.structured_stream_validated`(`_run("structured_stream", _streaming(...))`). ☆이 메서드가 없으면 `FailoverChat.__getattr__` 이 첫 Ollama 의 것을 돌려 **넘김 없이 로컬로만** 갔다(RED 에서 확인) |
| `components/conversation/decision_unit.py` | `decide(..., stream=None)` — `stream` 이 있고 모델이 `structured_stream_validated` 를 가지면 그것으로. 없으면(다른 호출자 · 평가 스크립트 · 시험 대역) 지금 그대로 |
| `components/conversation/trip_messages.py` | `_try_decide` 가 가드레일 `travel.chat_decision_stream.*` 를 읽어 넘긴다(없는 키는 `ConfigError` — 조용히 넘기지 않음) |
| `config/guardrails.yaml` | `travel.chat_decision_stream` 새 항목 + 출처 주석 |
| `wiki/external/llm-failover.md` | 「시간」 절에 계약 한 줄 |
| `tests/unit/travel/test_chat_decision_stream.py` | 새 시험 15건(스키마 동일성은 고정 대기 호출이 받는 스키마와 비교 · Ollama 대역은 완료 표시 줄을 준다 — v9 계열 계약과 공통) |

## 설정값과 근거

| 키 | 값 | 근거 |
|---|---|---|
| `first_token_seconds` | 8 | 첫 조각 실측 0.9초(지시문 캐시 있음) · 3.5초(없음), x600 지시문 읽기 약 2초(2026-10-14 보고서). 두 배 넘게 두되 예전 9초보다 짧게 — 죽었거나 막힌 로컬을 예전보다 늦게 알지 않는다 |
| `stall_seconds` | 5 | 사용자 승인 값. 조각 사이 실측 최대 0.22초(계획 읽기 0.17~0.7초) |
| `max_seconds` | 15 | = 고객 응답 SLA `llm_failover_total_seconds`. 정상 답 실측 최대 12.0초(로컬) · 5.1~7.3초(x600) · 8.9초(로컬, 10-26 앞 보고서)를 끊지 않는다 |

### 고객 응답 SLA(15초)와의 관계 — 기본안(되돌릴 수 있음)

- 정상 답은 15초 안에 로컬로 끝난다. 예전에는 9초를 넘긴 정상 답이 유료로 넘어가 첫 턴 20초가 됐다(x600, 미확인 추정).
- 로컬이 상한 15초를 다 쓰고 넘어가는 최악은 15초 + 유료(실측 2~3초 · 한도 `llm_failover_api_timeout_seconds` 8초)라 SLA 를 넘는다.
  예전 최악(9초 + 8초 = 17초)도 넘었다. 넘김 장치의 15초는 다시 시도(429 · 5xx) 판단에만 쓰는 목표값이고 강제로 끊지 않는다 — 이 동작은 바꾸지 않았다.
- 대안(결정 필요 시): `max_seconds` 12 — 로컬 최악 + 유료 실측 ≈ 15초, 대신 지시문 캐시 없는 로컬 정상 답(12.0초)을 끊을 수 있다.

## 검증

- RED(구현 전): 새 시험 14/15 실패 — `decide() got an unexpected keyword argument 'stream'` · 가드레일 키 없음 · `structured_stream_validated` 없음,
  넘김 시험은 `FailoverChat` 이 첫 Ollama 로 새어 유료 답 대신 로컬 답/정지가 그대로 올라왔다. 통과 1건은 「설정 없으면 기존 호출」(기존 동작).
- GREEN: 빠른 관문 tests/architecture · contract · unit · security(`not live and not db and not slow`, 네트워크 · DB 차단 runner) **9354 통과 · 실패 0**(기준 d3d0a063 같은 runner 9339 + 새 15, 빠진 nodeid 0), ruff F/E9 통과.
  (앞서 376f2a67 위에서도 9326 통과 · 실패 0 = 9311 + 15.) RED 는 d3d0a063 기준 트리에서 다시 확인했다(14/15 실패).
- 로컬 live v9 사본(`integ-v9-20261026-025943/source` 읽기 전용 → 작업자 사본)에 같은 변경: 새 15건 통과, 빠른 관문 실패 · 오류 33건은 **v9 기준 사본과 nodeid 까지 같다**(새 실패 0 — 사본에 없는 `.env.apikeys.example` · `acop_composer` · `wiki/records/evidence` 등 스냅숏 공백과 v9 계열 시험 대역의 `llm_failover_daily_cap` 누락). v9 는 계획 읽기 쪽이 다른 계열(`reader` 예산 · `deadline`)이라 채팅 넘김은 `reader` 없이 기존 `_run` 을 쓴다.
- 실 E4B(tripilot-pointer:e4b-ft · 127.0.0.1:11434 · ctx 8192 · 넘김 없음 · 유료 호출 0) 「실내를 야외로 바꿔줘」(x600 trip 40b3f9f0 v1 모양 · 합성 id):

| 회 | 방식 | 걸린 시간 | 첫 조각 | 조각 사이 최대 | 결정 |
|---|---|---|---|---|---|
| 1 | 조금씩 받기 | 12.02초 | 3.52초 | 0.22초 | clarify · 북촌한옥마을 / 국립중앙박물관 / N서울타워 |
| 2 | 고정 대기(기존 `structured_validated`) | 8.52초 | — | — | 같음 |
| 3 | 조금씩 받기 | 8.64초 | 0.91초 | 0.16초 | 같음 |

  원출력(`raw_before_validation`) 1=2=3 · 서버 후처리 결과(`raw`) 1=2=3. 조각 220개. 측정은 자연 시간을 재려고 넉넉한 감시값(30/5/60초)으로 했고,
  세 번 모두 새 설정값(8/5/15)으로도 끊기지 않는다. 같은 지시문의 연속 호출은 Ollama 캐시로 첫 조각이 빨라진다(1회 → 3회).
  넘김(유료) 경로는 대역으로만 시험했다.

## 남은 것 · 주의

- **넘김이 꺼진 로컬 서빙**(`ACOP_LLM_FAILOVER_ENABLED=false`)은 `OllamaChat` 을 직접 부르므로 첫 조각 8초 안에 모델이 답을 시작하지 못하면(식은 모델 올리기 약 28초)
  바로 `DecisionFailed`(「해석 모델 응답 오류」)다. 예전에는 `ollama_timeout_seconds`(60초)까지 기다렸다. 예열(`model_warmup`)과 `keep_alive` 가 그 몫이다.
- x600 Case 의 `decision.model_path` 로 20초 첫 턴이 유료였는지는 여전히 미확인(부모 · 읽기 전용).
- 다른 호출자(평가 스크립트 `eval/decision_unit/*`)는 `stream` 을 넘기지 않아 기존 호출 그대로다.

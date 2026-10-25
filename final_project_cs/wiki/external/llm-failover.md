---
type: contract
title: 모델 서버 장애 시 OpenAI 로 자동 전환
description: Ollama(GPU 서버)가 모두 죽거나 늦으면 서버용 OpenAI 키로 자동으로 넘기는 장치 — 넘기는 조건 · 회로 차단기 · 개인정보 · 비용 상한 · 켜는 법
status: draft
implementation_status: implemented
validation_status: partial
verified_at: 2026-10-07T23:19:00+09:00
tags: [agent, state, security]
owners: [human:미배정]
domain: neutral
domain_note: 모델 호출 경로(Ollama · OpenAI)의 신뢰성 장치라 도메인 낱말이 없다. 코드 `app/infrastructure/llm_failover.py`
---

# 모델 서버 장애 시 OpenAI 로 자동 전환

## 2026-10-08 사용자 지정 운영 모델

공개 배포 환경에서는 `ACOP_LLM_FAILOVER_ENABLED=true`, `ACOP_LLM_FAILOVER_MODEL=gpt-6-luna`로 전환한다. 키는 `ACOP_OPENAI_API_KEY_SERVER`만 사용한다. 로컬 개발 환경의 스위치 기본 꺼짐은 유지한다. GPT-6 호출은 `max_completion_tokens`를 쓰고, Luna는 짧은 JSON·문장 추출을 위해 `reasoning_effort=none`을 명시한다. 개인 키를 대신 쓰거나 복사하지 않는다. 호출 상한·마스킹·전환 경로 기록은 기존 계약을 유지한다. 실제 적용 여부와 시험은 해당 날짜 작업 리포트로 확인한다.

`[2026-10-07 사용자 지시]` 「올라마나 외부 GPU 서버가 모두 장애면 서버키(개인키 말고)로 자동 전환돼서 동작하게」.
코드 [llm_failover.py](../../app/infrastructure/llm_failover.py) · 시험 `tests/unit/infrastructure/test_llm_failover.py` · `test_retriever_failover.py`. 결정 [D-CS-016](../decisions/D-CS-016-llm-failover-server-key.md) · 불변식 `INV-CS-SEC-012`~`015`([카탈로그](../quality/invariants.md)).

## 평소 경로의 모델 `[2026-10-14 사용자 지시]`

평소 경로(Ollama)의 코드 기본 모델은 우리 데이터로 가르친 E4B `tripilot-pointer:e4b-ft` 다(전에는 학습 없는 `gemma4:12b`). 요청 해석·일정 짚기를 이 모델 하나가 맡고, 문맥 길이 `ollama_num_ctx` 기본 8192 와 함께 쓴다. 그 모델이 없는 곳(개발 PC 등)은 `ACOP_OLLAMA_MODEL` 로 있는 모델을 지정한다. 아래 「정확도」 표의 Gemma 4 12B 는 **2026-10-07 에 잰 당시 평소 경로**다. 로컬 대기 한도도 6초에서 9초로 올려 x600 서버 운영과 맞췄다(학습 E4B 한 건 5.1~7.3초라 6초면 8건 중 6건이 유료 대체로 넘어갔다 — `wiki/records/reports/2026-10-14_채팅해석_근본개선_1차.md`).

## 한 줄 요약

모델 서버(Ollama)가 연결 실패 · 시간 초과 · 5xx · 빈 답을 내면 **그 한 호출**을 서버용 OpenAI 키로 다시 부른다. 연속으로 실패하면 서버를 한동안 건너뛰고 곧장 OpenAI 로 간다. **스위치는 기본 꺼짐**이고, 배포(운영) 환경 파일에서만 켠다.

## 왜 필요한가

모델 서버 한 대가 서비스 전체의 **단일 장애점**이었다. Ollama 가 멈추면 채팅의 할 일 고르기(결정 단위) · 계획 읽기 · 알림 번역 · 분류가 모두 「모름」으로 끝났다. 사람 대기 답을 쓰지 않는 규칙이라 고객에게는 「이해하지 못했어요」만 보였다.

## 어디에 걸리나

모델을 부르는 모든 자리가 `ollama_chat.from_settings()` 가 돌려주는 객체를 쓴다. 스위치가 켜지면 이 객체가 **같은 메서드(`json` · `text` · `structured` · `see` · `loaded` · `warm`)를 가진 `FailoverChat`** 이 되므로 호출하는 코드는 바뀌지 않는다.

| 하는 일 | 부르는 곳 | 넘기나 |
|---|---|---|
| 채팅 한 마디 → 할 일 + 대상(결정 단위) | `decision_unit.decide` → `structured` | 예 |
| 계획 읽기의 글 이해 · 영업시간 정리 | `intake` · `planner.enrich_hours` 의 `json` · `text` | 예 |
| 알림 번역 | `translate.make_translator` → `text` | 예 |
| 문장 분류 · 신고 추출 | `feedback._ollama_llm` · `trip_intake.extract` → `json` | 예 |
| 후보 이유 문장 | `intake/reasons.py` → `structured` | 예 |
| 규정 검색의 질문 임베딩 | `rag/retriever.py` | 예(1536 칸이 채워져 있을 때만 — 아래) |
| 사진 · 스캔 받아쓰기 | `intake/sources.py` → `see` | **아니오(기본)** — 이미지를 가릴 수 없다. `llm_failover_vision` 을 따로 켜면 넘긴다 |
| 일정 항목 짚기 가르친 모델 | `item_pointer.py` | 따로 필요 없음 — 이미 모델이 못 불리면 낱말 규칙으로 돌아간다 |
| 모델 예열 | `model_warmup.py` (화면 예열 · `[2026-10-26]` 넘김 장치의 식은 첫 Ollama 뒤 예열이 같은 중복 억제를 쓴다) | 아니오 — 첫 Ollama 만 데운다(API 는 데울 것이 없다) |

`[미확인]` 후보 장소 비슷함 계산(`intake/embeddings.py`, 다른 세션이 작업 중)은 Ollama 임베딩을 직접 부르므로 이 장치에 안 걸려 있다.

## 어떻게 움직이나

```text
호출 → ① Ollama(들) 앞에서부터 → ② 모두 안 되면 OpenAI(서버용 키)
```

1. **경로 순서.** `ollama_base_url`, 그다음 `ollama_fallback_base_urls`(쉼표로 이은 Ollama 들 — 예: 무료 서버 + GPU 서버). 하나라도 답하면 그 답을 쓴다. **모두** 안 될 때만 OpenAI 로 간다.
2. **넘기는 조건.** 연결 실패 · 시간 초과 · 5xx · 429 · 빈 답. 429 · 5xx 는 **한 번만** 0.4초 쉬었다가 다시 시도한다(전체 시간 안에 다 들어갈 때만). 모양이 틀린 답(JSON 이 아님)은 그 한 호출만 넘기고 서킷에는 세지 않는다 — 서버는 살아 있다.
3. **시간.** Ollama 는 9초(`llm_failover_primary_timeout_seconds`, 2026-10-14 에 6초에서 올렸다. 연결은 5초), OpenAI 는 8초, 한 호출 전체 15초 안에 끝나게 한다(고객 응답 SLA).
   `[2026-10-26 사용자 승인]` **채팅 해석(`decision_unit.decide`)은 고정 9초 대신 답 조각 감시**다 — `structured_stream_validated`(스키마 `format` · 스키마 검사 · 근거 검사 그대로)로 조금씩 받으며 첫 조각 · 조각 사이(5초) · 맨 위 상한(가드레일 `travel.chat_decision_stream`)을 보고, 끊기면 받다 만 답을 버리고 다음 경로(유료)가 처음부터 다시 답한다(계획 읽기 `json_stream` 과 같은 넘김 계약 · 조용히 고정 대기 호출로 되돌아가지 않는다). 로컬 모델이 안 올라와 있으면 곧바로 다음 경로로 간다.
   `[2026-10-26 사용자 결정 · 라우팅 감사 12c]` **분류 계획(`execution_plan.classify_plan` → `feedback.ask_json`)도 고정 50초 대신 같은 답 조각 감시**다 — `structured_stream`(받은 답은 스키마 검사, 뜻 검사는 `validate_plan`)으로 받으며 가드레일 `travel.watch.plan_stream`(첫 조각 · 조각 사이 5초 · 맨 위 상한)을 보고, 끊기면 다음 경로(넘김이 켜진 곳은 유료)가 처음부터 다시 답하고 끝내 못 답하면 Case `classification_failed`다. 로컬 모델이 안 올라와 있어도 고정 대기 호출로 바꾸지 않는다(채팅 해석의 적재 대기 갈래를 쓰지 않는다).
   `[2026-10-26]` **식은 첫 Ollama 는 뒤에서 한 번 예열한다** — 조각 감시 경로(`json_stream` · `structured_stream` · `structured_stream_validated`)가 첫 Ollama 의 `loaded`(`/api/ps`) 에서 모델이 없다고 보면 이번 요청은 기다리지 않고 다음 경로로 넘기고(`not_loaded`, 서킷에 안 셈), 데몬 스레드에서 예열을 시작한다. 예열 장치는 조립 루트(`composition._llm_failover_warm`)가 꽂는 **화면 예열과 같은 `model_warmup.warmup`** 이다 — 이미 올라가 있으면 아무것도 안 하고, 가드레일 `web_guard.warmup.dedupe_seconds` 안의 되풀이는 한 번으로(웹 `/v1/web/warmup` 과 같은 상태), 실제 적재는 `FailoverChat.warm`(긴 제한시간 `ollama_timeout_seconds` 의 첫 Ollama). 예열이 도는 동안 온 식은 요청은 스레드를 더 만들지 않는다. 예열 실패는 경고 로그(`llm_failover background warm failed`)만 남기고 고객 응답은 그대로다. 두 번째 이후 Ollama(`ollama_fallback_base_urls`)는 데우지 않는다. 고객 남용 방어(`web_guard.count("warmup")`)는 고객 요청을 세는 장치라 이 내부 예열은 세지 않는다.
   `[2026-10-26]` **넘김이 꺼진 로컬 서빙**(`from_settings` 가 `OllamaChat` 을 그대로 돌려줌)은 다음 경로가 없다. 그래서 `OllamaChat.structured_stream_validated` 는 모델이 식어 있으면 조각 감시 대신 **적재를 기다리는 고정 대기 호출**(`structured_validated`, 제한시간 `ollama_timeout_seconds`)로 답하고 검사를 지난 최종 글을 `on_piece` 에 한 번 준다(10-26 이전과 같은 동작). 상태를 못 물으면 그대로 조금씩 받는다.
   `[2026-10-26]` **붙잡아 둘 시간(`keep_alive`)은 같은 모델이면 하나다** — Ollama 는 요청마다 만료를 다시 정하므로, 일정 짚기(`item_pointer.register_from_settings`)가 해석과 같은 모델(`ollama_pointer_model == ollama_model`)이면 `ollama_pointer_keep_alive` 대신 해석의 `ollama_keep_alive` 를 보낸다(문맥 길이 `num_ctx` 와 같은 규칙, 따로 적힌 값은 경고 후 무시). 둘 다 기본은 빈 값 = 보내지 않음 = 서버 `OLLAMA_KEEP_ALIVE` 를 따른다. 일정 짚기만 `30m` 를 보내 서버 `-1` 을 덮어 30분 뒤 모델이 내려간 것이 x600 `not_loaded` 의 원인 후보였다(`records/reports/2026-10-26_x600_채팅해석_유료넘김_원인.md`).
4. **회로 차단기.** 한 서버가 **연속 3번** 서버 문제로 실패하면 60초 동안 **건너뛴다**(바로 다음 경로로). 60초가 지나면 한 호출만 시험해서 성공하면 닫고 실패하면 다시 60초를 연다. 상태는 프로세스 안 전역이라 요청마다 `from_settings` 를 불러도 이어진다. OpenAI 쪽도 같은 서킷이 있다(키가 틀렸을 때 매번 8초씩 기다리지 않게).
5. **넘긴 답도 같은 검증.** 목록 밖 번호 거부(`decide`) · 분류 라벨 검사 · 번역의 숫자 · 단위 대조는 모델이 달라도 그대로 돈다. 이 장치는 모양만 맞춘다(스키마를 `response_format` 으로 주고, 거부되면 글로 적은 JSON 모드로 한 번 더).
6. **개인정보.** OpenAI 로 보내는 글은 `redaction.masked` 로 한 번 더 가린다(전화 · 카드 · 이메일 · `sk-` 키). 호출부가 이미 가린 글이라 보통 달라지지 않는다. 일정 제목 · 시각 같은 판단에 필요한 칸만 이미 프롬프트에 들어 있고 이름 · 연락처 칸은 처음부터 없다. **이미지는 가릴 수 없다** — 그래서 기본은 안 넘긴다.
7. **비용 상한.** API 로 넘긴 호출은 `external_call_budget` 의 `openai_failover` 줄로 센다(기본 하루 2,000 · 한 달 30,000). 넘으면 더 안 부르고 실패로 올린다(`budget_exhausted`). 한도 표를 못 읽으면 **부른다**(서비스를 살리는 쪽) — 경고를 남긴다.
8. **기록.** 로그 `app.llm_failover`(경로 전환 · 서킷 열림/닫힘), 프로세스 안 지표 `llm_failover.snapshot()`(`ok:<호출>:<경로>` · `fail:<경로>:<이유>` · `skip:<경로>:<이유>` · 마지막 전환 · 서킷 상태), 호출 직후 `current_path()`. 채팅 결정은 Case 의 `decision.model_path = {path: local|api, backend, reasons}` 에 남는다(넘김 장치가 켜져 있을 때만).
9. **실패.** 모든 경로가 실패하면 `OllamaError`(「모든 모델 경로가 실패했다: ollama=connect, openai=auth」)로 올라간다 — 부르는 쪽이 이미 이것을 「모름」으로 다룬다. **키 값은 어떤 메시지 · 로그에도 안 싣는다**(상태 코드와 이유 이름만).

## 규정 검색은 왜 따로 준비해야 하나

규정 검색은 질문을 임베딩해서 청크 벡터와 비교한다. 평소는 Ollama 의 `bge-m3`(1024차원, `embedding_1024` 칸)다. Ollama 가 죽었을 때 OpenAI 로 질문을 임베딩하면 **1536차원**이라 `embedding` 칸으로 검색해야 하는데, 여행 규정 코퍼스는 그 칸이 비어 있었다. 그래서:

- 그 칸이 비어 있으면 **넘기지 않고 예외**를 낸다 — 다른 벡터로 몰래 검색하면 근거 0건이 「규정이 없다」로 읽힌다(`RULE.md` §3.2).
- 채우려면 `python -m scripts.embed_chunks_openai`(서버용 키로 청크 본문 그대로 임베딩 · 1024 칸은 안 건드림 · `--dry-run` 으로 수만 센다). **배포 DB 에서도 한 번 돌려야 한다.**

## 정확도 — 넘긴 모델이 Gemma 만큼 맞나 `[실측 2026-10-07]`

채팅 결정 단위의 재생 시험(`eval/decision_unit/replay.py`, 실제 대화 66문장, 정답은 Claude 표기)을 Ollama 자리를 막고 OpenAI 로만 돌렸다. 한 번씩 잰 값이다(반복 없음 — 편차는 모른다).

| 모델 | 맞음 | 엉뚱한 대상 변경 | 쓸데없는 되묻기 | 지연 p95 |
|---|---:|---:|---:|---:|
| Gemma 4 12B(평소 경로, GPU 서버 혼잡 없을 때) | 64/66 = 97.0% | 0 | 1 | 5.8초 |
| `gpt-4.1` | **64/66 = 97.0%** | 0 | 1 | 3.9초 |
| `gpt-4.1-mini` | 55/66 = 83.3% | 0 | 9 | 3.2초 |
| `gpt-4o-mini` | 52/66 = 78.8% | **1** | 3 | 3.0초 |

작은 모델은 이름으로 일정을 못 짚거나(「무구옥 주소 알려줘」→ 대상 없음) 엉뚱한 일정을 바꿨다(「그럼 그 다음식당 바꿔」→ 다른 날 식당). 그래서 기본을 `gpt-4.1` 로 했다. 호출당 비용이 작은 모델보다 크지만(단가는 확인하지 않았다 `[미확인]`) 일 상한(2,000)이 하루 비용의 위쪽을 막는다. 화면 조작 30문장은 `gpt-4o-mini` 로만 쟀다(27/30). 알림 번역 · 분류 · 계획 읽기를 OpenAI 로 돌린 정확도는 `[미측정]`. 보고서 `eval/decision_unit/report_openai_failover_*.json`.

## 켜는 법

배포(운영) 환경 파일에서만 켠다. 개발 PC 에서는 켜지 않는다 — 연결이 끊겼을 때 시험 · 측정이 조용히 유료 API 로 새고, 어느 모델의 값인지 섞인다.

| 이름 | 값 | 설명 |
|---|---|---|
| `ACOP_LLM_FAILOVER_ENABLED` | `true` | 스위치(기본 `false`) |
| `ACOP_OPENAI_API_KEY_SERVER` | 서버용 키 | 비어 있으면 스위치가 켜져 있어도 안 넘긴다. 개인 키로 대신하지 않는다 |
| `ACOP_LLM_FAILOVER_MODEL` | `gpt-4.1`(기본) | 비우면 `ACOP_LLM_MODEL`(지금 `gpt-4o-mini`). 왜 `gpt-4.1` 인지는 아래 「정확도」 |
| `ACOP_OLLAMA_FALLBACK_BASE_URLS` | 비움 | Ollama 가 둘 이상일 때만 |
| `ACOP_LLM_FAILOVER_VISION` | `false` | 이미지도 넘길지(기본 안 넘김) |
| `…_PRIMARY_TIMEOUT_SECONDS` · `…_API_TIMEOUT_SECONDS` · `…_TOTAL_SECONDS` · `…_FAILURES` · `…_OPEN_SECONDS` · `…_DAILY_CAP` · `…_MONTHLY_CAP` | 9 · 8 · 15 · 3 · 60 · 2000 · 30000 | 기본값은 [settings.py](../../app/core/settings.py) |

## 한계 — 확인한 것과 못 한 것

- **시험:** mock 서버 시험(Ollama 자리는 정해진 응답을 내는 가짜 전송 함수와 **이 PC 안에 잠깐 띄운 진짜 HTTP mock 서버** — 닫힌 포트 · 느린 서버 · 5xx · 정상, OpenAI 자리는 가짜 클라이언트)으로 위 동작을 확인했다.
- **실서버 확인:** 서버용 키로 **실제 OpenAI** 를 불러 넘어가는 것을 확인했다 — json · text · structured · embedding 각 1번, 규정 검색 1번(로컬 개발 DB), 결정 단위 재생 약 300번(모델 비교, 위 표). Ollama 자리는 닫힌 포트였다. x600 서버의 실제 Ollama · GPU 서버를 죽여 보는 시험, **배포 환경에 켜는 일은 하지 않았다**.
- 결정 단위 정확도는 위 표(실제 대화 66문장)만 쟀다 — 다른 호출(번역 · 분류 · 계획 읽기)의 OpenAI 경로 정확도는 `[미측정]`. 재생 도구는 `from_settings` 를 쓰므로 스위치가 꺼진 개발 환경에서는 늘 Ollama 만 잰다(OpenAI 경로로 재려면 `ACOP_OLLAMA_BASE_URL` 을 닫힌 주소로 두고 스위치를 켠다).
- 지표는 프로세스를 다시 띄우면 0 으로 돌아간다(영구 기록은 로그).

## 운영 반영 확인 — 2026-10-08

GPT-6 Luna 자동 전환을 운영 환경에 반영했고 실제 Ollama 연결 실패를 거친 응답 3/3이 API로 성공했다. [작업 리포트](../records/reports/2026-10-08_2245_Luna_자동전환_운영반영.md).

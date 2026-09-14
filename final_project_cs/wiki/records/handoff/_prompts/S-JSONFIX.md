# 구현 지시 — Team LLM 호출이 400 을 받는다 (json_object 요구사항)

## 0. 진전과 남은 결함

지난 수정으로 **연결은 뚫렸다.** `APIConnectionError` 가 사라지고 OpenAI 가 응답한다.
남은 것은 요청 형식 하나다:

```
BadRequestError: Error code: 400 -
{'error': {'message': "'messages' must contain the word 'json' in some form,
 to use 'response_format' of type 'json_object'", 'type': 'invalid_request_error'}}
```

결과: `answer = None` × 3, `고유 answer 1`.

## 1. 원인

`response_format={"type": "json_object"}` 를 쓰면 OpenAI 는 **프롬프트(messages) 안에
문자열 "json" 이 들어 있을 것**을 요구한다. Team 프롬프트에 그 단어가 없다.

## 2. 소유 범위

```
app/infrastructure/llm/**
prompts/billing/** , prompts/technical/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/**`, `app/presentation/**`, `eval/**`, `knowledge/**`,
`config/**`, `scripts/**`, `tests/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`.

## 3. 고칠 것 (둘 중 하나. **1번을 권장**)

1. **프롬프트에 JSON 출력 지시를 명시한다** — 어차피 필요한 문장이다.
   예: `아래 스키마의 JSON 객체로만 답하라. (JSON only)` + 스키마 필드 나열
   ★프롬프트 파일을 고치면 **버전을 올려라** (`.v1.md` → `.v2.md`).
   `prompts` 테이블이 `UNIQUE(prompt_key, version)`·`UNIQUE(prompt_key, sha256)` 이라
   같은 버전의 내용을 덮어쓰면 평가 재현성이 깨진다
2. 또는 `response_format` 을 쓰지 않고 응답을 파싱한다
   (★그러면 malformed JSON repair 1회 규칙이 살아 있어야 한다 — `config/guardrails.yaml`)

★**어느 쪽이든 Team 이 실제 답변을 내야 한다.** 고정 문구를 만들지 마라.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **123 passed 유지** (live 는 deselected).

★실호출 검증은 **당신이 못 한다**(이 환경은 외부 네트워크가 막혀 있다).
코드와 프롬프트만 고치고, **검수 담당이 돌린다.**
★mock/fake 로 돌려놓고 "완료" 라고 쓰지 마라.

## 5. 리포트

`wiki/records/reports/2026-08-13_S-JSONFIX_리포트.md` — 어느 방식을 골랐는지,
프롬프트 버전을 올렸는지, 변경 파일.

## 6. 하지 말 것
- ❌ 고정 문구 answer
- ❌ 프롬프트 같은 버전에 덮어쓰기
- ❌ 소유 범위 밖 수정
- ❌ 실호출 없이 "동작 확인" 이라고 쓰기

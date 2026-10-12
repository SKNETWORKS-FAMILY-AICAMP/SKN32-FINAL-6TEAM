# 구현 지시 — Team 의 LLM 어댑터가 실호출을 못 한다

## 0. 결함 (실측 2026-08-13)

Proposed 러너가 실제 Team 을 호출하면:
```
error: APIConnectionError: Connection error.
cost: 0.0  in_tok: 0  lat: 0  prediction: null
```

**같은 셸에서 OpenAI 는 정상이다:**
```
OK  latency=1443ms  usage=CompletionUsage(prompt_tokens=16, completion_tokens=2)
```

★**환경이 아니라 코드 경로의 문제다.**
baseline A·B 러너의 `_call_openai()` 는 동작한다 (540런에서 A $0.045, B $0.118 실소모).
**Proposed 만 실패한다** → Team 이 쓰는 LLM 어댑터 경로가 다르고, 그게 깨져 있다.

상세: `wiki/records/reports/debugs/2026-08-13_1600_Team의_LLM_실호출_경로가_동작한적이_없다.md`

## 1. 원인 후보 (확인해서 고쳐라)

1. ★**`os.getenv` 로 키를 읽는가** — `.env` 는 `os.environ` 에 안 들어간다.
   반드시 `app.core.settings.get_settings()` 를 쓴다.
   S-API 가 정확히 이걸로 전 요청 500 을 냈다
   (`wiki/records/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md`)
2. base_url·proxy·timeout 설정이 baseline 러너와 다른가
3. 클라이언트를 모듈 import 시점에 만들어 키가 비어 있는 상태로 굳었는가

★**동작이 확인된 참조 구현**: `eval/runners/common.py` 의 `_call_openai()`
```python
client = OpenAI(api_key=_settings().openai_api_key, timeout=args.timeout)
```
같은 방식으로 만들어라.

## 2. 소유 범위

```
app/infrastructure/llm/**
app/modules/customer_ops/*.py      (LLM 주입부만, 최소 변경)
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/**`, `app/presentation/**`, `eval/**`, `knowledge/**`,
`config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 3. 고칠 것

1. Team 이 쓰는 LLM 어댑터가 **`get_settings()`** 로 키·모델을 읽게 한다
2. 클라이언트를 **호출 시점에** 만든다 (import 시점 아님)
3. 실패 시 예외를 **삼키지 마라** — `TeamResult` 를 조작해 성공으로 만들지 마라.
   ★단 지금처럼 `APIConnectionError` 를 그대로 올려 상위가 `degraded` 로 기록하는 것은 맞다
4. ★**기존 fake 주입 경로를 유지한다.** 테스트가 fake 로 계속 돌아야 한다

## 4. ★실호출 스모크 테스트를 하나 둔다

이번 결함의 근본 원인은 **주입 가능한 의존성을 fake 로만 검증한 것**이다.
이 프로젝트에서 같은 패턴이 다섯 번 반복됐다.

`tests/live/test_llm_live.py` 를 만들고 `@pytest.mark.live` 를 붙인다:
- 실제 LLM 을 **한 번** 호출해 응답이 오는지만 확인
- `pyproject.toml` 또는 `pytest.ini` 에 마커를 등록하고
  **기본 실행(`pytest tests -q`)에서는 제외**되게 한다 (`-m "not live"` 기본값)
- ★**수동으로 `pytest tests/live -m live` 로 돌릴 수 있어야 한다**

★이 환경에서는 당신이 실호출을 못 한다(`APIConnectionError`).
**테스트를 만들되 실행은 하지 마라.** 검수 담당이 돌린다.

## 5. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **123 passed 유지, 0 failed, skipped 0** (live 테스트는 기본 실행에서 제외).

★그리고 **어디를 어떻게 고쳤는지** 리포트에 적어라 —
`os.getenv` 였는지, 클라이언트 생성 시점이었는지, 무엇을 baseline 과 맞췄는지.

## 6. 리포트

`wiki/records/reports/2026-08-13_S-LLMFIX_리포트.md` — 원인, 변경 파일,
baseline `_call_openai()` 와 무엇이 달랐는지, live 마커 등록 방법.

## 7. 하지 말 것
- ❌ `os.getenv` 유지
- ❌ 예외를 삼켜 성공으로 만들기
- ❌ fake 주입 경로 제거
- ❌ live 테스트를 기본 실행에 넣기
- ❌ `eval/**` 수정
- ❌ 실호출을 시도하고 실패했다고 코드가 맞다고 결론내기

# 구현 지시 — Team 이 LLM 결과를 버리고 하드코딩 문구를 답변으로 쓴다

## 0. 결함 (근본 원인)

`app/modules/customer_ops/billing.py`:

```python
if self.llm is not None:
    await self.llm.complete("billing.answer", task.input_text, {...})   # 45행: 결과를 버린다
...
answer = "구독과 결제 이력을 확인했습니다. 정책 근거를 바탕으로 안내할 수 있습니다."  # 49행
return TeamResult(..., answer=answer, ...)
```

★**LLM 을 호출하고 반환값을 쓰지 않는다.** 하드코딩 문자열이 답변이 된다.

실측 (평가 러너에서 3건):
```
err: None          ← LLM 호출은 성공한다
valid: 8           ← 인용도 정상
고유 answer: 1     ← 3건이 전부 같은 문구
```

`technical.py` 도 같은 구조인지 확인하고 함께 고쳐라.

## 1. 왜 중요한가

Proposed 는 **이 프로젝트가 만든 것 그 자체**다. 답변이 고정 문구면
평가가 측정하는 것은 시스템의 능력이 아니라 **검색 배선**뿐이다.

★이 프로젝트에서 같은 종류를 여섯 번째 겪는다 — **"호출한다"와 "결과를 쓴다"는 다른 사건이다.**

## 2. 소유 범위

```
app/modules/customer_ops/billing.py
app/modules/customer_ops/technical.py
prompts/billing/** , prompts/technical/**
tests/unit/teams/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/**`, `app/presentation/**`, `eval/**`, `knowledge/**`,
`config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 3. 고칠 것

1. ★`self.llm.complete(...)` 의 **반환값을 받아 `answer` 로 쓴다.**
   하드코딩 문자열을 지워라
2. LLM 응답이 JSON 이면 `answer` 필드를 꺼내 쓴다.
   ★스키마가 안 맞으면 **repair 1회** 후 실패로 처리한다
   (`config/guardrails.yaml` 의 `malformed_json_repair_attempts`)
3. ★`self.llm is None` 이면(테스트의 fake 미주입 등) **기존 동작을 유지**한다.
   기존 116→123건 테스트가 깨지면 안 된다
4. ★**근거 없는 답변을 만들지 마라** — `TeamResult` validator 가
   `answer` 가 있는데 `evidence` 가 비면 거부한다. 지금 구조를 유지하라
5. `escalate`/`waiting` 경로는 그대로 둔다. 고칠 것은 **`completed` 경로의 answer** 다

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **123 passed 유지, 0 failed, skipped 0** (live 는 deselected).

★실호출 검증은 **당신이 못 한다**(외부 네트워크 차단). 코드만 고치고
**검수 담당이 돌린다.** fake 로 돌려놓고 "answer 가 달라졌다" 고 쓰지 마라 —
fake 는 원래 고정값을 준다.

## 5. 리포트

`wiki/records/reports/2026-08-13_S-TEAMANSWER_리포트.md` — 두 Team 각각 어디를 고쳤는지,
LLM 응답에서 `answer` 를 꺼내는 방식, 스키마 불일치 처리.

## 6. 하지 말 것
- ❌ 하드코딩 문구 유지 / 다른 고정 문구로 교체
- ❌ LLM 반환값을 버리기
- ❌ `evidence` 없이 `answer` 채우기
- ❌ 기존 테스트 깨기
- ❌ 소유 범위 밖 수정
- ❌ fake 결과를 실호출 검증으로 보고

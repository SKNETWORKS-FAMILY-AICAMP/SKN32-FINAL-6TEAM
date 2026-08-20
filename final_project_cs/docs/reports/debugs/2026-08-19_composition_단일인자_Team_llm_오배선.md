# 결함 — 단일 인자 생성자 Team 에 `tools` 가 `llm` 자리로 잘못 들어간다

DoD-29 사실수집(`docs/reports/2026-08-19_DoD29-사실수집.md` §4)에서 발견했다.
**고쳤는지와 무관하게 먼저 기록한다**(`RULE.md` §4.1).

## 1. 위치

`app/composition.py:88-101` `_instantiate_team()`

## 2. 재현

```python
import inspect
class Fake:
    def __init__(self, llm=None): ...
params = [p for p in inspect.signature(Fake).parameters.values()
          if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
required = [p for p in params if p.default is p.empty]
print(len(required) <= 1 and len(params) <= 1)  # True → implementation(tools) 분기를 탄다
```

## 3. 실측

`app/modules/customer_ops/response_review.py::ResponseGenerationReviewTeam.__init__(self, llm=None)`
가 정확히 이 형태다 — 위치 인자 1개(`llm`), 기본값 있음. `_instantiate_team()`
의 조건 `len(required) <= 1 and len(positional) <= 1`(0 <= 1, 1 <= 1)이
참이 되어 `implementation(tools)` 분기를 탄다 — **`ReadToolbox` 인스턴스가
`llm` 자리에 들어간다.**

지금은 `config/project.yaml` 에 `response_generation_review` 가 등록돼
있지 않아 이 경로가 실행되지 않는다(DoD-29 사실수집 §2 로 확인) — **아직
터지지 않았을 뿐이다.**

## 4. 원인

`_instantiate_team()` 의 분기 로직이 **파라미터 개수만** 보고 이름을
안 본다. `(tools,)` 형태의 단일 인자 Team 과 `(llm=None,)` 형태의 단일
인자 Team 을 구분하지 못한다 — 둘 다 "위치 인자 1개, 필수 0개"로 같은
모양이라 항상 `tools` 를 넣는 쪽으로만 분기한다.

## 5. 위험도

- 지금은 등록 안 돼 있어 **잠재 결함**이다. 하지만 DoD-29 를 다음 단계로
  진행하려면(=`config/project.yaml` 에 이 Team 을 등록하려면) **반드시
  먼저 밟게 되는 경로**다. 등록하는 순간 `self.llm` 이 `ReadToolbox` 가
  되고, `execute()` 안의 `if self.llm is not None: response =
  await self.llm.complete(...)` 가 `ReadToolbox` 에 없는 메서드를
  호출해 즉시 `AttributeError` 로 죽는다 — 고객 응대 흐름 전체가 막힌다.
- **VOC & Store Manager(`VocStoreManagerTeam(tools, llm=None)`)는 영향
  없다** — 위치 인자가 2개(`tools`, `llm`)라 다른 분기(`implementation(tools, llm)`)
  를 탄다. 지금 이 결함의 영향 범위는 `ResponseGenerationReviewTeam` 하나뿐이다.

## 6. 수정

`_instantiate_team()` 이 단일 위치 인자의 **이름**을 보고 분기하도록
고쳤다 — 이름이 `llm` 이면 `llm` 을 넣고, 그 외(`tools` 등)면 기존대로
`tools` 를 넣는다. 이후 등록될 단일 인자 Team 이 `llm` 이외의 이름을
쓰면 여전히 오배선될 수 있으므로, 근본적으로는 Team 생성자 시그니처를
`(tools, llm=None)` 로 통일하는 게 더 안전하지만 이번 범위에서는 기존
Team(`ResponseGenerationReviewTeam`)의 시그니처를 바꾸지 않고 조립기
쪽만 방어적으로 고쳤다 — 계약 파일(`docs/handoff/_prompts/S-RESPONSE-REVIEW-PORT.md`)
이 이미 이 시그니처로 승인됐고, 이제 와서 Team 쪽을 바꾸면 그 계약과
어긋난다.

## 7. 검증

`tests/unit/test_composition_root.py` 에 회귀 테스트를 추가해
`_instantiate_team` 이 `llm` 이름의 단일 인자에는 `llm` 값을, 그 외
이름에는 `tools` 값을 넣는지 직접 확인한다.

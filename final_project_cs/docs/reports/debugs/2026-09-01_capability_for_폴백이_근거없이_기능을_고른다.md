# capability_for()가 매칭 실패 시 근거 없이 capabilities[0]을 고른다

- 발견 경위: 다른 세션이 라우팅 규칙(`resolve()` → `capability_for()`)을
  설명하다가 "아무것도 안 맞으면 첫 번째 것을 쓴다"는 폴백을 스스로 의심하고
  재현 여부를 확인해 보내왔다. 코드로 직접 재현해 사실임을 확인했다.
- 판정: **실재, 항상 도달 가능**(가상의 엣지케이스가 아니라 `intent="other"`
  의 정상 경로). 미수정.

## 재현

```python
from app.composition import build_registry
registry = build_registry()
entry = registry.resolve(case_type="other", intent="other")
print(entry.manifest.team_id)                    # voc_store_manager
print(entry.manifest.capabilities)                # ['voc.aggregate', 'voc.escalate']
registry.capability_for(entry, "other")           # -> 'voc.aggregate'  (아무 매칭도 없는데)
```

`app/core/registry.py:88-96`:

```python
@staticmethod
def capability_for(entry: RegisteredTeam, intent: str | None = None) -> str:
    intent = (intent or "").lower()
    if intent:
        for capability in entry.manifest.capabilities:
            if capability.lower() == intent or capability.lower().startswith(intent + "."):
                return capability
    return entry.manifest.capabilities[0]   # ← 매칭 실패해도 여기로 떨어진다
```

## 왜 문제인가

- `resolve()`는 정확히 하나가 아니면 `RegistryError`로 실패한다(`registry.py:84-85`,
  `"case must resolve to exactly one active team"`). `capability_for()`만
  같은 상황에서 조용히 폴백한다 — 같은 파일 안에서 두 메서드의 "모르면
  어떻게 하나" 기준이 다르다.
- `capability_for()`의 반환값은 장식이 아니다. `controller.py:127`이
  `payload={"owner_team_id": ..., "capability": capability}`로 **Case
  이벤트에 그대로 기록**한다. `voc.aggregate`를 부른 적도 없는데
  Case 감사 기록에는 `voc.aggregate`가 호출됐다고 남는다 — `CLAUDE.md`
  §0.1 "근거 없으면 답하지 않는다"가 막으려는 바로 그 상황이다.
- **"other" intent는 이 경로를 항상 탄다.** `voc_store_manager`가
  `accepted_case_types=["other"]`인 유일한 팀이고, 그 팀의 capability
  둘(`voc.aggregate`, `voc.escalate`) 중 "other." 로 시작하는 게 없다.
  분류기가 `other`를 낼 때마다(정상적인 라벨 값, `feedback.py`의
  `INTENTS` 안에 있다) 이 폴백이 매번 실행된다 — 희귀 케이스가 아니다.

## 왜 지금 안 고쳤는가

단순히 매칭 실패를 `RegistryError`로 바꾸면 **"other" intent 케이스 전체가
라우팅에서 하드크래시**한다 — 지금은 이게 예외 상황이 아니라 이 intent의
유일한 정상 경로이기 때문이다. `_capability()`(`controller.py:68-72`)가
`_task()`(`controller.py:153`)에서 호출되는데, 이 지점은 ROUTING 단계의
`RegistryError` 처리(`controller.py:124-132`, 잡아서 `ROUTING_FAILED` →
`escalated`로 보낸다) 범위 **밖**이다. 즉 그냥 raise로 바꾸면 잡아 주는
곳 없이 `run_case()` 밖으로 예외가 그대로 터진다.

제대로 고치려면 둘 중 하나가 같이 가야 한다:

1. VOC 팀 매니페스트에 `other` 로 시작하는 capability를 실제로 추가해
   매칭 실패 자체가 안 나게 하거나,
2. `capability_for()`가 매칭 실패 시 예외를 던지게 하고, `controller.py`
   쪽에서 그 예외를 `ROUTING_FAILED`/`escalated`로 우아하게 받는 처리를
   같이 넣는다.

지금 `controller.py::run_case()`는 트랜잭션 경계를 좁히는 별도 리팩터링이
진행 중이라(`docs/reports/debugs/2026-09-01_Controller가_LLM호출을_트랜잭션_안에서_한다.md`)
같은 파일의 예외 처리 경로를 동시에 건드리면 충돌한다. 재현과 원인만
남기고, 그 리팩터링이 끝난 뒤 이어서 다룬다.

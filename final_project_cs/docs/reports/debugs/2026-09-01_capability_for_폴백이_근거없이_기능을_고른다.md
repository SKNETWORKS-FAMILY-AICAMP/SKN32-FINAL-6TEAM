# capability_for()가 매칭 실패 시 근거 없이 capabilities[0]을 고른다

## 해결됨 (2026-09-01, 두 번째 시도)

raise 기반 수정을 되돌린 뒤, 다른 방향으로 다시 고쳤다 — **동작은 그대로
두고 근거만 명시적으로 만든다.** `TeamManifest`에 `default_capability:
str | None = None`을 추가했다(`app/core/contracts.py`,
`docs/handoff/01_계약_Pydantic.md`). `capability_for()`는 매칭 실패 시
`entry.manifest.default_capability or entry.manifest.capabilities[0]`을
쓴다 — 선언이 없으면 전과 완전히 같은 값을 반환한다(하위호환, 동작 변경 0).

실측으로 확인된 3개 팀(voc_store_manager·fulfillment_logistics·
return_refund)에 지금 실제로 나가는 값과 **똑같은** `default_capability`를
명시적으로 선언했다 — `voc.aggregate`·`fulfillment.track`·
`return.check_eligibility`. 값은 안 바뀌었지만 이제 "왜 이 값인지"가
매니페스트에 적혀 있다.

검증: 5개 intent 전부 `resolve()`→`capability_for()` 결과가 수정 전과
바이트 단위로 동일함을 확인. 회귀 테스트 3건 추가
(`tests/unit/core/test_registry_capability_default.py`). 517 passed,
회귀 0건.

## 시도했다가 되돌림 (2026-09-01, 첫 번째 시도)

`capability_for()`가 매칭 실패 시 `RegistryError`를 던지도록 고치고
`controller.py`에 그 예외를 escalated로 받는 처리까지 같이 넣었다.
**전체 테스트로 돌리자마자 8건이 실패했다** — `git checkout`으로 즉시
되돌렸다(커밋한 적 없음).

원인은 이 문서가 처음에 놓친 것이다: intent="other" 뿐 아니라, **실제
운영 중인 intent 5개 중 3개(shipping·exchange·other)가 전부 이
폴백에 의존하고 있었다.**

```
order    -> procurement_order_payment | 매칭: order.verify 등 있음
shipping -> fulfillment_logistics     | 매칭 없음 (폴백 의존)
return   -> return_refund             | 매칭: return.check_eligibility 있음
exchange -> return_refund             | 매칭 없음 (폴백 의존)
other    -> voc_store_manager         | 매칭 없음 (폴백 의존)
```

`fulfillment_logistics`·`return_refund`는 capability 가 여러 개라
"팀에 capability 가 하나뿐이면 고를 것도 없다"는 식의 우회도 못 쓴다 —
정말로 5개 중 3개가 이 폴백이 있어야 라우팅이 된다. VOC 하나만의
문제가 아니라 **intent(5종, 거친 라벨)로 capability(팀마다 2~6종,
세분화된 동작)를 고르는 지금 방식 자체가 원래 안 맞는 매핑**이었다.
raise 로 막으면 정상 라우팅의 절반 이상이 죽는다.

그래서 이 결함은 "폴백을 없애면 된다"가 아니라 "intent→capability
매핑을 다시 설계해야 한다"(더 세분화된 분류, 또는 매니페스트에 명시적
`default_capability` 필드 추가 등)로 바뀐다 — registry.py 한 곳
패치로 끝날 일이 아니라 별도로 설계할 일이다. 아래는 최초 판정
그대로 남긴다.

---

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

# DoD-22 — Team 의 직접 Tool 호출 금지

- v7 §27 항목 22 / 검증 방법: Team module AST 정적 검사 + runtime 차단 관측
- 실행: 2026-08-16 → **2026-09-06 재측정**
- 판정: **통과** (판정은 그대로, 근거를 새로 만들었다)

## ★2026-09-06 — 판정은 맞았고 **근거 서술이 틀렸다**

낡음 표시(`wiki/quality/dod-evidence-drift.md`)를 따라 확인했더니 인용한
근거 둘이 **실재하지 않았다.**

| 이 문서가 인용했던 것 | 실제 |
|---|---|
| 정적: `tests/unit/core/test_core_isolation.py` | **그 경로에 파일이 없다.** `tests/contract/` 로 옮겨졌고, 그 파일은 `app/core` 만 훑는다 — 즉 **"Core → Team" 한 방향만** 보고 "Team → 인프라" 는 아무도 안 봤다 |
| 런타임: `pytest.raises(ToolNotAllowed)` | **그런 테스트가 저장소에 없었다.** 문구만 있었다 |

**그런데 판정 자체는 옳았다.** 오늘 실측으로 확인했다.

```
Team 모듈 6개(manifest 보유) → 인프라 직접 import 위반 0
allowlist 밖 호출        → ToolNotAllowed: tool 'read.order' is not allowed for this task
allowlist 안이지만 미구현 → ToolNotAllowed: unknown tool 'read.nonexistent'
```

그래서 판정을 뒤집지 않고 **근거를 만들었다** —
`tests/contract/test_team_tool_discipline.py` (10건).

★**여기서 한 번 오진했다.** 처음엔 `app/modules/**` 를 통째로 훑어 위반
2건이 나왔다(`feedback.py` 의 `app.presentation.security`·지연 `openai`).
그런데 이 파일은 **manifest 가 없다 — Team 이 아니다.** 인라인 분류의 라벨
어휘·프롬프트 구현이고 소유가 코어 1 쪽이다(v9 §3-A). DoD-22 가 말하는
것은 **Team** 의 tool 규율이므로, 검사 범위를 파일 위치가 아니라
**manifest 유무**로 정했다. 그 판단을 테스트 docstring 에도 남겼다.

★검사가 눈이 멀지 않았는지도 봤다 — 같은 규칙을 `feedback.py` 에 걸면
위반 2건을 실제로 집어낸다. 대상이 0개면 실패하는 가드도 넣었다
(`test_team_modules_are_actually_found`), 대상을 못 찾으면 검사 전체가
언제나 통과하기 때문이다.

## 재현 명령

## 재현 명령

```powershell
python -m pytest tests/contract/test_team_tool_discipline.py tests/contract/test_core_isolation.py -q
python -m pytest -k "rejects_task_tools_outside_manifest" -q
```

## 실제 출력 (2026-09-06)

```
tests/contract/test_team_tool_discipline.py .......... 10 passed
tests/contract/test_core_isolation.py                   1 passed
-k rejects_task_tools_outside_manifest                  1 passed
```

무엇을 덮는지:

```
정적(AST) — 대상은 manifest 를 가진 Team 6개
  catalog_verification · fulfillment_logistics · procurement_order_payment
  response_review · return_refund · voc_store_manager
  금지 루트(app.infrastructure · psycopg · openai · app.presentation ·
  app.application) 직접 import  →  0건

런타임
  allowlist 밖          → ToolNotAllowed
  allowlist 안·미구현   → ToolNotAllowed("unknown tool")   ← 오타를 조용히 넘기지 않는다
  allowlist 안·구현됨   → 관문을 통과한다                   ← 막는 것만 보면 전부 망가져도 통과한다

dispatch 시점(2026-08-24 추가분)
  TeamTask.allowed_tools ⊄ manifest.allowed_tools → ToolScopeViolation, Team 호출 안 함
```

## 판정 근거

| 요구 | 결과 |
|---|---|
| Team 이 인프라 tool 을 직접 import 하지 않음 | **통과** — AST 검사 |
| `allowed_tools` 밖 호출이 런타임에 거부됨 | **통과** — `ToolNotAllowed` |
| ★정적 + 런타임 **둘 다** | **통과** — v7 이 둘을 함께 요구한다 |
| Core 가 Team 내부를 import 하지 않음 | **통과** — 위반 0 |

## ★정적 검사만으로는 부족하다

import 를 안 해도 **문자열로 tool 이름을 만들어 registry 에 넘길 수 있다.**
그래서 v7 이 `runtime spy` 를 함께 요구한다. 런타임 차단이 실제로 예외를 던지는 것을
관측했다 — 이름 목록을 비교하는 것이 아니라 **호출이 막히는 것**을 봤다.

## 한계

- AST 검사는 **정적 import** 만 본다. `importlib` 로 동적 로드하면 못 잡는다
- runtime 차단은 registry 를 거치는 호출만 본다. Team 이 직접 psycopg 를 잡으면
  AST 가 잡아야 하는데, 그건 위 한계와 맞물린다 — **두 검사가 서로의 구멍을 완전히 덮지는 않는다**

## ★2026-08-24 갱신 — 이 문서와 다른 경계: dispatch 시점 scope 검사도 이제 있다

위 검사는 "Team 이 실행 **중** 자기 manifest 밖 tool 을 부르면 막히는가"다.
sample 대조로 발견된 것은 그와 다른 경계 — `LocalTeamExecutor.execute()`가
**Controller 가 넘긴 `TeamTask.allowed_tools`가 애초에 Team 의
`manifest.allowed_tools` 부분집합인지**를 Team module 호출 **전에**
검사하지 않았다. 이제 부분집합이 아니면 `ToolScopeViolation`을 던지고
Team 을 아예 호출하지 않는다(`test_local_executor_rejects_task_tools_outside_manifest`).
기존 direct-call 동등성 테스트로 정상 흐름도 유지되는지 확인했다.
상세: `docs/reports/2026-08-24_S-BASEMENT-01-AUTH-CONTRACT_리포트.md`

# DoD-22 — Team 의 직접 Tool 호출 금지

- v7 §27 항목 22 / 검증 방법: Team module AST/import 정적 검사 + runtime spy
- 실행: 2026-08-16
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/unit/core/test_core_isolation.py tests/unit/teams/test_team_scenarios.py -q
```

## 실제 출력

```
통과

정적(AST):
  app/modules/**/*.py 의 import 를 파싱해 금지 대상 참조 0건
  Core → Team 내부 import 위반 0건

런타임:
  registry 가 넘긴 tool 이름이 manifest.allowed_tools 밖이면
    raise ToolNotAllowed(name)
  pytest.raises(ToolNotAllowed) 로 실제 차단 관측
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

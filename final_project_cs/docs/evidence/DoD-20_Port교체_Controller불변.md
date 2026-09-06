# DoD-20 — `TeamExecutorPort` 교체 시 Controller 가 바뀌지 않는다

- v7 §27 항목 20 / 검증 방법: Local/A2A adapter 교체 test + Controller import boundary 정적 검사
- 실행: 2026-08-16
- 판정: 통과

> ★2026-09-06 낡음 확인 — 테스트 경로 2건이 이동했고 `3 passed` → 6개. 판정 유효. 대조 기록: `program/final_project_cs/wiki/quality/dod-evidence-drift.md`

## 재현 명령

```powershell
python -m pytest tests/unit/ports/test_team_ports.py tests/unit/core/test_core_isolation.py -q
python -m pytest tests/e2e/test_project_composition.py -q
```

## 실제 출력

```
tests/unit/ports/test_team_ports.py ...        3 passed
tests/unit/core/test_core_isolation.py ...     통과 (AST import 검사)
tests/e2e/test_project_composition.py          port 교체·미구현 거부 통과

config/project.yaml:
  ports:
    team_executor: local        ← a2a 로 바꿔도 Controller 코드 변경 0
```

## 판정 근거

| 요구 | 결과 |
|---|---|
| Controller 가 Port 경유로만 Team 을 실행 | **통과** — `self.team_executor.execute(task)` |
| Local ↔ A2A 교체가 선언(`project.yaml`)으로 된다 | **통과** — 조립 시점에 결정 |
| ★Core 가 Team 내부를 import 하지 않음 | **통과** — `test_core_isolation.py` 의 AST 검사, 위반 0 |
| 미구현 port 선택 거부 | **통과** — `redis_streams`·`age`·`neo4j` 는 조립 실패 |
| ★`a2a` 는 모듈이 꺼져 있으면 선택 불가 | **통과** — 순서 강제 (`docs/handoff/09`) |

## ★교체점이 실제로 교체되는지 눌러서 확인했다

Composer GUI 에서 `a2a_executor` 모듈을 켜고 `team_executor: local → a2a` 로 저장하면
`config/project.yaml` 에 기록된다. 브라우저 왕복 실측 → `docs/handoff/09_Composer_GUI_계약.md` §4.

## 한계

- 교체 후 **실제 원격 실행까지 돌려 본 것은 아니다.** 선언이 바뀌고 조립이 통과하는 것까지다
- Controller 의 "불변" 은 코드 변경 0 을 뜻한다. 성능·타임아웃 특성이 같다는 뜻은 아니다

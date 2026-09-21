# DoD-20 — `TeamExecutorPort` 교체 시 Controller 가 바뀌지 않는다

- v7 §27 항목 20 / 검증 방법: Local/A2A adapter 교체 test + Controller import boundary 정적 검사
- 실행: 2026-08-16
- 판정: 통과

## ★2026-09-06 갱신 — 판정은 유효하고, 낡은 이름·수치·경로만 현행으로 고쳤다


| 낡았던 것 | 지금 (실측 2026-09-06) |
|---|---|
| `tests/unit/core/test_core_isolation.py` | **`tests/contract/test_core_isolation.py`** 로 이동 |
| `3 passed` | **7 passed** (ports 6 + 격리 1) |

```powershell
python -m pytest tests/unit/ports/test_team_ports.py tests/contract/test_core_isolation.py -q
→ 7 passed
```

늘어난 넷은 이후 세션들이 이 경계에 붙인 것이다 — 그중 하나가
`test_local_executor_rejects_task_tools_outside_manifest`(2026-08-24)로,
Controller 가 넘긴 `allowed_tools` 가 manifest 부분집합이 아니면 Team 을
아예 호출하지 않는다. **Port 교체 불변성은 그대로**이고 덮는 범위가 늘었다.


## 재현 명령 (2026-09-06 현행)

```powershell
python -m pytest tests/unit/ports/test_team_ports.py tests/contract/test_core_isolation.py -q
python -m pytest tests/integration/a2a/test_remote_round_trip.py -q
```

★**둘째 줄도 낡아 있었다.** 옛 명령 `tests/e2e/test_project_composition.py` 는
지금 **테스트가 0건 돈다**(그 파일이 없다). LOCAL↔A2A 교체를 실제로 밟는 것은
`tests/unit/ports/test_team_ports.py`(직접 호출 동등성·manifest 밖 tool 거부·
원격 상태 매핑·타임아웃 경계)와 `tests/integration/a2a/test_remote_round_trip.py`
다 — 합쳐 **16 passed**.

★아래 「실제 출력」의 `tests/unit/core/...` 는 **옛 경로**다(2026-08-16
기록). 지금은 `tests/contract/` 이고 합계도 3 → 7 이다. 당시 기록은 그대로 둔다.

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
| ★`a2a` 는 모듈이 꺼져 있으면 선택 불가 | **통과** — 순서 강제 (`wiki/records/handoff/09`) |

## ★교체점이 실제로 교체되는지 눌러서 확인했다

Composer GUI 에서 `a2a_executor` 모듈을 켜고 `team_executor: local → a2a` 로 저장하면
`config/project.yaml` 에 기록된다. 브라우저 왕복 실측 → `wiki/records/handoff/09_Composer_GUI_계약.md` §4.

## 한계

- 교체 후 **실제 원격 실행까지 돌려 본 것은 아니다.** 선언이 바뀌고 조립이 통과하는 것까지다
- Controller 의 "불변" 은 코드 변경 0 을 뜻한다. 성능·타임아웃 특성이 같다는 뜻은 아니다

# DoD-19 — LOCAL/A2A 가 동일 `TeamResult` 로 정규화된다

- v7 §27 항목 19 / 검증 방법: 두 Executor contract test 에서 canonical JSON 비교
- 실행: 2026-08-16
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/unit/ports/test_team_ports.py -q
```

## 실제 출력

```
3 passed

test_local_executor_is_identical_to_direct_team_call
  LocalTeamExecutor(registry).execute(task).model_dump()
    == team.execute(task).model_dump()            → 동일

test_a2a_maps_remote_states_without_exposing_them
  {"status":"input_required", ...}          → outcome=waiting   next_action=wait_for_input
  {"status":"completed", "artifact":{...}}  → outcome=completed next_action=respond
  {"status":"failed", "failure_code":"boom"}→ outcome=failed    next_action=escalate

test_agent_card_advertises_capabilities
```

## 판정 근거

| 요구 | 결과 |
|---|---|
| LOCAL 실행이 Team 직접 호출과 동일한 결과 | **통과** — `model_dump()` 완전 일치 |
| A2A 원격 상태가 `TeamResult` 로 정규화 | **통과** — 3종 매핑 |
| ★원격 상태 어휘가 밖으로 새지 않음 | **통과** — `input_required` 가 아니라 `wait_for_input` 으로 나온다 |
| Controller 가 두 Executor 를 구분하지 않음 | **통과** — `TeamExecutorPort` 경유 (DoD-20) |

## ★이 테스트가 한 번 흔들렸다

`observed_at=datetime.now(UTC)` 가 두 호출에서 다르게 찍혀 `model_dump()` 비교가
클럭 틱에 걸렸다. 전체 실행 중 1회 관측, 단독 실행은 통과.
fixture 시각을 고정해 해소했다 → `wiki/records/reports/debugs/2026-08-14_시계에_걸린_테스트가_가끔_실패한다.md`

★**결과 전체를 비교할 때는 비결정 필드가 섞여 있는지 본다.** 시각·UUID·순서가 대표적이다.

## 한계

- A2A 쪽은 **더미 Transport** 다. 실제 원격 Agent 와 왕복하지 않았다 (DoD-26·27 이 그 항목)
- Artifact 의 큰 payload·스트리밍은 다루지 않았다

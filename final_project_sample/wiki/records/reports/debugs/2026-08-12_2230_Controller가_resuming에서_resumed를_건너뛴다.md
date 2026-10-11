# 결함 — Controller 가 `resuming` 에서 `resumed` 를 건너뛰고 완료시키려 한다

- 발견: 2026-08-12 22:30, **S-CTRL 테스트가 잡았다** (Codex 작성, Claude 확인)
- 상태: 미수정 → 수정 발주
- 위험도: **높음** — 승인 후 종단 완료 경로가 막힌다 (v5 M2 게이트 차단)

## 1. 위치

`app/application/controller.py` — TeamResult 적용 경로 (`controller.py:133` 부근,
`NextAction.RESPOND` → `EventType.COMPLETED` 매핑)

## 2. 재현

```powershell
python -m pytest tests/integration/controller/test_controller_integration.py::test_e2e_cancelled_customer_post_charge_approval_flow -q
```

## 3. 실측 출력

```
app.core.contracts.InvalidTransition: 허용되지 않은 전이:
  resuming --completed--> ?  (이 상태에서 가능한 이벤트: ['resumed', 'resume_failed'])
app\domain\case.py:63
```

관측된 상태 전이: `... ('waiting_approval', 4), ('resuming', 5)` 에서 멈춤.
기대: `('running', 6), ('resolved', 7)` 까지.

## 4. 원인

REST approve endpoint 가 `APPROVED` 이벤트로 `waiting_approval → resuming` 까지 만든다.
그 다음 Controller 가 Team 결과(`next_action=respond`)를 **`COMPLETED` 이벤트로 곧장 적용**한다.

v5 §5-1 상태표상 `resuming` 의 허용 다음 상태는 `running`(`resumed`) 과 `escalated`(`resume_failed`) 뿐이다.
`resuming --completed--> resolved` 는 **존재하지 않는 전이**다.

★`controller.resume()` (controller.py:169) 은 `RESUMED` 를 올바르게 발행한다.
문제는 **승인 경로가 그 함수를 타지 않는다**는 것이다. 승인 후 실행 재개가
`resume()` 을 거치지 않고 메인 루프로 들어간다.

## 5. 이 결함이 드러난 방식이 중요하다

- **상태기계가 스스로 막았다.** `transition_case()` 단일 진입점과 전이표가
  잘못된 상태 변경을 런타임에 거부했다. 직접 `UPDATE` 하는 구현이었다면
  `resolved` 로 조용히 넘어가고 이벤트 이력이 깨진 채 통과했을 것이다.
- **테스트가 상태·version 순서를 리스트로 단언**했기 때문에 잡혔다.
  "최종 상태가 resolved 인가"만 봤다면 예외 메시지만 보고 테스트를 느슨하게 고쳤을 수도 있다.
- ★**Codex 가 제품 코드를 고치지 않고 보고했다.** 지시서에
  "테스트가 결함을 드러내면 고치지 말고 리포트에 적어라"를 넣은 것이 작동했다.

## 6. 대응

Controller 메인 루프가 Case 상태를 확인해, `resuming` 이면 **먼저 `RESUMED` 를 발행**해
`running` 으로 옮긴 뒤 Team 결과를 적용하도록 고친다.
`resume_node` 는 `RESUME_NODE_FOR_WAIT[wait_reason]` 로 결정한다 (이미 존재).

수정 후 재검증: 시나리오 1의 전이 순서가
`classifying(1) → routing(2) → running(3) → waiting_approval(4) → resuming(5) → running(6) → resolved(7)`
로 관측돼야 한다.

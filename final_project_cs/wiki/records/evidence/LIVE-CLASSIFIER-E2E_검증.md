# evidence — REST API 실 classifier 종단(e2e) 라이브 테스트

- 실행: 2026-08-17
- 판정: 통과
- 관련: `wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md` 의 "남은 위험" —
  "실 REST API 경로를 진짜로 도는 e2e 테스트가 없다"를 메운다

## 재현 명령

```powershell
python -m pytest tests/live/test_feedback_classifier_live_e2e.py -m live -q
```

## 실제 출력

```
1 passed in 4.64s
```

두 번 반복 실행해 정상 통과 확인, 그 뒤 tenant 잔존 여부를 직접 조회해 0건임을
확인(재실행해도 흔적을 안 남긴다).

## ★계약 설계 실수를 실행하며 직접 발견·수정했다

Codex 에게 넘긴 계약(`wiki/records/handoff/_prompts/S-LIVE-CLASSIFIER-E2E.md`)은
`create_app(controller=None)` 이면 controller 가 실행되지 않고 분류 단계에서
멈춘다고 가정했다. **이 가정이 틀렸다.** 실제로 `app/presentation/api/app.py`
는:

```python
injected_controller = controller is not None
if controller is None:
    controller = composition.build_controller()   # 항상 진짜 controller 를 만든다
runtime_controller = controller if injected_controller or
    getattr(classifier, "__module__", "").startswith("app.composition") else None
```

classifier 를 주입하지 않으면(`composition.build_classifier()` 가 기본값이 되고
그 `__module__` 은 `"app.composition"`) `runtime_controller` 는 **항상 진짜
controller** 가 된다 — `controller=None` 인자와 무관하게. 즉 이 테스트는
분류뿐 아니라 **진짜 Team 실행까지 전부 탄다.**

Codex 가 계약대로 만든 최초 버전을 처음 실행했을 때 그대로 드러났다:

```
AssertionError: real classifier rejected the message: {'case_id': '...',
  'status': 'escalated', ..., 'intent': 'shipping',
  'issue_code': 'shipping_delivered_not_received', ...}
```

★**분류 자체는 완벽했다** — `intent='shipping'`, `issue_code=
'shipping_delivered_not_received'` — 이 세션에서 고친 결함이 실제로 고쳐졌다는
뜻이다. 실패한 건 이 테스트의 원래 단언(`status != "escalated"`)이 잘못된
범위였기 때문 — 합성 고객이라 주문 데이터가 없으니 Team 이 정상적으로
`policy_not_found` 나 "주문 없음" 계열로 escalate 할 수 있고, 그건 이 테스트가
보증할 범위가 아니다.

### 수정 — Claude 가 직접(Codex 재위임 없이)

이 테스트의 관심사를 **분류 성공 여부만**으로 좁혔다. 최종 case 상태 대신
`case_events` 에서 `CLASSIFIED` 이벤트를 직접 조회해 `payload_json.intent` 가
새 도메인 값인지 확인하고, `CLASSIFICATION_FAILED` 이벤트가 없는지 확인한다.

동시에 발견한 두 번째 문제 — 테스트 정리(teardown)가 `agent_runs` 계열 테이블을
지우지 않아 `ForeignKeyViolation` 으로 **정리 자체가 실패**하고 있었다(controller
가 실제로 실행되니 `agent_runs`·`team_tasks`·`llm_calls` 행이 생기는데, 이걸
계약에 명시하지 않았다 — 내 계약 누락). 정리 순서에 `llm_calls`→`team_tasks`→
`agent_runs` 를 `customer_cases` 보다 먼저 지우도록 추가.

이 실패로 정리 트랜잭션이 롤백되며 **첫 실행분 tenant 1개가 DB 에 영구히
남았다.** 수동으로 같은 FK 순서로 지워 정리했다(재현 로그는 이 문서 하단).

## 잔존 데이터 정리 기록

```
found: ['live_classifier_cbb9e870e2e64984bfd77ead45208be2']
cleaned
```

정리 후 `SELECT count(*) FROM tenants WHERE tenant_id LIKE 'live_classifier_%'`
→ `0`.

## 최종 확인

```powershell
python -m pytest -q          # 295 passed, 2 deselected (test_llm_live + 이 테스트)
```

## 이 테스트가 실제로 증명하는 것

- 운영 REST API(`POST /v1/cases`)에 실 한국어 쇼핑몰 메시지를 보내면
- 실제 주입되는 그 classifier(`composition.build_classifier()`)가
- 실 OpenAI 호출로 `intent="shipping"` 을 정확히 반환하고
- `feedback.py::INTENTS` 검증을 통과해 `CLASSIFIED` 이벤트가 기록된다

이것이 이 세션에서 고친 최고 심각도 결함(`wiki/records/evidence/
PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md`)의 **자동화된, 재실행 가능한 증거**다 —
지금까지는 Claude 가 터미널에서 수동으로 한 번 확인한 것뿐이었다.

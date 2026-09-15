# S-CONSUMER-IDEMPOTENCY-GATE — DoD-23 게이트 추가

## 배경 (읽지 않아도 되는 맥락 — 판단에만 참고)

`wiki/records/evidence/DoD-23_consumer_idempotency.md` 는 "부분 통과"다. v7 §27 항목 23은
"모든 consumer 가 at-least-once 하에서 idempotent 하다"를 요구하는데, 지금 이
시스템의 message consumer 는 `app/infrastructure/messaging/worker.py` 의
`OutboxWorker` **하나뿐**이고, 그건 이미 `tests/integration/controller/test_controller_integration.py`
의 `test_outbox_duplicate_is_delivered_once` 로 증명됐다. 부분 통과인 이유는
**"consumer 가 하나뿐이라 검증할 게 없다"** 이지 검증이 빠졌다는 뜻이 아니다.

evidence 파일의 "재측정 조건" 2번이 남은 실제 작업이다:
> 새 consumer 가 그 테스트 없이 추가되지 못하게 하는 게이트를 만든다
> (검사하지 않는 규칙은 지켜지지 않는다)

## 반드시 읽을 파일 (이 목록 밖은 읽지 않아도 된다)

1. `app/infrastructure/messaging/worker.py` — 지금 유일한 consumer
2. `app/infrastructure/messaging/outbox.py`, `app/infrastructure/messaging/ports.py`
3. `tests/integration/controller/test_controller_integration.py` 에서
   `test_outbox_duplicate_is_delivered_once` 함수 하나만
4. `tests/architecture/test_basement_is_domain_free.py` — **스타일 참고용**.
   `Path` 로 소스를 스캔해서 위반을 찾는 이 저장소의 architecture test 관례를 그대로 따른다
5. `wiki/records/evidence/DoD-23_consumer_idempotency.md`

## 만들 것

**한 파일만 새로 만든다: `tests/architecture/test_consumer_idempotency_gate.py`**

이 테스트가 지켜야 할 성질 — **진짜로 실패할 수 있어야 한다** (v7 도메인 이 저장소는
"항상 참인 단언"을 이미 여러 번 겪었다. 그런 걸 만들면 안 된다):

1. `app/infrastructure/messaging/` 아래 `*.py` 를 소스 스캔해서 **consumer 클래스**
   (예: `class ....Worker` 나 `class ....Consumer` 패턴 — 정규식으로 찾는다)를 전부 찾는다.
2. **알려진·검증된 consumer 이름의 명시적 목록**(예: `PROVEN_IDEMPOTENT_CONSUMERS = {"OutboxWorker"}`)
   을 테스트 파일 상단에 상수로 선언한다.
3. 1번에서 스캔한 실제 consumer 집합과 2번의 선언된 집합이 **정확히 일치하는지** assert 한다.
   - 스캔된 집합에 선언 목록에 없는 이름이 있으면 → 실패. 메시지에
     "새 consumer 를 추가했으면 duplicate-delivery idempotency 테스트를 쓰고
     PROVEN_IDEMPOTENT_CONSUMERS 에 추가하라" 고 안내한다.
   - 선언 목록에는 있는데 스캔에서 사라진 이름이 있어도 실패시킨다(코드가 지워졌는데
     목록만 남는 것도 거짓 안전감이다).
4. **이 테스트 자체가 진짜로 잡아내는지 스스로 확인**하고 그 확인 방법을
   테스트 파일 맨 위 docstring 한두 줄에 남긴다 (예: "확인 방법: 이 디렉터리에
   `class DummyConsumer` 를 추가하고 목록에 넣지 않은 채 돌리면 실패하는지
   로컬에서 확인했다"). ★**always-true 검사면 안 된다** — 이 요구를 어기면
   반려한다.

## 하지 않을 것 (범위 밖)

- `OutboxWorker` 자체의 동작을 바꾸지 않는다.
- 새로운 consumer(가짜/예시)를 실제로 추가하지 않는다 — 지금 시스템은 consumer
  가 하나뿐인 게 사실이고, 그걸 유지한 채로 게이트만 만든다.
- `wiki/records/evidence/DoD-23_consumer_idempotency.md` 의 "판정"을 "통과"로 바꾸지 않는다.
  여전히 consumer 가 하나뿐이므로 "부분 통과"가 맞다 — 대신 그 파일 맨 아래에
  "게이트 추가됨(`tests/architecture/test_consumer_idempotency_gate.py`), 재현 명령과
  실제 출력"을 붙인다. **재현 명령은 반드시 실제로 실행해서 나온 출력을 그대로 붙인다** —
  실행하지 않고 상상한 출력을 쓰지 않는다.
- `config/guardrails.yaml` 이나 `app/core/**` 를 건드리지 않는다.

## 완료 기준

```powershell
python -m pytest tests/architecture/test_consumer_idempotency_gate.py -v
python -m pytest -q   # 전체 스위트가 그대로 초록이어야 한다 (2026-08-17 기준 321 passed)
```

`wiki/records/reports/` 에 짧은 리포트를 남긴다: 무엇을 만들었는지, 왜 always-true 가
아닌지 어떻게 확인했는지, 전체 스위트 실행 결과 원문.

로그·임시 빌드 산출물은 저장소 안이 아니라 `%TEMP%` 에 쓴다.

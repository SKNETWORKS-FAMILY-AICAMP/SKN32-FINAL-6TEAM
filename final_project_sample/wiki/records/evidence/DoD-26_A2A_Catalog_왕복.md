# DoD-26 — A2A Catalog Verification 왕복

- v7 §27 항목 26 / 검증 방법: Agent Card 발견 → Task working → input-required → 추가 입력 → Artifact 완료, `waiting_external`/resume 상태 검증
- 실행: 2026-08-16
- 판정: 통과 (★한계는 아래 참조)

## 재현 명령

```powershell
python -m pytest tests/integration/a2a/test_remote_round_trip.py -q
```

## 실제 출력

```
10 passed

test_agent_card_is_discovered_not_assumed
  GET /.well-known/agent-card.json  →  200
  name = "Catalog & Verification Remote Team"
  capabilities = {catalog.lookup, order.verify}
  authentication.scheme = bearer

test_full_round_trip_working_input_required_then_artifact
  1) discover  → capability "order.verify" 확인
  2) POST /a2a/tasks            → status=working
  3) GET  /a2a/tasks/{id}       → status=input-required
                                   input_schema.required = ["order_id"]
     → TeamResult(next_action=wait_for_input)
  4) POST /a2a/tasks/{id}/input {"order_id":"ORD-42"}   ← ★재개
                                → status=completed
  5) Artifact → TeamResult(outcome=completed, next_action=respond)
     answer 에 "ORD-42" 포함
     evidence[0].source_type = remote_agent

test_missing_input_is_rejected_by_the_remote     → 422
```

## 무엇이 바뀌었나

전에는 **고정 dict 를 돌려주는 더미 Transport** 였다:

```python
class Transport:
    async def submit(self, endpoint, task): return self.response   # 고정 응답
```

지금은 실제 원격 앱(`app/presentation/a2a/remote_agent.py`)에
**HTTP 로** 말한다(`app/infrastructure/a2a/http_transport.py`).

★`A2ATeamExecutor` 는 **한 줄도 안 바꿨다.** transport 만 갈아 끼웠다 — Port 를 둔 이유다(DoD-20).

## 판정 근거

| v7 요구 | 결과 |
|---|---|
| Agent Card **발견** | **통과** — 만드는 게 아니라 `GET` 으로 가져온다 |
| Task `working` 관측 | **통과** |
| `input-required` → 추가 입력 → **재개** | **통과** — `POST /input` 으로 실제로 되돌려 보낸다 |
| Artifact 로 완료 | **통과** — `TeamResult` 로 정규화 |
| Catalog & Verification Remote Team | **통과** — 전용 원격 Team 으로 구현 |
| 원격이 스키마를 강제 | **통과** — `order_id` 없으면 422 |

## ★계약을 하나 늘렸다 — `Evidence.source_type = "remote_agent"`

원격이 돌려준 근거를 `tool_result` 로 뭉개면
**우리 시스템이 확인한 사실**과 **남의 시스템이 그렇다고 말한 것**이 구분되지 않는다.
신뢰도가 다르고, 근거 대조(§9-E)에서도 다르게 다뤄야 한다.

테스트가 이 구멍을 먼저 잡았다 — `remote_agent` 가 Literal 에 없어 validation 이 거부했다.

## 한계

- ★**프로세스 경계를 넘지 않는다.** `httpx.ASGITransport` 로 in-process 에 붙였다.
  상태코드·헤더·직렬화는 실제로 타지만 **네트워크 단절·부분 응답·TLS 는 재현되지 않는다**
- `waiting_external` Case 상태로 두고 resume 하는 **Controller 종단**은 아직이다.
  여기서 관측한 것은 Executor·Transport 층의 왕복이다
- 원격이 하나뿐이다. capability 로 **여러 원격 중 고르는** 라우팅은 없다

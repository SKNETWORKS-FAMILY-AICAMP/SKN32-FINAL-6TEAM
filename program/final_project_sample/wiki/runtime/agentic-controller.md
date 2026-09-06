---
type: concept
title: Controller 가 Case 를 어떻게 굴리나
description: 한 트랜잭션 안에서 라우팅·실행·결과 적용을 한다. 두 개의 시계가 따로 돈다
status: draft
tags: [architecture, state, agent]
---

# Controller 가 Case 를 어떻게 굴리나

`run_case()` 하나가 전부다. `application/controller.py:107-163`

```
연결 열기 → Case 읽기 → 트랜잭션 시작
  ① routing 이면 Team 을 찾아 routed
  ② resuming 이면 resumed
  ③ 벽시계 초과 검사
  ④ Team 실행 (타임아웃 걸고)
  ⑤ 결과 적용
```

**전부 한 트랜잭션이다.** 중간에 실패하면 아무것도 안 남는다.

## ★ 시계가 둘이다

`[실측]` 서로 다른 것을 잰다.

| 가드레일 | 무엇을 잰다 | 초과하면 |
|---|---|---|
| `case_wall_clock_seconds` | **Case 하나가 전체로 얼마나 걸렸나** | `GUARDRAIL_ESCALATED` |
| `team_timeout_seconds` | **Team 호출 하나가 얼마나 걸렸나** | `GUARDRAIL_ESCALATED` |

**벽시계는 Team 실행 전에 잰다.** 이미 오래 걸린 Case 는 Team 을 부르지도 않는다.

`[실측]` 둘 다 `payload` 에 **어느 가드레일이 걸렸고 실제 관측값이 얼마인지**를 남긴다.

```python
payload={"guardrail": "team_timeout_seconds", "observed": ...}
```

**"타임아웃 났다"가 아니라 "무엇이 몇 초에 걸렸다"를 남긴다.**

## ★ 대조는 Team 이 돌려준 것으로 하지 않는다

`[실측]` 코드 주석이 이유를 적어 뒀다. `controller.py:158-160`

> **대조에는 Controller 가 만든 `task.context` 를 넘긴다.**
>
> Team 이 돌려준 `result.context` 를 쓰면 **근거와 제안을 같은 쪽이 지어낼 수 있어 대조가 순환한다.**
>
> **위조할 수 없는 쪽으로 잰다.**

**이게 [verification.md](../quality/verification.md) 가 성립하는 전제다.** 대조 대상을 Team 이 고를 수 있으면 대조가 의미 없다.

## 라우팅에 실패하면

`[실측]` `RegistryError` 를 잡아 `ROUTING_FAILED` 로 보낸다.

```python
payload={"failure_code": "no_team"}
```

**그리고 run 을 `failed` 로 닫는다.** 열어 둔 채 끝내지 않는다.

## 재개는 대기 사유에 따라 노드가 다르다

`[실측]` `RESUME_NODE_FOR_WAIT[wait_reason]`

```
state_json.wait_reason  →  어느 노드부터 다시 시작할지
기본값 "customer_input"
```

**어디서 멈췄는지를 Case 가 들고 있다.** Controller 가 추측하지 않는다.

## 재시도가 걸리는 곳과 안 걸리는 곳

`[실측]` **`_transition_with_retry()` 를 쓰는 곳은 세 곳뿐이다.**

| 이벤트 | 재시도 |
|---|---|
| `ROUTED` · `ROUTING_FAILED` | **있다** |
| `VALID_INPUT` | **있다** |
| `RESUMED` · 가드레일 escalation · 결과 적용 | **없다** |

→ [conflict-retry.md](conflict-retry.md)

## 검증 실패는 조용히 넘어가지 않는다

`[실측]` `_reject_unverified()`.

> 제안이 사실과 어긋나면 폐기하고 `escalated` 로 보낸다.
>
> **조용히 무시하지 않는다.** 실패한 필드와 기대값·실제값의 **hash** 를 남긴다.

**hash 를 남기는 게 중요하다.** 값 자체를 남기면 PII 가 로그로 샌다.

## 관계

- [case-lifecycle.md](case-lifecycle.md) — 상태와 전이
- [conflict-retry.md](conflict-retry.md) — 충돌 재시도
- [message-broker.md](message-broker.md) — 결과 발행
- [../quality/verification.md](../quality/verification.md) — 무엇과 대조하나

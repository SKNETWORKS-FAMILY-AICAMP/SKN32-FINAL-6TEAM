---
type: concept
title: Memory
description: 과거 이력과 유사 Case를 ContextPack에 넣는다. 예산에서 가장 먼저 잘리는 자리다
status: draft
tags: [data]
owners: [human:미배정]
domain: neutral
---

# Memory

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/context.py` · `case_events` · `customer_cases`

## 두 가지

`ContextPack`에 들어가는 이력은 둘이다.

| 섹션 | 무엇 | 예산 | 상한 |
|---|---|---|---|
| `history_summary` | **이 Case**의 지난 경과 | 1,200 토큰 | 10,000자 |
| `similar_cases` | **다른 Case** 중 비슷한 것 | 600 토큰 | 3건 |

`[실측]` `config/guardrails.yaml`

★`[실측 2026-09-10 작업 트리]` **예산은 있고 채워 넣는 곳이 비어 있다.** `Controller._task()` 가 `history_entries=[]` 를 넘기고 유사 Case 도 기본 빈 목록이다(`controller.py:93`). **그래서 이 두 섹션은 지금 늘 비어 있다** — 아래 「가장 먼저 잘리는 자리」는 채워졌을 때의 이야기다.

## ★ 가장 먼저 잘리는 자리다

`SECTION_FILL_ORDER`에서 둘 다 뒤쪽이다.

```python
SECTION_FILL_ORDER = (
    "system_instruction", "case_state", "tool_facts",
    "policy_rag", "history_summary", "similar_cases",
)
```

**마지막에 채우는 것이 가장 먼저 잘린다.** `similar_cases`가 `eviction_order`의 첫 줄이다.

```yaml
eviction_order:
  - similar_cases        ← 가장 먼저
  - history_detail
  - low_score_rag
  - duplicate_tool_facts
```

**이 배치가 우선순위 판단이다.** 지금 이 Case의 사실(`tool_facts`)과 정책(`policy_rag`)이 남의 비슷한 사례보다 중요하다.

## 잘려도 조용하지 않다

```
omissions: ["history_summary:detail:3", ...]
degraded: true
```

**Team이 "이력이 깎였다"를 알고 판단한다.**

## 출처는 이벤트다

`case_events`가 append-only라 **이력을 재생할 수 있다.**

```python
replay_case(conn, tenant_id=..., case_id=...)
```

`[실측]` 재생은 결정적이다.

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-RT-001` | 이벤트 재생은 결정적이다 | `tests/unit/core/test_case_reducer.py::test_replay_is_deterministic` |
| `INV-CS-RT-004` | 부분 접기 결과가 단계별 결과와 같다 | `tests/unit/core/test_case_reducer.py::test_fold_reproduces_step_by_step_result` |

**004가 요약의 근거다.** 어디서 접어도 같은 결과가 나와야 요약을 믿을 수 있다.

## 상태 패치는 병합이다

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-RT-005` | 상태 패치는 병합되며 기존 값을 지우지 않는다 | `tests/unit/core/test_case_reducer.py::test_state_patch_merges_and_does_not_wipe` |

**부분 갱신이 나머지를 날리면 이력이 사라진다.**

## 격리

유사 Case 검색도 tenant·customer를 벗어나지 않는다.

**남의 Case가 "비슷한 사례"로 들어오면 정보 유출이다.**

→ [../data/tenancy.md](../data/tenancy.md)

## LangGraph checkpoint와 다르다

| | Memory | checkpoint |
|---|---|---|
| 무엇 | 업무 이력 | 실행 snapshot |
| 권위 | `customer_cases`가 정본 | 재개용 |
| 되돌리기 | **안 함** | 실행 재개는 함 |

**checkpoint로 업무 상태를 되돌리지 않는다.**

## 지금 범위

`[미확보]` 장기 기억(고객별 선호·과거 패턴 누적)은 아직 없다. 현재 Memory는 **Case 단위 이력**과 **유사 Case 3건**이다.

## 관계

- [context-broker.md](context-broker.md) — 조립
- [context-budget.md](context-budget.md) — 예산과 축출 순서
- [rag-retrieval.md](rag-retrieval.md) — 다른 입력원
- [../runtime/shared-state.md](../runtime/shared-state.md) — 이벤트와 재생

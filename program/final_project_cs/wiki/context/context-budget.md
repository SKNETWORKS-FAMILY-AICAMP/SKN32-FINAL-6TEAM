---
type: contract
title: Context 예산
description: 12,000 토큰을 섹션별로 나누고 정해진 순서로 자른다. 자를 수 없는 것은 거부한다
status: draft
tags: [architecture, cost]
owners: [human:미배정]
---

# Context 예산

`config/guardrails.yaml` · `app/core/context.py`

**가드레일 수치는 `config/guardrails.yaml` 한 곳에만 둔다.** 코드에 흩어 놓지 않는다.

## 배분

`[실측]`

```yaml
context:
  token_budget: 12000
  sections:
    system_instruction: 1800   # 고정 — 제거하지 않음
    case_state:         2400   # 고정 — 제거하지 않음
    tool_facts:         2400
    policy_rag:         3600
    history_summary:    1200
    similar_cases:        600
```

**합이 정확히 12,000이어야 한다.** 다르면 기동 시 예외다.

## 제거 순서

```yaml
  eviction_order:
    - similar_cases
    - history_detail
    - low_score_rag
    - duplicate_tool_facts
  never_evict:
    - case_state
    - latest_safety_policy
```

**결정론적이다.** 같은 입력이면 항상 같은 것이 잘린다. 이게 재현성의 조건이다.

## 상한

```yaml
  max_evidence_items: 40
  max_similar_cases: 3
  max_history_summary_chars: 10000
```

토큰 예산과 별개로 **개수 상한**이 있다. 짧은 evidence가 100개 들어오는 걸 막는다.

## 왜 12,000인가

`[실측]` 설정 주석이 밝힌 세 가지. **모델의 context window 한계가 아니다.**

| 이유 | 설명 |
|---|---|
| 건당 LLM 비용 통제 | 입력 토큰이 곧 비용. 현재 실측 입력 8,968 토큰 |
| lost-in-the-middle 완화 | 길수록 중간 내용을 놓친다 |
| 실험 재현성 | 예산이 흔들리면 A/B 비교가 무의미해진다 |

**세 번째가 특히 중요하다.** 예산을 늘리면 이전 측정과 비교할 수 없다.

## 토큰을 어떻게 세는가

`tiktoken`으로 **실측**한다. 어림잡지 않는다.

```python
@lru_cache(maxsize=4)
def _encoder(model: str = "cl100k_base") -> tiktoken.Encoding: ...
```

## ★ 자를 수 없으면 거부한다

`INV-CS-CTX-002`가 이것이다.

**잘라서 의미가 깨지는 구간은 조용히 자르지 않는다.** `ContextBudgetError`를 던진다.

```python
class ContextBudgetError(RuntimeError): ...
```

조용히 자르면 Team이 반쪽 정책을 보고 판단한다. **차라리 실패하는 게 낫다.**

## 예산이 실제로 문제를 일으킨 사례

`[실측]` 이 프로젝트에서 두 번 터졌다.

**하나 — 프로덕션 밖에서.** 학습 데이터 수확 스크립트가 Broker를 우회해 evidence가 중복됐고, 중앙값 10,670 토큰이 되어 12GB VRAM 학습이 OOM으로 죽었다.

**둘 — 학습 max_length 기본값.** `train.py`의 `max_length=512`가 실제 데이터(중앙값 10,670)의 5%만 남기고 잘랐다. 그 상태의 loss 개선은 **잘린 쓰레기를 더 잘 예측하도록 배운 것**이었다.

**둘 다 "조용히 잘렸다"가 원인이다.** 그래서 `omissions`와 `degraded`가 있다.

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-CTX-001` | 예산 초과 시 정해진 순서로 축출한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_eviction_is_budgeted_and_ordered` |
| `INV-CS-CTX-002` | 자를 수 없는 구간은 거부한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_rejects_untruncatable_sections` |

## 바꾸려면

| 바꾸는 것 | 함께 해야 할 것 |
|---|---|
| `token_budget` | 계약의 `Literal[12000]` 변경 + `contract_version` 상향 + 재평가 |
| 섹션 배분 | 합이 `token_budget`과 같아야 함 |
| `eviction_order` | `SECTION_FILL_ORDER`와 역순 유지 |

**평가 수치를 이전과 비교하려면 예산을 안 바꿔야 한다.**

## 관계

- [context-broker.md](context-broker.md) — 조립 로직
- [../teams/team-contract.md](../teams/team-contract.md) — `ContextPack`의 `degraded`·`omissions`
- [../../../wiki/business/infrastructure-cost.md](../../../wiki/business/infrastructure-cost.md) — 토큰이 비용이 되는 경로

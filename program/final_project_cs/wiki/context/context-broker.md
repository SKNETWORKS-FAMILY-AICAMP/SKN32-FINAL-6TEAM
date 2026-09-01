---
type: concept
title: Context Broker
description: Team이 필요로 하는 자료를 예산 안에서 모아 ContextPack으로 만든다. Team은 직접 읽지 않는다
status: draft
tags: [architecture, data]
owners: [human:미배정]
---

# Context Broker

`app/core/context.py` (282줄)

## 책임

Team이 선언한 `required_context`를 보고 자료를 읽어 **`ContextPack` 하나로 조립한다.**

읽는 곳은 셋이다.

```
read 도구 (주문·배송·정책·반품)
RAG 검색 (지식 문서)
Memory (과거 이력)
```

## 경계

**Team은 read 도구를 직접 호출하지 않는다.** 부족하면 `need_more_context`로 Controller에 요청한다.

이렇게 하는 이유는 **읽기 예산을 Core가 통제**하기 위해서다. → [context-budget.md](context-budget.md)

## 섹션과 예산

`[실측]` `config/guardrails.yaml`

| 섹션 | 예산 | 제거 |
|---|---|---|
| `system_instruction` | 1,800 | **절대 안 함** |
| `case_state` | 2,400 | **절대 안 함** |
| `tool_facts` | 2,400 | 중복부터 |
| `policy_rag` | 3,600 | 점수 낮은 것부터 |
| `history_summary` | 1,200 | 상세부터 |
| `similar_cases` | 600 | **가장 먼저** |
| **합계** | **12,000** | |

`[실측]` 코드가 **합이 `token_budget`과 다르면 기동 시 예외를 던진다.**

```python
if total != self.budget:
    raise ...(f"섹션 예산 합 {total} 이 token_budget {self.budget} 과 다르다")
```

**설정을 잘못 고치면 조용히 넘어가지 않고 바로 죽는다.** 좋은 설계다.

## 채우는 순서와 자르는 순서는 역순이다

```python
SECTION_FILL_ORDER = (
    "system_instruction", "case_state", "tool_facts",
    "policy_rag", "history_summary", "similar_cases",
)
```

**앞에 있을수록 먼저 자리를 잡는다.** 마지막에 채우는 것이 자리가 없을 때 가장 먼저 잘린다.

`eviction_order`는 정확히 이 역순이어야 한다. 코드 주석이 그렇게 못박고 있다.

## ★ 무엇을 뺐는지 반드시 남긴다

```python
NEVER_EVICT = frozenset({"system_instruction", "case_state"})
```

잘린 것은 전부 `omissions`에 기록된다. `[실측]` 실제 태그.

```
tool_facts:duplicate:<id>      중복이라 뺌
tool_facts:max_items:<id>      40개 상한
tool_facts:budget:<id>         예산 초과
policy_rag:low_score:<id>      점수 낮음
history_summary:detail:<n>     상세 생략
```

그리고 `degraded=true`가 붙는다.

**코드 주석이 이유를 적어 뒀다.**

> 무엇을 뺐으면 반드시 `omissions`에 남긴다. **신호 없는 축소는 폴백이다.**

**Team이 "자료가 깎였다"를 알아야 판단이 정직해진다.** 모르고 답하면 근거 없는 답이 된다.

## 12,000이라는 숫자의 근거

`[실측]` 설정 파일 주석이 밝히고 있다. **모델 context window 한계가 아니다.**

| 이유 | |
|---|---|
| 건당 LLM 비용 통제 | 입력 토큰이 곧 비용 |
| lost-in-the-middle 완화 | 길수록 중간을 놓친다 |
| 실험 재현성 | 예산이 흔들리면 비교가 안 된다 |

계약에서도 `token_budget: Literal[12000]`으로 고정돼 있다. **바꾸려면 계약 변경이다.**

## 정렬 규칙

| 섹션 | 무엇 기준 |
|---|---|
| `tool_facts` | `observed_at` 내림차순 — 최근 사실 우선 |
| `policy_rag` | `score` 내림차순 — 관련도 우선 |

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-CTX-001` | 예산 초과 시 정해진 순서로 축출한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_eviction_is_budgeted_and_ordered` |
| `INV-CS-CTX-002` | 자를 수 없는 구간은 거부한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_rejects_untruncatable_sections` |

## 실패 사례 — Broker를 우회하면

`[실측]` 학습 데이터 수확 스크립트가 `ContextBroker.build()`를 안 거치고 `team_result.evidence`를 그대로 썼다.

그 결과 **정책 청크가 두 번 중복**됐다 — 개별 policy evidence 8개 + 그걸 통째로 품은 병합 evidence 1개.

```
중앙값 10,670 토큰 → 12GB VRAM 학습 OOM
evidence 예산 400자로 낮춰서야 완주
```

**프로덕션은 안전했다.** 문제는 Broker를 우회한 스크립트였다.

**교훈은 우회 경로를 만들지 말 것이다.**

## 관계

- [context-budget.md](context-budget.md) — 예산 상세
- [rag-retrieval.md](rag-retrieval.md) — 지식 검색
- [memory.md](memory.md) — 이력
- [../teams/team-contract.md](../teams/team-contract.md) — `ContextPack` 계약
- [../teams/team-boundary.md](../teams/team-boundary.md) — 왜 Team이 직접 안 읽는가

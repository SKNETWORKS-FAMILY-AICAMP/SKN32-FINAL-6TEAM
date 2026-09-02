---
type: contract
title: 가드레일 수치 단일 출처
description: 이 숫자들은 config/guardrails.yaml 에만 존재한다. 코드 두 곳에 나타나면 그 자체가 결함이다
status: draft
tags: [contract, architecture, security]
---

# 가드레일 수치 단일 출처

`[실측]` `docs/handoff/06_가드레일_수치.md` 에서 이관.

## ★ 규칙이 먼저다

> **아래 숫자는 `config/guardrails.yaml` 에만 존재한다.**
>
> **같은 숫자가 코드 두 곳에 나타나면 그 자체가 결함이다.**

파이썬에서는 `app.core.settings.guardrails` 로만 읽는다.

**이 문서도 사본이다.** 값이 다르면 `guardrails.yaml` 이 맞다.

## 토큰 예산 — 총 12,000

| 구성 | 예산 | 제거 순서 |
|---|---:|---|
| system/team instruction | 1,800 | **고정. 제거하지 않음** |
| current Case state | 2,400 | 고정 · 최신 우선 |
| tool/DB facts | 2,400 | 오래된 fact 부터 |
| policy/RAG | 3,600 | 낮은 similarity 부터 |
| history summary | 1,200 | 상세 history 부터 |
| similar cases | 600 | **전체 제거 (가장 먼저)** |
| **입력 총량** | **12,000** | deterministic |

```
초과 시:  similar_cases → history 상세 → 낮은 점수 RAG → 중복 tool facts
```

→ [../context/context-budget.md](../context/context-budget.md)

## 신뢰성

| 대상 | 제한 | 초과하면 |
|---|---:|---|
| LLM call timeout | **20초** | 2회 exponential retry |
| Team timeout | **90초** | 실패 기록 후 handoff/escalate |
| Case wall-clock | **180초** | `escalated` |
| LLM retry | 2회 | fallback 1회 후 실패 |
| malformed JSON repair | 1회 | contract error |
| **graph loop** | **12 step** | `escalated` |
| Team task | 6 / case | — |
| **tool call** | **12 / case** | loop guard |
| input token | 12,000 | deterministic truncation |
| **daily cost** | **tenant 당 50 USD** | 신규 자동 실행 중지 · 알림 |

### ★ loop guard 가 하나 더 있다

> **동일 tool + 정규화 arguments signature 가 2회 반복되면 `escalated`.**

**횟수 제한과 별개다.** 12번을 안 채워도 **같은 걸 두 번 하면 멈춘다.**

## RAG

| 항목 | 값 |
|---|---|
| 문서 수 | **25** |
| 총 청크 | **300~400** (문서당 12~16) |
| retrieval | pgvector cosine **top-k = 8** → metadata filter |
| 임베딩 | `text-embedding-3-small` **1536차원** — DDL `vector(1536)` 과 일치해야 한다 |
| index | `hnsw (embedding vector_cosine_ops)` |
| hybrid BM25 / rerank | **Phase 2.** feature flag 뒤. 기본 경로에 안 넣는다 |

→ [../context/corpus-authoring.md](../context/corpus-authoring.md)

## VOC 급증 — 문구 그대로

```
급증 =  오늘_count >= max(5, 1.5 * 최근7일_평균)
   AND  오늘_count - 최근7일_평균 >= 3
```

배치는 **매일 00:10 UTC**.

`[실측]` **금지된 것이 명시돼 있다.**

```
❌ z-score · embedding clustering · topic modeling
```

**단순한 규칙을 고른 게 의도다.** 왜 급증이라 판정했는지 사람이 설명할 수 있어야 한다.

## Resume token

| 항목 | 값 |
|---|---|
| TTL | **24시간** |
| 사용 | **일회성** |
| 저장 | **★평문 저장 금지 — hash 만** |
| 동일 `event_id` 재처리 | idempotent |
| **TTL 만료** | **자동 종료 아님 → `escalated` + 운영자 알림** |

**마지막 줄이 중요하다.** 만료됐다고 조용히 닫지 않는다.

## 낙관적 동시성

```
충돌 시 최신 Case 를 읽어 최대 2회 재계산
같은 Case 에 active run 1개만
UPDATE … WHERE tenant_id AND case_id AND version = :expected  → affected 0 이면 StateConflict
```

→ [../runtime/shared-state.md](../runtime/shared-state.md)

## 평가

| 항목 | 값 |
|---|---|
| golden | **60** (order 15 · shipping 15 · return 15 · exchange 15) |
| holdout | **20** — **평가 기간 중 프롬프트 수정 금지** |
| 반복 | **3회** |
| seed | **7** |
| bootstrap | **10,000회** paired, 95% percentile CI |
| McNemar | discordant pair. **셀 수 < 25 면 exact** |

→ [../../../wiki/evaluation/protocol.md](../../../wiki/evaluation/protocol.md)

## 보존·감사

| 항목 | 값 |
|---|---|
| 최소 보존기간 | **90일** |
| audit 기록 | actor · action · before/after **hash** |
| **audit 금지 항목** | **API key 원문 · 결제 식별자 원문** |

**before/after 를 hash 로 남기는 이유가 금지 항목과 같다.** 값을 남기면 그게 곧 유출이다.

## 관계

- [invariants.md](invariants.md) — 무엇이 강제되나
- [../context/context-budget.md](../context/context-budget.md) — 토큰 예산
- [../runtime/shared-state.md](../runtime/shared-state.md) — 동시성
- [../../../wiki/evaluation/protocol.md](../../../wiki/evaluation/protocol.md) — 평가 절차

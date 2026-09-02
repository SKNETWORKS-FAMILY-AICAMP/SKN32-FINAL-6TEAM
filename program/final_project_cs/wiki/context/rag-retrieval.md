---
type: concept
title: RAG 검색
description: 정책·FAQ 문서를 찾아 ContextPack에 넣는다. tenant와 scope로 좁힌다
status: draft
tags: [data, security]
owners: [human:미배정]
---

# RAG 검색

`app/infrastructure/rag/retriever.py`

## 인터페이스

`[실측]`

```python
def search_policy(
    tenant_id: str, query: str, allowed_scopes: list[str], top_k: int | None = None
): 
    limit = get_guardrails().get("rag.top_k") if top_k is None else top_k
```

**세 가지가 필수 인자다.**

| 인자 | 왜 필수 |
|---|---|
| `tenant_id` | 다른 회사 문서가 나오면 안 된다 |
| `allowed_scopes` | Team이 볼 수 있는 범위만 |
| `query` | — |

`top_k`는 guardrails에서 온다. **코드에 숫자를 박지 않는다.**

## scope로 좁힌다

Team manifest의 `knowledge_scope`가 검색 범위를 정한다.

`[실측]` 예: Return & Refund Team

```python
knowledge_scope = ["order", "return", "refund", "exchange", "policy"]
```

**Response Review Team은 `read.policy`만 갖는다.** 주문 문서를 못 본다.

## 코퍼스

`[실측]` 2026-08-17 기준

| | 값 |
|---|---|
| 문서 | 25건 |
| 청크 | **306** |
| 차원 | 1536 (`text-embedding-3-small`) |

DB 직접 조회로 확인한 값이다. **문서에 적힌 수가 아니라 DB를 세어 갱신한다.**

## ★ 코퍼스 게이트

`[실측]` `python -m scripts.check_corpus`가 검사한다.

**건수만 세면 통과하는 것이 계속 나왔다.** 그래서 게이트가 여러 축을 본다.

| 검사 | 왜 |
|---|---|
| 문서 수·청크 수 | 기본 |
| 중복률 | **가장 어려운 것이 길이가 아니라 중복이다** |
| 제목 점유율 | 마감 3섹션이 25문서에 같은 제목이면 상한에 걸린다 |
| 조사 오류 | 한국어 문법 |

`[실측]` 게이트 자체의 결함도 2건 나왔다. 조사 검사기가 `초과`·`결과` 같은 받침 없는 한자어를 오탐했고, 제목 점유율 상한에 걸릴 뻔해 문서군별 제목을 4종으로 교대시켰다.

**게이트를 만들면 게이트도 틀린다.**

## ★ 코퍼스에 법령이 들어간다 — 지어내면 틀린 답을 가르친다

`[실측]` `docs/plans/2026-08-17_코퍼스_25문서_배분안.md`

> **지어낸 숫자를 쓰면 코퍼스 자체가 틀린 답을 가르친다.**

**초안의 법정 기준 4곳이 틀렸다.** codex 교차검증에서 잡혔고 재확인해 고쳤다.

| 항목 | 기준 | 주의 |
|---|---|---|
| 청약철회 (단순변심) | **7일** | **기산점은 계약내용 서면을 받은 날.** 공급이 늦으면 공급받은 날 |
| 표시·광고와 다른 경우 | **3개월 이내 + 안 날부터 30일** | **단순변심 7일과 별개로 살아 있다** |
| 대금 환급 | **3영업일** | **기산점이 유형별로 다르다.** 반품은 재화를 반환받은 날 |
| **환급 지연이자** | **연 15%** | 법의 "연 40% 이내"는 **상한**이고 실제 요율은 시행령의 15% |
| 반품 배송비 | 단순변심은 소비자 부담 | 판매자 귀책이면 판매자 |
| 청약철회 제한 | **6개 범주** | 포장 훼손은 그중 **하나일 뿐** |
| 불리한 특약 | **무효** | "반품 금지"는 효력 없음 |

**"연 40%"를 그대로 쓴 게 대표적 오류였다.** 상한과 실제 요율을 혼동했다.

### 25문서 배분

```
order 5 · shipping 5 · return 4 · exchange 3
refund 4 · support 2 · incident 2
```

### 범위 밖

**쿠폰·적립금 · 개인정보 변경 · 세금계산서 · 해외직구 · 정기구독**은 넣지 않는다.

`[실측]` **쿠폰·적립금이 범위 밖인 게 [D-001](../../../wiki/decisions/D-001-payment-ownership.md)과 일관된다.**

## 격리

검색 결과가 다른 테넌트 문서를 가져오면 안 된다.

```
tests/integration/rag/test_rag_integration.py
```

`[실측]` 시나리오 질의로 확인했다. "배송완료 미수령 → doc_01", "반품 수량 초과 → doc_14"가 `top_k=8` 안에서 검색된다.

## 예산 안에서 잘린다

검색 결과가 그대로 들어가지 않는다. Context Broker가 `policy_rag` 섹션 예산(3,600 토큰) 안에서 점수 순으로 담는다.

잘린 것은 `omissions`에 남는다.

```
policy_rag:low_score:<source_id>
```

→ [context-budget.md](context-budget.md)

## 실패하면 조용히 메우지 않는다

**RAG가 죽었을 때 일반 지식으로 메우지 않는다.**

```
ContextPack.degraded = true
omissions 에 무엇이 빠졌는지 기록
```

**신호 없는 축소는 폴백이다.** 이 프로젝트가 금지하는 것이다.

## 실패 사례

`[실측]` 두 가지가 있었다.

**하나 — 테스트가 옛 도메인 질의로 하드코딩돼 있었다.** 구독/청구 도메인 질의라 쇼핑몰 코퍼스에서 붉었다. 쇼핑몰 시나리오로 재작성했다.

**둘 — 코퍼스를 코덱스가 재작성했더니 조사 오손 3,401건이 났다.** 재발주 대신 직접 작성으로 전환했다.

## 관계

- [context-broker.md](context-broker.md) — 검색 결과를 조립하는 쪽
- [context-budget.md](context-budget.md) — `policy_rag` 예산
- [memory.md](memory.md) — 다른 입력원
- [../data/tenancy.md](../data/tenancy.md) — 격리
- [../teams/team-contract.md](../teams/team-contract.md) — `knowledge_scope`

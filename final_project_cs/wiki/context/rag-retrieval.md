---
type: concept
title: RAG 검색
description: 정책·FAQ 문서를 찾아 ContextPack에 넣는다. tenant와 scope로 좁힌다
status: draft
tags: [data, security]
owners: [human:미배정]
domain: mixed
domain_note: '[2026-09-22] 코퍼스가 둘이 됐다 — 쇼핑몰 25문서(기록)와 여행 12문서(운영)가 같은 테넌트에 공존하고 scope 로 갈린다. 여행 쪽은 context/travel-corpus.md 가 정본이다'
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

`[실측 2026-09-22 작업 트리]` 예: Activity Team(`app/modules/travel_ops/activity.py`)

```python
knowledge_scope = ["travel_activity", "travel_weather", "travel_cancellation", "travel_access"]
```

★`[2026-09-22 정정]` 여행 Team 의 scope 에 **`travel_` 접두**가 붙었다. 앞 값들(`activity`·`cancellation`·`refund`·`weather` · `booking`·`penalty`·`supplier` · `opening_hours`·`dietary` · `transit`·`route_exception` · `lodging` · `flight`)은 **한 개를 빼고 전부 문서 0건**이었고, 예외인 `refund` 는 하필 **쇼핑몰 코퍼스에 실재하는 scope** 라 여행 질의가 쇼핑몰 환불 문서를 근거로 집어 왔다(되돌려 실측: top-8 중 7건). 지금 값 — Activity `travel_activity`·`travel_weather`·`travel_cancellation`·`travel_access` · Dining `travel_dining`·`travel_cancellation`·`travel_access` · Mobility `travel_mobility`·`travel_weather`·`travel_cancellation` · Booking Handoff `travel_cancellation`·`travel_activity`·`travel_dining` · Lodging/Flight 는 `policy` 선언 자체를 뺐다.

★**도구 권한(`allowed_tools`)과 검색 범위(`knowledge_scope`)는 다른 축이다.** `[정정 2026-09-10]` 이 자리는 「Response Review Team 은 `read.policy` 만 갖는다. 주문 문서를 못 본다」였다 — 퇴역 Team 이고, `read.policy` 는 **도구 권한**이라 어떤 문서를 검색하나는 정하지 않는다. 그건 `knowledge_scope` 가 정한다. ★`[2026-09-22 정정]` 이 자리는 「바뀌지 않은 것은 코퍼스다」였다 — **이제 바뀌었다.** 여행 코퍼스 12문서·130청크가 들어갔고 여행 Team 넷이 그것을 본다. 검색 코드는 여전히 도메인을 모른다.

## 코퍼스

`[실측 2026-09-22]` **코퍼스가 둘이다.** 같은 테넌트(`demo`)에 공존하고 `scope` 로만 갈린다.

| | 쇼핑몰 (2026-08-17) | 여행 (2026-09-22) |
|---|---:|---:|
| 문서 | 25 | **12** |
| 청크 | **306** | **130** |
| 1536칸 (`text-embedding-3-small`) | 306 | **0** |
| 1024칸 (`bge-m3`, 로컬) | 306 | **130** |

DB 직접 조회로 확인한 값이다. **문서에 적힌 수가 아니라 DB를 세어 갱신한다.**

★여행 130청크에는 **OpenAI 벡터가 없다**(크레딧 없음). 그래서 `ACOP_EMBEDDING_PROVIDER=openai` 로 되돌리면 여행 scope 검색이 **예외로 죽는다** — 조용히 0건이 되지 않게 `search_policy` 가 직접 검사한다. 여행 코퍼스가 무엇을 담고 무엇을 안 담는지는 → [travel-corpus.md](travel-corpus.md)

## ★ 코퍼스 게이트

`[실측]` `python -m scripts.check_corpus`가 검사한다.

**건수만 세면 통과하는 것이 계속 나왔다.** 그래서 게이트가 여러 축을 본다.

| 검사 | 왜 |
|---|---|
| 문서 수·청크 수 | 기본 |
| 중복률 | **가장 어려운 것이 길이가 아니라 중복이다** |
| 제목 점유율 | 마감 3섹션이 25문서에 같은 제목이면 상한에 걸린다 |
| 조사 오류 | 한국어 문법 |

★`[2026-09-22]` 게이트가 **컬렉션마다 따로** 돈다(쇼핑몰·여행). 섞어서 재면 쇼핑몰 코퍼스가 2026-08-17 에 받은 판정이 여행 문서가 늘 때마다 달라진다. 여행 쪽 건수 기준은 `config/guardrails.yaml` 의 `rag.travel.*` 이고 내용 기준(길이·중복·조사·수치)은 **같은 상수**를 쓴다. 두 코퍼스의 scope 이름이 겹치지 않는지도 여기서 센다.

`[실측]` 게이트 자체의 결함도 2건 나왔다. 조사 검사기가 `초과`·`결과` 같은 받침 없는 한자어를 오탐했고, 제목 점유율 상한에 걸릴 뻔해 문서군별 제목을 4종으로 교대시켰다.

**게이트를 만들면 게이트도 틀린다.**

## ★ 코퍼스에 법령이 들어간다 — 지어내면 틀린 답을 가르친다

`[실측]` `wiki/records/plans/2026-08-17_코퍼스_25문서_배분안.md`

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

`[실측]` 세 가지가 있었다.

**하나 — 테스트가 옛 도메인 질의로 하드코딩돼 있었다.** 구독/청구 도메인 질의라 쇼핑몰 코퍼스에서 붉었다. 쇼핑몰 시나리오로 재작성했다.

**둘 — 코퍼스를 코덱스가 재작성했더니 조사 오손 3,401건이 났다.** 재발주 대신 직접 작성으로 전환했다.

**셋 — 검색이 한 번도 동작하지 않았던 기간이 있었는데 테스트는 초록이었다.** [DoD-06](../records/evidence/DoD-06_정책FAQ_25건_300청크.md). 적재 직후 `search_policy()`는 **100% 실패**하고 있었다 — 질의 벡터가 tuple → `(...)`, list → `double precision[]`로 렌더링돼 `operator does not exist: vector <=> double precision[]`로 죽었다(`%s::vector` 캐스트로 해결).

그동안 RAG 테스트는 데이터 부재를 `skip`으로 넘겨 **`74 passed, 4 skipped`**로 초록이었다. 검색이 전혀 안 되는데 테스트 결과만 보면 정상이었다.

> **skip은 통과가 아니다.**

[run.md](../operations/run.md)와 `CLAUDE.md`가 테스트 총계에 굳이 `skipped 0`을 같이 적는 이유가 이것이다 — 숫자가 아니라 규칙이다.

## 관계

- [context-broker.md](context-broker.md) — 검색 결과를 조립하는 쪽
- [context-budget.md](context-budget.md) — `policy_rag` 예산
- [travel-corpus.md](travel-corpus.md) — **여행 코퍼스**가 담는 것과 안 담는 것
- [memory.md](memory.md) — 다른 입력원
- [../data/tenancy.md](../data/tenancy.md) — 격리
- [../teams/team-contract/index.md](../teams/team-contract/index.md) — `knowledge_scope`

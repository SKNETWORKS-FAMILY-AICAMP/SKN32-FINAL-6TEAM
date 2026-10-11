# RAG·LLM·벡터DB 구현

## 검색 파이프라인

정책 문서를 `knowledge_documents`와 `knowledge_chunks`에 저장하고, 1536차원 embedding을 pgvector에 적재했다. 검색은 top-k=8이며 tenant와 허용 scope를 함께 필터링한다. 현재 seed 실측은 `tenants=1`, `demo_customers=10`, `knowledge_documents=25`, `knowledge_chunks=300`이다.

| 질의 | 1위 | 2위 | 관측 |
|---|---|---|---|
| 해지했는데 결제가 됐어요 | `doc_06#c1` refund, 0.5198 | `doc_06#c3` refund, 0.4595 | doc_06이 1·2·8위 |
| Pro로 바꿨는데 기능이 안 보여요 | `doc_14#c1` entitlement, 0.4088 | `doc_14#c2` entitlement, 0.4013 | top-8은 entitlement/incident |

`allowed_scopes=['billing']`일 때 반환 scope 집합은 `['billing']`인 8건이며, 다른 tenant로 조회한 결과는 0건이다. 이는 전체 정식 평가가 아니라 위 두 질의에 대한 관측이다.

## Context Broker 조합

Broker는 Case 상태·Team facts·policy RAG·history·similar cases를 정해진 섹션 예산 안에 조합한다. 정책 근거에는 검색 결과의 `source_id`를 유지하고, 예산 초과 시 omission을 기록한다. LLM에는 ContextPack의 masked text만 전달하는 것이 목표지만, PII 종단 검증은 근거상 판정이 분리되어 있다.

hybrid BM25+rerank는 구현·검증하지 않았고 Phase 2다.

## 근거

- `wiki/records/evidence/DoD-06_정책FAQ_25건_300청크.md`
- `wiki/records/evidence/DoD-07_tenant격리_PII.md`
- `wiki/records/reports/2026-08-12_S-RAG_적재_검색_리포트.md`
- `wiki/records/reports/2026-08-12_2045_RAG검색_수정_리포트.md`
- `wiki/records/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md`

# 2026-08-13 S-GRAPHTEST 리포트

## 1. 추가한 테스트

- `tests/integration/graph/test_sql_graph_adapter.py`
  - `test_path_returns_case_evidence_chunk_document_hops`
    - 전용 tenant의 `Case → Evidence → KnowledgeChunk → KnowledgeDocument` 실제 경로와 hop 종류·깊이를 검증한다.
  - `test_graph_queries_are_tenant_isolated`
    - 다른 tenant의 `path()`, `neighbors()`, `subgraph()` 결과가 비어 있고 다른 tenant 노드를 노출하지 않는지 검증한다.
  - `test_neighbors_and_subgraph_return_expected_structure`
    - 직접 연결 neighbors, depth 증가 동작, subgraph의 root·nodes·edges 구조를 검증한다.
  - `test_recursive_walk_respects_depth_limit_on_cycle`
    - 문서↔청크 순환 관계에서 재귀 결과가 `depth=4`를 넘지 않는지 검증한다.

테스트 fixture는 `test_<uuid>` tenant 2개를 만들고 각 tenant에 customer, case, event, document, chunk를 적재한다. teardown에서는 case event, chunk, document, case, customer, tenant 순서로 자기 tenant의 행을 삭제하며 `demo` tenant에는 접근하지 않는다.

## 2. 완료 조건 명령의 실제 출력

신설 테스트:

```text
....                                                                     [100%]
============================== warnings summary ===============================
... PytestCacheWarning: could not create cache path ...\.pytest_cache... [WinError 5] 액세스가 거부되었습니다
4 passed, 1 warning in 0.77s
```

전체 테스트:

```text
........................................................................ [ 58%]
..............FFF..................................                      [100%]
=========================== short test summary info ===========================
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[해지했는데 결제가 됐어요-doc_06]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[Pro로 바꿨는데 기능이 안 보여요-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
3 failed, 120 passed, 2 warnings in 17.98s
```

PostgreSQL tenant 확인:

```text
tenants=1
```

## 3. 실패한 테스트와 원인

graph adapter 테스트 실패는 없다. 전체 실행의 기존 RAG 테스트 3건은 `app/infrastructure/rag/retriever.py`의 OpenAI `embeddings.create()` 호출에서 실패했다. 이 실행 환경에서 `api.openai.com:443` 연결이 정책으로 차단되어 `[WinError 10013]`이 발생했고, 최종적으로 `openai.APIConnectionError: Connection error.`가 발생했다.

이는 이번 작업에서 요구한 실제 LLM·임베딩 호출 금지 및 외부 네트워크 차단 환경과 일치한다. 실패를 숨기거나 단언을 약화하지 않았다.

`SqlGraphAdapter`에서는 tenant 누락으로 인한 교차 노출을 재현하지 못했다. `path()`, `neighbors()`, `subgraph()` 모두 다른 tenant 데이터에 대해 격리된 결과를 반환했다.

## 4. 검증하지 못한 것

- 전체 테스트 suite의 최종 119건 이상·0 skipped 조건은 충족하지 못했다. 기존 RAG 네트워크 의존 테스트 3건이 실패하여 최종 결과는 120 passed, 3 failed, 0 skipped였다.
- 외부 OpenAI embedding 서비스가 차단되어 RAG 검색 자체의 relevance 결과는 검증하지 못했다.
- 제품 코드(`app/**`)는 수정하지 않았다.

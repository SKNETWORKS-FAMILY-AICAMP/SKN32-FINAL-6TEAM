# 2026-08-13 S-GRAPHTEST

- 목적: 미검증 `SqlGraphAdapter`의 실제 PostgreSQL 동작과 tenant 격리 검증.
- 변경: `tests/integration/graph/test_sql_graph_adapter.py`에 path, neighbors, subgraph, 재귀 깊이 제한, cross-tenant 격리 테스트 4건 추가.
- 데이터: `test_<uuid>` tenant 2개에 Case/Event/Evidence/KnowledgeDocument/KnowledgeChunk 그래프를 fixture로 만들고 FK 순서로 teardown. `demo` tenant는 보존.
- 검증: graph 테스트 `4 passed`; 전체 `120 passed, 3 failed, 0 skipped`; `tenants=1`.
- 실패 원인: 기존 RAG 테스트 3건이 OpenAI embedding 호출 중 외부 네트워크 차단(`[WinError 10013]`, `openai.APIConnectionError`)으로 실패.
- 제품 코드 수정 없음.

# S-MODULARIZE 구현 리포트

## 결과

계약 문서 `wiki/records/handoff/07_모듈화_구조.md` 기준으로 단계별 골격과 Case Runtime, Access/Action, Presentation, Infrastructure, Team Module 재배치를 적용했다. 기존 import 경로는 호환 re-export로 유지했다.

## 단계별 검증

| 단계 | 내용 | 결과 |
|---|---|---|
| 1 | 목표 패키지 골격과 `__init__.py` 생성 | 완료 |
| 2 | Case Runtime 구현 이동 및 re-export | 113 passed, 3 baseline RAG network failures |
| 3 | Access/Action auth 및 Team Module 경계 | 관련 회귀 통과 |
| 4 | MCP/Web/Schemas presentation 재배치 | UI·API 회귀 통과 |
| 5 | VectorStore 및 Graph Port/SQL Adapter 골격 | 컴파일·계약 테스트 통과 |
| 6 | `local_team_a`, `local_team_b` 재배치 | Team 회귀 통과 |

전체 `python -m pytest tests -q`: 116개 실행, 113 passed, 3 failed, 0 skipped. 실패 3건은 기존 RAG 테스트의 OpenAI embedding 네트워크 차단이며 구조 변경과 무관하다.

## 신설 7종

1. `app/core/case_runtime/remote_team/TeamExecutorPort`, `LocalTeamExecutor`
2. `app/core/case_runtime/remote_team/A2ATeamExecutor`
3. `app/presentation/a2a/agent_card.py` Agent Card builder
4. `app/core/case_runtime/context/graph_retrieval/GraphStorePort`
5. `app/infrastructure/graphstore/SqlGraphAdapter`
6. `app/core/case_runtime/context/vector_retrieval/` Vector retrieval Port 골격
7. `app/infrastructure/vectorstore/` Vector adapter 위치

A2A adapter는 Agent Card 발견, Task 발행, 상태 매핑, Artifact 수신 인터페이스만 제공한다. 원격 호출은 주입 client/fake로 대체 가능하다. Graph adapter는 PostgreSQL JOIN/`WITH RECURSIVE` 기반이며 별도 graph DB를 도입하지 않았다.

## Re-export 경로

- `app/core/contracts.py`
- `app/core/transition.py`
- `app/core/context.py`
- `app/core/registry.py`
- `app/application/controller.py`
- `app/application/case_service.py`
- `app/domain/case.py`
- `app/domain/events.py`
- `app/presentation/security.py`
- `app/presentation/api/mcp.py`
- `app/presentation/ui/routes.py`
- `app/infrastructure/rag/retriever.py`
- `app/modules/customer_ops/billing.py`
- `app/modules/customer_ops/technical.py`

## 미이동분과 사유

`app/application/feedback_job.py`, `app/modules/customer_ops/feedback.py`, `app/tools/`, DB/session/migration 및 messaging adapter는 07 문서의 단계별 대응표에 직접 지정되지 않아 기존 위치를 유지했다. `infrastructure/messaging`은 Port/Adapter 분리가 별도 후속 작업으로 남아 있다. 금지 범위인 `eval/**`, `knowledge/**`, `wiki/records/evidence/**`, `wiki/records/handoff/**`, `config/**`, `scripts/**`는 수정하지 않았다.

## DoD/DB

`python -m scripts.verify_dod`: 기존 판정 유지(통과 8, 부분통과 7, 미작성 2). PostgreSQL 확인 결과는 `tenants=1`이다.

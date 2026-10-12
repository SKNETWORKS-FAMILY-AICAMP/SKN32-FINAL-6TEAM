# 구현계획서 md 고도화 보고서

대상 파일: `A-COP_구현계획서_A2A_Graph반영.md`

| 섹션 | 변경 전 | 변경 후 | 이유 |
|---|---|---|---|
| 8-5 Message Broker | Agent 사이 통신 인프라로만 설명 | Coordination이 Task/Event와 MessageBus Port를 소유하고, Infrastructure가 InMemory/Redis/RabbitMQ Adapter를 구현하도록 분리 | Controller의 판단 책임과 Broker의 전달 책임을 구분하고 Adapter 교체 경계를 명확히 하기 위해 |
| 8-A Message Broker와 Context Broker | Broker의 역할과 구현 위치가 섞여 있음 | `message_bus.publish(task)` 계약, 계층 표, `redis.xadd(...)` 직접 호출 금지 원칙 추가 | HTML의 최신 아키텍처 결정 동기화 |
| 8-C Agent/Team 경합과 동시성 처리 책임 | 별도 경합 책임 절 없음 | 경합 종류별 담당 표, SharedStateUpdate 계약, SUCCESS/CONFLICT/NOT_FOUND 결과, Retry/Replan 규칙 추가 | Team 간 조정과 State/Action 무결성 책임을 분리하기 위해 |
| 9-C MCP / A2A / Message Broker | 프로토콜 비교만 있음 | A2A 1.0, Linux Foundation, 150개 이상 조직, 주요 클라우드 통합, AAIF, MCP/A2A 역할과 도입 순서 추가 | 2026-08 리서치 사실 반영 |
| 9-D Graph DB / GraphRAG | GraphRAG를 선택 사항으로만 설명 | 비용, 단일 사실 조회의 한계, 72~80% 프로덕션 실패 분석, 환각 위험, 3단계 채택 게이트 추가 | 도입 여부를 평가로 결정할 수 있게 하기 위해 |
| 9-D 우리 설계의 강점 | 일반적인 GraphRAG 구조 설명 | PostgreSQL FK에서 결정적으로 Projection하고 LLM 추출을 사용하지 않는 구조를 명시 | 엔티티·관계 환각과 추출 비용을 구조적으로 줄이는 근거 제시 |
| 12 Agent / Orchestration | LangGraph만 기재 | LangGraph 1.0, `AsyncPostgresSaver`, `InMemorySaver` 미사용, `thread_id = case_id` 추가 | 운영 환경의 재시작 복구와 Case 매핑 기준을 명시하기 위해 |
| 16 팀 역할 | Core Part A / Part B 분리 | Core 1 Case Runtime & Coordination, Core 2 Access & Action Platform의 수직 기능 영역으로 전면 교체 | 코드 책임과 사람 담당을 구분하고 두 Core가 end-to-end로 책임지게 하기 위해 |
| 16 DB 소유 | 백엔드 담당자 중심의 포괄적 분담 | Core 1/Core 2 데이터 소유 표와 공통 DB 합의 추가 | DB 책임을 기능 영역에 맞춰 나누고 Alembic 등 공통 기반을 함께 관리하기 위해 |
| 16 CAS와 Idempotency | 차이가 별도로 설명되지 않음 | Case 상태 동시 수정은 CAS, 동일 Action 중복 실행은 idempotency key로 구분 | 서로 다른 대상과 책임임을 명확히 하기 위해 |
| 18-A 결정사항의 주의점 | 해당 절 없음 | Broker, in-process queue, 이중 제어, Core 1 병목, Core 간 왕복, Alembic, A2A 이중 상태, GraphRAG 중단 기준 표 추가 | 새 결정의 실행상 위험과 대응 기준을 계획서에 남기기 위해 |

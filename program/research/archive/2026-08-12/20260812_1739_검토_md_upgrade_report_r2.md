# 구현계획서 2차 고도화 보고서

대상: `A-COP_구현계획서_A2A_Graph반영.md`  
확인일: 2026-08-12

| 섹션 | 변경 전 | 변경 후 | 이유 |
|---|---|---|---|
| 0. 한 줄 요약 | Graph Store를 파생 Projection으로 단정 | `GraphStorePort`와 `SqlGraphAdapter`를 명시하고 PostgreSQL을 유일한 Source of Truth로 명시 | MVP에서는 SQL로 시작하되 Graph 계획을 제거하지 않기 위해서다. |
| 8-A | at-least-once가 18-A 주의점에 있음 | 8-A에 consumer의 `message_id` 기록·중복 스킵·강제 중복/재시도 테스트 규칙을 추가 | 주의점이 아니라 모든 consumer가 따라야 하는 구현 규칙이기 때문이다. |
| 8-C | Team이 Tool을 호출하고 Core 2 Action Layer를 거쳐 State로 복귀 | Context Broker가 읽기를 준비하고 Team은 `ActionProposal`만 반환하며 Controller가 Core 2를 호출 | Team과 Core 2의 직접 결합을 제거하고 입력 재현성과 토큰·조회 비용을 관리하기 위해서다. |
| 9-C | A2A·AAIF 관련 수치와 시점을 출처 없이 단정 | 각 주장에 각주를 달고 외부 리서치 인용이며 자체 측정치가 아님을 표시 | 감사 #11의 출처 요구를 반영했다. |
| 9-D 도입 | GraphRAG와 Graph DB 판단이 한 흐름에 섞임 | LLM 지식그래프 추출과 정형 관계 그래프 질의를 분리하고 전자는 미채택, 후자는 PostgreSQL로 채택 | 두 GraphRAG 유형의 비용과 적용 조건을 구분하기 위해서다. |
| 9-D MVP 판단 | 시나리오 A/B/C에 Graph가 필요한 것처럼 읽힘 | 깊이 1~2는 JOIN·집계로 충분하고 C는 `GROUP BY`·`HAVING`·윈도 함수가 적합하다고 명시 | “현재 규모에서는 그냥 JOIN”이라는 정직한 판단을 반영했다. |
| 9-D Graph 우위 | Graph가 유리한 조건이 추상적임 | A2A 위임 토폴로지와 설명가능성 경로를 가변 깊이 질의로 명시하고 전환 조건을 수치·조건으로 고정 | Graph를 나중에 도입할 실질적 기준이 필요하기 때문이다. |
| 9-D Port / Adapter | 후보 Graph Store만 나열 | `GraphStorePort` 코드, MVP `SqlGraphAdapter`, Phase 2 `AgeGraphAdapter`/`Neo4jGraphAdapter` 추가 | 같은 계약으로 저장소를 비교하고 교체할 수 있게 하기 위해서다. |
| 9-D 운영 비용 | 별도 Graph Store 비용이 설명에 흩어짐 | Projection 동기화·재시도·순서 역전·삭제·불일치 검증을 포함한 25~40인·일 표 추가 | MVP에서 전용 저장소를 미루는 실질 근거를 수치화했다. |
| 9-D 비교 실험 | 채택 게이트만 존재 | 8~9주차 동일 질의셋과 근거 포함률·p95·인·일·Projection lag 비교 설계 추가 | 결과와 무관하게 발표용 판단 기준표를 산출하기 위해서다. |
| 9-D 판단 기준표 | 판단표 없음 | 관계 깊이, 스키마, 관계 위치, 경로 빈도, 시각화, 팀 규모, 운영 인력별 SQL/Graph 임계 조건 추가 | 발표에서 Graph DB 도입 조건을 구체적으로 설명하기 위해서다. |
| 12. 기술 스택 | `Graph Store Adapter / GraphRAG PoC` | `GraphStorePort (MVP: SQL Adapter, Phase 2: AGE/Neo4j 비교)` | 확정된 Port/Adapter 방향과 일치시키기 위해서다. |
| 14. 구현 단계 | 일반적인 단계 설명만 있음 | 1~2주차 Core 1 계약·가짜 구현 표, 나머지 5명의 병렬 작업, Contract Freeze Day와 병목 신호 추가 | Core 1 완성을 기다리지 않고 전체 팀이 착수할 수 있게 하기 위해서다. |
| 16. 팀 역할 | Team이 Tool을 직접 호출하는 경계로 읽힘 | Context Pack, `TeamManifest.required_context`, `ActionProposal`, `ExecuteAction`/`ActionResult` 계약을 기준으로 역할을 재정렬 | Team 개발자와 Core 2의 결합을 줄이기 위해서다. |
| 16. DB 소유 | Alembic 단일 브랜치가 주의점으로만 언급됨 | rebase, 동시 revision 금지, `alembic merge` 금지, upgrade/downgrade CI 검증 규칙 추가 | Core 1·2의 DB 소유 분리에서 revision 충돌을 예방하기 위해서다. |
| 18-A | at-least-once와 직접 Tool 호출 계약이 주의점 표에 있음 | at-least-once는 8-A 구현 규칙으로 이동하고, 18-A는 새 Core 계약과 LangGraph/Broker 경계를 설명 | 결정사항의 위치와 책임 경계를 일치시키기 위해서다. |
| 참고 출처 | GraphRAG 비용, A2A 조직 수, AAIF 시점 등에 각주 없음 | `## 참고 출처`와 확인일, 주장별 각주 추가 | 감사 #10·#11의 출처 및 외부 인용 표시 요구를 반영했다. |

검증 결과, 절 번호 `8-A`, `8-B`, `8-C`, `9-C`, `9-D`, `14`, `16`, `18-A`는 유지했다. 문서 내 `Vector Search + Graph Search` 표현은 `Vector Search + 관계 조회(GraphStorePort)`로 교체했고, 12장 기술 스택도 새 Adapter 정책에 맞췄다.

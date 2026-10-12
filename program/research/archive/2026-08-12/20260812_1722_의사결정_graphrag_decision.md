# GraphRAG 도입 의사결정

## 결론

**별도 GraphRAG 및 Neo4j 같은 Graph Store는 도입하지 않는다.** 대신 PostgreSQL을 Source of Truth로 유지하고, 필요한 관계 탐색은 명시적인 SQL JOIN/재귀 CTE와 Context Broker의 관계 조회 모듈로 구현한다.

판정은 다음과 같다.

| 구분 | 판정 |
|---|---|
| 비정형 문서에서 LLM으로 지식 그래프를 추출하는 Microsoft GraphRAG 계열 | **도입하지 않음** |
| 이미 FK로 존재하는 데이터를 그래프로 질의하는 방식 | **관계 탐색은 채택하되, Graph DB가 아닌 SQL로 구현** |
| 이번 프로젝트에서 “GraphRAG”라는 명칭 사용 | **부적절하거나 오해의 소지가 있음** |

우리 데이터는 문서 25건, 6명, 8~10주 규모이며 Case·Issue·Policy·Product·AgentTeam·Action이 이미 관계형으로 존재한다. 이 조건에서는 그래프의 질의 의미는 유용하지만, 별도 그래프 저장소의 추가 효과보다 Projection 동기화·디버깅·발표 준비 비용이 크다. 가장 정확한 표현은 **“Vector RAG + PostgreSQL 관계 탐색 기반 Context Broker”**다.

---

## 1. 두 가지 GraphRAG를 분리한 판정

### 1.1 비정형 문서에서 LLM으로 그래프를 추출하는 방식

**우리에게 필요하지 않다.** 정책/FAQ가 약 25건이고, 핵심 업무 데이터는 이미 PostgreSQL의 테이블과 FK로 관리된다. 따라서 문서에서 `Case -HAS_ISSUE-> Issue` 같은 관계를 LLM이 다시 추출할 이유가 없다.

이 방식의 리서치상 비용·위험은 이번 프로젝트와 맞지 않는다.

| 항목 | 우리 프로젝트에 미치는 의미 |
|---|---|
| Vector RAG 대비 3~5배 비용 | 8~10주 부트캠프에서 품질 개선 대비 비용이 큼 |
| 엔티티/관계 환각 | 정책과 업무 관계를 잘못 연결할 수 있음 |
| 500페이지 기준 약 45분, $50~200 인덱싱 | 문서 25건에서는 기능적 이득보다 파이프라인 구축 비용이 문제 |
| 그래프 구축·운영 오버헤드 | 평가, Case 처리, 외부 AI 연동에 쓸 시간을 잠식 |

리서치의 “교차 문서 multi-hop에서만 GraphRAG가 유리하다”는 조건도, 우리 경우에는 문서 추출 그래프가 아니라 DB 관계로 이미 충족할 수 있다.

### 1.2 FK를 그래프로 Projection하여 질의하는 방식

**관계 탐색 기능 자체는 유용하지만, 전용 Graph DB 도입은 필요하지 않다.** 이 방식은 추출 환각이 없고, 그래프 탐색 표현으로 여러 관계를 따라갈 수 있다. 그러나 현재 규모와 스키마에서는 실질적으로 **다중 JOIN 또는 재귀 CTE에 그래프라는 이름을 붙인 것**에 가깝다.

이것이 나쁜 것은 아니다. 다만 “GraphRAG가 관계를 발견했다”고 주장하면 과장이다. 정확한 주장은 다음이다.

> PostgreSQL의 정형 관계를 SQL로 결정적으로 탐색하고, 그 결과를 Vector RAG 문서 검색 결과와 함께 Context Pack으로 조합한다.

---

## A. Vector RAG보다 Graph가 나은 질의가 있는가?

**있다.** 다만 “Graph가 Vector RAG보다 낫다”와 “전용 Graph DB가 SQL보다 낫다”는 다른 주장이다. 아래 세 질의는 벡터 검색보다 관계 탐색이 분명히 낫지만, 현재 데이터에서는 모두 SQL JOIN으로 충분하다.

### 질의 1 — 시나리오 A: 환불 판단의 관계 근거 조회

질의 예시:

> “이 Case의 고객이 사용한 Product, 해당 Product에 적용되는 Policy, 현재 구독/결제 상태, 이미 실행되었거나 승인 대기 중인 Action을 한 번에 보여줘. 환불 가능 여부의 근거도 반환해줘.”

| 관점 | 동작과 한계 |
|---|---|
| Vector RAG | “환불”, “해지 후 결제”와 유사한 정책 문서를 찾는다. 하지만 이 Case의 실제 Product·구독 상태·결제 트랜잭션·기존 Action과 문서를 정확히 연결한다는 보장이 없다. 비슷한 정책을 찾아도 현재 Case에 적용되는지 판단할 연결 키가 약하다. |
| Graph 탐색 | `Case → Product → Policy`, `Case → Action`, `Case → Transaction`을 따라가 현재 Case에 직접 연결된 근거만 구성한다. |
| SQL JOIN 가능 여부 | **가능하다.** `customer_cases`를 기준으로 `subscriptions`, `products`, `policies`, `transactions`, `action_requests`를 Case/customer/product 키로 JOIN하면 된다. 재귀도 필요 없다. |
| Graph만의 추가 이득 | 없음. 그래프 표기와 탐색 API가 편리할 수는 있지만, 이 질의의 정답성과 실행 결과는 SQL이 더 직접적이다. |

### 질의 2 — 시나리오 B: 권한 오류의 원인 경로 조회

질의 예시:

> “Free로 변경된 고객에게 왜 Pro 기능이 남아 있는가? 고객의 구독 상태에서 entitlement, 캐시/동기화 이벤트, 관련 제품 정책, 최근 장애까지 이어지는 원인 후보를 보여줘.”

| 관점 | 동작과 한계 |
|---|---|
| Vector RAG | “권한 동기화 실패”, “캐시 문제” FAQ나 장애 문서를 찾는 데 유용하다. 하지만 문서가 이 고객의 실제 entitlement, account state, incident history와 연결되지는 않는다. |
| Graph 탐색 | `Case → Customer → Account/Subscription → Entitlement`, 그리고 `Issue → Product → Incident/Policy` 경로를 조합해 현재 상태와 원인 후보를 연결한다. |
| SQL JOIN 가능 여부 | **가능하다.** 고객/계정/구독/entitlement/이벤트/incident의 FK가 존재하면 다중 JOIN으로 조회한다. 이벤트 시간순 경로는 `ORDER BY`, 재귀적 상태 흐름은 재귀 CTE로 처리할 수 있다. |
| Graph만의 추가 이득 | FK가 확정된 경로를 탐색하는 것뿐이라 전용 Graph DB가 더 정확해지는 것은 아니다. SQL 결과를 Context Pack으로 정규화하면 동일한 LLM 입력을 만들 수 있다. |

### 질의 3 — 시나리오 C: 반복 VOC에서 원인과 담당 Team까지 연결

질의 예시:

> “최근 30일 동안 급증한 Issue를 찾아, 영향을 받은 Product, 관련 Policy, 유사 Case 수, 수행된 Action, 담당 AgentTeam까지 연결해 어느 팀에 알릴지 알려줘.”

| 관점 | 동작과 한계 |
|---|---|
| Vector RAG | 유사한 문의 문장과 VOC 문서를 찾을 수 있다. 그러나 기간별 빈도, 동일 Issue의 정확한 집계, Product/Policy/Team/Action 연결은 의미 유사도만으로 안정적으로 계산하기 어렵다. |
| Graph 탐색 | `Issue → Case → Product/Policy/Action/AgentTeam`을 따라 관련 객체를 모으고, 기간 조건과 함께 반복 경로를 탐색할 수 있다. |
| SQL JOIN 가능 여부 | **가능하다. 오히려 SQL이 적합하다.** `GROUP BY issue_id`, `COUNT(*)`, 기간 필터, `HAVING`, 다중 JOIN으로 급증·담당 Team·처리 이력을 정확히 계산한다. 추세는 윈도 함수로 처리한다. |
| Graph만의 추가 이득 | 관계를 시각화하거나 경로를 자유롭게 탐색하는 UX에는 장점이 있을 수 있다. 그러나 25건 문서와 시연 규모에서 전용 Graph Store가 필요한 수준의 복잡도는 아니다. |

### A의 종합 판정

세 질의 모두 다음 구조가 최선이다.

```text
Vector RAG: 정책/FAQ의 의미 검색
PostgreSQL SQL: 현재 Case와 정형 데이터의 정확한 관계·집계 조회
Context Broker: 두 결과를 하나의 Context Pack으로 조합
LLM: 근거를 바탕으로 설명·판단·응답 생성
```

따라서 답은 **“Graph적인 질의는 있다. 하지만 Graph DB가 SQL JOIN을 대체해야 할 질의는 없다”**이다.

---

## B. 세 가지 선택지의 비용 대비 효과

아래 인원·일은 1명이 하루 동안 설계·구현·테스트에 집중하는 기준이다. 6명 전체의 총 프로젝트 인원·일은 10주 × 5일 × 6명 = 300인·일이지만, 아래 비용은 Graph/관계 탐색에 추가로 배정되는 작업량이다.

| 선택지 | 구현 비용(10주, 추가 인·일) | 얻는 것 | 잃는 것 | 심사 방어력 |
|---|---:|---|---|---|
| 1. GraphRAG 도입 안 함, Vector RAG만 | **0~2인·일** | 문서 검색, 정책 근거, 구현 단순성, 평가 시간 확보 | 관계 기반 Context를 별도 모듈로 보여주기 어려움 | **중간**. “Graph를 검토했고 데이터 특성상 SQL로 대체했다”는 설명이 필요 |
| 2. PostgreSQL 재귀 CTE/JOIN, Graph DB 없음 | **5~8인·일** | Case-Policy-Product-Action-Team 경로, 정확한 집계, 관계 근거 Context Pack, SQL 재현성 | 그래프 전용 시각화/자유 경로 탐색은 제한적 | **높음**. Source of Truth와 일관되고 JOIN 대비 차이를 솔직히 설명 가능 |
| 3. 별도 Graph Store + Projection 동기화 | **25~40인·일** | 그래프 탐색 API, 경로 시각화, 다중 홉 질의의 표현력, GraphRAG 데모 | 이중 저장, 동기화 지연/실패, 스키마 매핑, 운영·디버깅, 평가 복잡도 | **낮음~중간**. 기술 시연은 강하지만 “왜 이 규모에 필요한가” 질문에 취약 |

### 선택지 3의 숨은 비용 산정

3번의 25~40인·일에는 단순히 Neo4j를 띄우는 비용만 포함하지 않는다.

| 작업 | 예상 비용 |
|---|---:|
| Graph 모델·Adapter·쿼리 설계 | 4~6인·일 |
| PostgreSQL → Graph 초기 Projection/seed | 3~5인·일 |
| 변경 이벤트 또는 주기 동기화 구현 | 5~8인·일 |
| 재시도·중복·순서 역전·삭제 반영 테스트 | 4~6인·일 |
| Graph 쿼리 결과를 Context Pack에 결합 | 3~5인·일 |
| 모니터링·불일치 검증·발표용 시각화 | 4~6인·일 |
| **합계** | **25~40인·일** |

#### Projection 동기화는 누가, 언제, 무엇으로 하는가

현재 팀 역할을 기준으로 하면 Core 1 담당자가 소유해야 한다. Case와 Shared State의 Source of Truth를 관리하는 사람이 변경 이벤트의 의미와 순서를 가장 잘 알고 있기 때문이다. 다만 Core 1의 기존 범위가 이미 넓으므로, Graph를 넣으면 해당 담당자의 1~2주가 사실상 동기화 작업에 묶인다.

구체적인 운영안은 다음과 같다.

| 항목 | 현실적인 안 |
|---|---|
| 누가 | Core 1 담당자 1명, Agent Team 개발자 1명이 Graph query/Context 결합을 보조 |
| 언제 | 2주차 스키마 확정 후 모델링, 3주차 seed, 4주차 동기화, 5주차 통합 테스트, 이후 매주 불일치 점검 |
| 무엇으로 | PostgreSQL transaction outbox 또는 DB 변경 이벤트 → Projection worker → Neo4j bulk write/merge |
| 보장해야 할 것 | idempotency, 재시도, 삭제/수정 반영, event ordering, projection lag, PostgreSQL과 Graph 간 건수·관계 일치 검증 |
| 데모 전 작업 | 데모 데이터 재생성 뒤 Projection 재실행, 불일치 점검, Graph 장애 시 SQL fallback 확인 |

Graph Store는 파생 Projection이므로 PostgreSQL commit과 Graph 반영 사이에 일시적인 불일치가 생긴다. 이를 숨기지 않고 처리하려면 최소한 `projection_status`, 재처리 명령, lag 지표와 fallback 경로가 필요하다. 이 운영 비용이 현재 프로젝트의 실제 숨은 비용이다.

### 비용 대비 효과의 수치화

선택지 2를 채택하려면 관계 질의 3개를 SQL로 구현하고, 각 질의에 대해 10개 이상의 고정 테스트 케이스를 둔다. 선택지 3은 같은 테스트를 SQL와 Graph 양쪽에 두어야 하므로 최소 2배의 회귀 테스트 대상이 된다.

전용 Graph Store를 정당화하려면 Graph 질의가 SQL 구현보다 다음을 모두 입증해야 한다.

1. 사전 정의한 multi-hop 질의 30개 중 정답 근거 포함률이 **10%p 이상 높을 것**.
2. 평균 응답 지연이 SQL 경로보다 **20% 이상 낮을 것**.
3. Projection lag와 불일치가 데모 기간 동안 **0.5% 이하**일 것.
4. 추가 구현·운영 비용 25~40인·일을 감안해도 전체 평가 점수가 **10% 이상 개선**될 것.

현재 데이터 규모와 시나리오에서는 이 조건을 만족할 근거가 없다.

---

## C. 최종 판정과 계획서 수정안

### 최종 판정: 도입하지 않는다

정확히는 **전용 GraphRAG/Graph Store는 도입하지 않고, SQL 관계 탐색을 도입한다.** 이유는 다음 네 가지다.

1. LLM 기반 그래프 추출은 우리 데이터가 이미 정형화되어 있어 불필요하다.
2. 관계 탐색이 유용한 A/B/C 질의는 존재하지만, 모두 PostgreSQL JOIN·집계·재귀 CTE로 재현 가능하다.
3. PostgreSQL이 Source of Truth인데 별도 Projection을 추가하면 동기화라는 새로운 실패 지점이 생긴다.
4. 25건 문서, 6명, 8~10주에서 25~40인·일을 Graph Store에 쓰는 것은 Agent Team, 평가, 데모 완성도를 낮출 가능성이 크다.

### 10주 실행안

| 주차 | 작업 | 담당 |
|---:|---|---|
| 1주차 | SQL 관계 질의 3개와 평가 데이터셋/정답 기준 확정 | Core 1 + UX/Evaluation |
| 2주차 | PostgreSQL 스키마/FK 확정, JOIN·재귀 CTE Repository 인터페이스 작성 | Core 1 |
| 3주차 | Vector RAG와 SQL 관계 조회를 Context Broker에 결합 | Core 1 + Agent Team 담당자 |
| 4~6주차 | 시나리오 A/B/C 구현, 정책/FAQ 25건 인덱싱, 관계 근거를 포함한 Context Pack 검증 | Agent Team 3명 |
| 7주차 | Baseline A/B/Proposed 평가 하니스에 SQL 관계 경로 포함 | UX/Evaluation + Core 1 |
| 8주차 | 정확도·근거 포함률·지연·비용·재처리 성공률 측정 및 보완 | 전원 |
| 9주차 | 대시보드와 SQL 관계 경로 시각화, 발표 시연 고정 | UX/Evaluation + Core 1 |
| 10주차 | 회귀 테스트, 실패 사례 정리, Graph 미채택 근거 발표 준비 | 전원 |

### 계획서에 넣을 대안 문구

> ### 9-D. 관계 인지형 Context Broker — GraphRAG 대체안
>
> 본 프로젝트는 비정형 문서에서 LLM으로 지식 그래프를 추출하는 GraphRAG와, 이미 정형화된 관계 데이터를 그래프로 탐색하는 방식을 구분한다. 정책/FAQ 문서가 약 25건이고 Case·Issue·Policy·Product·AgentTeam·Action 관계가 PostgreSQL의 FK로 존재하므로, 전용 Graph DB 및 LLM 기반 그래프 추출은 채택하지 않는다.
>
> Context Broker는 pgvector 기반 Vector RAG로 정책/FAQ의 의미 검색을 수행하고, PostgreSQL JOIN·재귀 CTE로 현재 Case의 Product·Policy·Issue·Action·AgentTeam 관계를 결정적으로 조회한다. 두 결과를 Context Pack으로 조합하여 Agent Team에 전달한다. PostgreSQL은 유일한 Source of Truth이며 별도 Projection 동기화는 두지 않는다.
>
> 이는 Graph를 검토하지 않은 것이 아니라, 관계 탐색의 가치를 SQL로 검증한 결과이다. 시나리오 A의 환불 근거 연결, B의 권한 오류 원인 경로, C의 반복 VOC 집계는 관계 조회로 평가한다. 사전 정의한 관계 질의에서 Vector RAG 단독 대비 유의미한 개선이 있는지 측정하되, 별도 Graph Store는 10주 일정과 6명 규모에서 비용 대비 효과가 없으므로 보류한다.
>
> 따라서 본 시스템의 정확한 명칭은 **“Vector RAG + PostgreSQL 관계 탐색 기반 Context Broker”**이며, Graph DB 도입은 향후 데이터 규모와 질의 복잡도가 검증된 뒤 별도 조건으로 재평가한다.

계획서의 기존 표현 중 다음도 바꾸는 것이 좋다.

| 기존 표현 | 수정 표현 |
|---|---|
| `Vector Search + Graph Search` | `Vector Search + PostgreSQL 관계 조회` |
| `Graph Store: 관계 탐색용 파생 Projection` | `Graph Store는 이번 범위에서 보류; PostgreSQL이 관계 탐색과 Source of Truth를 함께 담당` |
| `GraphRAG PoC` | `관계 질의 SQL PoC 및 Vector RAG 비교 평가` |
| `선택: 채택 게이트를 통과한 GraphRAG` | `선택: 사전 정의한 성능 기준을 충족할 때만 향후 Graph Store 재검토` |

---

## D. 심사 방어 문답

### Q1. “GraphRAG 왜 넣었어요?”

**권장 답변**

> 처음에는 Case, Issue, Policy, Product, AgentTeam, Action 사이의 다중 홉 관계를 Context에 넣기 위해 GraphRAG를 검토했습니다. 다만 GraphRAG에는 문서에서 LLM으로 그래프를 추출하는 방식과, 이미 정형화된 관계를 그래프로 조회하는 방식이 섞여 있습니다. 우리 프로젝트는 후자에 해당하고, 관계가 PostgreSQL FK로 이미 확정되어 있습니다. 그래서 별도 Graph DB를 추가하는 대신 PostgreSQL JOIN과 재귀 CTE로 관계 근거를 조회하고 Vector RAG와 조합했습니다. Graph의 탐색 가치는 사용하되, 이 규모에서 불필요한 이중 저장과 Projection 동기화 비용은 만들지 않은 결정입니다.

### Q2. “그거 그냥 JOIN 아니에요?”

**권장 답변**

> 맞습니다. 현재 데이터 규모에서는 본질적으로 결정적인 다중 JOIN/재귀 CTE입니다. Graph라는 이름으로 새 기술을 도입했다고 과장하지 않습니다. 저희가 구현한 차별점은 Graph DB 자체가 아니라, 관계형 상태 조회와 Vector RAG를 Context Broker에서 하나의 근거 묶음으로 조합하고, Agent Team이 그 근거를 사용해 Case를 처리하는 구조입니다. 향후 관계가 문서에만 있고 다중 홉 탐색이 반복적으로 실패한다면 Graph Store를 검토하겠지만, 지금은 SQL이 더 단순하고 검증 가능합니다.

### Q3. “왜 Graph DB를 안 넣었어요?”

**권장 답변**

> 도입 비용과 얻는 효과를 같은 질의에서 비교했습니다. 시나리오 A/B/C의 관계 질의는 모두 SQL로 정확히 계산할 수 있고, PostgreSQL이 이미 Source of Truth입니다. Graph DB를 추가하면 25~40인·일의 모델링, Projection 동기화, 재시도·불일치 검증, 이중 회귀 테스트가 필요합니다. 6명·8~10주 부트캠프에서는 그 비용이 Agent Team과 평가 완성도를 낮출 수 있어 채택하지 않았습니다. 대신 관계 질의 3개, 각 10개 이상 테스트 케이스, Baseline A/B/Proposed 비교로 미채택을 실험적으로 방어했습니다.

### Q4. “그럼 Vector RAG만으로 충분하지 않나요?”

**권장 답변**

> Vector RAG만으로는 문서 의미 검색은 되지만, 특정 Case의 실제 Product·Policy·Action·Team 연결이나 기간별 Issue 집계에는 약합니다. 그래서 Vector RAG를 버린 것이 아니라, SQL 관계 조회를 보완 정보로 추가했습니다. 다만 그 보완 정보의 저장·질의 계층은 Graph DB가 아니라 기존 PostgreSQL입니다.

### Q5. “나중에 언제 Graph Store를 도입하겠어요?”

**권장 답변**

> 사전 정의한 multi-hop 질의 30개에서 Graph 경로가 SQL보다 근거 포함률을 10%p 이상 높이고, 평균 지연을 20% 이상 낮추며, Projection 불일치가 0.5% 이하이고, 전체 평가 점수가 10% 이상 개선될 때 재검토하겠습니다. 현재는 그 조건을 입증할 데이터나 운영 필요성이 없습니다.

---

## 근거 요약

- 계획서 9-D: GraphRAG는 단일 사실보다 교차 문서 multi-hop에서 의미가 있고, 채택 게이트를 통과해야 하며, PostgreSQL FK에서 결정적으로 Projection하는 방식을 제안함.
- 계획서 10장: A는 결제·구독·정책·Action, B는 entitlement·account·incident, C는 반복 Issue·Product·Policy·Team·Action 연결을 요구함.
- 계획서 11장: 핵심 운영 데이터와 Action/Case 이력이 관계형 테이블로 존재함.
- `program/research/_research_facts.md`: 일반적인 GraphRAG의 비용 3~5배, 그래프 구축 오버헤드와 LLM 추출 환각 위험, 그리고 표준 RAG를 먼저 배포한 뒤 실패 지점으로 확장하라는 권고.

**최종 한 줄:** 관계 탐색은 한다. 그러나 이번 프로젝트에서는 그것을 GraphRAG/Graph DB라고 부르지 않고, PostgreSQL 관계 조회와 Vector RAG를 결합한 Context Broker로 구현한다.

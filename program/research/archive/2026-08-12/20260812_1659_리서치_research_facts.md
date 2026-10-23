# 2026-08 기준 웹 리서치 결과 (계획서/브리핑에 반영할 사실)

## 1. A2A — 채택 근거가 확실해졌다
- 2025년 6월 Google이 A2A를 **Linux Foundation**에 이관. 2026년 4월 기준 **1주년, 150개 이상 조직** 참여.
- **스펙 1.0 안정화.** 엔터프라이즈 기능 포함: **Signed Agent Card**(암호학적 신원 검증), 멀티테넌시, 웹 정합 아키텍처(로드밸런싱 고려).
- 주요 클라우드 통합 완료: **Microsoft Azure AI Foundry / Copilot Studio**, **AWS Bedrock AgentCore Runtime**, **Google Vertex AI**.
- 실제 프로덕션 도입 분야: 공급망, 금융, 보험, IT 운영.
- **2025년 12월 Linux Foundation 산하에 Agentic AI Foundation(AAIF) 신설, MCP와 A2A를 함께 거버넌스.**
  공동 창립: Anthropic, Google, OpenAI, Microsoft, AWS, Block.
  → "왜 이 두 프로토콜을 같이 쓰냐"에 대한 가장 강력한 근거. 같은 재단이 관리하는 상호보완 표준이다.

## 2. MCP와 A2A의 역할 구분 (업계 정설)
- **MCP = 수직 통합**: Agent가 아래쪽 Tool/데이터로 내려가는 연결.
- **A2A = 수평 통합**: Agent와 Agent가 옆으로 협업/위임하는 연결.
- 권장 도입 순서: **"MCP first, A2A gradually."** 내부 도구/지식을 MCP로 먼저 붙이고, 조직·부서를 넘는 협업이 실제 요구가 될 때 A2A를 넣는다.
- 다수 개발자에게는 MCP만으로 충분하다는 것이 중론. A2A는 **에이전트 독립성·위임 실행·상호운용성이 실제 요구일 때** 도입.

## 3. GraphRAG — 무지성 도입은 위험 (가장 중요)
- **비용 3~5배 프리미엄.** 단일 사실 조회(single-fact lookup)에는 **거의 무가치한데 추출 비용은 전액 발생**한다.
- GraphRAG가 값을 하는 곳은 **교차 문서 multi-hop "connect-the-dots" 질의뿐**이다.
- 2026년 분석: **엔터프라이즈 RAG 구현의 72~80%가 프로덕션 도달 실패.** graph 구축 오버헤드가 반복적 원인.
- LLM 기반 지식 추출 파이프라인이 **엔티티와 관계를 환각**해서, 수작업 교정이 비싸게 드는 부서지기 쉬운 구조를 만든다.
- 인덱싱 비용 실측: 500페이지 코퍼스 기준 **GraphRAG 약 45분 / $50~200**, **LightRAG 약 3분 / $0.50**.
- 권장 접근: **표준 RAG를 먼저 배포하고 어디서 실패하는지 측정한 뒤, 실패가 관계 기반 검색에서 나올 때만 Graph로 이동.**
  파일럿이 하이브리드 베이스라인을 못 이기면 추가 아키텍처·유지보수 부담은 정당화되지 않는다.

## 4. LangGraph — 운영 기준
- **LangGraph 1.0이 2025년 10월 릴리스.** PostgreSQL 체크포인팅으로 step 단위 복구 제공.
- **프로덕션에서 InMemorySaver 절대 금지.** 파드 재시작 한 번에 진행 중 상태가 통째로 날아간다.
- 표준 워크로드는 **AsyncPostgresSaver**, 고트래픽은 **RedisSaver**.
- **thread_id는 반드시 논리적 업무 식별자에 매핑**한다(예: user_id + session_id). 우리 프로젝트에서는 case_id.
- Uber, Klarna, LinkedIn, Replit, AppFolio 등 실제 프로덕션 사용. 사실상 표준.

# A-COP 브리핑 HTML 시각화·다이어그램·순서도 사실 검증 리포트

대상: `A-COP_브리핑_A2A_Graph반영_최종.html`  
사실 기준: `A-COP_구현계획서_A2A_Graph반영.md`  
검증 범위: HTML의 아키텍처 그림, Workflow 순서도, 스키마, ERD, 모듈화/GraphRAG 그림과 관련 표·설명.

| # | 위치(섹션/그림) | 문제 유형 | 무엇이 잘못됐나 | 근거 | 수정 제안 | 심각도(높음/중간/낮음) |
|---:|---|---|---|---|---|---|
| 1 | 3-2 상세 아키텍처, dispatch 이후 | 내부 모순 / 흐름 오류 | 상세 그림은 Local/Remote 실행 결과를 `Shared State`에 먼저 반영한 다음 `Tool / Action Layer`로 내려간다. 그러나 4-3 Team Subgraph는 `Tool / Action 실행` 후 결과 검증과 `TeamResult`를 반환하는 순서다. MD도 Tool Layer를 실제 side effect 실행 계층으로 설명한다. 현재 그림만 보면 팀 결과를 저장한 뒤에야 Action을 실행하는 것으로 읽혀 3-2와 4-3의 실행 순서가 어긋난다. | HTML: “`Local/Remote 결과를 TeamResult로 정규화`” → “`Shared State / State Repository`” → “`Tool / Action Layer`” (`A-COP_브리핑_A2A_Graph반영_최종.html:967-974`); HTML: “`Tool / Action 실행`” → “`결과 검증`” → “`PASS → TeamResult`” (`...html:1115-1127`); MD: Tool Layer는 “실제 외부 side effect 실행” (`A-COP_구현계획서_A2A_Graph반영.md:197-203`). | Action이 Team 내부 실행의 일부라면 3-2에서도 Team 실행 경로 안에 배치하고, Action 결과/TeamResult가 Shared State로 돌아오도록 화살표를 재배치한다. Action이 Controller 후속 단계라면 4-3의 순서와 “TeamResult 이후 Action” 계약을 명시한다. | 높음 |
| 2 | 3-4 동시성 처리 책임 표·도입문 | MD 불일치 / 책임 경계 | HTML은 같은 Case의 실행·상태 경합을 “Core 1이 정책부터 DB 무결성까지 end-to-end”로 담당한다고 단정한다. 사실 기준 MD는 Coordination, State Repository/DB, Tool Layer를 분리하고, 같은 Shared State 동시 수정은 State Repository/DB가 담당한다고 구분한다. 발표 시 사람 역할과 코드 책임을 혼동할 수 있다. | HTML: “`Core 1이 정책부터 DB 무결성까지 end-to-end로 담당`” 및 Shared State 동시 UPDATE 담당 `Core 1` (`...html:1037-1067`); MD: “Coordination은 ... 경합을 조정하고, Shared State와 Tool Layer는 ... 일관성을 보장” 및 `같은 Shared State 동시 수정 | State Repository / DB` (`...md:347-360`). | HTML 문구를 MD의 책임 분해에 맞추고, “Core 1이 정책·조정 계약을 소유하되 State Repository/DB가 CAS·Transaction을 구현”처럼 조직 소유와 코드 책임을 구분한다. | 높음 |
| 3 | 3-1 Level 1 전체 흐름 | 그림 자체 결함 / 방향 모호 | `Customer Case Layer` 다음에 Vector RAG·Graph Store·DB State·Memory가 별도 화살표 없이 가로로 놓이고, 그 아래 단일 `↓`가 `Context Broker`로 이어진다. 네 원천이 Context Broker에 입력되는지, Case Layer가 네 원천을 거쳐야 다음 단계로 가는지 그림만으로는 분명하지 않다. 3-2에서는 Context Broker가 자료원을 선택·조합하고 Controller로 Context Pack을 보내는 구조라 표현이 다르다. | HTML: Case Layer → `context-source-grid-4` → Context Broker의 일렬 배치 (`...html:863-872`); HTML: 상세 그림에서는 Context Broker와 네 자료원을 묶고 `Context Pack`을 Controller로 보내는 표현 (`...html:909-926`). | 네 자료원에서 Context Broker로 들어가는 입력 화살표를 명시하거나, 자료원을 Broker 내부/주변의 “조회 대상”으로 묶는다. 3-1의 캡션에 “수직 화살표는 제어 흐름, 자료원은 Broker가 선택 조회하는 원천”이라고 적는다. | 중간 |
| 4 | 4-5 Message Broker 순서도와 3-2 | 내부 일관성 확인 | `Controller → Message Broker → Agent Team Worker/Slot → result/event → Broker → Controller`로 그려져 있어 Broker가 판단하지 않고 전달만 한다는 설명과 일치한다. 3-2의 Local 경로도 `Controller가 TeamTask 생성 → Message Broker / Queue / Retry → Local Agent Team Slot → TeamResult / Event`로 같은 방향이다. 이 항목은 문제 없음으로 확인했다. | HTML: 4-5의 순서도와 “`Controller가 결정하고 Broker가 전달한다`” (`...html:1143-1157`); HTML: Local 실행 경로 (`...html:939-949`); MD: Broker는 판단하지 않고 전달 (`...md:219-227`). | 수정 불필요. 다만 결과선을 양방향으로 읽어야 하므로 현재처럼 `result/event → Broker → Controller`를 유지한다. | 낮음 |
| 5 | 4-6 Local/Remote 실행 순서도 | MD 일치 / 문제 없음 | Registry가 `execution_type`을 기준으로 LOCAL과 A2A를 나누고, 두 경로를 TeamResult로 정규화해 Shared State에 반영한다. MD의 확장 규칙과 일치한다. | HTML: `execution_type?` → `LOCAL: Message Broker → Local Team Slot`, `A2A: A2A Adapter → Remote Agent`, 이후 `TeamResult로 정규화` (`...html:1159-1184`); MD: LOCAL/A2A 경로와 TeamResult 정규화 (`...md:421-439`). | 수정 불필요. | 낮음 |
| 6 | 절 번호: 9-A Agent Team 모듈화, 9-B GraphRAG | MD 불일치 / 탐색성 | 같은 내용을 가리키는 절 번호가 MD의 `8-B Agent Team 플러그인/모듈화`, `9-D Graph DB / GraphRAG`와 HTML의 `9-A`, `9-B`로 다르다. 사용자가 기준 문서와 교차 참조할 때 잘못된 절로 이동할 수 있다. | HTML: `9-A. Agent Team 모듈화`, `9-B. Graph DB / GraphRAG 활용 계획` (`...html:1459`, `...html:1513`); MD: `8-B. Agent Team 플러그인/모듈화 계획`, `9-D. Graph DB / GraphRAG 활용 계획` (`...md:262`, `...md:443`). | 발표본과 구현계획서의 번호를 통일하거나, 제목에 “구현계획서 기준 8-B/9-D”를 병기한다. | 중간 |
| 7 | ERD: `agent_team_registry`–`agent_runs` 관계 | 그림 자체 결함 / FK·범례 모순 | `agent_runs`의 `team_id`는 HTML 박스 안에서 `FK team_id`로 표시됐는데, 해당 관계선은 보라색 점선이다. 범례는 실선을 “직접 FK / 소유 관계”, 보라 점선을 “실행 시 참조되는 Registry / Knowledge 관계”라고 정의한다. 같은 선이 FK인지 단순 실행 참조인지 혼재되어 ERD의 관계 의미가 모호하다. | HTML: `agent_runs`의 `FK team_id` (`...html:1370`); HTML: Registry에서 agent_runs로 가는 보라 점선 및 “`team_id reference`” (`...html:1378-1379`); HTML 범례 “`실선: 직접 FK`”, “`보라 점선: 실행 시 참조되는 ... 관계`” (`...html:1382`). | 실제 DB FK라면 실선으로 바꾸고, FK가 아닌 Registry 조회 참조라면 `agent_runs.team_id`를 FK로 표기하지 말고 “resolved_team_id/reference” 등 의미를 명확히 한다. | 높음 |
| 8 | ERD 전체와 MD 주요 테이블/관계 | 누락 / 설명 부족 | MD의 주요 테이블에는 `action_approvals`, `customer_feedback`, `agent_teams`, `api_tokens / oauth_connections`, `voc_reports` 등이 포함되고, 핵심 관계에는 `action_requests 1:1 or N:1 approval records`가 있다. HTML ERD에는 `action_requests`는 있으나 `action_approvals`와 그 관계가 보이지 않는다. 승인 흐름을 강조하는 브리핑에서 ERD만 보면 승인 레코드가 어디에 저장되는지 알 수 없다. | MD 주요 테이블·관계 (`...md:519-539`); HTML ERD에 표시된 하위 박스는 `memory_items`, `agent_runs`, `action_requests`까지이며 (`...html:1368-1371`), HTML의 A2A/Graph 확장도 Registry·Graph만 설명한다 (`...html:1386-1408`). | ERD에 `action_approvals`와 관계선을 추가하거나, “승인 테이블은 생략한 개념 ERD”라는 범위 주석을 명시한다. | 중간 |
| 9 | ERD 선 스타일과 `knowledge_documents` | 관계 의미 / 근거 부족 | `knowledge_documents`에서 `agent_runs`로 가는 점선은 `retrieval evidence`로 표시되어 있지만, MD의 핵심 관계는 `knowledge_documents N:1 domain/module`이고 Graph 모델에는 Case가 KnowledgeDocument를 `USED_EVIDENCE`로 연결한다. 현재 ERD는 문서가 실행 기록의 근거인지, 도메인/모듈 소속인지, Graph 파생 관계인지 구분하지 않는다. | HTML: `knowledge_documents` 필드와 `retrieval evidence` 점선 (`...html:1376`, `...html:1380-1382`); MD: `knowledge_documents N:1 domain/module` 및 Graph의 `Case -USED_EVIDENCE-> KnowledgeDocument` (`...md:534-539`, `...md:465-475`). | 선의 의미를 “관계형 FK”, “실행 시 evidence reference”, “Graph projection edge”로 분리해 범례를 세분화하고, 관계형 ERD와 Graph 모델을 별도 그림으로 나눈다. | 중간 |
| 10 | 9-B GraphRAG 설명 및 기술 적용 수준 | 근거 없는 수치 | HTML은 “`GraphRAG 비용은 Vector RAG보다 3~5배 높고`”라고 수치화한다. MD에도 같은 수치가 있으나, 두 파일 모두 측정 조건·벤치마크·출처를 제시하지 않는다. 비용은 모델, hop 수, 저장소, 질의량에 따라 달라지는 값이므로 사실처럼 고정하면 질문에 답하기 어렵다. | HTML: 3~5배 비용 주장 (`...html:1513-1517`); MD: 동일 주장 (`...md:443-446`). | 프로젝트 측정값이면 측정 환경·쿼리셋·비용 산식을 붙이고, 외부 근거가 없으면 “예상/가설이며 PoC에서 측정”으로 낮춘다. | 높음 |
| 11 | 9. 외부 AI 연동 도입부 | 근거 없는 숫자·시점 주장 | “A2A 스펙 1.0”, “150개 이상 조직”, “2025년 12월 AAIF 출범”을 외부 사실로 제시하지만 HTML 안에 출처 링크나 각주가 없다. MD에도 같은 문장이 있으므로 HTML과 MD의 내용 일치는 확인되지만, 발표 자료 자체의 검증 가능한 근거가 부족하다. | HTML: 외부 AI 연동 도입부의 해당 주장 (`...html:1412-1413`); MD: 같은 주장 (`...md:407-410`). | 공식 표준/재단 문서 링크와 확인일을 각주로 붙이고, 변동 가능한 참여 조직 수는 기준일을 명시하거나 삭제한다. | 중간 |
| 12 | 7-1 Customer Case Schema와 8 ERD | 내부 용어 불일치 | Schema 예시는 소유 팀을 `owner_team_id`로 표현하고 (`7-1`), ERD의 `customer_cases`는 `owner / version`만 표시한다. 반면 ERD의 `agent_runs`는 `FK team_id`를 별도로 둔다. 발표자가 Schema의 소유 팀과 실행 팀의 차이를 설명하지 않으면 두 필드가 같은 의미인지 알기 어렵다. | HTML Schema: `owner_team_id` (`...html:1304-1322`); HTML ERD: `customer_cases`의 `owner / version`, `agent_runs`의 `FK team_id` (`...html:1365`, `...html:1370`). | `customer_cases.owner_team_id`와 `agent_runs.team_id`의 의미를 각각 “현재 Case owner”와 “해당 실행에 선택된 Registry team”으로 캡션/필드명에 명시하거나, 실제 스키마에 맞게 이름을 통일한다. | 중간 |
| 13 | 3-1, 3-2, 4-1~4-6, 8 ERD, 9-A, 9-B | 설명 부족 / 캡션 | HTML에는 `figure`/`figcaption` 구조가 없고, 시각 요소가 일반 `div class="diagram"`, `module-diagram`, `graph-flow`, `svg`로 삽입되어 있다. 섹션 제목은 있지만 각 그림의 입력·출력·화살표 의미를 한 문장으로 설명하는 독립 캡션은 없다. 특히 ERD의 실선/점선 범례는 그림 하단에 있으나, 3-1/3-2/9-A/9-B에는 같은 수준의 읽기 안내가 없다. | HTML: 일반 diagram 컨테이너와 제목 (`...html:849-850`, `...html:895-897`); ERD SVG 컨테이너 (`...html:1348-1354`); GraphRAG flow (`...html:1537-1547`); 파일 전체 검색 결과 `figure`/`figcaption` 요소 부재. | 각 시각 요소 아래에 “이 그림에서 읽을 것” 1문장을 추가한다. 예: “실선은 제어/실행 흐름, 점선은 조회·참조 관계이며, 결과는 TeamResult로 정규화된다.” | 낮음 |
| 14 | 전체 HTML 시각화의 반응형/텍스트 배치 | 그림 자체 결함 점검 | ERD는 `min-width:1120px`와 `overflow-x:auto`로 큰 화면에서 가로 스크롤이 발생할 수 있으나 잘림 방지 처리가 있다. 다수의 monospace 순서도는 `white-space: pre-wrap`, 테이블은 `overflow-x:auto`라서 소스상 텍스트가 박스 밖으로 잘리는 증거는 확인되지 않았다. 이 항목은 문제 없음으로 확인했다. | HTML: ERD의 `min-width:1120px`, `overflow-x:auto` (`...html:1353-1354`); CSS: `.mono { white-space: pre-wrap; }`, `.table-wrap { overflow-x:auto; }` (`...html:91`, `...html:114-120`). | 수정 불필요. 실제 발표 화면에서 ERD 가독성만 한 번 확인한다. | 낮음 |

## 문제 없음으로 확인한 항목

- 3-2와 4-5의 Message Broker 역할 자체는 일치한다. Controller가 Task/Retry 정책을 정하고 Broker는 Queue·Delivery·Retry·Event를 전달하는 구조이며, MD의 “Broker는 판단하지 않고 전달” 원칙과 맞는다 (`...html:1143-1157`, `...md:219-227`).
- 4-6의 Local/A2A 분기와 `TeamResult` 정규화는 MD의 Registry 확장 규칙과 일치한다 (`...html:1159-1184`, `...md:421-439`).
- Context Broker와 Message Broker를 “판단에 필요한 정보 구성” 대 “결정된 Task/Event 운반”으로 구분한 설명은 서로 일치한다 (`...html:1154-1157`, `...md:217-244`).
- ERD의 `users → customer_cases`, `customer_cases → case_events`, `customer_cases → agent_runs` 실선 방향은 HTML에 표시된 FK 필드와 대체로 맞는다 (`...html:1363-1373`). 다만 #7~#9의 점선 의미는 별도 정리가 필요하다.
- HTML은 대상 파일 자체를 수정하지 않았으며, 이번 작업에서 생성한 변경물은 이 리포트뿐이다.

## 요약

### 즉시 고쳐야 할 것

1. 3-2 상세 아키텍처에서 Tool/Action과 Shared State의 순서를 4-3의 실제 Team 실행 흐름과 맞춘다.
2. ERD의 `agent_runs.team_id`를 FK로 둘지 실행 참조로 둘지 결정하고 선 스타일·범례를 일치시킨다.
3. 3-4의 Core 1 “DB 무결성까지 end-to-end” 표현을 MD의 Coordination / State Repository·DB / Tool Layer 책임 분해와 맞춘다.
4. 3~5배 비용 수치와 A2A 생태계 숫자·시점에 출처 또는 측정 조건을 붙인다.

### 판단 필요

- ERD에 `action_approvals` 등 MD의 전체 테이블을 추가할지, 현재 그림을 “핵심 관계만 표시한 개념 ERD”로 제한할지 결정한다.
- `owner_team_id`, `agent_runs.team_id`, Registry의 `team_id`를 각각 어떤 생명주기와 FK 정책으로 사용할지 확정한다.
- `knowledge_documents`–`agent_runs` 점선을 관계형 evidence reference로 볼지 Graph projection edge로 볼지 결정한다.
- HTML 절 번호를 MD에 맞출지, HTML 번호를 유지하면서 MD 기준 번호를 병기할지 결정한다.

### 무시 가능

- ERD의 넓은 화면 가로 스크롤은 소스상 `overflow-x:auto`로 처리되어 있다.
- 4-5의 Broker 왕복 결과선과 4-6의 Local/A2A 결과 정규화는 현재 설명과 일치한다.
- 3-1의 A/B/Remote Team 명칭은 HTML이 “구조 설명용 예시”라고 명시하므로 실제 Team 이름/개수의 사실 오류로 보지 않았다 (`...html:876-884`).

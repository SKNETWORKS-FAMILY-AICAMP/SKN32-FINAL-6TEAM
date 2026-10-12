# -*- coding: utf-8 -*-
"""AI 시스템 아키텍처(멀티 에이전트 아키텍처)를 만든다.

양식은 다른 주제(대화형 데이터 분석)의 예시가 채워진 상태로 배포됐다.
절 구조와 서식은 그대로 두고 본문만 paraId 로 찾아 바꾼다.
범위는 제출표(A-COPilot_제출표.xlsx)를 따른다. Commerce Ops 는 확장 범위다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from docxfill import Doc, esc

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FORMS))
c = lambda n: os.path.join(REPO, "program", "plan", "diagram", "charts", n)

d = Doc(os.path.join(FORMS, "[모델링 및 평가] AI 시스템 아키텍처 (멀티 에이전트 아키텍처)_양식.docx"),
        os.path.join(HERE, "_tmp_arch"))

d.replace_text("SK 네트웍스 Family AI 00기 : _____팀",
               "SK 네트웍스 Family AI 32기 : 6팀 A-COPilot")
d.replace_text("2026. 4. 18. ", "2026. 10. 6.")
d.replace_text("000", "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우")
d.fill_empty_para("00000015", "https://github.com/roroblack/A-COP.git")

B = {
    # 1.1 서비스 개요 및 목적
    "00000028": [
        "A-COP는 기업이 자사 고객 응대를 Agentic AI로 운영하도록 구축하고 판매하는 B2B 플랫폼이다. "
        "고객이 남긴 문의를 Case라는 업무 단위로 만들고, 여러 전문 Team이 역할을 나눠 처리하도록 조정한다. "
        "Case는 접수부터 종료까지 상태와 이력을 추적하는 단위이며, 모든 처리 기록은 PostgreSQL을 "
        "단일 원천으로 저장한다.",
        "이 문서가 증명하려는 것은 모델 성능이 아니라 오케스트레이션이다. "
        "오케스트레이션은 여러 에이전트의 실행 순서와 조건을 총괄해 지휘하는 일을 말한다. "
        "모델을 교체해도 Case 생명주기, Context Broker, Team 라우팅, 승인, 멱등성, "
        "대기와 재개가 그대로 유지되는지가 핵심 판정 대상이다.",
        "범위를 먼저 밝힌다. 이번 기간에 여는 것은 CS 응대와 제한된 검증 범위의 문의, 조회다. "
        "상품, 주문, 배송, 반품을 포함한 전면 Commerce Ops는 확장 범위이며 "
        "검증 쇼핑몰이 준비되는 대로 진행한다.",
    ],
    # 1.2 주요 사용자
    "0000002A": [
        "주요 사용자는 둘이다. 고객센터 운영자와 상담 관리자가 감독 면을 맡고, "
        "자기 AI 비서로 문의와 조회를 하려는 최종 소비자가 소비자 면을 맡는다.",
    ],
    "0000002C": [
        "Case 생명주기 관리. 접수, 분류, 라우팅, 실행, 보류, 승인 대기, 재개, 종료의 "
        "12개 상태를 코드로 강제한다.",
    ],
    "0000002D": [
        "인라인 분류. Case를 만들 때 감성, 의도, 이슈를 한 번에 분류하고 실패하면 사람에게 넘긴다.",
    ],
    "0000002E": [
        "Context Broker 기반 근거 조합. Team이 필요한 자료를 대신 읽어 ContextPack으로 묶어 준다. "
        "Team은 조회 도구를 직접 부르지 않는다.",
    ],
    "0000002F": [
        "승인 경계와 감사. 환불처럼 위험한 작업은 ActionProposal로만 올라오고 사람이 승인해야 실행된다. "
        "누가 무엇을 왜 했는지는 감사 로그로 남는다.",
        "외부 AI 연동. REST와 OpenAPI, MCP, A2A로 외부 에이전트가 Case를 열고 상태를 조회한다. "
        "지금 여는 범위는 제한된 검증 범위의 문의와 조회다.",
    ],
    # 1.3 설계 목표
    "00000031": [
        "설계 목표는 세 가지다. 첫째, Team을 Registry 등록형으로 만들어 새 업무 Team을 추가해도 "
        "Core 코드가 바뀌지 않게 한다. Team 하나를 늘리는 일이 전면 수정 작업이 된다면 설계가 잘못된 것으로 본다. "
        "둘째, 부수효과를 코어 2 한 곳으로 모아 승인과 멱등성과 감사를 공통으로 강제한다. "
        "셋째, 근거 없는 제안을 실행 전에 차단해 쓰기 권한을 여는 전제 조건을 만든다.",
    ],
    # 1.4 고려사항
    "00000033": [
        "확장성. Team은 TeamManifest와 표준 계약만으로 등록된다. Core는 Team 내부의 그래프와 프롬프트와 "
        "검색 코드를 가져오지 않으므로 도메인 팩 교체가 구조적으로 가능하다.",
    ],
    "00000034": [
        "동시성. 여러 에이전트가 같은 Case를 동시에 고칠 수 있다. Shared State에 비교 후 교체 방식을 "
        "적용해 나중 쓰기가 앞선 쓰기를 조용히 덮어쓰지 못하게 막는다.",
    ],
    "00000035": [
        "신뢰성 우선. 자동화율을 앞세우지 않는다. 어디서 자동화하지 않았는지와 "
        "사람에게 넘길 때의 인계 품질을 함께 지표로 제시한다.",
    ],
    # 2.3 오케스트레이션
    "0000005C": [
        "최상위 흐름은 LangGraph로 구성하고 흐름 결정은 Agentic Controller가 한다. "
        "Message Broker는 Task와 Event의 배달만 담당하고 Team 선택이나 판단은 하지 않는다. "
        "이 둘을 분리한 이유는, 배달 계층이 업무 판단을 겸하면 재시도와 중복 전달이 "
        "곧바로 업무 오류가 되기 때문이다.",
    ],
    "0000005D": [
        "Shared State 정의. Case별로 공유되는 상태 객체는 다음 키를 포함한다. 갱신은 비교 후 교체로만 이뤄진다.",
    ],
    "0000005E": ["case_state. Case의 현재 상태 12개 중 하나"],
    "0000005F": ["classification. 인라인 분류 결과인 sentiment, intent, issue_code, severity"],
    "00000060": ["context_pack. Context Broker가 조합한 근거 묶음. RAG 문서, DB 현재 상태, Case 이력, Memory"],
    "00000061": ["team_result. Team이 반환한 판단 결과와 근거 부족 신호"],
    "00000062": ["action_proposals. Team이 제안한 작업 목록. 실행 전 상태이며 부수효과는 아직 없다."],
    "00000063": [
        "approval_state. 승인 요청과 결재 결과. action_requests, action_approvals 테이블과 대응한다.",
        "resume_token. 보류 후 재개할 때 검증하는 토큰이다. 위조된 재개를 막는다.",
    ],
    "00000064": [
        "동시성 제어. Shared State 갱신은 버전 비교 후 교체로만 허용하고 충돌 시 재시도한다. "
        "Case 상태 전이는 허용된 다음 상태 표를 벗어나면 거부한다. "
        "무한 루프는 재계획 횟수 상한으로 차단한다.",
    ],
    # 2.4 기술 스택
    "00000066": [
        "실행 기반. Python, FastAPI, PostgreSQL, pgvector, LangGraph를 쓴다. "
        "Message Broker는 프로세스 안 큐와 Outbox 방식으로 시작하고 어댑터 교체로 확장한다. "
        "Outbox는 DB 기록과 메시지 발행을 한 트랜잭션으로 묶어 "
        "기록은 됐는데 메시지가 안 나가는 상황을 막는 방식이다.",
        "외부 진입. REST와 OpenAPI가 1순위이고 MCP와 A2A는 경계와 검증까지 구현한다. "
        "MCP는 외부 AI가 우리 기능을 도구로 불러 쓰게 하는 규약이고, "
        "A2A는 에이전트끼리 작업을 주고받는 규약이다.",
        "배포. AWS와 Docker는 Phase 2다. 현재 로컬 개발 환경에 Docker가 없어 "
        "로컬은 PostgreSQL을 직접 실행하고 배포 단계에서 컨테이너화한다.",
    ],
    "00000067": ["지식 저장소는 셋으로 나뉜다."],
    "00000068": ["Vector DB(pgvector). 정책, FAQ, 응대 지침 문서를 조각으로 나눠 의미 검색에 사용한다."],
    "00000069": [
        "Graph DB. Case, 이슈, 정책, Team, Action의 관계를 다룬다. Port와 Adapter로 분리해 두고 "
        "8주차와 9주차 비교 실험에서 채택 기준을 넘지 못하면 도입하지 않는다.",
    ],
    "0000006A": [
        "sLLM 파인튜닝 전략. 목표는 지식 주입이 아니라 출력 스키마 준수, "
        "주문과 취소와 환불과 배송 도메인 어휘, 근거와 승인과 보류를 표시하는 톤을 맞추는 것이다. "
        "정책의 진실값과 주문 상태, 금액은 계속 Context Broker와 DB에서 읽는다. "
        "1차는 라이선스 확인이 끝난 공개 데이터를 한국어로 재작성해 쓰고 2차는 비식별 실데이터를 더한다. "
        "실데이터가 500건 미만이면 학습 반복을 1회에서 2회로 제한한다. "
        "부트캠프 시트상 자체 sLLM 항목의 6팀 필수 여부는 문구가 3, 4번 주제로 돼 있어 불명확하며 "
        "강사 확인 전까지 필수로 단정하지 않는다.",
    ],
    # 3. Workflow
    "0000007A": [
        "1단계 사용자 요청. 고객이 결제는 취소했는데 다음 달에도 요금이 빠져나갔다고 문의한다. "
        "REST 또는 MCP를 통해 Agent Gateway로 들어온다.",
    ],
    "0000007B": [
        "2단계 Case 생성과 인라인 분류. Case를 new로 만들고 classifying으로 전환한다. "
        "감성과 의도와 이슈를 분류하고 실패하면 사람에게 넘긴다.",
    ],
    "0000007C": ["3단계 라우팅과 근거 조합. Controller와 Registry와 Context Broker가 함께 움직인다."],
    "0000007D": [
        "Registry가 Case 유형과 의도로 Team을 찾는다. 조건 하나에 Team이 정확히 하나만 나와야 하며 "
        "0개나 2개면 담당 없음으로 처리하고 사람에게 넘긴다.",
    ],
    "0000007E": [
        "Context Broker가 RAG 문서, DB 현재 상태, Case 이력, Memory를 Team 권한 범위 안에서 골라 "
        "ContextPack으로 묶는다. Team이 정보가 부족하다고 판단하면 Controller에 다시 요청한다.",
    ],
    "0000007F": [
        "4단계 Team 실행과 제안 생성. Team은 부수효과를 실행하지 않고 ActionProposal만 반환한다. "
        "제안의 각 필드는 ContextPack, DB와 대조해 검증하고 근거에 없는 주장을 담은 제안은 거부한다.",
    ],
    "00000080": [
        "5단계 승인과 실행. 고위험 Action은 Case를 승인 대기로 두고 사람의 결재를 기다린다. "
        "승인되면 Tool과 Action Layer가 실행하며, 같은 요청이 여러 번 들어와도 "
        "실제 처리는 한 번만 일어나도록 멱등성 키로 막는다. 실행 결과는 감사 로그에 남는다.",
    ],
    "00000081": [
        "6단계 응답과 종료. Response Generation & Review Team이 근거를 인용한 답변을 만들고 자체 검수를 거친다. "
        "Case는 resolved로 전환되고 자동 처리 한계에 걸리면 escalated로 사람에게 넘어간다. "
        "모든 전이는 case_events에 추가만 되는 방식으로 기록돼 나중에 그대로 재생할 수 있다.",
    ],
    # 4.1
    "00000091": [
        "판정 기준. 검색 결과가 없거나 유사도가 기준 아래일 때 근거 부족으로 본다. "
        "정확한 임계값은 실제 분포를 측정한 뒤 확정하며 임의로 정한 값을 확정치처럼 쓰지 않는다.",
    ],
    "00000092": [
        "대응. 지어낸 답을 내보내지 않고 사람에게 넘긴다. 이때 근거가 부족해 기권한 비율과 "
        "근거가 충분한데 기권한 비율을 함께 측정해, 안전을 이유로 무조건 넘기는 회피를 걸러낸다.",
    ],
    # 4.2
    "00000094": [
        "제어 로직. Controller의 재계획 횟수에 상한을 두고 초과하면 즉시 중단한다. "
        "Case 상태 전이표에 없는 전이는 거부한다.",
    ],
    "00000095": [
        "부분 성공 처리. 일부 Team만 성공했을 때 전체를 실패로 버리지 않는다. "
        "지금까지의 결과를 Case에 남기고 남은 판단은 사람에게 인계한다. "
        "인계할 때 어떤 근거로 어디까지 처리했는지를 함께 전달한다.",
    ],
    # 4.3
    "00000097": [
        "재시도 전략. 외부 API와 LLM 호출은 시간 초과 시 대기 시간을 늘려 가며 재시도한다. "
        "부수효과가 있는 호출은 반드시 멱등성 키를 함께 보내 재시도가 중복 실행이 되지 않게 한다. "
        "동일 요청 10회에 실제 부수효과 1회를 검증 기준으로 둔다.",
    ],
    "00000098": [
        "비동기 대기. 결제사나 택배사처럼 결과가 나중에 오는 경우 Case를 외부 대기 상태로 두고 콜백을 기다린다. "
        "재개는 토큰 검증을 통과해야만 이뤄진다. "
        "Outbox에 쌓인 메시지는 워커가 다시 집어 재발행하므로 중간에 프로세스가 죽어도 유실되지 않는다.",
    ],
    # 4.4
    "0000009A": [
        "출력 검수. Response Generation & Review Team이 응답을 내보내기 전에 개인정보 노출과 정책 위반, "
        "근거 없는 주장을 검사한다. 검사 규칙은 config/guardrails.yaml에 두고 코드와 분리한다.",
        "쓰기 권한의 전제. ActionProposal은 근거 대조를 통과해야만 승인 대기로 올라간다. "
        "근거 정합률과 근거 초과율을 지표로 남기고 거부 사유는 평가에 연결한다.",
    ],
    # 5 도입
    "000000A9": [
        "모델링 단계의 완성도는 다음 지표로 검증한다. 골든셋 60건과 홀드아웃 20건을 쓰고 각 군을 3회 실행한다. "
        "홀드아웃은 개발 중 보지 않는 검증용 표본이며 홀드아웃으로 프롬프트나 학습 데이터를 다시 고치지 않는다. "
        "비교군은 A가 단일 LLM, B가 고정 워크플로와 정책 검색, Proposed가 A-COP 전체다.",
        "목표치는 착수 시점의 기준선이며 실제 분포를 측정한 뒤 재산정할 수 있다. "
        "지표는 분모, 모델, temperature, seed, 프롬프트 버전, 데이터셋 해시, "
        "부트스트랩 95퍼센트 신뢰구간과 함께 보고한다.",
    ],
    # 6 결론
    "000000C7": [
        "본 아키텍처의 핵심은 새로운 모델이나 새로운 검색 기법이 아니라 "
        "여러 에이전트가 한 일을 검증하고 통제하는 층이다. "
        "Team은 판단만 하고 부수효과는 코어 2 한 곳에서만 일어나며 승인과 멱등성과 감사가 공통으로 강제된다. "
        "Team을 Registry 등록형으로 둔 덕분에 도메인 팩 교체와 Team 추가가 Core 수정 없이 가능하다.",
    ],
    "000000C8": [
        "남은 과제는 넷이다. 첫째, 전면 Commerce Ops는 확장 범위이며 검증 쇼핑몰이 준비되는 대로 진행한다. "
        "둘째, GraphRAG는 8주차와 9주차 비교 실험 결과에 따라 채택 여부를 정하고 기준을 넘지 못하면 도입하지 않는다. "
        "셋째, 이상 판정의 임계값은 유형과 시간대별 기준선을 쌓은 뒤 확정한다. "
        "넷째, 결과 표본이 60건이고 도메인이 하나로 고정돼 있으므로 일반화 주장을 하지 않는다. "
        "LLM 채점자의 편향과 Mock 의존도 함께 한계로 기록한다.",
    ],
}
for pid, texts in B.items():
    d.replace_para(pid, texts)

# ---------------------------------------------------------------- 2.2 표
AGENTS = [
    ("Agentic Controller", "LangGraph 최상위 그래프",
     "Case 상태 판정, Team 라우팅, 재계획, 전이 이벤트 기록. 흐름 결정의 유일한 주체다."),
    ("Context Broker", "pgvector RAG와 DB 조회",
     "Team이 필요로 하는 근거를 권한 범위 안에서 읽어 ContextPack으로 조합한다. "
     "Team은 조회 도구를 직접 부르지 않는다."),
    ("VOC & Store Manager", "LangGraph와 규칙 기반 집계",
     "이상징후와 급증 탐지, 반복 불만 식별, 급증 이후 원인 축 판별과 다른 Team으로의 위임 제안. "
     "이번 기간 착수 범위다."),
    ("Response Generation & Review", "LLM, RAG, Guardrails",
     "근거를 인용한 답변 생성과 자체 검수. 개인정보와 정책 위반과 근거 없는 주장을 "
     "내보내기 전에 차단한다. 이번 기간 착수 범위다."),
    ("MCP Server 표면", "MCP Tool과 Resource",
     "소비자의 개인 AI가 붙는 접점이다. 지금은 제한된 검증 범위의 문의와 조회만 노출한다."),
    ("Commerce Ops 팩", "확장 범위",
     "Procurement + Order & Payment, Fulfillment & Logistics, Return & Refund, "
     "Catalog & Verification. 검증 쇼핑몰이 준비되는 대로 진행하는 확장 범위다."),
]
anchor = d.xml.index("Supervisor Agent")
row_start = d.xml.rindex("<w:tr>", 0, anchor)
last = d.xml.index("최종 게이트(Gate).")
row_end = d.xml.index("</w:tr>", last) + len("</w:tr>")
template_row = d.xml[row_start:d.xml.index("</w:tr>", row_start) + len("</w:tr>")]
rows = []
for name, stack, role in AGENTS:
    r = re.sub(r' w14:paraId="[0-9A-F]{8}"', "", template_row)
    for old, new in zip(["Supervisor Agent", "GPT-4o",
                         "질의 해석(Intent Parsing), 작업 분할(Decomposition), "
                         "하위 에이전트 라우팅 및 최종 결과 Join."],
                        [name, stack, role]):
        assert old in r, "셀 없음: " + old
        r = r.replace(old, esc(new))
    rows.append(r)
d.xml = d.xml[:row_start] + "".join(rows) + d.xml[row_end:]

# ---------------------------------------------------------------- 5장 평가 표
METRICS = [
    ("분류 (인라인)", "intent accuracy, issue macro-F1, 골든셋 60건", "혼동행렬 보고, 목표치는 1차 측정 후 확정"),
    ("근거 (RAG와 제안)", "groundedness, 근거 정합률, 근거 초과율", "근거 초과율 0에 수렴, 정합률 우선"),
    ("오케스트레이션", "task success, resolution rate, 스키마 준수율", "Proposed가 A와 B 대비 개선, 95퍼센트 신뢰구간"),
    ("안전과 기권", "적절한 기권율, 과잉 기권율, 멱등성", "동일 요청 10회에 부수효과 1회"),
]
old_cells = [
    ("RAG (Search)", "RAGAS (Faithfulness, Answer Relevancy)", "0.85 이상"),
    ("SQL (Analysis)", "SQL Execution Success Rate / Syntax Accuracy", "95% 이상"),
    ("Orchestration", "Task Completion Rate (Join Node 성공률)", "98% 이상"),
    ("Guardrails", "PII Detection Rate / Hallucination Rate", "99% / &lt; 5%"),
]
tbl5 = d.xml.index("평가 대상")
head5, body5 = d.xml[:tbl5], d.xml[tbl5:]
for old, new in zip(old_cells, METRICS):
    for o, n in zip(old, new):
        assert o in body5, "평가표 셀 없음: " + o
        body5 = body5.replace(o, esc(n), 1)
d.xml = head5 + body5

# ---------------------------------------------------------------- 2.1 그림
span = d._find_para("00000045")
s, e = span
blk = d.xml[s:e]
open_tag = re.match(r'(<w:p\b[^>]*>)', blk).group(1)
ppr = re.match(r'<w:pPr>.*?</w:pPr>', blk[len(open_tag):], re.S)
imgs = (d.image_xml(c("uml_component_v2.png"), 6.3)
        + d.caption("그림 1. A-COP Basement 컴포넌트 구성. 파란 영역이 코어 1, 붉은 영역이 코어 2, "
                    "초록 영역이 Registry에 등록되는 도메인 팩이다.")
        + d.image_xml(c("10_case_states.png"), 6.3)
        + d.caption("그림 2. Case 상태 전이 12개. 보류와 재개가 상태로 표현된다.")
        + d.image_xml(c("uml_sequence_v2.png"), 5.6)
        + d.caption("그림 3. 문의 한 건이 접수부터 응답까지 지나는 순서."))
d.xml = d.xml[:s] + imgs + d.xml[e:]

# ---------------------------------------------------------------- API 초안을 2.4 뒤에 붙인다
api_rows = [
    ("POST /v1/cases", "Case 생성", "코어 2", "고객 문의를 접수한다. 응답은 case_id와 상태다."),
    ("GET /v1/cases/{id}", "Case 조회", "코어 2", "상태, 분류 결과, 최근 이벤트를 돌려준다."),
    ("GET /v1/cases/{id}/events", "이벤트 이력", "코어 2", "추가만 되는 전이 기록을 시간순으로 돌려준다."),
    ("POST /v1/cases/{id}/messages", "고객 추가 입력", "코어 2", "보류 중인 Case를 재개시킨다. 토큰 검증을 거친다."),
    ("GET /v1/actions/pending", "승인 대기 목록", "코어 2", "운영자 화면이 쓴다."),
    ("POST /v1/actions/{id}/approve", "승인", "코어 2", "결재자와 시각을 감사 로그에 남긴다."),
    ("MCP tool open_support_case", "문의 열기", "코어 2", "외부 AI가 Case를 연다. 제한된 검증 범위다."),
    ("MCP tool get_case_status", "상태 조회", "코어 2", "읽기 전용이다."),
    ("MCP resource policy_docs", "정책 문서", "코어 2", "읽기 전용 자료다."),
    ("A2A task delegate", "원격 위임", "코어 2", "Catalog & Verification 경로다. 확장 범위다."),
]
api_items = [
    ("b", "2.5 API 인터페이스 초안"),
    "외부에서 들어오는 경로는 셋이다. REST와 OpenAPI가 1순위이고, MCP는 소비자의 개인 AI가 붙는 접점이며, "
    "A2A는 원격 에이전트에 작업을 위임하는 경로다. 아래는 착수 시점의 초안이며 계약 버전으로 관리한다.",
]
for path, name, owner, desc in api_rows:
    api_items.append(("l", "%s . %s . 담당 %s . %s" % (path, name, owner, desc)))
api_items += [
    ("b", "공통 규칙"),
    ("l", "인증은 API Key와 Scope로 시작하고 Phase 2에서 OAuth 2.0과 OpenID Connect로 확장한다."),
    ("l", "부수효과를 내는 요청에는 멱등성 키를 필수로 받는다. 같은 키로 재시도하면 첫 결과를 돌려준다."),
    ("l", "모든 요청과 응답은 감사 로그에 남긴다. 비밀값은 로그에 남기지 않는다."),
    ("l", "새 endpoint는 독립 resource, scope, 멱등성, 감사, 평가 fixture가 모두 있을 때 "
          "계약 버전으로 추가한다. 개수를 맞추려고 기존 resource를 억지로 합치지 않는다."),
]
d.insert_after_para("0000006A", d.build(api_items))

out = d.save(os.path.join(FORMS, "[모델링 및 평가] AI 시스템 아키텍처_A-COPilot.docx"))
print("저장:", out)

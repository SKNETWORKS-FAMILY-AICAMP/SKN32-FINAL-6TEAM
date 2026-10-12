# -*- coding: utf-8 -*-
"""시스템 구성도를 만든다.

양식은 다른 주제의 예시가 채워진 상태로 배포됐다. 절 구조는 두고 본문만 바꾼다.
우리 구성과 다른 항목(MySQL, ChromaDB, Redis 등)은 실제 선택으로 고쳐 적는다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from docxfill import Doc, esc, check

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FORMS))
c = lambda n: os.path.join(REPO, "program", "plan", "diagram", "charts", n)

d = Doc(os.path.join(FORMS, "[모델배포] 시스템 구성도_양식.docx"),
        os.path.join(HERE, "_tmp_sysdiag"))

d.replace_text("SK 네트웍스 Family AI 00기 : _____팀",
               "SK 네트웍스 Family AI 32기 : 6팀 A-COPilot")
d.replace_text("2026. 4. 18. ", "2026. 10. 21.")
d.replace_text("000", "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우")
d.fill_empty_para("00000015", "https://github.com/roroblack/A-COP.git")


def fill_row(row_xml, values):
    cells = list(re.finditer(r'<w:tc>.*?</w:tc>', row_xml, re.S))
    assert len(cells) == len(values), "셀 수가 다르다 %d vs %d" % (len(cells), len(values))
    out, last = [], 0
    for m, val in zip(cells, values):
        check(val)
        cell, seen = m.group(0), [False]

        def sub(mm):
            if not seen[0]:
                seen[0] = True
                return '<w:t xml:space="preserve">%s</w:t>' % esc(val)
            return '<w:t xml:space="preserve"></w:t>'
        cell = re.sub(r'<w:t[^>]*>[^<]*</w:t>', sub, cell)
        out.append(row_xml[last:m.start()] + cell)
        last = m.end()
    return "".join(out) + row_xml[last:]


def replace_rows(first_anchor, last_anchor, rows):
    i = d.xml.index(first_anchor)
    rs = d.xml.rindex("<w:tr>", 0, i)
    re_ = d.xml.index("</w:tr>", d.xml.index(last_anchor)) + len("</w:tr>")
    tpl = re.sub(r' w14:paraId="[0-9A-F]{8}"', "",
                 d.xml[rs:d.xml.index("</w:tr>", rs) + len("</w:tr>")])
    d.xml = d.xml[:rs] + "".join(fill_row(tpl, r) for r in rows) + d.xml[re_:]


# ---------------------------------------------------------------- 1. 전체 구조
d.replace_para("00000028", ["아래가 전체 구성이다."])
d.insert_after_para("00000028",
                    d.image_xml(c("uml_component_v2.png"), 6.3)
                    + d.caption("그림 1. 전체 서비스 구조. 파란 영역이 코어 1 Case Runtime, "
                                "붉은 영역이 코어 2 Access and Action, 초록 영역이 도메인 팩이다.")
                    + d.image_xml(c("uml_deploy_v2.png"), 6.3)
                    + d.caption("그림 2. 배포 구성. 현재 로컬 개발은 PostgreSQL 직접 실행이고 "
                                "컨테이너화는 Phase 2다."))

d.replace_para("0000002A", [
    "계층 분리. 운영 화면은 React 기반 콘솔로 백엔드와 분리한다. 백엔드는 FastAPI 하나이며 "
    "그 안에서 코어 1과 코어 2가 책임을 나눈다. 코어 1은 Case 생명주기와 Team 조정을, "
    "코어 2는 외부 진입과 실제 실행과 승인과 감사를 맡는다.",
])
d.replace_para("0000002B", [
    "상태 가시화. Team 사이에 공유되는 값은 Shared State 하나로 모은다. "
    "case_state, classification, context_pack, team_result, action_proposals, "
    "approval_state, resume_token 을 담는다. 갱신은 비교 후 교체로만 이뤄져 "
    "동시에 고쳐도 나중 쓰기가 앞선 쓰기를 덮지 않는다.",
])
d.replace_para("0000002C", [
    "비동기 처리. 결제사나 택배사처럼 결과가 나중에 오는 호출은 Case 를 외부 대기 상태로 두고 "
    "콜백을 기다린다. 이벤트 전달은 Outbox 로 한다. DB 기록과 메시지 발행을 한 트랜잭션으로 묶어 "
    "기록은 됐는데 메시지가 안 나가는 상황을 막는다.",
])
d.replace_para("0000002D", [
    "MCP 연결. 소비자의 개인 AI 가 우리 MCP Server 에 붙어 Tool 과 Resource 를 쓴다. "
    "지금 여는 범위는 문의와 조회다. 환불이나 주문 실행은 아직 열지 않았다.",
])
d.replace_para("0000002F", [
    "재생 가능한 기록. Case 의 모든 상태 전이를 case_events 에 추가만 한다. "
    "고치지 않으므로 나중에 그대로 재생해 무슨 일이 있었는지 되짚을 수 있다.",
])
d.replace_para("00000030", [
    "구성으로 늘리는 확장. Team 은 Registry 에 등록하는 방식이라 도입 기업이 Team 을 추가해도 "
    "Core 코드는 바뀌지 않는다. Team 을 하나 늘리는 일이 전면 수정 작업이 된다면 설계가 잘못된 것이다.",
])

# ---------------------------------------------------------------- 2. 구성 요소
d.replace_para("0000003F", [
    "배포 목표는 자체 호스팅이다. 고객사 환경에 올려 데이터가 밖으로 나가지 않게 한다. "
    "AWS 와 Docker 는 Phase 2 다.",
])
d.replace_para("00000040", [
    "현재 로컬 개발 환경에는 Docker 가 설치돼 있지 않다. 로컬은 PostgreSQL 을 직접 실행하고 "
    "배포 단계에서 컨테이너화한다. 이 사실을 숨기지 않는다.",
    "설정은 대상 서버가 아니라 우리가 운영하는 중앙 저장소에 둔다. "
    "2026-08-29 결정이며 정본은 program/plan/A-COP_Composer_중앙설정저장소_결정.md 다. "
    "구성을 바꾸는 코드는 중앙 설정 서비스 한 곳에만 설치하고, 고객사에 배포되는 대상에는 넣지 않는다. "
    "쓰기 가능한 구성 관리 기능이 고객 대면 프로세스에 있으면 취약점 하나가 서비스 전체에 닿기 때문이다.",
    "대상은 기동할 때 중앙에서 자기 선언을 읽기만 한다. 설정을 바꿀 때 고객 서버에 접속하지 않는다.",
    "지금 상태는 저장 계층만 있고 아직 연결되지 않았다. "
    "config_store.py 와 마이그레이션과 통합 테스트 10건은 있고 테스트는 통과한다. "
    "다만 이 모듈을 부르는 곳이 아직 없다. "
    "대상이 중앙에 못 붙을 때의 동작과 반영 방법도 아직 정하지 않았다.",
])
d.replace_para("00000042", [
    "백엔드 API 서버. FastAPI 하나다. 최상위 흐름은 LangGraph 로 구성하고 "
    "Agentic Controller 가 어느 Team 에 일을 줄지 정한다.",
])
d.replace_para("00000043", [
    "MCP 서버와 A2A 어댑터. 코어 2 안에 둔다. 외부 AI 가 들어오는 문이며 "
    "인증과 권한 범위를 여기서 확인한다.",
])
d.replace_para("00000045", [
    "PostgreSQL. 업무 상태의 단일 원천이다. customer_cases, case_events, shared_state, "
    "agent_runs, team_tasks, outbox, action_requests, action_approvals, audit_logs 를 담는다. "
    "MySQL 이 아니라 PostgreSQL 을 쓰는 이유는 pgvector 확장 때문이다.",
])
d.replace_para("00000046", [
    "pgvector. 지식 문서 조각과 임베딩을 담는다. 별도 벡터 DB 서버를 세우지 않고 "
    "같은 PostgreSQL 안의 확장으로 둔다. 그래야 지식과 업무 상태를 한 트랜잭션에 묶을 수 있다.",
])
d.replace_para("00000047", [
    "Graph Store. Case 와 이슈와 정책과 Team 과 Action 의 관계를 다룬다. "
    "Port 와 Adapter 로 분리해 두었고 지금 동작하는 선택은 PostgreSQL 기반 구현이다. "
    "Apache AGE 와 Neo4j 는 후보이며 8주차와 9주차 비교 실험에서 채택 기준을 넘을 때만 도입한다.",
])
d.replace_para("00000048", [
    "메시지 전달. MVP 는 프로세스 안 큐와 Outbox 다. Redis 나 RabbitMQ 는 어댑터 교체로 "
    "Phase 2 에 붙인다. 지금 단계에서 별도 서버를 세우지 않는다.",
])
d.replace_para("0000004A", [
    "메인 추론 모델. 상용 LLM 을 쓰고 프롬프트 버전과 모델과 temperature 와 seed 를 기록한다. "
    "평가에서 군을 비교하려면 이 값들이 고정돼야 한다.",
])
d.replace_para("0000004B", [
    "자체 파인튜닝 모델. 목표는 지식 주입이 아니라 출력 스키마 준수와 도메인 어휘와 톤이다. "
    "부트캠프 시트의 자체 sLLM 항목은 문구가 3, 4번 주제로 돼 있어 6팀 필수 여부가 불명확하며 "
    "강사 확인 전까지 필수로 단정하지 않는다.",
])
d.replace_para("0000004D", [
    "MCP 와 A2A. MCP 는 외부 AI 가 우리 기능을 도구처럼 불러 쓰게 하는 규약이고 "
    "A2A 는 에이전트끼리 작업을 주고받는 규약이다. A2A 는 Catalog and Verification 경로에 쓴다. "
    "외부 업무 시스템 연동은 코어 2 의 Tool and Action Layer 를 거친다.",
])

# ---------------------------------------------------------------- 3. 데이터 흐름
d.replace_para("0000005C", [
    "수집. 브라우저 확장으로 본인 계정의 주문 기록을 읽고, 택배사 조회 API 를 부르고, "
    "공개 데이터셋을 내려받는다. 웹 크롤링과 로그인 자동화는 하지 않는다.",
])
d.replace_para("0000005D", [
    "정규화. 스키마를 통일하고 개인정보를 걷어내고 중복을 없앤다. "
    "자릿수가 큰 식별자는 문자열로 저장한다. 숫자로 두면 자릿수가 잘리기 때문이다.",
])
d.replace_para("0000005E", [
    "색인. 문서를 조각으로 나눠 임베딩을 만들고 pgvector 에 적재한다. "
    "조각마다 원본 문서와 위치를 남겨 인용을 되짚을 수 있게 한다.",
])
d.replace_para("0000005F", [
    "이관. 배포 단계에서 운영 PostgreSQL 로 옮긴다. 원본 수집 파일은 저장소에 올리지 않는다.",
])
d.replace_para("00000061", ["문의 접수. REST 또는 MCP 로 들어온다. Case 를 만들고 new 로 둔다."])
d.replace_para("00000062", [
    "인라인 분류. classifying 상태에서 감성과 의도와 이슈를 한 번에 분류한다. "
    "실패하면 사람에게 넘긴다.",
])
d.replace_para("00000063", [
    "라우팅과 근거 조합. Registry 가 Case 유형과 의도로 Team 을 찾는다. 조건 하나에 Team 이 하나여야 한다. "
    "Context Broker 가 필요한 자료를 Team 권한 범위 안에서 골라 ContextPack 으로 묶는다.",
])
d.replace_para("00000064", [
    "Team 실행. Team 은 부수효과를 실행하지 않고 ActionProposal 만 반환한다. "
    "제안의 각 필드는 ContextPack 과 DB 에 대조해 검증한다.",
])
d.replace_para("00000065", [
    "승인과 응답. 고위험 Action 은 사람이 승인해야 실행된다. 같은 요청이 여러 번 들어와도 "
    "실제 처리는 한 번만 일어난다. 응답에는 근거를 인용하고 결과는 감사 로그에 남는다.",
])

AGENTS = [
    ("Agentic Controller", "Case 상태 판정과 Team 라우팅과 재계획",
     "case_state, team_result", "다음 Team 또는 종료 판정"),
    ("Context Broker", "권한 범위 안에서 근거를 읽어 조합",
     "context_pack", "ContextPack"),
    ("VOC and Store Manager", "이상징후와 급증 탐지, 원인 축 판별과 위임 제안",
     "case_events 집계", "리포트와 알림, 위임 제안"),
    ("Response Generation and Review", "근거를 인용한 답변 생성과 자체 검수",
     "context_pack, action_proposals", "답변 초안과 검수 결과"),
    ("Tool and Action Layer", "승인된 Action 실행과 감사 기록",
     "approval_state", "실행 결과와 감사 로그"),
]
replace_rows("Router", "자연어 응답 리포트", AGENTS)

# ---------------------------------------------------------------- 4. 기술 스택
STACK = [
    ("Language", "Python", "3.11", "시스템 메인 언어"),
    ("Framework", "FastAPI", "0.11x", "백엔드 API 와 외부 진입"),
    ("Orchestration", "LangGraph", "0.2.x", "최상위 흐름과 Team 내부 그래프"),
    ("Database", "PostgreSQL", "16", "업무 상태의 단일 원천"),
    ("Vector", "pgvector", "0.7.x", "지식 조각 임베딩과 의미 검색"),
    ("Graph", "PostgreSQL 기반 구현", "현재 선택", "관계 조회. AGE 와 Neo4j 는 채택 기준 통과 시"),
    ("ORM", "SQLAlchemy", "2.0.x", "모델 정의. 스키마 이관은 Alembic"),
    ("Protocol", "MCP", "SDK 0.1.x", "외부 AI 도구 연동"),
    ("Protocol", "A2A", "스펙 1.0", "원격 에이전트 위임"),
    ("Auth", "API Key 와 Scope", "MVP", "Phase 2 에 OAuth 2.0 과 OpenID Connect"),
    ("Frontend", "React", "18", "운영 콘솔"),
    ("Test", "pytest", "8.x", "계약 테스트와 회귀 테스트"),
    ("Eval", "bootstrap 과 McNemar", "자체 구현", "군 비교와 통계 검정"),
    ("Infrastructure", "Docker", "Phase 2", "로컬에는 미설치. 배포 단계에서 컨테이너화"),
]
replace_rows("Language", "서비스 컨테이너화 관리", STACK)

# ---------------------------------------------------------------- 보안 항목
d.replace_para("000000B2", [
    "확인 완료. 비밀값은 환경변수로만 받고 파일에 저장하지 않으며 화면과 감사 로그에 출력하지 않는다.",
])
d.replace_para("000000B3", [
    "확인 완료. 응답을 내보내기 전에 개인정보 노출을 검사한다. "
    "검사 규칙은 config/guardrails.yaml 에 두고 코드와 분리한다.",
])
d.replace_para("000000B4", [
    "확인 완료. Team 이 낸 제안은 ContextPack 과 DB 에 대조한다. "
    "근거에 없는 대상이나 금액이나 수량을 담은 제안은 거부하고 사유를 기록한다. "
    "이것이 프롬프트 주입에 대한 방어이자 쓰기 권한을 여는 전제 조건이다.",
])
d.replace_para("000000B5", [
    "일부 확인. 토큰 사용량과 비용은 평가 리포트에 run 단위로 기록한다. "
    "호출 속도 제한은 아직 넣지 않았다. 확인되지 않은 것을 확인 완료로 적지 않는다.",
])
d.insert_after_para("000000B5", d.build([
    ("l", "확인 완료. 부수효과가 있는 요청은 멱등성 키를 필수로 받는다. "
          "동일 요청 10회에 실제 처리 1회를 검증 기준으로 둔다."),
    ("l", "확인 완료. 고위험 Action 은 사람 승인 없이 실행되지 않는다. "
          "승인자와 시각을 action_approvals 에 남긴다."),
    ("l", "확인 완료. 서버는 127.0.0.1 에만 바인딩한다. 운영 콘솔을 외부에 노출하지 않는다."),
]))

out = d.save(os.path.join(FORMS, "[모델배포] 시스템 구성도_A-COPilot.docx"))
print("저장:", out)

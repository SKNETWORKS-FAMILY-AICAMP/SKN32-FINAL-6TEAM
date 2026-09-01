# -*- coding: utf-8 -*-
"""낱장 열두 장 말고 나머지 그림들의 내용.

★그림(PNG)과 화면(HTML)이 같은 값을 쓰게 하려고 한곳에 모았다. 예전엔 그리는
  코드 안에 값이 박혀 있어서, 4번 단계가 코어 1 로 갔는데 전체 지도만 모델
  갈래에 그대로 있었다. 한쪽만 고쳐지는 일이 실제로 났다.

★색은 이름으로 둔다. matplotlib 은 draw.py 의 상수로, 브라우저는 CSS 변수로
  각자 옮긴다. 16진수를 여기 박으면 어느 한쪽이 못 쓴다.
"""

#: 전체 지도의 가로 갈래. 어느 단계가 어느 갈래인지는 적지 않는다.
#: 단계 색이 곧 갈래다. `sheet_data.SHEETS` 의 색과 맞춰 본다.
LANES = [
    ("코어 2   진입과 실행", "red"),
    ("코어 1   Case 조정", "blue"),
    ("모델     Agent Team", "green"),
    ("근거 조합", "purple"),
    ("기록", "grey"),
]
LANES_FOOT = ("가로가 시간이다. 왼쪽 이름표가 그 단계를 누가 맡는지다. "
              "같은 담당이 흐름 중간에 다시 나온다.")

#: 큰 구조 네 갈래. (제목, 부제, 색, [(이름, 이 건이 쓰나, 메모)])
STRUCTURE_HEAD = ("큰 구조에서 이 케이스가 건드리는 것",
                  "넷을 다르게 부른다. 무엇을 뺄 수 있고 무엇을 못 빼는지가 여기서 "
                  "갈린다. 채운 동그라미가 이 환불 한 건이 실제로 지나는 것이다.")
STRUCTURE = [
    ("컴포넌트  9", "빼면 시스템이 아니다. 고를 수 없다", "blue", [
        ("Case lifecycle · transition_case()", True, "3 · 10"),
        ("계약 모델 (TeamTask · TeamResult · ContextPack)", True, "전 단계"),
        ("Team Registry", True, "5 · 6"),
        ("Context Broker", True, "7"),
        ("DB repository · session", True, "3 · 8 · 12"),
        ("Case service (run · resume)", True, "8"),
        ("Controller", True, "5 ~ 10"),
        ("설정 · 가드레일", True, "7"),
        ("Outbox 원자성", False, "이 건은 안 씀"),
    ]),
    ("모듈  6", "켜고 끌 수 있다. 끄면 그 표면도 사라진다", "green", [
        ("vector_rag", True, "7"),
        ("voc  (분류 · 일일 배치)", True, "4 · 소유는 코어 1"),
        ("mcp", False, "이 건은 REST 로 들어왔다"),
        ("ops_ui", False, "운영자 화면"),
        ("graph_store", False, "관리자 화면 전용"),
        ("a2a_executor", False, "지금 꺼져 있다"),
    ]),
    ("인스턴스  Agent Team 6", "개수가 늘고 주는 것은 이것뿐이다", "green", [
        ("return_refund", True, "8 · 이 건을 맡는다"),
        ("response_generation_review", False, "9 · 지금 꺼짐"),
        ("voc_store_manager", False, "껍데기. 계약만 유지"),
        ("procurement_order_payment", False, ""),
        ("fulfillment_logistics", False, ""),
        ("catalog_verification", False, ""),
    ]),
    ("Port  6", "구현을 갈아 끼우는 자리", "purple", [
        ("TeamExecutorPort  =  LocalTeamExecutor", True, "8"),
        ("정책 검색 함수  =  search_policy", True, "7"),
        ("분류기  =  feedback.classify", True, "4"),
        ("LLM  =  OpenAITeamLLM", True, "4 · 9"),
        ("MessageBrokerPort  =  Outbox", False, ""),
        ("GraphStorePort  =  SqlGraphAdapter", False, ""),
    ]),
]

#: 상태 열두 개. 단계 열둘과 겹치지 않는다.
LIFECYCLE_HEAD = ("작은 구조에서 본 같은 흐름  ·  상태 12개",
                  "앞의 열두 단계는 코드가 지나는 순서지 상태가 아니다. "
                  "둘 다 열둘이라 헷갈리지만 겹치지 않는다.")
LIFECYCLE_MAIN = [("new", "행을 만든 찰나"), ("classifying", "분류 중"),
                  ("routing", "팀 찾는 중"), ("running", "팀이 도는 중"),
                  ("resolved", "종결")]
LIFECYCLE_WAIT = [("waiting_input", "고객 답을 기다림"),
                  ("waiting_approval", "사람 결재를 기다림"),
                  ("waiting_external", "외부 콜백을 기다림"),
                  ("resuming", "다시 이어서 실행")]
LIFECYCLE_END = [("escalated", "사람에게 넘김", "red"),
                 ("failed", "실패로 끝남", "red"),
                 ("cancelled", "취소됨", "grey")]
LIFECYCLE_WHY = ("왜 헷갈리나",
                 "단계도 열둘이고 상태도 열둘이다. 그런데 1번 신원 확인과 2번 중복 확인은 "
                 "Case 가 생기기 전이라 상태가 아예 없고, 반대로 waiting_external 과 "
                 "cancelled 는 코드 흐름 열두 단계에 안 나온다. "
                 "한쪽을 다른 쪽으로 번역하려 하면 안 맞는다.")

#: 전달 문서가 바뀌어 가는 모양. (이름, 색, 몇 번 단계, [필드])
CONTRACTS_HEAD = ("전달 문서가 바뀌어 가는 모양",
                  "같은 문의 하나가 다섯 번 모습을 바꾼다. 각 계약은 extra 필드를 "
                  "금지해서 조용히 늘어나지 않는다.")
CONTRACTS = [
    ("HTTP 요청", "red", 1, ["request_id", "customer_id", "message", "channel"], ""),
    ("Principal", "red", 1, ["tenant_id", "scopes", "key_id"], "여기서 tenant 가 붙는다"),
    ("ContextPack", "purple", 7, ["sections", "evidence[]", "degraded", "omissions[]"],
     "근거가 붙는다"),
    ("TeamTask", "green", 8, ["case_id", "capability", "context_pack", "run_id"],
     "팀에게 넘어간다"),
    ("TeamResult", "green", 8, ["next_action", "answer", "evidence[]", "proposals[]"],
     "판단이 붙는다"),
]
CONTRACTS_TABLES = [
    ("customer_cases", "지금 상태 1행. 이벤트를 적용한 결과"),
    ("case_events", "무슨 일이 있었나 4행. 추가만 한다"),
    ("action_requests", "멱등성 기록 1행"),
    ("agent_runs · llm_calls", "실행과 프롬프트 기록"),
]

#: 갈림길. (단계, 무슨 일이 생기면, 어떻게 되나, 왜 그렇게 하나, 색)
BRANCHES_HEAD = ("다른 길로 빠지는 경우",
                 "앞의 열두 장은 전부 통과한 길이다. 실제로는 아래에서 갈린다. "
                 "어느 쪽이든 조용히 넘어가지 않는다.")
BRANCHES_COLS = ("단계", "무슨 일이 생기면", "어떻게 되나", "왜 그렇게 하나")
BRANCHES = [
    (4, "분류가 목록 밖 라벨을 냈다", "classification_failed 를 남기고 escalated",
     "값을 비워 둔다. 추정으로 채우면 그 오류가 답변까지 간다", "red"),
    (5, "받는 팀이 둘이거나 없다", "routing_failed 를 남기고 escalated",
     "조용히 아무 팀이나 고르지 않는다", "red"),
    (7, "정책 검색이 실패했다", "degraded=true 와 omissions 를 붙여서 계속",
     "빈 결과를 조용히 쓰지 않는다. 팀이 그 신호를 보고 판단한다", "amber"),
    (8, "근거가 잘렸다 (degraded)", "degraded_context 로 escalated",
     "근거가 모자란 채로 확답을 만들지 않는다", "red"),
    (8, "반품 사유나 수량을 모른다", "waiting_input 으로 멈춤",
     "고객에게 물어보고 답이 오면 이어서 돈다", "amber"),
    (8, "이미 진행 중인 반품이 있다", "return_already_in_history 로 escalated",
     "중복 처리를 사람이 판단하게 넘긴다", "red"),
    (8, "반품 기간이 지났다 (기본 7일)", "return_period_expired 로 escalated",
     "예외를 코드가 정하지 않는다", "red"),
    (0, "돈이 나가는 제안이 나왔다", "waiting_approval 로 멈춤",
     "고위험 Action 은 사람이 승인해야 실행된다", "amber"),
    (0, "결제사 응답이 안 온다", "unknown 으로 남기고 자동 재실행 안 함",
     "돈이 나갔는지 모르는 상태를 모른다 고 적는다", "grey"),
]

#: 이 흐름이 실제로 남기는 표. (표 이름, 몇 행인지, 색, [칸], 한 줄 메모)
ARTIFACTS_HEAD = ("이 흐름이 실제로 만드는 것",
                  "앞 장들이 보여 준 JSON 은 HTTP 로 오가는 몸통이거나 메모리 위의 "
                  "객체다. 디스크에 파일로 떨어지지 않는다.")
ARTIFACTS_BANNER = ("이 흐름에서 새로 생기는 파일은 없다. 전부 데이터베이스 행이다. "
                    "파일이 생기는 곳은 따로 있고 다음 장에 적었다.")
ARTIFACTS = [
    ("customer_cases", "1행 · 지금 상태", "blue", [
        "case_id       uuid",
        "tenant_id     text",
        "customer_id   uuid",
        "status        case_status   resolved",
        "subject       text          고객 메시지",
        "state_json    jsonb         answer 가 여기 들어간다",
        "intent        text          return",
        "issue_code    text          return_fee_or_period",
        "sentiment     text          negative",
        "owner_team_id text          return_refund",
        "version       int           4",
        "created_at / updated_at     timestamptz",
    ], "이 표는 case_events 를 순서대로 적용한 결과다"),
    ("case_events", "4행 · 추가만 한다", "blue", [
        "event_id           uuid",
        "case_id            uuid",
        "aggregate_version  int    1 2 3 4",
        "event_type         text   created",
        "                          classified",
        "                          routed",
        "                          completed",
        "payload_json       jsonb",
        "actor_type         text   api",
        "actor_id           text   키 식별자",
        "UNIQUE(case_id, aggregate_version)",
    ], "UPDATE 도 DELETE 도 하지 않는다"),
    ("action_requests", "1행 · 멱등성 기록", "red", [
        "action_id        uuid",
        "case_id          uuid",
        "action_type      text   case.create",
        "arguments_json   jsonb",
        "idempotency_key  text   sha256 문자열",
        "status           action_status",
        "provider_ref     text",
        "UNIQUE(tenant_id, idempotency_key)",
    ], "이 UNIQUE 하나가 중복 처리를 막는다"),
    ("agent_runs", "1행 · 실행 기록", "green", [
        "run_id          uuid",
        "case_id         uuid",
        "graph_revision  text",
        "status          text",
        "attempt         int",
        "started_at / finished_at   timestamptz",
    ], ""),
    ("llm_calls", "분류에 쓴 호출", "green", [
        "call_id        uuid",
        "run_id         uuid",
        "prompt_id      uuid   prompts 표를 가리킨다",
        "provider / model      text",
        "input_tokens / output_tokens   int",
        "latency_ms / cost_microusd",
        "response_json  jsonb",
    ], "어느 프롬프트가 만든 답인지 되짚을 수 있다"),
]
ARTIFACTS_FOOT = ("team_tasks 와 outbox 와 action_approvals 는 이 케이스에서 안 쓴다. "
                  "승인이 필요한 제안이 없었고 발행할 메시지도 없었기 때문이다.")

#: 진짜 파일 이름. (묶음 제목, 색, [(파일, 무엇인지)])
FILENAMES_HEAD = ("그럼 파일은 어디서 생기나",
                  "실제로 있는 이름만 적었다. 이 케이스가 읽는 것과, 다른 경로에서 "
                  "쓰는 것을 나눴다.")
FILENAMES = [
    ("이 케이스가 읽는 파일", "blue", [
        ("config/project.yaml", "무슨 모듈과 Team 을 쓸지의 선언. 기동할 때 읽는다"),
        ("config/guardrails.yaml", "12,000 토큰 예산과 scope 10종. 수치의 단일 출처"),
        ("prompts/response/generate.v2.md", "응답 생성 프롬프트. DB prompts 표에 등록해 쓴다"),
        ("prompts/response/review_tone.v1.md", "톤 검토 프롬프트. 9번 단계가 꺼져 있어 이번엔 안 썼다"),
    ]),
    ("Composer 가 설정을 바꿀 때 쓰는 파일", "purple", [
        ("config/project.yaml", "최종 기록 자리. 통째로 다시 쓴다"),
        (".project.validate.<uuid>.yaml", "검증용 임시 파일. 검사 끝나면 지운다"),
        (".project.write.<uuid>.yaml", "쓰기용 임시 파일. 원자적 교체에 쓴다"),
        ("composer_events.jsonl", "누가 언제 무엇을 바꿨는지 한 줄에 하나"),
    ]),
    ("평가가 만드는 파일", "green", [
        ("eval/datasets/golden.jsonl", "문제집 60건. 보면서 고쳐도 된다"),
        ("eval/datasets/holdout.jsonl", "문제집 20건. 보고 고치면 안 된다"),
        ("eval/reports/2026-08-31_stage3_v6_review_comparison.jsonl",
         "실행 결과. 날짜와 조건이 이름에 박힌다"),
        ("docs/evidence/DoD-21_Graph_관계질의.md", "통과했다고 주장하는 근거"),
    ]),
]
FILENAMES_FOOT = ("고객 문의 한 건을 처리하는 동안 새로 생기는 파일은 하나도 없다. "
                  "파일은 설정을 바꿀 때와 평가를 돌릴 때 생긴다.")

#: "왜 그렇게 판단했나" 를 되짚는 세 가지 방법.
#: (번호, 제목, 색, 되나, [(무엇을 보나, 어떻게 확인하나)])
TRACEBACK_HEAD = ("왜 그렇게 판단했나를 되짚는 세 가지 방법",
                  "설계가 이렇게 되어 있다는 것을 직접 확인하는 자리다. "
                  "셋 중 둘은 실제로 되고, 하나는 지금 비어 있다.")
TRACEBACK = [
    (1, "운영 화면에서 눈으로 본다", "blue", True, [
        ("/ui/cases", "Case 목록. 상태와 담당 팀이 한눈에 나온다"),
        ("/ui/cases/<case_id>", "Evidence 카드. 각 주장이 무엇에 근거하는지 보여 준다"),
        ("/ui/cases/<case_id>/trace", "Trace 타임라인. 어느 단계를 언제 지났는지 순서대로"),
        ("근거가 잘린 Case", "화면 맨 위에 빨간 배너가 뜬다. 무엇이 빠졌는지 함께 적는다"),
        ("개인정보", "masked() 로 가리고 보여 준다. 원문 그대로는 화면에 안 뜬다"),
    ]),
    (2, "표 사이 연결을 따라간다", "green", True, [
        ("case_events.payload_json", "각 단계에서 실제로 무엇이 오갔는지가 들어 있다"),
        ("agent_runs.run_id", "실행 한 번을 묶는 번호. 어느 실행의 일인지 가른다"),
        ("llm_calls.prompt_id", "prompts 표를 가리킨다. 어느 프롬프트 어느 판이 만든 답인지"),
        ("llm_calls.response_json", "모델이 실제로 돌려준 원문"),
        ("controller.py 의 근거 세기", "ContextPack 쪽으로 센다. Team 이 근거와 제안을 "
                                  "둘 다 지어내 스스로를 증명하는 것을 막는다"),
    ]),
    (3, "API 응답을 본다  (지금은 비어 있다)", "red", False, [
        ("GET /v1/cases/<case_id>", "evidence 배열이 나오기는 한다"),
        ("claim", "created · classified · routed · completed. 지나온 단계 이름뿐"),
        ("value", "{} 로 비어 있다. 무엇을 근거로 판단했는지는 안 실린다"),
        ("내용은 어디 있나", "case_events.payload_json 에 저장은 돼 있다. "
                       "응답이 그것을 안 꺼내 쓸 뿐이다"),
        ("그래서", "API 만으로는 되짚을 수 없다. 1번이나 2번으로 해야 한다"),
    ]),
]
TRACEBACK_FOOT = ("셋 다 사람이 열어 보는 것이지만, 2번은 SQL 로 기계가 따라갈 수 있다. "
                  "3번을 채우면 바깥 시스템도 되짚을 수 있게 된다.")

# -*- coding: utf-8 -*-
"""열두 단계의 내용. 화면은 build_trace_html.py 가 만든다.

★코드는 손으로 옮겨 적지 않는다. `final_project_cs` 에서 줄 번호로 잘라 온다.
  옮겨 적으면 저장소가 바뀌었을 때 조용히 낡는다. 대신 줄이 밀리면 엉뚱한 코드가
  들어가므로, 자를 때 첫 줄이 기대한 문자열을 담고 있는지 확인한다.
  안 맞으면 생성이 그 자리에서 실패한다.

★코드마다 `plain` 을 붙인다. 코드를 처음 보는 사람이 읽을 풀이다.
  코드만 보여 주면 "그래서 이게 무슨 뜻인데" 에서 멈춘다.

★payload 는 "무슨 형식인지" 를 이름과 함께 적는다. HTTP 몸통인지 메모리 객체인지
  DB 행인지가 다르다. 형식을 안 적으면 "무슨 파일로 저장되나" 라는 오해가 생긴다.
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CS = os.path.join(REPO, "final_project_cs")


def cut(rel, start, end, expect):
    """rel 파일의 start~end 줄을 그대로 가져온다. 첫 줄에 expect 가 있어야 한다."""
    path = os.path.join(CS, rel)
    if not os.path.isfile(path):
        raise SystemExit("파일이 없다: %s" % rel)
    lines = io.open(path, encoding="utf-8").read().split("\n")
    chunk = lines[start - 1:end]
    if not chunk or expect not in chunk[0]:
        raise SystemExit("줄이 밀렸다: %s:%d 가 %r 를 담아야 하는데 %r 이다"
                         % (rel, start, expect, (chunk[0] if chunk else "")))
    body = [l for l in chunk if l.strip()]
    pad = min((len(l) - len(l.lstrip()) for l in body), default=0)
    return "\n".join(l[pad:] if len(l) >= pad else l for l in chunk).rstrip()


def code(rel, start, end, expect, plain):
    return {"path": "%s:%d" % (rel, start), "code": cut(rel, start, end, expect),
            "plain": plain}


STEPS = [
    dict(
        n=1, title="문 앞에서 신원 확인", owner="코어 2 · 정세환", color="red",
        why="API 키를 확인하고 case:write 권한이 있는지 본다. 통과해야 Principal 이 만들어지고, "
            "그 안의 tenant_id 가 이후 모든 조회 조건에 붙는다.",
        add=[("메모리 객체", "Principal", [
            'tenant_id = "demo"',
            'scopes    = {"case:write"}',
            'key_id    = "key-01"'])],
        code=[code("app/presentation/security.py", 47, 58, "def require_scope",
                   "문지기를 만들어 주는 함수입니다. 건물 입구마다 다른 출입증을 요구하듯, "
                   "경로마다 다른 권한을 요구할 수 있게 문지기를 찍어 냅니다.\n\n"
                   "첫 세 줄이 중요합니다. 서버가 켜질 때 <b>그런 권한이 설정에 등록돼 있는지부터</b> "
                   "봅니다. 오타로 없는 권한 이름을 적으면 그 자리에서 서버가 안 뜹니다. "
                   "요청이 들어온 뒤에 알아차리면 늦기 때문입니다.\n\n"
                   "안쪽 dependency 가 요청마다 도는 부분입니다. 손님의 출입증을 확인하고"
                   "(authenticate), 그 출입증에 이 문을 열 권한이 없으면 403 으로 돌려보냅니다. "
                   "통과하면 <b>누구인지를 담은 쪽지</b>(Principal)를 만들어 넘깁니다.")],
    ),
    dict(
        n=2, title="같은 요청이 아까 왔었나", owner="코어 2 · 정세환", color="red",
        why="네 가지를 재료로 지문을 만들고, 그 지문으로 이미 처리한 적이 있는지 먼저 찾는다. "
            "있으면 새로 만들지 않고 그때 만든 Case 를 그대로 돌려준다.",
        add=[("파이썬 문자열", "idempotency_key", [
            "sha256(tenant_id) + sha256(request_id)",
            "  + sha256(action_type) + sha256(subject)",
            "  를 이어 붙여 다시 sha256",
            'a3f1c9d2...  (64자)']),
             ("SQL 조회", "action_requests 조회", [
                 "SELECT case_id FROM action_requests",
                 " WHERE tenant_id=%s AND idempotency_key=%s",
                 "결과 없음. 새로 만든다"])],
        code=[code("app/core/idempotency.py", 8, 15, "def idempotency_key",
                   "같은 요청인지 알아보는 <b>지문</b>을 만듭니다.\n\n"
                   "sha256 은 어떤 글이든 넣으면 64자짜리 고정 길이 문자열을 내주는 계산입니다. "
                   "같은 글을 넣으면 언제나 같은 값이 나오고, 한 글자만 달라도 완전히 다른 값이 "
                   "나옵니다. 그래서 지문이라고 부릅니다.\n\n"
                   "재료가 넷입니다. 어느 고객사인지, 요청 번호가 무엇인지, 무슨 종류의 작업인지, "
                   "그리고 <b>실제 업무 대상</b>이 무엇인지입니다. 넷을 각각 지문으로 만든 뒤 "
                   "이어 붙여 다시 한 번 지문을 뜹니다.\n\n"
                   "요청 번호만 쓰지 않는 이유가 있습니다. 클라이언트가 요청 번호를 새로 매겨 "
                   "보내면 같은 환불이 두 번 나갑니다. 업무 대상까지 재료에 넣으면 그것도 "
                   "같은 지문이 되어 걸립니다.")],
    ),
    dict(
        n=3, title="Case 를 만들고 첫 이벤트를 남긴다", owner="코어 1 · 최연우", color="blue",
        why="행을 만들고 created 이벤트를 남긴다. 둘이 한 트랜잭션이다. "
            "전이표가 (new, created) 를 classifying 으로 정해 두어서, new 는 행을 만든 찰나에만 있다.",
        add=[("DB 행 생성", "customer_cases", [
            "status  = classifying",
            "version = 1",
            'subject = "어제 주문한 거 취소하고..."']),
             ("DB 행 생성", "case_events", [
                 "aggregate_version = 1",
                 "event_type        = created",
                 "actor_type        = api"])],
        state=("classifying", 1),
        code=[code("app/core/transition.py", 116, 136, "def transition_case",
                   "Case 의 상태를 바꾸는 <b>유일한 문</b>입니다. 이 프로젝트에서 상태를 "
                   "직접 고치는 코드는 없습니다. 전부 이 함수를 지납니다.\n\n"
                   "설명글에 적힌 세 가지가 핵심입니다.\n\n"
                   "<b>이 함수는 저장을 확정하지 않습니다.</b> 부르는 쪽이 트랜잭션을 열고 닫습니다. "
                   "트랜잭션은 여러 작업을 한 덩어리로 묶어서 <b>다 되거나 다 안 되게</b> 하는 "
                   "장치입니다. 상태는 바뀌었는데 기록이 안 남는 상황을 막습니다.\n\n"
                   "<b>expected_version 이 자물쇠입니다.</b> 내가 읽었을 때 버전이 3이었으면 3을 "
                   "같이 넘깁니다. 그 사이 다른 사람이 바꿔서 4가 됐으면 거부합니다. 두 사람이 "
                   "동시에 승인 버튼을 눌러도 나중 것이 앞 것을 조용히 덮어쓰지 않습니다.\n\n"
                   "<b>outbox 는 밖으로 보낼 메시지입니다.</b> 상태 변경과 같은 덩어리로 묶여서, "
                   "기록은 됐는데 알림이 안 나가는 일이 없습니다.")],
    ),
    dict(
        n=4, title="의도와 이슈와 감성을 한 번에 분류", owner="모델 · 송채영", color="green",
        why='"취소" 라고 썼지만 환불을 원하는 문의라 intent 가 return 으로 간다. '
            "이 한 단어가 어느 팀이 받을지를 정한다. 라벨 넷이 전부 정해진 목록 안에 있어야 통과한다.",
        add=[("DB 행 갱신", "customer_cases", [
            'intent     = "return"',
            'issue_code = "return_fee_or_period"',
            'sentiment  = "negative"',
            "status     = routing",
            "version    = 2"])],
        state=("routing", 2),
        code=[code("app/modules/customer_ops/feedback.py", 86, 105, "def classify",
                   "문의 한 줄을 읽고 라벨 네 개를 붙입니다. 무슨 의도인지, 무슨 이슈인지, "
                   "감정이 어떤지, 얼마나 급한지입니다.\n\n"
                   "이 함수는 거의 전부가 <b>검사</b>입니다. 실제로 분류하는 줄은 "
                   "<code>raw = provider(masked(text))</code> 한 줄이고, 나머지는 그 결과가 "
                   "쓸 만한지 따집니다.\n\n"
                   "<code>masked(text)</code> 를 먼저 지납니다. 전화번호나 주소 같은 개인정보를 "
                   "지운 뒤에야 AI 에게 넘긴다는 뜻입니다.\n\n"
                   "검사가 넷입니다. 글이 비었나, 결과가 객체 모양인가, 라벨 네 개가 다 있나, "
                   "그 값이 <b>미리 정한 목록 안에 있나</b>입니다. 하나라도 어긋나면 예외를 냅니다.\n\n"
                   "왜 이렇게까지 하냐면, AI 가 목록에 없는 말을 지어내면 그 값이 그대로 "
                   "데이터베이스에 들어가고 다음 단계가 팀을 못 찾기 때문입니다. "
                   "여기서 막지 않으면 한참 뒤에 이상한 곳에서 터집니다.")],
    ),
    dict(
        n=5, title="어느 팀 일인지 찾는다", owner="코어 1 · 최연우", color="blue",
        why="Registry 가 여섯 팀의 자기소개만 보고 고른다. 정확히 하나가 아니면 실패한다. "
            "조용히 아무 팀이나 고르지 않는다.",
        add=[("DB 행 갱신", "customer_cases", [
            'owner_team_id = "return_refund"',
            "status        = running",
            "version       = 3"])],
        state=("running", 3),
        code=[code("app/core/registry.py", 54, 79, "def resolve",
                   "여섯 팀 중 이 문의를 받을 팀 하나를 고릅니다.\n\n"
                   "고르는 방법이 중요합니다. 이 코드에는 <b>팀 이름이 하나도 안 적혀 있습니다.</b> "
                   "각 팀이 \"나는 이런 유형을 받는다\" 고 적어 둔 자기소개(manifest)만 보고 "
                   "거릅니다. 그래서 팀을 늘리거나 줄여도 이 코드는 안 바뀝니다.\n\n"
                   "두 단계로 거릅니다. 먼저 <b>받을 수 있는 유형</b>이 맞는 팀만 남기고, "
                   "그다음 intent 로 시작하는 기능을 가진 팀이 있으면 그쪽을 우선합니다.\n\n"
                   "마지막 두 줄이 이 함수의 성격입니다. 남은 팀이 <b>정확히 하나가 아니면 "
                   "예외를 냅니다.</b> 둘이 잡히거나 하나도 없으면 아무 팀이나 고르지 않고 "
                   "사람에게 넘깁니다. 잘못된 팀이 답하는 것보다 답을 늦추는 편이 낫기 때문입니다.")],
    ),
    dict(
        n=6, title="그 팀의 무슨 기능을 쓸지 고른다", owner="코어 1 · 최연우", color="blue",
        why="intent 와 같거나 intent 로 시작하는 첫 capability 에서 멈춘다. "
            "목록 순서가 곧 우선순위라 순서를 바꾸면 동작이 바뀐다.",
        add=[("메모리 값", "capability", [
            'capabilities = ["return.check_eligibility",',
            '                "return.request",',
            '                "refund.calculate"]',
            '고른 것 = "return.check_eligibility"'])],
        code=[code("app/core/registry.py", 82, 89, "def capability_for",
                   "팀은 정해졌고, 이제 그 팀의 어느 기능을 부를지 고릅니다.\n\n"
                   "규칙이 아주 단순합니다. 팀이 할 수 있는 일 목록을 <b>위에서부터 훑다가</b> "
                   "intent 와 같거나 intent 로 시작하는 것을 만나면 거기서 멈춥니다.\n\n"
                   "이 케이스에서는 intent 가 <code>return</code> 이고 목록 맨 위가 "
                   "<code>return.check_eligibility</code> 라 그것이 뽑힙니다.\n\n"
                   "알아 둘 것이 하나 있습니다. <b>목록 순서가 곧 우선순위입니다.</b> "
                   "설정 파일에서 순서를 바꾸면 다른 기능이 뽑힙니다. 규칙이 단순해서 예측이 "
                   "되는 대신, 순서를 함부로 바꾸면 안 됩니다.\n\n"
                   "마지막 줄은 아무것도 안 맞을 때입니다. 그때는 첫 번째 것을 씁니다.")],
    ),
    dict(
        n=7, title="근거를 모아 예산 안으로 자른다", owner="근거 조합", color="purple",
        why="12,000 토큰 예산에 맞춰 섹션별로 자른다. 잘라낼 수 없는 섹션이 넘치면 조용히 자르지 않고 "
            "예외를 낸다. 뺀 것은 omissions 에 이름으로 남긴다.",
        add=[("메모리 객체", "ContextPack", [
            "sections   정책 3,600 · 상태 2,400 ...",
            "evidence   [출처가 붙은 근거]",
            "degraded   false",
            "omissions  []"])],
        code=[code("app/core/context.py", 195, 211, "def build",
                   "AI 에게 넘길 근거를 모아 정해진 크기 안으로 줄입니다.\n\n"
                   "먼저 <b>토큰</b>이 무엇인지 알아야 합니다. AI 가 글을 세는 단위입니다. "
                   "한글은 대충 한 글자가 1~2 토큰입니다. 한 번에 넣을 수 있는 양에 한계가 있어서, "
                   "이 프로젝트는 12,000 토큰으로 정해 두었습니다.\n\n"
                   "이 함수의 순서가 핵심입니다. <b>잘라낼 수 없는 것부터 검사합니다.</b> "
                   "AI 에게 주는 지시문과 지금 Case 의 상태가 그것입니다. 이 둘이 예산을 넘으면 "
                   "조용히 자르지 않고 <b>예외를 냅니다.</b>\n\n"
                   "왜 그렇게 하냐면, Case 상태를 몰래 잘라 내면 AI 가 반쪽짜리 사실을 보고 "
                   "답하기 때문입니다. 그 답은 틀렸는데 틀린 줄 아무도 모릅니다. "
                   "차라리 그 자리에서 멈추고 \"프롬프트를 줄여야 한다\" 고 말하는 편이 낫습니다.\n\n"
                   "잘라도 되는 것은 그다음입니다. 뺀 것은 <code>omissions</code> 에 이름으로 "
                   "남겨서, 답변을 만들 때 \"근거가 모자란 상태였다\" 는 것을 알 수 있게 합니다."),
              code("config/guardrails.yaml", 13, 22, "context:",
                   "위 함수가 쓰는 <b>숫자가 적혀 있는 설정 파일</b>입니다.\n\n"
                   "숫자를 코드가 아니라 설정에 두는 이유가 있습니다. 같은 숫자가 코드 두 곳에 "
                   "있으면 한쪽만 고쳐집니다. 그러면 어느 쪽이 진짜인지 알 수 없게 됩니다. "
                   "이 프로젝트는 그런 상태를 <b>그 자체로 결함</b>이라고 봅니다.\n\n"
                   "전체 12,000 을 섹션별로 나눠 놨습니다. 정책 문서에 3,600, Case 상태에 2,400 "
                   "같은 식입니다. 주석에 <code>고정</code> 이라고 적힌 둘이 위에서 말한 "
                   "\"잘라낼 수 없는 것\" 입니다.")],
    ),
    dict(
        n=8, title="Team 이 판단한다", owner="모델 · 서유현", color="green",
        why="도구 셋으로 사실을 읽고 검사를 순서대로 한다. 하나라도 걸리면 거기서 멈춘다. "
            "환불이 맞다고 판단해도 실행하지 않는다. 제안만 돌려준다.",
        add=[("메모리 객체", "TeamResult", [
            'next_action = "respond"',
            "evidence    = [주문 · 반품이력 · 정책]",
            "proposals   = []   실행 제안 없음"])],
        code=[code("app/modules/customer_ops/return_refund.py", 79, 100, "async def execute",
                   "반품 담당 팀이 실제로 판단하는 부분입니다.\n\n"
                   "코드 모양을 먼저 보세요. <b>검사하고 문제가 있으면 곧바로 돌려보내는</b> "
                   "형태가 반복됩니다. 아래로 갈수록 조건이 다 통과한 상태가 됩니다.\n\n"
                   "첫 검사가 <code>task.context.degraded</code> 입니다. 7번 단계에서 근거가 "
                   "잘렸다는 신호입니다. 근거가 모자란 채로는 확답을 만들지 않고 사람에게 "
                   "넘깁니다(<code>ESCALATE</code>).\n\n"
                   "그다음 <code>self.tools.call</code> 로 사실을 읽습니다. 주문, 반품 이력, "
                   "정책 문서 셋입니다. 여기서 <code>task.allowed_tools</code> 를 같이 넘기는 "
                   "것이 중요합니다. <b>이 팀이 쓸 수 있다고 등록된 도구</b> 밖은 도구함이 "
                   "거부합니다. 팀이 마음대로 아무 데이터나 읽을 수 없습니다.\n\n"
                   "<code>seen</code> 은 같은 도구를 계속 부르는 무한 반복을 막는 장치입니다.\n\n"
                   "이 함수 어디에도 환불을 실제로 하는 코드가 없습니다. "
                   "<b>돌려주는 것은 판단과 제안뿐입니다.</b>")],
    ),
    dict(
        n=9, title="답변 문장을 만들고 톤을 검토한다", owner="모델 · 송채영", color="green",
        why="이 단계는 지금 꺼져 있다. config/project.yaml 의 response_review.enabled 가 false 라서 "
            "함수가 첫 조건에서 그대로 돌려준다. 고객이 받는 문장은 Team 이 코드에 적어 둔 고정 문구다.",
        add=[("설정 값", "config/project.yaml", [
            "response_review:",
            "  enabled: false",
            "  owner_team_id: response_generation_review",
            "검토를 건너뛴다"])],
        code=[code("app/application/controller.py", 179, 190, "async def _maybe_review",
                   "만든 답변을 다른 팀이 한 번 더 검토하는 단계입니다. 함수 이름의 "
                   "<code>maybe</code> 가 \"할 수도 있고 안 할 수도 있다\" 는 뜻입니다.\n\n"
                   "<b>지금은 안 합니다.</b> 네 번째 줄의 조건에서 걸립니다. "
                   "<code>config/project.yaml</code> 의 <code>response_review.enabled</code> 가 "
                   "<code>false</code> 라서, 함수가 아무것도 안 하고 받은 것을 그대로 돌려줍니다.\n\n"
                   "그래서 지금 고객이 받는 문장은 <b>팀이 코드에 적어 둔 고정 문구</b>입니다. "
                   "AI 가 매번 새로 쓴 문장이 아닙니다.\n\n"
                   "켜면 아래 코드가 돕니다. 검토할 팀을 찾고, 그 팀이 볼 수 있게 맥락을 다시 "
                   "포장하고, 새 작업으로 만들어 넘깁니다.\n\n"
                   "이 사실을 숨기지 않는 이유가 있습니다. 켜져 있다고 착각하면 문장 품질을 "
                   "잘못 평가하게 됩니다.")],
    ),
    dict(
        n=10, title="결과를 상태로 반영한다", owner="코어 1 · 최연우", color="blue",
        why="respond 이므로 completed 이벤트를 남기고 종결한다. 상태와 이벤트가 같은 트랜잭션이라 "
            "답은 나갔는데 기록이 없는 상황이 안 생긴다.",
        add=[("DB 행 갱신", "customer_cases", [
            "status     = resolved",
            "version    = 4",
            "state_json = { answer: ... }"]),
             ("DB 행 생성", "case_events", [
                 "aggregate_version = 4",
                 "event_type        = completed"])],
        state=("resolved", 4),
        code=[code("app/application/controller.py", 173, 178, "def _apply_result",
                   "팀이 돌려준 결과를 Case 상태에 반영합니다. 짧지만 이 프로젝트의 규칙이 "
                   "다 들어 있습니다.\n\n"
                   "첫 줄에서 <code>_event_for_result</code> 를 부릅니다. 팀이 "
                   "\"답하겠다\" 고 했는지 \"사람에게 넘기겠다\" 고 했는지에 따라 남길 이벤트가 "
                   "달라지는데, 그 판단을 여기서 합니다.\n\n"
                   "그다음 <b>3번 단계에서 봤던 그 함수</b>를 다시 부릅니다. 상태를 바꾸는 문이 "
                   "하나뿐이라는 규칙이 여기서도 지켜집니다.\n\n"
                   "<code>expected_version=case[\"version\"]</code> 를 넘기는 것을 보세요. "
                   "팀이 도는 동안 누가 이 Case 를 건드렸으면 여기서 거부됩니다.\n\n"
                   "<code>actor_type=\"controller\"</code> 는 \"누가 이 변경을 했는가\" 를 "
                   "남기는 것입니다. 나중에 기록을 보면 사람이 한 것인지 시스템이 한 것인지 "
                   "구별됩니다.")],
    ),
    dict(
        n=11, title="고객이 답을 받는다", owner="코어 2 · 정세환", color="red",
        why="상태와 답변과 근거를 함께 내보낸다. 근거를 빼고 답만 주지 않는다. "
            "왜 그렇게 판단했는지 되짚을 수 있어야 하기 때문이다.",
        add=[("HTTP 응답 몸통 (JSON)", "GET /v1/cases/{case_id}", [
            '{ "case_id": "...", "status": "resolved",',
            '  "version": 4, "intent": "return",',
            '  "issue_code": "return_fee_or_period",',
            '  "sentiment": "negative",',
            '  "links": { "self": "/v1/cases/..." },',
            '  "answer": "...검토할 수 있습니다.",',
            '  "pending_actions": [],',
            '  "evidence": [ { "source_type": "case_event",',
            '      "source_id": "...", "claim": "created",',
            '      "value": {}, "observed_at": "..." } ] }'])],
        code=[code("app/presentation/api/cases.py", 117, 123, "@router.get",
                   "고객이 자기 Case 를 조회하는 경로입니다. 여기서 나가는 것이 "
                   "<b>고객이 실제로 받는 JSON</b> 입니다. 파일이 아니라 통신 내용입니다.\n\n"
                   "<code>_case_or_404</code> 가 본인 Case 인지 확인합니다. 남의 것이면 "
                   "\"권한이 없다\" 가 아니라 <b>\"없다\"(404)</b> 고 답합니다. "
                   "\"권한이 없다\" 고 하면 그 번호의 Case 가 존재한다는 사실이 새어 나갑니다.\n\n"
                   "마지막 두 줄이 이 프로젝트의 원칙입니다. 답변만 주지 않고 "
                   "<b>근거를 같이 내보냅니다.</b> 이 Case 에 일어난 사건들을 근거 목록으로 "
                   "만들어 붙입니다. 어디서 온 정보인지(source_type), 그 근거의 식별자가 "
                   "무엇인지(source_id), 언제 본 것인지(observed_at)가 함께 갑니다.\n\n"
                   "왜 그렇게 하냐면, 나중에 \"왜 이렇게 답했냐\" 는 질문에 답할 수 있어야 "
                   "하기 때문입니다."),
              code("app/presentation/api/cases.py", 61, 64, "def _view",
                   "Case 한 건을 밖에 내보낼 모양으로 바꾸는 함수입니다.\n\n"
                   "<b>데이터베이스에 있는 것을 전부 내보내지 않습니다.</b> 여기 적힌 필드만 "
                   "나갑니다. 내부에서만 쓰는 값이 실수로 새어 나가는 것을 막습니다.\n\n"
                   "<code>str(case[\"case_id\"])</code> 처럼 문자열로 바꾸는 것은, 자릿수가 큰 "
                   "식별자를 숫자로 두면 받는 쪽에서 자릿수가 잘리기 때문입니다.\n\n"
                   "<code>links</code> 는 \"이 Case 를 다시 보려면 어디로 오면 되는지\" 를 "
                   "알려 주는 주소입니다.")],
    ),
    dict(
        n=12, title="기록이 남는다", owner="공통", color="grey",
        why="다섯 표에 흔적이 남는다. case_events 는 고치지 않고 추가만 하므로, "
            "나중에 이벤트만 재생하면 그때 무슨 일이 있었는지 그대로 되짚을 수 있다.",
        add=[("최종 DB 상태", "남은 행", [
            "customer_cases   1행  resolved v4",
            "case_events      4행  created, classified,",
            "                      routed, completed",
            "action_requests  1행  succeeded",
            "agent_runs       1행  시작과 종료",
            "llm_calls        분류에 쓴 프롬프트와 모델"])],
        code=[code("app/infrastructure/db/migrations/001_schema.sql", 13, 14,
                   "CREATE TABLE IF NOT EXISTS customer_cases",
                   "데이터가 실제로 저장되는 <b>표의 설계도</b>입니다. 두 줄이지만 이 흐름의 "
                   "결론이 여기 있습니다.\n\n"
                   "첫 줄 <code>customer_cases</code> 가 <b>지금 상태</b>입니다. status, "
                   "intent, version 같은 것이 여기 한 행으로 들어갑니다. 계속 갱신됩니다.\n\n"
                   "둘째 줄 <code>case_events</code> 가 <b>무슨 일이 있었나</b>입니다. "
                   "맨 끝의 <code>UNIQUE(case_id, aggregate_version)</code> 를 보세요. "
                   "같은 Case 에 같은 번호의 사건이 두 번 들어갈 수 없다는 뜻입니다. "
                   "순서가 어긋나거나 중복되는 것을 데이터베이스가 막습니다.\n\n"
                   "이 표는 <b>추가만 하고 고치지 않습니다.</b> 그래서 나중에 이벤트를 순서대로 "
                   "다시 적용하면 그때 상태를 그대로 되살릴 수 있습니다. 위의 "
                   "<code>customer_cases</code> 는 사실 그 결과를 미리 계산해 둔 것뿐입니다.\n\n"
                   "<code>jsonb</code> 는 자유로운 모양의 데이터를 담는 칸이고, "
                   "<code>timestamptz</code> 는 시간대까지 함께 저장하는 시각입니다.")],
    ),
]

FILES_NOTE = [
    ("이 흐름이 만드는 파일",
     "없습니다. 전부 데이터베이스 행입니다. 위에 보이는 JSON 은 HTTP 로 오가는 몸통이고 "
     "디스크에 파일로 떨어지지 않습니다."),
    ("이 흐름이 읽는 파일",
     "config/project.yaml · config/guardrails.yaml · prompts/response/generate.v2.md · "
     "prompts/response/review_tone.v1.md"),
    ("파일이 생기는 다른 경로",
     "Composer 가 설정을 바꿀 때 config/project.yaml 과 .project.write.&lt;uuid&gt;.yaml 과 "
     "composer_events.jsonl · 평가를 돌릴 때 eval/reports/&lt;날짜&gt;_&lt;조건&gt;.jsonl"),
]

# -*- coding: utf-8 -*-
"""취소·환불 한 건이 지나는 길을 브라우저에서 돌려 보는 시뮬레이터를 만든다.

    python program/onboarding/build_trace_sim.py

★코드는 손으로 옮겨 적지 않는다. `final_project_cs` 에서 줄 번호로 잘라 온다.
  옮겨 적으면 저장소가 바뀌었을 때 조용히 낡는다. 여기서 자르면 줄이 밀렸을 때
  엉뚱한 코드가 들어가는데, 그걸 막으려고 자를 때 첫 줄이 기대한 문자열로
  시작하는지 확인한다. 안 맞으면 생성이 실패한다.

★페이로드는 "무슨 형식인지" 를 이름과 함께 적는다. HTTP 몸통인지 파이썬 객체인지
  DB 행인지 SQL 인지가 다르다. 앞서 만든 그림이 이걸 뭉개서 "그럼 무슨 파일로
  저장되나" 라는 오해를 만들었다.
"""
import html
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CS = os.path.join(REPO, "final_project_cs")
OUT = os.path.join(HERE, "취소환불_케이스_시뮬레이터.html")


def slice_code(rel, start, end, expect):
    """rel 파일의 start~end 줄을 그대로 가져온다. 첫 줄이 expect 로 시작해야 한다."""
    path = os.path.join(CS, rel)
    if not os.path.isfile(path):
        raise SystemExit("파일이 없다: %s" % rel)
    lines = io.open(path, encoding="utf-8").read().split("\n")
    chunk = lines[start - 1:end]
    if not chunk or expect not in chunk[0]:
        raise SystemExit(
            "줄이 밀렸다: %s:%d 가 %r 로 시작해야 하는데 %r 이다"
            % (rel, start, expect, (chunk[0] if chunk else "")))
    # 공통 들여쓰기를 걷어낸다. 그대로 두면 화면 왼쪽이 비어 보인다.
    body = [l for l in chunk if l.strip()]
    pad = min((len(l) - len(l.lstrip()) for l in body), default=0)
    return "\n".join(l[pad:] if len(l) >= pad else l for l in chunk).rstrip()


#: 열두 단계. payload 는 (형식, 이름, [줄...]) 이고 code 는 저장소에서 잘라 온다.
STEPS = [
    dict(
        n=1, title="문 앞에서 신원 확인", owner="코어 2 · 정세환", color="red",
        why="API 키를 확인하고 case:write 권한이 있는지 본다. 통과해야 Principal 이 만들어지고, "
            "그 안의 tenant_id 가 이후 모든 조회 조건에 붙는다.",
        add=[("메모리 객체", "Principal", [
            'tenant_id = "demo"',
            'scopes    = {"case:write"}',
            'key_id    = "key-01"'])],
        code=[("app/presentation/security.py:47", "python",
               slice_code("app/presentation/security.py", 47, 58, "def require_scope"))],
    ),
    dict(
        n=2, title="같은 요청이 아까 왔었나", owner="코어 2 · 정세환", color="red",
        why="네 가지를 재료로 해시를 만들고, 그 키로 이미 처리한 적이 있는지 먼저 찾는다. "
            "있으면 새로 만들지 않고 그때 만든 Case 를 그대로 돌려준다.",
        add=[("파이썬 문자열", "idempotency_key", [
            "sha256(tenant_id) + sha256(request_id)",
            "  + sha256(action_type) + sha256(subject)",
            "  를 다시 sha256 한 값",
            'a3f1c9d2...  (64자)']),
             ("SQL 조회", "action_requests", [
                 "SELECT case_id FROM action_requests",
                 " WHERE tenant_id=%s AND idempotency_key=%s",
                 "결과 없음 → 새로 만든다"])],
        code=[("app/core/idempotency.py:8", "python",
               slice_code("app/core/idempotency.py", 8, 15, "def idempotency_key"))],
    ),
    dict(
        n=3, title="Case 를 만들고 첫 이벤트를 남긴다", owner="코어 1 · 최연우", color="blue",
        why="행을 만들고 created 이벤트를 남긴다. 둘이 한 트랜잭션이다. "
            "전이표가 (new, created) 를 classifying 으로 정해 두어서, new 는 행을 만든 찰나에만 있다.",
        add=[("DB 행", "customer_cases", [
            "status  = classifying",
            "version = 1",
            'subject = "어제 주문한 거 취소하고..."']),
             ("DB 행", "case_events", [
                 "aggregate_version = 1",
                 "event_type        = created",
                 "actor_type        = api"])],
        state=("classifying", 1),
        code=[("app/core/transition.py:116", "python",
               slice_code("app/core/transition.py", 116, 127, "def transition_case"))],
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
        code=[("app/modules/customer_ops/feedback.py:86", "python",
               slice_code("app/modules/customer_ops/feedback.py", 86, 105, "def classify"))],
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
        code=[("app/core/registry.py:54", "python",
               slice_code("app/core/registry.py", 54, 79, "def resolve"))],
    ),
    dict(
        n=6, title="그 팀의 무슨 기능을 쓸지 고른다", owner="코어 1 · 최연우", color="blue",
        why="intent 와 같거나 intent 로 시작하는 첫 capability 에서 멈춘다. "
            "목록 순서가 곧 우선순위라 순서를 바꾸면 동작이 바뀐다.",
        add=[("메모리 값", "capability", [
            'capabilities = ["return.check_eligibility",',
            '                "return.request",',
            '                "refund.calculate"]',
            '선택 = "return.check_eligibility"'])],
        code=[("app/core/registry.py:82", "python",
               slice_code("app/core/registry.py", 82, 89, "def capability_for"))],
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
        code=[("app/core/context.py:195", "python",
               slice_code("app/core/context.py", 195, 211, "def build")),
              ("config/guardrails.yaml", "yaml",
               slice_code("config/guardrails.yaml", 13, 22, "context:"))],
    ),
    dict(
        n=8, title="Team 이 판단한다", owner="모델 · 서유현", color="green",
        why="도구 셋으로 사실을 읽고 다섯 가지를 순서대로 검사한다. 하나라도 걸리면 거기서 멈춘다. "
            "환불이 맞다고 판단해도 실행하지 않는다. 제안만 돌려준다.",
        add=[("메모리 객체", "TeamResult", [
            'next_action = "respond"',
            "evidence    = [주문 · 반품이력 · 정책]",
            "proposals   = []   실행 제안 없음"])],
        code=[("app/modules/customer_ops/return_refund.py:79", "python",
               slice_code("app/modules/customer_ops/return_refund.py", 79, 100, "async def execute"))],
    ),
    dict(
        n=9, title="답변 문장을 만들고 톤을 검토한다", owner="모델 · 송채영", color="green",
        why="이 단계는 지금 꺼져 있다. config/project.yaml 의 response_review.enabled 가 false 라서 "
            "함수가 첫 줄에서 그대로 돌려준다. 고객이 받는 문장은 Team 이 코드에 적어 둔 고정 문구다.",
        add=[("설정 값", "config/project.yaml", [
            "response_review:",
            "  enabled: false",
            "  owner_team_id: response_generation_review",
            "→ 검토를 건너뛴다"])],
        code=[("app/application/controller.py:179", "python",
               slice_code("app/application/controller.py", 179, 190, "async def _maybe_review"))],
    ),
    dict(
        n=10, title="결과를 상태로 반영한다", owner="코어 1 · 최연우", color="blue",
        why="respond 이므로 completed 이벤트를 남기고 종결한다. 상태와 이벤트가 같은 트랜잭션이라 "
            "답은 나갔는데 기록이 없는 상황이 안 생긴다.",
        add=[("DB 행 갱신", "customer_cases", [
            "status     = resolved",
            "version    = 4",
            "state_json = { answer: ... }"]),
             ("DB 행", "case_events", [
                 "aggregate_version = 4",
                 "event_type        = completed"])],
        state=("resolved", 4),
        code=[("app/application/controller.py:173", "python",
               slice_code("app/application/controller.py", 173, 178, "def _apply_result"))],
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
        code=[("app/presentation/api/cases.py:117", "python",
               slice_code("app/presentation/api/cases.py", 117, 123, "@router.get")),
              ("app/presentation/api/cases.py:61", "python",
               slice_code("app/presentation/api/cases.py", 61, 64, "def _view"))],
    ),
    dict(
        n=12, title="기록이 남는다", owner="공통", color="grey",
        why="다섯 표에 흔적이 남는다. case_events 는 고치지 않고 추가만 하므로, "
            "나중에 이벤트만 재생하면 그때 무슨 일이 있었는지 그대로 되짚을 수 있다.",
        add=[("최종 DB 상태", "남은 행", [
            "customer_cases   1행  resolved v4",
            "case_events      4행  created → classified",
            "                      → routed → completed",
            "action_requests  1행  succeeded",
            "agent_runs       1행  시작과 종료",
            "llm_calls        분류에 쓴 프롬프트와 모델"])],
        code=[("app/infrastructure/db/migrations/001_schema.sql:13", "sql",
               slice_code("app/infrastructure/db/migrations/001_schema.sql", 13, 14,
                          "CREATE TABLE IF NOT EXISTS customer_cases"))],
    ),
]

FILES_NOTE = [
    ("이 흐름이 만드는 파일", "없다. 전부 데이터베이스 행이다. "
     "위에 보이는 JSON 은 HTTP 로 오가는 몸통이고 파일로 저장되지 않는다."),
    ("이 흐름이 읽는 파일", "config/project.yaml · config/guardrails.yaml · "
     "prompts/response/generate.v2.md · prompts/response/review_tone.v1.md"),
    ("파일이 생기는 다른 경로", "Composer 가 설정을 바꿀 때 config/project.yaml 과 "
     ".project.write.&lt;uuid&gt;.yaml 과 composer_events.jsonl · "
     "평가를 돌릴 때 eval/reports/&lt;날짜&gt;_&lt;조건&gt;.jsonl"),
]


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    from sim_page import build

    build(STEPS, FILES_NOTE, OUT)

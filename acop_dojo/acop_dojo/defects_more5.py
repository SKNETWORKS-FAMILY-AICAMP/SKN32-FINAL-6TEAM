"""추가 결함 5 — 원장에 있는데 세는 곳이 없던 규칙 9개.

`CLAUDE.md` 가 가장 앞에 내세우는 규칙들인데 깨져도 아무 테스트가 울지 않았다.
결함을 만들어 게이트에 걸어야 어디를 메워야 하는지가 드러난다.
"""
from __future__ import annotations

from .defects import Defect

MORE5: list[Defect] = [
    Defect(
        defect_id="INV-TEAM-004",
        title="승인 필요 제안을 첫 건만 보고 넘긴다",
        invariant="Team 은 승인 없이 실행하지 않는다 — 승인 필요 제안이 있으면 wait_for_approval 이어야 한다",
        path="app/core/contracts.py",
        old="        if any(p.approval_required for p in self.action_proposals):",
        new="        if self.action_proposals and self.action_proposals[0].approval_required:",
        lesson=(
            "제안이 여러 건일 때 첫 건만 본다. 앞에 승인 불필요 제안을 두고 뒤에 환불을 붙이면 "
            "완료로 처리돼 승인 없이 나간다. any 를 첫 원소 검사로 바꾸는 것은 흔한 '최적화' 다."
        ),
        counterfactuals=["제안은 보통 한 건이다", "승인 화면에서 다시 본다"],
        difficulty=3,
    ),
    Defect(
        defect_id="INV-MCP-001",
        title="MCP 도구 하나가 쓰기 scope 를 요구한다",
        invariant="MCP 는 read-only 다 — 결제·환불·구독 변경을 하지 않는다",
        path="app/presentation/api/mcp.py",
        old='@mcp.tool(meta={"required_scope": "mcp:read"})\ndef open_support_case(',
        new='@mcp.tool(meta={"required_scope": "case:write"})\ndef open_support_case(',
        lesson=(
            "개인 AI 가 붙는 표면은 읽기 전용이어야 한다. 쓰기 scope 를 요구하기 시작하면 "
            "그 경로로 쓰기가 가능해진다는 뜻이고, 승인 경로를 우회하는 문이 열린다."
        ),
        counterfactuals=["Case 를 만드는 건 쓰기니까 맞다", "scope 이름은 표시일 뿐이다"],
    ),
    Defect(
        defect_id="INV-AUTH-002",
        title="승인 엔드포인트가 읽기 권한으로 열린다",
        invariant="승인자는 action:approve scope 가 있어야 한다",
        path="app/presentation/api/cases.py",
        old='require_scope("action:approve")',
        new='require_scope("case:read")',
        lesson=(
            "고위험 Action 의 승인이 읽기 권한으로 가능해진다. 환불과 구독 변경은 되돌릴 수 "
            "없으므로 이 문이 가장 좁아야 한다."
        ),
        counterfactuals=["인증만 됐으면 승인해도 된다", "화면에서 버튼을 숨기면 된다"],
    ),
    Defect(
        defect_id="INV-UNKNOWN-001",
        title="provider 실패를 성공으로 기록한다",
        invariant="provider timeout 을 성공으로 추정하지 않는다 — unknown 으로 남긴다",
        path="app/infrastructure/messaging/worker.py",
        old="UPDATE outbox SET status='unknown',last_error=%s",
        new="UPDATE outbox SET status='sent',last_error=%s",
        lesson=(
            "결제 provider 가 응답하지 않은 것과 성공한 것은 다르다. 성공으로 기록하면 "
            "사람이 확인해야 할 건이 조용히 사라지고, 이중 청구나 미청구를 나중에야 안다."
        ),
        counterfactuals=["재시도했으니 됐을 것이다", "실패면 예외가 났을 것이다"],
    ),
    Defect(
        defect_id="INV-STATE-005",
        title="이벤트를 역순으로 재생한다",
        invariant="case_events 는 append-only 이고 순서가 곧 상태다",
        path="app/core/transition.py",
        old="    ORDER BY aggregate_version",
        new="    ORDER BY aggregate_version DESC",
        lesson=(
            "상태는 이벤트를 순서대로 접은 결과다. 순서가 뒤집히면 재생 결과가 현재 상태와 "
            "달라진다. append-only 가 지켜져도 순서를 잃으면 같은 것을 잃는다."
        ),
        counterfactuals=["어느 순서든 같은 이벤트면 같다", "현재 상태는 따로 저장돼 있다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-STATE-006",
        title="checkpoint 가 업무 상태를 들고 다닌다",
        invariant="checkpoint 는 실행 snapshot 이다 — 권위 있는 projection 은 customer_cases 다",
        path="app/application/case_service.py",
        old='"node_name": node_name, "runtime_state": dict(runtime_state or {})}',
        new='"node_name": node_name, "runtime_state": dict(runtime_state or {}, status="running")}',
        lesson=(
            "checkpoint 에 업무 상태를 넣기 시작하면 어느 쪽이 진짜인지 모르게 된다. "
            "checkpoint 는 버려도 되는 실행 스냅샷이어야 한다."
        ),
        counterfactuals=["상태를 같이 들고 다니면 편하다", "재개할 때 필요하다"],
        difficulty=3,
    ),
    Defect(
        defect_id="INV-CLASS-002",
        title="일부만 분류돼도 성공으로 친다",
        invariant="분류 실패는 조용히 넘기지 않는다 — classification_failed 를 남기고 escalated 로 간다",
        path="app/presentation/api/cases.py",
        old='if not result or not all(k in result for k in ("intent", "issue_code", "sentiment")):',
        new="if not result:",
        lesson=(
            "intent 만 오고 issue_code 가 빠진 응답이 성공으로 처리된다. 빈 라벨이 Case 에 "
            "저장되고 그 라벨로 라우팅까지 간다. 분류 실패는 escalated 로 가야 할 일이다."
        ),
        counterfactuals=["일부라도 있으면 쓸 만하다", "나중에 다시 분류하면 된다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-VERSION-001",
        title="checkpoint 의 graph_revision 이 하드코딩됐다",
        invariant="산출물에 버전을 박는다 — 같은 입력이라도 버전이 다르면 결과가 다르다",
        path="app/application/case_service.py",
        old='return {"case_id": str(case_id), "run_id": str(run_id), "graph_revision": self.graph_revision,',
        new='return {"case_id": str(case_id), "run_id": str(run_id), "graph_revision": "controller-v1",',
        lesson=(
            "실행마다 다를 수 있는 값을 고정 문자열로 박으면, 나중에 어느 버전이 만든 "
            "산출물인지 되짚을 수 없다. 가드레일 수치와 같은 이유로 한 곳에서만 온다."
        ),
        counterfactuals=["지금은 하나뿐이라 상관없다", "로그에 남으니 괜찮다"],
    ),
    Defect(
        defect_id="INV-STATE-007",
        title="SQL 쪽 버전 조건이 사라졌다",
        invariant="상태 변경은 읽은 시점의 version 과 정확히 맞아야 한다 (SQL 쪽 방어)",
        path="app/core/transition.py",
        old="      AND version = %(expected_version)s",
        new="      AND version = version",
        lesson=(
            "낙관적 동시성은 파이썬과 SQL 두 겹으로 지킨다. SQL 쪽을 풀면 파이썬 검사를 "
            "지나온 두 실행이 모두 UPDATE 에 성공해 나중 것이 먼저 것을 덮어쓴다."
        ),
        counterfactuals=["파이썬에서 이미 봤다", "트랜잭션이 알아서 막는다"],
        difficulty=3,
    ),
]

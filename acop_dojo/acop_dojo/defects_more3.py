"""추가 결함 3 — 계약 모델과 도메인 리듀서.

이 자리를 고른 이유는 실측이다. 21개 후보를 돌려 보니 계약 모델·도메인·검증·Team
모듈에 심은 결함은 테스트가 잡고, 권한·구성·outbox 에 심은 것은 잡지 못했다.
학습 문제는 잡히는 곳에서 만들고, 안 잡히는 곳은 테스트 사각지대로 따로 기록한다.
"""
from __future__ import annotations

from .defects import Defect

MORE3: list[Defect] = [
    Defect(
        defect_id="INV-EVIDENCE-001",
        title="근거 없는 확정 답변이 통과한다",
        invariant="answer 가 있으면 evidence 가 있어야 한다 — 근거 없는 확정 답변은 만들지 않는다",
        path="app/core/contracts.py",
        old="        if self.answer and not self.evidence:",
        new="        if self.answer and self.evidence is None:",
        lesson=(
            "evidence 는 기본값이 빈 리스트라 None 이 되지 않는다. 조건이 영영 참이 되지 않아 "
            "검사가 사라진다. 이 서비스에서 가장 무거운 규칙이 소리 없이 꺼진다."
        ),
        counterfactuals=["LLM 이 근거를 알아서 붙인다", "빈 리스트도 근거가 없다는 뜻이니 같다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-APPROVAL-001",
        title="승인 대기인데 제안이 하나도 없어도 통과한다",
        invariant="wait_for_approval 은 action_proposals 가 최소 1건 있어야 한다",
        path="app/core/contracts.py",
        old="            if not self.action_proposals:",
        new="            if self.action_proposals is None:",
        lesson=(
            "무엇을 승인하라는지 없는 승인 대기가 만들어진다. 승인자는 판단할 대상이 없는 "
            "화면을 보게 되고, 그걸 승인하면 아무 일도 일어나지 않는다."
        ),
        counterfactuals=["제안은 나중에 붙이면 된다", "승인 화면에서 다시 확인한다"],
    ),
    Defect(
        defect_id="INV-RESPOND-001",
        title="빈 답변으로 응답이 완료된다",
        invariant="respond 는 answer 가 있어야 한다",
        path="app/core/contracts.py",
        old="            if not self.answer:",
        new="            if self.answer is None:",
        lesson=(
            "빈 문자열은 None 이 아니다. 답변 없는 응답이 정상 종료로 기록되고 "
            "고객에게는 아무것도 가지 않는다."
        ),
        counterfactuals=["빈 문자열도 답변이다", "상위에서 빈 값을 거른다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-ESCALATE-001",
        title="사유 없는 에스컬레이션이 통과한다",
        invariant="escalate 는 failure_code 또는 warnings 가 있어야 한다",
        path="app/core/contracts.py",
        old="            if not self.failure_code and not self.warnings:",
        new="            if self.failure_code is None and self.warnings is None:",
        lesson=(
            "warnings 는 기본값이 빈 리스트라 None 이 되지 않는다. 왜 사람에게 넘겼는지 "
            "적히지 않은 채로 넘어가고, 받은 사람은 처음부터 다시 조사해야 한다."
        ),
        counterfactuals=["에스컬레이션 자체가 신호다", "사유는 로그를 보면 된다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-MERGE-001",
        title="상태 병합이 덮어쓰기가 됐다",
        invariant="state_json 은 덮어쓰기가 아니라 병합이다 — 이전 근거를 지우지 않는다",
        path="app/domain/case.py",
        old="    state = dict(current.state_json)",
        new="    state = {}",
        lesson=(
            "이벤트를 적용할 때마다 이전 상태가 통째로 사라진다. 상태는 이벤트를 접은 결과라서 "
            "이 한 줄이 앞선 모든 근거를 지운다."
        ),
        counterfactuals=["필요한 값은 payload 에 다시 담으면 된다", "이벤트 로그에 남으니 괜찮다"],
    ),
    Defect(
        defect_id="INV-EVIDENCE-002",
        title="근거 id 대조 방향이 뒤집혔다",
        invariant="든 근거는 ContextPack 에 실재하는 것이어야 한다",
        path="app/core/verification.py",
        old="    for evidence_id in sorted(set(rationale_evidence_ids) - facts.evidence_ids):",
        new="    for evidence_id in sorted(facts.evidence_ids - set(rationale_evidence_ids)):",
        lesson=(
            "방향이 뒤집히면 '없는 근거를 들었다' 대신 '안 쓴 근거가 있다'를 잡는다. "
            "지어낸 근거가 그대로 통과하고, 멀쩡한 제안이 대신 걸린다."
        ),
        counterfactuals=["차집합은 어느 쪽이든 같다", "근거 id 는 형식만 맞으면 된다"],
        difficulty=3,
    ),
    Defect(
        defect_id="INV-PII-004",
        title="마스킹이 잎 노드에서 아무 일도 하지 않는다",
        invariant="PII 는 저장 시 마스킹한다",
        path="app/core/redaction.py",
        old="    return masked(value) if isinstance(value, str) else value",
        new="    return value",
        lesson=(
            "구조는 다 훑지만 정작 문자열에 아무 규칙도 적용하지 않는다. 재귀는 도는데 "
            "결과가 원문 그대로다."
        ),
        counterfactuals=["상위에서 이미 마스킹했다", "구조를 훑었으면 된 것이다"],
    ),
    Defect(
        defect_id="INV-WAITINPUT-001",
        title="입력 대기의 사유가 아무 값이나 통과한다",
        invariant="wait_for_input 은 wait_reason 이 customer_input 이어야 한다",
        path="app/core/contracts.py",
        old='            if self.wait_reason != "customer_input":',
        new="            if self.wait_reason is None:",
        lesson=(
            "대기 사유는 재개 경로를 고르는 데 쓰인다. 아무 문자열이나 통과하면 "
            "재개할 때 어디로 돌아가야 하는지 정할 수 없다."
        ),
        counterfactuals=["사유는 사람이 읽는 설명일 뿐이다", "값이 있으면 된 것이다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-HANDOFF-001",
        title="넘길 곳 없는 인계가 통과한다",
        invariant="handoff 는 handoff_capability 가 있어야 한다",
        path="app/core/contracts.py",
        old="            if not self.handoff_capability:",
        new="            if self.handoff_capability is None:",
        lesson=(
            "빈 문자열은 None 이 아니다. 어디로 넘기라는지 없는 인계가 만들어지고 "
            "Registry 는 빈 capability 로 담당 Team 을 찾지 못한다."
        ),
        counterfactuals=["Controller 가 알아서 다시 라우팅한다", "빈 값이면 기본 팀으로 간다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-CLASSIFY-001",
        title="분류 라벨 검사가 or 에서 and 로 바뀌었다",
        invariant="분류가 실패하면 조용히 넘기지 않는다 — 잘못된 라벨은 거부한다",
        path="app/modules/customer_ops/feedback.py",
        old="    if result.intent not in INTENTS or result.sentiment not in SENTIMENTS:",
        new="    if result.intent not in INTENTS and result.sentiment not in SENTIMENTS:",
        lesson=(
            "둘 다 틀렸을 때만 막는다. 하나만 틀린 출력은 통과해 Case 에 저장되고, "
            "그 라벨로 라우팅까지 간다. 분류 실패는 조용히 넘기면 안 되는 것이었다."
        ),
        counterfactuals=["둘 중 하나만 맞아도 쓸 만하다", "뒤에서 다시 검사한다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-QUANTITY-001",
        title="수량 대조가 값이 있을 때 건너뛴다",
        invariant="수량이 참조 대상의 상한을 넘지 않는지 본다",
        path="app/core/verification.py",
        old="        if rule.field not in arguments or arguments[rule.field] is None:",
        new="        if rule.field not in arguments or arguments[rule.field] is not None:",
        lesson=(
            "조건이 뒤집혀 값이 있을 때 검사를 건너뛴다. 정작 확인해야 할 경우만 빠져나가서, "
            "주문 수량을 넘는 환불 제안이 그대로 통과한다."
        ),
        counterfactuals=["값이 있으면 이미 검증된 것이다", "상한은 DB 제약이 막는다"],
        difficulty=3,
    ),
]

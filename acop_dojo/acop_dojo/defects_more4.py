"""추가 결함 4 — 파트별 트랙을 채우기 위한 것.

트랙마다 자기 코드에서 낼 문제가 있어야 한다. VOC 와 프론트가 비어 있어 채웠다.
"""
from __future__ import annotations

from .defects import Defect

MORE4: list[Defect] = [
    Defect(
        defect_id="INV-VOC-001",
        title="분류 필수 필드 검사가 any 에서 all 로 바뀌었다",
        invariant="분류가 실패하면 조용히 넘기지 않는다 — 필드가 빠지면 거부한다",
        path="app/modules/customer_ops/feedback.py",
        old="    if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):",
        new="    if all(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):",
        lesson=(
            "네 필드가 전부 빠졌을 때만 막는다. 하나만 빠진 출력은 통과해서 "
            "빈 라벨이 Case 에 저장되고 그대로 라우팅까지 간다."
        ),
        counterfactuals=["일부라도 채워졌으면 쓸 만하다", "빠진 건 나중에 채우면 된다"],
    ),
    Defect(
        defect_id="INV-UI-001",
        title="근거 없는 제안인데 결정 버튼이 살아 있다",
        invariant="근거 없는 제안은 화면에서 결정할 수 없어야 한다",
        path="app/presentation/ui/routes.py",
        old='        disabled = " disabled" if not evidence else ""',
        new='        disabled = ""',
        lesson=(
            "Core 의 '근거 없으면 확정하지 않는다'가 화면에서 뚫린다. 규칙은 마지막 "
            "클릭까지 내려와야 한다 — 승인자가 누를 수 있으면 그건 막힌 게 아니다."
        ),
        counterfactuals=["서버가 어차피 막는다", "화면은 보여주기만 하면 된다"],
    ),
    Defect(
        defect_id="INV-REVIEW-002",
        title="금지어 검사가 사라졌다",
        invariant="생성된 답변은 금지어와 PII 를 검사한 뒤 내보낸다",
        path="app/modules/customer_ops/response_review.py",
        old='        problems = [f"forbidden_word:{word}" for word in FORBIDDEN_WORDS if word.lower() in text.lower()]',
        new="        problems = []",
        lesson=(
            "검토가 통과 도장만 찍는다. 금지어가 든 문장이 재시도 없이 그대로 고객에게 간다."
        ),
        counterfactuals=["LLM 이 알아서 안 쓴다", "사람이 최종 확인한다"],
    ),
    Defect(
        defect_id="INV-COMMERCE-002",
        title="제안이 근거 id 를 달지 않는다",
        invariant="제안에는 근거 id 가 붙어야 한다 — ContextPack 에 실재하는 것으로",
        path="app/modules/customer_ops/procurement_order_payment.py",
        old="            rationale_evidence_ids=[item.evidence_id for item in evidence],",
        new="            rationale_evidence_ids=[],",
        lesson=(
            "근거를 모아 놓고 제안에 달지 않으면 대조할 것이 없다. 승인자는 무엇을 보고 "
            "판단해야 할지 모르고, 검증기도 확인할 수 없다."
        ),
        counterfactuals=["근거는 Team 안에서만 쓰면 된다", "제안 내용이 맞으면 그만이다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-COMMERCE-003",
        title="배송 상태를 모르는데 아는 척 답한다",
        invariant="값을 모르면 비워 둔다 — 모르는 상태를 확정 답변으로 만들지 않는다",
        path="app/modules/customer_ops/fulfillment_logistics.py",
        old='            if not status or str(status).lower() in {"unknown", "unavailable"}:',
        new='            if status is None:',
        lesson=(
            "unknown 이나 빈 문자열이 그대로 답변 문장에 들어간다. 고객은 "
            "'배송 상태는 unknown입니다' 를 받는다. 모르면 사람에게 넘겨야 한다."
        ),
        counterfactuals=["값이 있으면 답할 수 있다", "unknown 도 상태의 하나다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-VOC-002",
        title="degraded 검사가 뒤집혔다",
        invariant="ContextPack 이 축소됐으면(degraded) 확정 답변을 만들지 않는다",
        path="app/modules/customer_ops/voc_store_manager.py",
        old="        if task.context.degraded:",
        new="        if not task.context.degraded:",
        lesson=(
            "조건이 뒤집히면 정상 맥락을 넘기고 축소된 맥락으로 답을 만든다. 정확히 "
            "반대로 동작한다 — degraded 일 때야말로 확정 답변을 만들면 안 되는 때다."
        ),
        counterfactuals=["근거가 하나라도 있으면 답할 수 있다", "degraded 는 참고용 표시다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-COMMERCE-004",
        title="조회된 배송 건수를 세지 않고 0으로 답한다",
        invariant="답변은 근거와 일치해야 한다",
        path="app/modules/customer_ops/fulfillment_logistics.py",
        old="                count = len(shipments) if isinstance(shipments, list) else 0",
        new="                count = 0",
        lesson=(
            "읽어 온 배송 목록을 세지 않고 0 이라고 답한다. 근거는 있는데 답변이 근거와 "
            "어긋나는 상태다 — 고객은 배송이 없다고 듣는다."
        ),
        counterfactuals=["건수는 부가 정보다", "목록은 화면에서 다시 조회한다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-COMMERCE-005",
        title="계약에 없는 능력을 받아도 처리한다",
        invariant="Team 은 자기 manifest 에 없는 capability 를 받으면 거부한다",
        path="app/modules/customer_ops/catalog_verification.py",
        old="        if task.capability not in self.manifest.capabilities:",
        new="        if task.capability in self.manifest.capabilities:",
        lesson=(
            "조건이 뒤집히면 자기가 할 수 있다고 선언한 일은 거부하고, 선언하지 않은 일을 "
            "받아 처리한다. Registry 가 계약을 보고 라우팅하는 의미가 사라진다. "
            "이 Team 은 A2A 로 원격에 뺄 수 있게 설계돼 있어서 계약이 더 중요하다."
        ),
        counterfactuals=["어차피 Registry 가 맞는 Team 만 부른다", "능력 이름은 문서용이다"],
        difficulty=2,
    ),
]

"""추가 결함. 불변식마다 서로 다른 형태로 두 개씩 두는 것이 목표다.

같은 규칙을 한 가지 모양으로만 보면 그 모양을 외운다. 다른 코드에서 같은 규칙이
다르게 깨지는 걸 봐야 규칙 자체를 익힌다.
"""
from __future__ import annotations

from .defects import Defect

MORE: list[Defect] = [
    Defect(
        defect_id="INV-STATE-003",
        title="이벤트 payload 의 필수 키 검사가 사라졌다",
        invariant="이벤트별 필수 키를 검사한다 — 없는 키를 조용히 넘기지 않는다",
        path="app/domain/case.py",
        old="    missing = [key for key in required if key not in payload]",
        new="    missing = []",
        lesson=(
            "필수 키가 빠진 이벤트가 그대로 기록된다. 상태는 이벤트를 접은 결과라서, "
            "한 번 잘못 들어간 이벤트는 재생할 때마다 같은 오염을 다시 만든다."
        ),
        counterfactuals=["Pydantic 이 어차피 잡아준다", "빠진 키는 나중에 채우면 된다"],
    ),
    Defect(
        defect_id="INV-STATE-004",
        title="등록되지 않은 이벤트가 조용히 통과한다",
        invariant="payload schema 가 등록되지 않은 이벤트는 거부한다",
        path="app/domain/case.py",
        old="    required = REQUIRED_PAYLOAD_KEYS.get(event_type)",
        new="    required = REQUIRED_PAYLOAD_KEYS.get(event_type, ())",
        lesson=(
            "기본값을 주면 '이 이벤트는 규격이 없다'는 신호가 사라진다. 새 이벤트를 만들면서 "
            "규격 등록을 잊어도 아무도 알려주지 않는다."
        ),
        counterfactuals=["빈 튜플이면 검사할 게 없으니 안전하다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-IDEM-002",
        title="멱등키의 요청 식별자가 Case 로 고정됐다",
        invariant="같은 요청을 두 번 실행해도 side effect 는 한 번만 난다",
        path="app/core/idempotency.py",
        old='    return str(state.get("request_id") or case["case_id"])',
        new='    return str(case["case_id"])',
        lesson=(
            "원래 요청 식별자를 버리고 Case 로만 키를 만들면, 같은 Case 안의 서로 다른 요청이 "
            "같은 키를 갖는다. 두 번째 요청이 중복으로 취급돼 사라진다."
        ),
        counterfactuals=["Case 하나에 요청은 하나뿐이다", "fallback 이 있으니 둘은 같은 값이다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-BUDGET-001",
        title="ContextPack 토큰 예산 상한이 두 배로 늘어났다",
        invariant="ContextPack 은 12,000 토큰 예산을 넘겨서 만들어질 수 없다",
        path="app/core/contracts.py",
        old="        if self.estimated_input_tokens > self.token_budget:",
        new="        if self.estimated_input_tokens > self.token_budget * 2:",
        lesson=(
            "예산은 모델 한계가 아니라 건당 비용과 품질 저하를 막는 장치다. 상한이 헐거워지면 "
            "절삭이 일어나야 할 때 일어나지 않고, 비용과 lost-in-the-middle 이 같이 는다."
        ),
        counterfactuals=["모델 context window 안이면 괜찮다", "예산은 권고값이다"],
    ),
    Defect(
        defect_id="INV-PII-003",
        title="마스킹이 리스트 안으로 내려가지 않는다",
        invariant="PII 는 저장 시 마스킹한다 — 구조 전체를 훑는다",
        path="app/core/redaction.py",
        old="        return [mask_json(item) for item in value]",
        new="        return list(value)",
        lesson=(
            "재귀가 끊기면 리스트 안에 든 값은 원문 그대로 저장된다. payload 는 보통 중첩 구조라 "
            "실제로 걸리는 경로가 많다."
        ),
        counterfactuals=["리스트에는 문자열이 안 들어간다", "상위에서 이미 마스킹했다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-VERIFY-001",
        title="사실 조회에 실패해도 제안을 통과시킨다",
        invariant="조회 자체가 실패했으면 통과시키지 않는다 — 사실을 모르는 상태다",
        path="app/core/verification.py",
        old="    if not facts.loaded:",
        new="    if facts.loaded and not facts.loaded:",
        lesson=(
            "사실을 못 읽은 것과 사실이 일치하는 것은 다르다. 이 검사가 죽으면 조회 실패가 "
            "'문제 없음'으로 바뀌어 근거 없는 제안이 승인 대기까지 올라간다."
        ),
        counterfactuals=["조회가 실패하면 어차피 뒤에서 막힌다", "빈 사실은 불일치가 없다는 뜻이다"],
        difficulty=3,
    ),
    Defect(
        defect_id="INV-CONFIG-001",
        title="선언되지 않은 모듈이 켜진 것으로 취급된다",
        invariant="project.yaml 에 선언되지 않은 모듈을 물으면 오류다",
        path="app/core/project_config.py",
        old='            raise ProjectConfigError(f"project.yaml module is not declared: {module_id}") from exc',
        new="            return True",
        lesson=(
            "선언에 없는 모듈이 켜진 것으로 답하면, 끈 줄 알았던 기능이 실제로는 돌아간다. "
            "구성 선언이 실제 조립을 지배하지 못하게 된다."
        ),
        counterfactuals=["없으면 기본값으로 켜는 게 안전하다", "어차피 구현이 없으면 안 돈다"],
    ),
]
